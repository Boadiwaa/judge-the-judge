"""Cached, rate-limited, call-counting LLM client (BUILD_SPEC §5.4).

Two providers, chosen by env JUDGE_PROVIDER:
- "local" (default): an OpenAI-compatible server on this machine, e.g. llama.cpp's llama-server
  serving Gemma / MedGemma GGUFs (DECISIONS D-14). URL from JUDGE_BASE_URL. When a JSON schema is
  passed, the server constrains decoding to it, so small models cannot emit unparseable output.
- "anthropic": Anthropic API via ANTHROPIC_API_KEY.

Every LLM call in the project goes through `LLM.complete`. Cache hits are free and do not count
toward the hard cap. The call counter persists in data/cache/_call_count.json so the cap holds
across script invocations.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
CACHE_DIR = DATA / "cache"
COUNT_FILE = CACHE_DIR / "_call_count.json"
HARD_CAP = 1500
DEFAULT_PROVIDER = "local"
DEFAULT_MODELS = {"local": "gemma-4-E2B-it-Q4_0", "anthropic": "claude-sonnet-5-5"}
DEFAULT_BASE_URL = "http://127.0.0.1:8081/v1"
MAX_TOKENS = 8000
LOCAL_TIMEOUT_S = 1800  # small models on a laptop can take minutes per long prompt
SEED = 20261028


class CallCapReached(RuntimeError):
    pass


class NoApiKey(RuntimeError):
    pass


class ServerUnavailable(RuntimeError):
    pass


def cache_key(model: str, system: str, user: str, temperature: float, schema: dict | None = None) -> str:
    parts = [model, system, user, temperature] + ([schema] if schema else [])
    blob = json.dumps(parts, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


class LLM:
    def __init__(self, model: str | None = None, dry_run: bool = False, cache_dir: Path = CACHE_DIR,
                 hard_cap: int = HARD_CAP, provider: str | None = None):
        self.provider = provider or os.environ.get("JUDGE_PROVIDER") or DEFAULT_PROVIDER
        if self.provider not in DEFAULT_MODELS:
            raise ValueError(f"unknown JUDGE_PROVIDER {self.provider}")
        self.model = model or os.environ.get("JUDGE_MODEL") or DEFAULT_MODELS[self.provider]
        self.base_url = (os.environ.get("JUDGE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.dry_run = dry_run
        self.cache_dir = cache_dir
        self.count_file = cache_dir / "_call_count.json"
        self.hard_cap = hard_cap
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = None

    # ---- call counter ----
    @property
    def calls_used(self) -> int:
        try:
            return json.loads(self.count_file.read_text())["calls"]
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            return 0

    def _bump(self) -> int:
        n = self.calls_used + 1
        self.count_file.write_text(json.dumps({"calls": n, "cap": self.hard_cap}))
        return n

    # ---- client ----
    def _get_client(self):
        if self._client is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise NoApiKey("ANTHROPIC_API_KEY is not set")
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def check_ready(self) -> None:
        """Fail fast with a clear message if the provider cannot be reached."""
        if self.provider == "anthropic":
            self._get_client()
            return
        try:
            with urllib.request.urlopen(f"{self.base_url}/models", timeout=5) as r:
                served = [m.get("id", "") for m in json.loads(r.read()).get("data", [])]
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            raise ServerUnavailable(
                f"no local model server at {self.base_url} ({e}). Start one, e.g.\n"
                f"  llama-server -m <model.gguf> --alias {self.model} --jinja -c 16384 --port 8081") from e
        # The cache and output folders are keyed by self.model, so the server must really be serving it
        if self.model not in served:
            raise ServerUnavailable(f"server is serving {served}, not {self.model}; "
                                    f"start it with --alias {self.model} or set JUDGE_MODEL")

    def _complete_local(self, system: str, user: str, temperature: float, schema: dict | None) -> str:
        body = {
            "model": self.model, "temperature": temperature, "seed": SEED, "max_tokens": MAX_TOKENS,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if schema:
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "judge", "schema": schema}}
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=LOCAL_TIMEOUT_S) as r:
            data = json.loads(r.read())
        return data["choices"][0]["message"]["content"] or ""

    def complete(self, system: str, user: str, temperature: float = 0.0, schema: dict | None = None) -> str | None:
        """schema: optional JSON schema; the local provider constrains output to it (ignored by anthropic)."""
        key = cache_key(self.model, system, user, temperature, schema if self.provider == "local" else None)
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text())["text"]
        if self.dry_run:
            print(f"--- DRY RUN [{self.provider}:{self.model}] system ({len(system)} chars) ---\n{system[:400]}…")
            print(f"--- user ({len(user)} chars) ---\n{user[:600]}…\n")
            return None
        if self.calls_used >= self.hard_cap:
            raise CallCapReached(f"hard cap of {self.hard_cap} LLM calls reached")
        if self.provider == "local":
            n = self._bump()
            t0 = time.time()
            try:
                text = self._complete_local(system, user, temperature, schema)
            except (urllib.error.URLError, OSError) as e:
                raise ServerUnavailable(f"local model server error: {e}") from e
            path.write_text(json.dumps({"model": self.model, "provider": "local", "text": text, "call_no": n}))
            print(f"[llm] call {n}/{self.hard_cap} ({time.time() - t0:.0f}s)")
            return text
        client = self._get_client()
        import anthropic

        delay = 2.0
        for attempt in range(6):
            try:
                n = self._bump()
                resp = client.messages.create(
                    model=self.model, max_tokens=MAX_TOKENS, temperature=temperature,
                    system=system, messages=[{"role": "user", "content": user}],
                )
                text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
                path.write_text(json.dumps({"model": self.model, "text": text, "call_no": n}))
                print(f"[llm] call {n}/{self.hard_cap}")
                return text
            except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError):
                if attempt == 5:
                    raise
                time.sleep(delay + random.random())
                delay *= 2
                if self.calls_used >= self.hard_cap:
                    raise CallCapReached(f"hard cap of {self.hard_cap} LLM calls reached")
        return None

"""Cached, rate-limited, call-counting Anthropic client (BUILD_SPEC §5.4).

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
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
CACHE_DIR = DATA / "cache"
COUNT_FILE = CACHE_DIR / "_call_count.json"
HARD_CAP = 1500
DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 8000


class CallCapReached(RuntimeError):
    pass


class NoApiKey(RuntimeError):
    pass


def cache_key(model: str, system: str, user: str, temperature: float) -> str:
    blob = json.dumps([model, system, user, temperature], ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


class LLM:
    def __init__(self, model: str | None = None, dry_run: bool = False, cache_dir: Path = CACHE_DIR,
                 hard_cap: int = HARD_CAP):
        self.model = model or os.environ.get("JUDGE_MODEL") or DEFAULT_MODEL
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

    def complete(self, system: str, user: str, temperature: float = 0.0) -> str | None:
        key = cache_key(self.model, system, user, temperature)
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text())["text"]
        if self.dry_run:
            print(f"--- DRY RUN [{self.model}] system ({len(system)} chars) ---\n{system[:400]}…")
            print(f"--- user ({len(user)} chars) ---\n{user[:600]}…\n")
            return None
        if self.calls_used >= self.hard_cap:
            raise CallCapReached(f"hard cap of {self.hard_cap} LLM calls reached")
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

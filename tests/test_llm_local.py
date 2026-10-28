"""Local (OpenAI-compatible) provider against a fake server: caching, call counting, model guard."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from jtj.llm import LLM, ServerUnavailable


class Fake(BaseHTTPRequestHandler):
    served = "fake-model"
    bodies: list = []

    def log_message(self, *a):
        pass

    def _send(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send({"data": [{"id": Fake.served}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Fake.bodies.append(body)
        self._send({"choices": [{"message": {"content": '{"findings": [], "overall_note_safety": "safe_as_is"}'}}]})


@pytest.fixture
def server(monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("JUDGE_BASE_URL", f"http://127.0.0.1:{srv.server_port}/v1")
    Fake.bodies = []
    yield srv
    srv.shutdown()


def test_local_call_cached_and_counted(server, tmp_path):
    llm = LLM(model="fake-model", provider="local", cache_dir=tmp_path)
    llm.check_ready()
    schema = {"type": "object"}
    a = llm.complete("sys", "user", schema=schema)
    b = llm.complete("sys", "user", schema=schema)
    assert a == b and json.loads(a)["findings"] == []
    assert llm.calls_used == 1 and len(Fake.bodies) == 1  # second call served from cache
    sent = Fake.bodies[0]
    assert sent["temperature"] == 0.0 and sent["response_format"]["json_schema"]["schema"] == schema


def test_model_mismatch_refused(server, tmp_path):
    with pytest.raises(ServerUnavailable):
        LLM(model="other-model", provider="local", cache_dir=tmp_path).check_ready()


def test_no_server(tmp_path, monkeypatch):
    monkeypatch.setenv("JUDGE_BASE_URL", "http://127.0.0.1:9/v1")
    with pytest.raises(ServerUnavailable):
        LLM(model="x", provider="local", cache_dir=tmp_path).check_ready()


def test_cap_enforced(server, tmp_path):
    llm = LLM(model="fake-model", provider="local", cache_dir=tmp_path, hard_cap=1)
    llm.complete("s", "u1")
    from jtj.llm import CallCapReached

    with pytest.raises(CallCapReached):
        llm.complete("s", "u2")

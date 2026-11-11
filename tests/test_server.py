"""The face: model-name parsing and one real HTTP round trip.

The whole public surface is an OpenAI-compatible endpoint whose *model name*
encodes swarm size, so parsing is not cosmetic -- it is the API contract.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from egregore.config import EgregoreConfig
from egregore.engine import Egregore
from egregore.providers import MockProvider
from egregore.server import MODEL_RE, EgregoreServer, parse_model_id, render_prompt

CONSTANT = "The socket is never closed before the retry loop starts."


@pytest.mark.parametrize("model,mode,agents", [
    ("zoth-egregore", "auto", None),
    ("egregore", "auto", None),
    ("zoth-egregore:auto", "auto", None),
    ("zoth-egregore:probe", "probe", None),
    ("zoth-egregore:max", "max", None),
    ("zoth-egregore:256", "fixed", 256),
    ("zoth-egregore:1000", "fixed", 1000),
    ("egregore:64", "fixed", 64),
    ("zoth-egregore-512", "fixed", 512),
    ("ZOTH-EGREGORE:128", "fixed", 128),
])
def test_parse_model_id(model, mode, agents):
    assert parse_model_id(model) == (mode, agents)


def test_unknown_model_names_do_not_raise():
    assert parse_model_id("gpt-4o") == ("auto", None)
    assert parse_model_id("") == ("auto", None)
    assert MODEL_RE.match("zoth-egregore:1000") is not None


def test_render_prompt_keeps_instructions_and_question():
    prompt = render_prompt([
        {"role": "system", "content": "answer in JSON"},
        {"role": "user", "content": "what broke?"},
    ])
    assert "answer in JSON" in prompt
    assert "what broke?" in prompt


def _engine(tmp_path):
    cfg = EgregoreConfig.from_env(
        cache_path=tmp_path / "cache.sqlite3",
        ledger_path=tmp_path / "ledger.jsonl",
        daily_path=tmp_path / "daily.json",
        cache_enabled=False,
    )
    return Egregore(MockProvider(responder=lambda m, msgs: CONSTANT), cfg)


def test_http_chat_completions_round_trip(tmp_path):
    cfg = _engine(tmp_path).cfg
    server = EgregoreServer(_engine(tmp_path), cfg)
    port = server.start_background(port=0)
    try:
        body = json.dumps({
            "model": "zoth-egregore:probe",
            "messages": [{"role": "user", "content": "why does the deploy fail?"}],
        }).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
        assert data["choices"][0]["message"]["content"].strip()
        assert data["object"] == "chat.completion"
        assert data["model"].startswith("zoth-egregore")
    finally:
        server.stop()


def test_http_models_endpoint_lists_the_face(tmp_path):
    eng = _engine(tmp_path)
    server = EgregoreServer(eng, eng.cfg)
    port = server.start_background(port=0)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=30) as resp:
            data = json.loads(resp.read().decode())
        ids = [m.get("id") for m in data.get("data", [])]
        assert any(str(i).startswith("zoth-egregore") for i in ids), ids
    finally:
        server.stop()


def test_http_lenses_and_dashboard_endpoints(tmp_path):
    eng = _engine(tmp_path)
    server = EgregoreServer(eng, eng.cfg)
    port = server.start_background(port=0)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/egregore/lenses?n=8&seed=test", timeout=30) as resp:
            data = json.loads(resp.read().decode())
        assert data["count"] == 8
        assert data["product_size"] == 3456
        assert len(data["lenses"]) == 8
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=30) as html_resp:
            html = html_resp.read().decode()
        assert "E G R E G O R E" in html
        assert "Live Deliberation Console" in html
    finally:
        server.stop()

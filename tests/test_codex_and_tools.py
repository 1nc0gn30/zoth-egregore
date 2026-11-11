"""Tests for the Design-Director + Formal Logic Codex and Zoth Tool Orchestrator."""

from __future__ import annotations

import json
import urllib.request

from egregore.cli import main as cli_main
from egregore.codex import codex_for_prompt, detect_domains
from egregore.config import EgregoreConfig
from egregore.engine import Egregore
from egregore.providers import MockProvider
from egregore.server import EgregoreServer
from egregore.zoth_tools import (
    BUILTIN_ZOTH_TOOLS,
    build_tool_augmentation_block,
    detect_zoth_environment,
    match_tools_for_prompt,
)


def test_default_scout_is_deepseek_flash():
    cfg = EgregoreConfig.from_env()
    assert "deepseek" in cfg.scout_model
    assert "flash" in cfg.scout_model


def test_codex_detects_design_and_motion_domains():
    doms = detect_domains("Design a responsive landing page with 60fps aperture motion and WCAG contrast")
    assert "design" in doms
    assert "motion" in doms
    block, tags = codex_for_prompt("Design a dark mode UI card with crisp typography")
    assert "LOGIC & RIGOR INVARIANTS" in block
    assert "DESIGN DIRECTOR CANON" in block
    assert tags[0] == "logic"
    assert "design" in tags


def test_codex_detects_systems_and_security_domains():
    doms = detect_domains("Audit JWT signature verification and distributed consensus backpressure")
    assert "security" in doms
    assert "systems" in doms


def test_zoth_tool_matching_picks_domain_specific_arsenal():
    assert len(BUILTIN_ZOTH_TOOLS) >= 12
    ui_tools = match_tools_for_prompt("Check WCAG APCA contrast and GLSL shader dither tokens", limit=3)
    ids = {t["id"] for t in ui_tools}
    assert "wcag-contrast-guard" in ids or "reality-shader-forge" in ids

    sec_tools = match_tools_for_prompt("Scan .env for secret leaks and verify JWT alg:none", limit=3)
    sec_ids = {t["id"] for t in sec_tools}
    assert "envguard-secrets-vault" in sec_ids or "jwt-inspector-guard" in sec_ids


def test_engine_injects_codex_and_zoth_tools_into_minds(tmp_path):
    seen_systems: list[str] = []

    def spy_responder(model, messages):
        seen_systems.append(messages[0]["content"])
        return "Use 8pt spacing, APCA Lc>=75 contrast, and run wcag-contrast-guard."

    cfg = EgregoreConfig.from_env(
        cache_path=tmp_path / "cache.sqlite3",
        ledger_path=tmp_path / "ledger.jsonl",
        daily_path=tmp_path / "daily.json",
        cache_enabled=False,
    )
    eng = Egregore(MockProvider(responder=spy_responder), cfg)
    res = eng.run("Audit this dark mode UI palette for WCAG contrast and responsive grid spacing")

    assert "design" in res.codex_domains
    assert len(res.zoth_tools) >= 1
    assert any("DESIGN DIRECTOR CANON" in s for s in seen_systems)
    assert any("IN-HOUSE ZOTH ARSENAL TOOLS" in s for s in seen_systems)
    d = res.to_dict()
    assert "codex_domains" in d
    assert "zoth_tools" in d


def test_server_exposes_tools_and_codex_endpoints(tmp_path):
    cfg = EgregoreConfig.from_env(
        cache_path=tmp_path / "cache.sqlite3",
        ledger_path=tmp_path / "ledger.jsonl",
        daily_path=tmp_path / "daily.json",
        cache_enabled=False,
    )
    eng = Egregore(MockProvider(), cfg)
    srv = EgregoreServer(eng, cfg)
    port = srv.start_background(port=0)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/egregore/tools?q=wcag+contrast") as r:
            data = json.loads(r.read().decode())
        assert "environment" in data
        assert len(data["matched_tools"]) >= 1

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/egregore/codex?q=webgl+motion+ui") as r2:
            cdata = json.loads(r2.read().decode())
        assert "logic" in cdata["domains"]
        assert "DESIGN DIRECTOR CANON" in cdata["codex"] or "MOTION CHOREOGRAPHY CANON" in cdata["codex"]
    finally:
        srv.stop()


def test_cli_tools_json(capsys):
    rc = cli_main(["tools", "distributed consensus and memory recall", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "environment" in out
    assert "matched_tools" in out
    env = detect_zoth_environment(probe_daemons=False)
    assert env["tier"] in ("zothos-native", "zoth-studio", "standalone")
    block, tools = build_tool_augmentation_block("plan a roadmap dag")
    assert "Adytum" in block and len(tools) >= 1

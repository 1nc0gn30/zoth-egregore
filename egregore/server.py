"""The face: EGREGORE as a single OpenAI-compatible model.

Hermes (or anything else that speaks OpenAI) points at this server and sees ONE
model. The swarm size is encoded in the model *name*, which is the whole trick:

    zoth-egregore          adaptive  (8 minds probe, escalate on disagreement)
    zoth-egregore:256      exactly 256 minds
    zoth-egregore:1000     the full congress
    zoth-egregore:probe    one cheap seed wave, fastest possible
    zoth-egregore:max      escalate to the ceiling if disagreement holds

So a caller chooses deliberation depth the same way it chooses a model, with no
new API to learn -- `model="zoth-egregore:512"` is a 512-mind deliberation.

Stdlib `http.server` only, matching `zoth-fast/router_proxy.py`.
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import EgregoreConfig, is_free

MODEL_RE = re.compile(r"^(?:zoth-)?egregore(?::|-)?(\d{1,4}|probe|max|auto)?$", re.I)


def parse_model_id(model: str) -> tuple[str, int | None]:
    """'zoth-egregore:256' -> ('fixed', 256) ; 'zoth-egregore' -> ('auto', None)."""
    m = MODEL_RE.match((model or "").strip())
    if not m:
        return "auto", None
    tail = (m.group(1) or "auto").lower()
    if tail in ("probe",):
        return "probe", None
    if tail in ("max",):
        return "max", None
    if tail in ("auto", ""):
        return "auto", None
    return "fixed", max(1, int(tail))


def render_prompt(messages: list[dict]) -> str:
    """Flatten an OpenAI message list into the text the minds deliberate over."""
    system_bits = [m.get("content", "") for m in messages if m.get("role") == "system"]
    turns = [m for m in messages if m.get("role") != "system"]
    parts: list[str] = []
    if system_bits:
        parts.append("CALLER INSTRUCTIONS:\n" + "\n".join(str(s) for s in system_bits))
    if len(turns) == 1:
        parts.append(str(turns[0].get("content", "")))
    else:
        convo = []
        for m in turns:
            role = {"user": "User", "assistant": "Assistant", "tool": "Tool"}.get(
                m.get("role", "user"), "User")
            convo.append(f"{role}: {m.get('content', '')}")
        parts.append("CONVERSATION:\n" + "\n".join(convo) +
                     "\n\nAnswer the final User turn.")
    return "\n\n".join(p for p in parts if p)


class EgregoreServer:
    def __init__(self, engine, config: EgregoreConfig | None = None) -> None:
        self.engine = engine
        self.cfg = config or engine.cfg
        self.started = time.time()
        self._thread: threading.Thread | None = None
        self._httpd: ThreadingHTTPServer | None = None
        self._runs: list[dict] = []
        self._lock = threading.Lock()

    # -- record keeping -----------------------------------------------------

    def record(self, model: str, result) -> None:
        with self._lock:
            self._runs.append({
                "ts": time.time(), "model": model, "agents": result.agents_spawned,
                "agreement": result.agreement, "cost_usd": result.cost_usd,
                "latency_s": result.latency_s, "stopped_by": result.stopped_by,
                "waves": len(result.waves),
            })
            del self._runs[:-200]

    def recent(self, limit: int = 20) -> list[dict]:
        with self._lock:
            return list(self._runs[-limit:])[::-1]

    # -- lifecycle ----------------------------------------------------------

    def serve_forever(self, host: str = "127.0.0.1", port: int | None = None) -> None:
        port = port or self.cfg.port
        handler = _make_handler(self)
        self._httpd = ThreadingHTTPServer((host, port), handler)
        self._httpd.daemon_threads = True
        self._httpd.serve_forever()

    def start_background(self, host: str = "127.0.0.1", port: int | None = None) -> int:
        port = port or self.cfg.port
        handler = _make_handler(self)
        self._httpd = ThreadingHTTPServer((host, port), handler)
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self._httpd.server_address[1]

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None


def _make_handler(server: EgregoreServer):
    cfg = server.cfg

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "zoth-egregore/0.1.0-beta"

        # -- plumbing ---------------------------------------------------

        def log_message(self, fmt, *args):  # keep the console usable
            if getattr(cfg, "verbose", False):
                BaseHTTPRequestHandler.log_message(self, fmt, *args)

        def _send(self, code: int, payload, ctype="application/json", extra: dict | None = None):
            if isinstance(payload, bytes):
                body = payload
            elif isinstance(payload, str):
                body = payload.encode("utf-8")
            else:
                body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                return {}

        def _sse_headers(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

        def _sse(self, obj: dict) -> bool:
            try:
                self.wfile.write(f"data: {json.dumps(obj)}\n\n".encode())
                self.wfile.flush()
                return True
            except (BrokenPipeError, ConnectionResetError):
                return False

        # -- routes -----------------------------------------------------

        def do_OPTIONS(self):  # noqa: N802
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):  # noqa: N802
            from urllib.parse import parse_qs, urlparse
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            qs = parse_qs(parsed.query)
            if path in ("/healthz", "/health"):
                return self._send(200, {"status": "ok", "model": cfg.model_id,
                                        "uptime_s": round(time.time() - server.started, 1),
                                        "provider_configured": bool(cfg.api_key)})
            if path == "/v1/models":
                return self._send(200, {"object": "list", "data": _model_list(cfg)})
            if path in ("/v1/egregore/lenses", "/lenses.json"):
                from .lenses import coverage, expand
                n = max(1, min(64, int((qs.get("n") or ["12"])[0])))
                seed = (qs.get("seed") or ["egregore"])[0]
                lenses = expand(n, seed=seed)
                return self._send(200, {
                    "count": len(lenses),
                    "product_size": 3456,
                    "coverage": coverage(lenses),
                    "lenses": [{"index": l.index, "signature": l.signature,
                                "archetype": l.archetype, "domain": l.domain,
                                "stance": l.stance} for l in lenses],
                })
            if path in ("/v1/egregore/stats", "/stats.json"):
                return self._send(200, {**server.engine.stats(), "recent_runs": server.recent(),
                                        "uptime_s": round(time.time() - server.started, 1)})
            if path in ("/", "/dashboard"):
                return self._send(200, _dashboard_html(server), "text/html; charset=utf-8")
            return self._send(404, {"error": {"message": f"no route {path}", "type": "not_found"}})

        def do_POST(self):  # noqa: N802
            path = self.path.split("?")[0].rstrip("/")
            if path == "/v1/chat/completions":
                return self._chat_completions()
            if path == "/v1/completions":
                return self._completions()
            if path in ("/v1/egregore/run", "/run"):
                return self._explicit_run()
            return self._send(404, {"error": {"message": f"no route {path}", "type": "not_found"}})

        # -- handlers ---------------------------------------------------

        def _chat_completions(self):
            body = self._read_json()
            model = str(body.get("model") or cfg.model_id)
            messages = body.get("messages") or []
            stream = bool(body.get("stream"))
            if not messages:
                return self._send(400, {"error": {"message": "messages is required",
                                                  "type": "invalid_request_error"}})
            mode, n_agents = parse_model_id(model)
            prompt = render_prompt(messages)
            rid = "chatcmpl-" + uuid.uuid4().hex[:24]
            created = int(time.time())

            if not prompt.strip():
                return self._send(400, {"error": {"message": "empty prompt",
                                                  "type": "invalid_request_error"}})

            if stream:
                return self._stream_chat(rid, created, model, mode, n_agents, prompt)

            try:
                res = server.engine.run(prompt, agents=n_agents, mode=mode)
            except Exception as e:  # noqa: BLE001
                return self._send(500, {"error": {"message": f"{type(e).__name__}: {e}",
                                                  "type": "server_error"}})
            server.record(model, res)
            usage = {
                "prompt_tokens": res.tokens_in,
                "completion_tokens": res.tokens_out,
                "total_tokens": res.tokens_in + res.tokens_out,
                "cost": round(res.cost_usd, 8),
            }
            return self._send(200, {
                "id": rid, "object": "chat.completion", "created": created, "model": model,
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": res.text}}],
                "usage": usage,
                "egregore": {k: v for k, v in res.to_dict().items() if k not in ("text", "clusters")},
            })

        def _stream_chat(self, rid: str, created: int, model: str, mode: str,
                         n_agents: int | None, prompt: str):
            self._sse_headers()
            sent_role = False

            def emit(delta_obj: dict, finish=None):
                return self._sse({
                    "id": rid, "object": "chat.completion.chunk", "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": delta_obj, "finish_reason": finish}],
                })

            if not emit({"role": "assistant", "content": ""}):
                return
            sent_role = True

            progress: list[dict] = []

            def cb(event: dict):
                if event.get("type") == "delta":
                    emit({"content": event.get("text", "")})
                else:
                    progress.append(event)

            try:
                res = server.engine.run(prompt, agents=n_agents, mode=mode, stream_cb=cb)
            except Exception as e:  # noqa: BLE001
                emit({"content": f"\n\n[egregore error: {type(e).__name__}: {e}]"})
                emit({}, finish="stop")
                self._sse("[DONE]")
                return

            if not any(p.get("type") == "collapse" for p in progress) and res.text:
                # non-streaming fallback path: emit the finished text in chunks
                for i in range(0, len(res.text), 48):
                    if not emit({"content": res.text[i:i + 48]}):
                        return
            emit({}, finish="stop")
            self._sse({
                "id": rid, "object": "chat.completion.chunk", "created": created, "model": model,
                "choices": [],
                "usage": {"prompt_tokens": res.tokens_in, "completion_tokens": res.tokens_out,
                          "total_tokens": res.tokens_in + res.tokens_out,
                          "cost": round(res.cost_usd, 8)},
            })
            self._sse("[DONE]")
            server.record(model, res)

        def _completions(self):
            body = self._read_json()
            prompt = body.get("prompt") or ""
            if isinstance(prompt, list):
                prompt = "\n".join(str(p) for p in prompt)
            model = str(body.get("model") or cfg.model_id)
            mode, n_agents = parse_model_id(model)
            try:
                res = server.engine.run(prompt, agents=n_agents, mode=mode)
            except Exception as e:  # noqa: BLE001
                return self._send(500, {"error": {"message": str(e), "type": "server_error"}})
            server.record(model, res)
            return self._send(200, {
                "id": "cmpl-" + uuid.uuid4().hex[:24], "object": "text_completion",
                "created": int(time.time()), "model": model,
                "choices": [{"index": 0, "text": res.text, "finish_reason": "stop", "logprobs": None}],
                "usage": {"prompt_tokens": res.tokens_in, "completion_tokens": res.tokens_out,
                          "total_tokens": res.tokens_in + res.tokens_out,
                          "cost": round(res.cost_usd, 8)},
            })

        def _explicit_run(self):
            body = self._read_json()
            prompt = body.get("prompt") or body.get("input") or ""
            if not prompt:
                return self._send(400, {"error": {"message": "prompt is required",
                                                  "type": "invalid_request_error"}})
            agents = body.get("agents")
            mode = body.get("mode")
            if not agents and not mode:
                mode = "auto"
            if agents:
                agents = max(1, min(int(agents), cfg.max_agents))
            try:
                res = server.engine.run(prompt, agents=agents, mode=mode)
            except Exception as e:  # noqa: BLE001
                return self._send(500, {"error": {"message": str(e), "type": "server_error"}})
            server.record("explicit", res)
            return self._send(200, res.to_dict())

    return Handler


def _model_list(cfg: EgregoreConfig) -> list[dict]:
    def entry(mid: str, desc: str) -> dict:
        return {
            "id": mid, "object": "model", "created": 0, "owned_by": "zoth",
            "permission": [], "root": mid, "parent": None,
            "description": desc,
        }

    created = 1735689600
    out = [
        entry(cfg.model_id, "EGREGORE adaptive — 8 minds probe, escalates while they disagree"),
        entry(f"{cfg.model_id}:probe", "EGREGORE probe — single seed wave, fastest reply"),
        entry(f"{cfg.model_id}:50", "EGREGORE — 50 minds"),
        entry(f"{cfg.model_id}:256", "EGREGORE — 256 minds"),
        entry(f"{cfg.model_id}:1000", "EGREGORE — 1000 minds (ceiling)"),
        entry(f"{cfg.model_id}:max", "EGREGORE — escalate to the ceiling if needed"),
    ]
    for e in out:
        e["created"] = created
    return out


def _dashboard_html(server: EgregoreServer) -> str:
    st = server.engine.stats()
    lim, bud, cac = st["limiter"], st["budget"], st["cache"]
    recent = server.recent(12)
    rows = "".join(
        f"<tr><td>{time.strftime('%H:%M:%S', time.localtime(r['ts']))}</td><td>{r['model']}</td>"
        f"<td>{r['agents']}</td><td>{r['agreement']:.2f}</td><td>{r['waves']}</td>"
        f"<td>${r['cost_usd']:.6f}</td><td>{r['latency_s']:.1f}s</td>"
        f"<td>{r['stopped_by']}</td></tr>" for r in recent) or \
        "<tr><td colspan=8>no runs yet — launch a deliberation below or POST /v1/chat/completions</td></tr>"
    return f"""<!doctype html><html lang="en"><head><meta charset=utf-8>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EGREGORE // One Model · 3,456 Lenses · One Answer</title>
<style>
:root{{--bg:#07090c;--panel:#0b1016;--line:#1b242e;--fg:#d8e2ea;--dim:#7c8b99;--acc:#4be3c1;--gold:#d4af37;--warn:#ffb454}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.55 ui-monospace,'JetBrains Mono',Menlo,monospace;padding:28px 32px;max-width:1280px;margin-inline:auto}}
header{{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;margin-bottom:24px;border-bottom:1px solid var(--line);padding-bottom:18px}}
h1{{font-size:22px;letter-spacing:.24em;margin:0 0 4px;color:var(--acc)}}
p.sub{{color:var(--dim);margin:0;letter-spacing:.05em;font-size:12px}}
.pill{{border:1px solid rgba(75,227,193,.35);background:rgba(75,227,193,.08);color:var(--acc);padding:4px 10px;border-radius:999px;font-size:11px;max-width:100%;overflow-wrap:anywhere}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px}}
.card{{border:1px solid var(--line);background:var(--panel);padding:14px 16px;border-radius:8px;min-width:0}}
.card .k{{color:var(--dim);font-size:11px;letter-spacing:.14em;text-transform:uppercase}}
.card .v{{font-size:21px;margin-top:6px;color:var(--acc);font-weight:700;overflow-wrap:anywhere}}
.split{{display:grid;grid-template-columns:1.25fr .95fr;gap:18px;margin-bottom:26px}}
@media(max-width:860px){{.split{{grid-template-columns:1fr}}body{{padding:16px}}h1{{font-size:18px;letter-spacing:.16em}}}}
.pane{{border:1px solid var(--line);background:var(--panel);padding:18px;border-radius:8px;min-width:0;max-width:100%}}
.pane h2{{margin:0 0 12px;font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--gold)}}
textarea,select,input{{width:100%;max-width:100%;background:#05070a;border:1px solid var(--line);color:var(--fg);font:inherit;padding:10px 12px;border-radius:6px}}
textarea{{min-height:92px;resize:vertical}}
.row{{display:flex;gap:10px;align-items:center;margin-top:10px;flex-wrap:wrap}}
button{{background:var(--acc);color:#04100d;border:0;padding:10px 16px;min-height:44px;border-radius:6px;font:inherit;font-weight:700;cursor:pointer}}
button.ghost{{background:transparent;color:var(--fg);border:1px solid var(--line)}}
button:disabled{{opacity:.5;cursor:wait}}
pre.out{{margin:14px 0 0;padding:12px;background:#05070a;border:1px solid var(--line);border-radius:6px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;max-height:300px;overflow:auto}}
.lens-list{{display:grid;gap:6px;max-height:260px;overflow:auto;margin-top:10px;font-size:12px}}
.lens-item{{padding:6px 9px;background:#05070a;border:1px solid #131b24;border-radius:5px;display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap}}
.table-wrap{{width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch}}
table{{width:100%;border-collapse:collapse;font-size:13px;min-width:560px}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #151d25;white-space:nowrap}}
th{{color:var(--dim);font-weight:500;font-size:11px;letter-spacing:.12em;text-transform:uppercase}}
code{{color:var(--acc);overflow-wrap:anywhere}}
footer{{margin-top:26px;padding-top:14px;border-top:1px solid var(--line);display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;color:var(--dim);font-size:12px}}
footer a{{color:var(--acc);text-decoration:none}}
</style></head><body>
<header>
  <div>
    <h1>E G R E G O R E <span style="font-size:11px;letter-spacing:.12em;vertical-align:middle;padding:3px 8px;border-radius:999px;border:1px solid rgba(255,180,84,.45);background:rgba(255,180,84,.12);color:var(--warn)">BETA &middot; v0.1.0-beta</span></h1>
    <p class=sub>one OpenAI-compatible face &middot; 3,456 co-prime Pantheon lenses (24&times;18&times;8) &middot; Beta-posterior consensus</p>
  </div>
  <div class=pill>scout: {server.cfg.scout_model} &rarr; synth: {server.cfg.synth_model}</div>
</header>
<div class=grid>
  <div class=card><div class=k>model face</div><div class=v>{server.cfg.model_id}</div></div>
  <div class=card><div class=k>runs</div><div class=v id=vRuns>{st['runs']}</div></div>
  <div class=card><div class=k>requests / min</div><div class=v id=vRpm>{lim['used_requests_window']}/{lim['rpm_limit']}</div></div>
  <div class=card><div class=k>spend today</div><div class=v id=vSpend>${bud['day_spent_usd']:.4f}</div></div>
  <div class=card><div class=k>cache hit rate</div><div class=v id=vCache>{cac.get('hit_rate',0):.0%}</div></div>
  <div class=card><div class=k>swarm range</div><div class=v>{server.cfg.min_agents}&ndash;{server.cfg.max_agents}</div></div>
</div>
<div class=split>
  <section class=pane>
    <h2>Live Deliberation Console (POST /v1/egregore/run)</h2>
    <textarea id=q placeholder="Ask a hard architectural, mathematical, or strategic question...">What breaks first when fanning out 500 concurrent LLM calls behind a single HTTP proxy, and what is the minimal architecture that prevents it?</textarea>
    <div class=row>
      <select id=mode style="width:auto;min-width:210px">
        <option value="probe">zoth-egregore:probe (8 minds fast)</option>
        <option value="auto" selected>zoth-egregore (adaptive Beta stop)</option>
        <option value="50">zoth-egregore:50 (50 minds)</option>
        <option value="256">zoth-egregore:256 (256 minds)</option>
      </select>
      <button id=runBtn type=button>Convene Minds</button>
    </div>
    <pre class=out id=out>Ready. Select deliberation depth and click Convene Minds.</pre>
  </section>
  <section class=pane>
    <h2>Co-Prime Lens Matrix (24 &times; 18 &times; 8 = 3,456)</h2>
    <div class=row style="margin-top:0">
      <input id=seed value="sovereign consensus" aria-label="Lens seed" style="flex:1">
      <button class=ghost id=lensBtn type=button>Sample 12 Lenses</button>
    </div>
    <div class=lens-list id=lenses></div>
  </section>
</div>
<section class=pane>
  <h2>Recent Deliberation Waves</h2>
  <div class=table-wrap><table><thead><tr><th>time</th><th>model</th><th>minds</th><th>agreement</th><th>waves</th>
  <th>cost</th><th>latency</th><th>stopped by</th></tr></thead><tbody id=rows>{rows}</tbody></table></div>
</section>
<footer>
  <span>POST <code>/v1/chat/completions</code> &middot; model <code>{server.cfg.model_id}:256</code> &middot; stats <code>/v1/egregore/stats</code></span>
  <span>Engineered by <a href="https://1nc0gn30.si">1nc0gn30</a> &bull; <a href="https://nullai.tech">NullAI Platform</a> &bull; <a href="https://buy.stripe.com/3cIfZg27PdKo2D64Ocfw40X">&#9749; Buy Us a Coffee</a></span>
</footer>
<script>
const $=id=>document.getElementById(id);
async function loadLenses(){{
  const r=await fetch('/v1/egregore/lenses?n=12&seed='+encodeURIComponent($('seed').value||'egregore'));
  const d=await r.json();
  $('lenses').innerHTML=(d.lenses||[]).map(l=>`<div class=lens-item><code>#${{l.index}} ${{l.signature}}</code><span style="color:#7c8b99">${{l.domain}}</span></div>`).join('');
}}
$('lensBtn').onclick=loadLenses;loadLenses();
$('runBtn').onclick=async()=>{{
  const btn=$('runBtn');btn.disabled=true;btn.textContent='Deliberating...';
  $('out').textContent='Dispatching co-prime lens wave...';
  try{{
    const m=$('mode').value;
    const payload={{prompt:$('q').value}};
    if(/^\\d+$/.test(m))payload.agents=parseInt(m,10);else payload.mode=m;
    const r=await fetch('/v1/egregore/run',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}});
    const d=await r.json();
    if(d.error)$('out').textContent='Error: '+(d.error.message||JSON.stringify(d.error));
    else $('out').textContent=`[minds=${{d.agents_spawned}} | agreement=${{d.agreement}} | clusters=${{(d.clusters||[]).length}} | stopped_by=${{d.stopped_by}} | cost=$${{d.cost_usd}}]\\n\\n`+(d.text||'(empty)');
  }}catch(e){{$('out').textContent='Error: '+e.message;}}
  btn.disabled=false;btn.textContent='Convene Minds';
}};
setInterval(async()=>{{
  try{{
    const r=await fetch('/v1/egregore/stats');const s=await r.json();
    $('vRuns').textContent=s.runs;$('vRpm').textContent=s.limiter.used_requests_window+'/'+s.limiter.rpm_limit;
    $('vSpend').textContent='$'+Number(s.budget.day_spent_usd||0).toFixed(4);
    $('vCache').textContent=Math.round((s.cache.hit_rate||0)*100)+'%';
  }}catch(_e){{}}
}},5000);
</script>
</body></html>"""

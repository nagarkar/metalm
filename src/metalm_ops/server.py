"""The ops dashboard: one page on loopback, one card per repo, refreshed in the background.

Answers only Host headers naming this machine (loopback or `*.ts.net`), else
421 (operations.md#served-apps). Serves `/`, `/health`, `/status.json` and
the SuperLM icons; `POST /refresh` collects at once (the Refresh button). Red
and amber rows carry a "Copy fix prompt" button (prompts.py). It writes nothing but `status.json`.
"""

from __future__ import annotations

import html
import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from typing import Callable

from metalm_ops import status as status_mod
from metalm_ops.prompts import fix_prompt
from metalm_ops.config import Config

REFRESH_SECONDS = 15 * 60
ASSETS = {
    "/favicon.ico": ("favicon.ico", "image/x-icon"),
    "/favicon-32.png": ("favicon-32.png", "image/png"),
    "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
    "/icon-192.png": ("icon-192.png", "image/png"),
}
DOT = {"green": "#1f9d55", "amber": "#d98a00", "red": "#d0342c"}

STYLE = """
:root{--bg:#f6f5f9;--card:#fff;--ink:#181426;--mute:#5d5870;--line:#e3e0ea}
@media (prefers-color-scheme:dark){:root{--bg:#120f1c;--card:#1d1929;--ink:#f2f0f7;--mute:#a7a1b8;--line:#2e2940}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.4 -apple-system,system-ui,sans-serif}
header{display:flex;align-items:center;gap:12px;padding:16px}header img{width:36px;height:36px}
h1{font-size:20px;margin:0}.sub{color:var(--mute);font-size:13px}
main{display:grid;gap:12px;align-items:start;padding:0 16px 24px;grid-template-columns:repeat(auto-fill,minmax(300px,1fr))}
details{background:var(--card);border:1px solid var(--line);border-radius:12px;max-width:480px}
summary{list-style:none;cursor:pointer;padding:12px 14px;display:flex;gap:10px;align-items:center}
summary::-webkit-details-marker{display:none}.name{font-weight:600}.line{color:var(--mute);font-size:13px}
.dot{width:12px;height:12px;border-radius:50%;flex:none}
table{width:100%;border-collapse:collapse;font-size:13px}td{padding:5px 14px;border-top:1px solid var(--line);vertical-align:top}
td:first-child{width:12px;padding-right:0}td.v{color:var(--mute)}
button{font:inherit;font-size:13px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);padding:4px 10px;cursor:pointer}
.refresh{margin-left:auto;font-size:15px;padding:8px 16px;background:#5a3fd9;color:#fff;border:none}.refresh[disabled]{opacity:.6}
td.fix{padding-top:0;border-top:none}
.banner{margin:0 16px 12px;padding:12px 14px;border-radius:12px;color:#fff;font-weight:600;max-width:640px}
"""
SCRIPT = """<script>
document.querySelectorAll('form[action="/refresh"]').forEach(f=>f.addEventListener('submit',()=>{const b=f.querySelector('button');b.disabled=true;b.textContent='Checking…'}));
document.querySelectorAll('button.copy').forEach(b=>b.addEventListener('click',async()=>{
  const done=()=>{b.textContent='Copied: paste into a new session'};
  try{await navigator.clipboard.writeText(b.dataset.prompt);return done()}catch(e){}
  const t=document.createElement('textarea');t.value=b.dataset.prompt;t.style.position='fixed';t.style.opacity='0';document.body.appendChild(t);t.select();
  const ok=document.execCommand&&document.execCommand('copy');t.remove();if(ok)return done();
  b.textContent='Copy failed: select the text below';b.insertAdjacentHTML('afterend','<p style="user-select:all">'+b.dataset.prompt.replace(/</g,'&lt;')+'</p>')
}));
</script>"""


def _dot(level: str) -> str:
    return f'<span class="dot" style="background:{DOT[level]}" title="{level}"></span>'


def _row(title: str, c: dict) -> str:
    row = f"<tr><td>{_dot(c['level'])}</td><td>{html.escape(c['check'])}</td><td class=v>{html.escape(c['detail'])}</td></tr>"
    if c["level"] == "green":
        return row
    prompt = html.escape(fix_prompt(title, c["check"], c["detail"]), quote=True)
    return row + f'<tr><td></td><td class=fix colspan=2><button type=button class=copy data-prompt="{prompt}">Copy fix prompt</button></td></tr>'


def _card(title: str, level: str, checks: list[dict]) -> str:
    counts = {lv: sum(c["level"] == lv for c in checks) for lv in DOT}
    line = " · ".join(f"{n} {lv}" for lv, n in counts.items() if n) or "nothing checked"
    failing = [c["check"] for c in checks if c["level"] != "green"]
    if failing:  # say which checks are not green, so the card explains its colour while closed
        line += ": " + ", ".join(html.escape(f) for f in failing)
    rows = "".join(_row(title, c) for c in checks)
    open_attr = " open" if level == "red" else ""
    return (
        f"<details{open_attr}><summary>{_dot(level)}<span><span class=name>{html.escape(title)}</span><br>"
        f"<span class=line>{line}</span></span></summary><table>{rows}</table></details>"
    )


def render(status: dict | None) -> str:
    """The whole page for one collected status (or a 'not collected yet' page)."""
    head = (
        '<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">'
        "<title>LM ops</title><link rel=icon href=/favicon.ico><link rel=icon type=image/png sizes=32x32 href=/favicon-32.png>"
        f"<link rel=apple-touch-icon href=/apple-touch-icon.png><style>{STYLE}</style></head><body>"
    )
    if status is None:
        return (
            head
            + '<header><img src=/icon-192.png alt=""><h1>LM ops</h1></header><p class=banner style="background:#5d5870">Collecting the first status…</p></body></html>'
        )
    when = datetime.fromisoformat(status["generated"]).astimezone().strftime("%Y-%m-%d %H:%M")
    reds = status_mod.reds(status)
    banner = (
        (f'<p class=banner style="background:{DOT["red"]}">{len(reds)} red: ' + html.escape("; ".join(reds[:3])) + ("…" if len(reds) > 3 else "") + "</p>")
        if reds
        else ""
    )
    cards = [_card("Backups", status_mod.worst([status_mod.Check(**c) for c in status["jobs"]]), status["jobs"])]
    cards += [_card(r["name"], r["level"], r["checks"]) for r in status["repos"]]
    return (
        head
        + f'<header><img src=/icon-192.png alt=""><div><h1>LM ops</h1><div class=sub>{_dot(status["level"])} checked {when}</div></div>'
        + "<form method=post action=/refresh style=margin-left:auto><button class=refresh>Refresh</button></form></header>"
        + banner
        + "<main>"
        + "".join(cards)
        + "</main>"
        + SCRIPT
        + "</body></html>"
    )


def host_allowed(host: str) -> bool:
    name = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
    return name in {"127.0.0.1", "localhost", "[::1]"} or name.endswith(".ts.net")


class State:
    """The latest collected status, shared between the refresh thread and requests."""

    def __init__(self, cfg: Config, collect: Callable[[Config], dict]):
        self.cfg, self.collect = cfg, collect
        self.status: dict | None = None
        self.lock = threading.Lock()
        saved = cfg.state_dir / "status.json"
        if saved.exists():
            try:
                self.status = json.loads(saved.read_text())
            except json.JSONDecodeError:
                self.status = None

    def refresh(self) -> None:
        """Collect now; a second caller waits for the run in progress instead of starting another."""
        with self.lock:
            result = self.collect(self.cfg)
            status_mod.save(self.cfg, result)
            self.status = result


def make_handler(state: State) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:  # the launch agent's log gets errors only
            pass

        def _send(self, code: int, body: bytes, kind: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if not host_allowed(self.headers.get("Host", "")):
                return self._send(421, b"misdirected request\n", "text/plain")
            path = self.path.split("?", 1)[0]
            if path == "/health":
                return self._send(200, b"ok\n", "text/plain")
            if path == "/":
                return self._send(200, render(state.status).encode(), "text/html; charset=utf-8")
            if path == "/status.json":
                return self._send(200, json.dumps(state.status).encode(), "application/json")
            if path in ASSETS:
                name, kind = ASSETS[path]
                return self._send(200, resources.files("metalm_ops").joinpath("assets", name).read_bytes(), kind)
            return self._send(404, b"not found\n", "text/plain")

        def do_POST(self) -> None:
            if not host_allowed(self.headers.get("Host", "")):
                return self._send(421, b"misdirected request\n", "text/plain")
            if self.path.split("?", 1)[0] != "/refresh":
                return self._send(404, b"not found\n", "text/plain")
            try:
                state.refresh()
            except Exception as exc:  # the page keeps the last good status
                return self._send(500, f"error: status collection failed: {exc}\n".encode(), "text/plain")
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Content-Length", "0")
            self.end_headers()

    return Handler


def serve(cfg: Config, port: int, collect: Callable[[Config], dict] = status_mod.collect) -> None:
    """Serve on 127.0.0.1:<port> until killed, refreshing every 15 minutes."""
    state = State(cfg, collect)
    stop = threading.Event()

    def loop() -> None:
        while not stop.is_set():
            try:
                state.refresh()
            except Exception as exc:  # a failed collection keeps the last good page
                print(f"error: status collection failed: {exc}", flush=True)
            stop.wait(REFRESH_SECONDS)

    threading.Thread(target=loop, daemon=True).start()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    try:
        httpd.serve_forever()
    finally:
        stop.set()
        httpd.server_close()

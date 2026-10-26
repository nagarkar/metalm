"""The dashboard server, on a spare loopback port with a fake collector.

Sources: operations.md#served-apps (loopback only, 421 for other hosts,
/health) and ui.md (favicon and icon in the page, a card says what is inside).
"""

from __future__ import annotations

import http.client
import threading
from http.server import ThreadingHTTPServer

import pytest

from metalm_ops import server
from ops_fixtures import make_cfg

STATUS = {
    "generated": "2026-10-26T12:00:00+00:00",
    "level": "red",
    "jobs": [{"check": "B2 snapshot", "level": "green", "detail": "2 h ago"}],
    "repos": [
        {
            "name": "alm",
            "level": "red",
            "checks": [
                {"check": "app :8700 /health", "level": "red", "detail": "port 8700: no answer in 3 s"},
                {"check": "backup <store>", "level": "green", "detail": "2 h ago"},
            ],
        }
    ],
}


@pytest.fixture
def live(tmp_path):
    state = server.State(make_cfg(tmp_path), lambda cfg: STATUS)
    state.refresh()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(state))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield httpd.server_address[1], state
    httpd.shutdown()


def get(port, path, host="127.0.0.1"):
    con = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    con.request("GET", path, headers={"Host": host})
    resp = con.getresponse()
    return resp.status, resp.read()


def test_health(live):
    assert get(live[0], "/health") == (200, b"ok\n")


@pytest.mark.parametrize("host, code", [("127.0.0.1:1", 200), ("localhost", 200), ("box.example.ts.net:8443", 200), ("evil.example.com", 421), ("", 421)])
def test_host_header(live, host, code):
    assert get(live[0], "/", host)[0] == code


def test_page_shows_cards_icon_and_escapes(live):
    code, body = get(live[0], "/")
    page = body.decode()
    assert code == 200
    assert "<link rel=icon href=/favicon.ico>" in page and "href=/apple-touch-icon.png" in page and "src=/icon-192.png" in page
    assert ">alm<" in page and "1 green · 1 red" in page
    assert "1 red: alm: app :8700 /health" in page
    assert "backup &lt;store&gt;" in page and "<store>" not in page
    assert "<details open>" in page  # a red card opens itself


@pytest.mark.parametrize("path", ["/favicon.ico", "/favicon-32.png", "/apple-touch-icon.png", "/icon-192.png"])
def test_icons_served(live, path):
    code, body = get(live[0], path)
    assert code == 200 and len(body) > 100


def test_status_saved_for_restart(live, tmp_path):
    port, state = live
    again = server.State(state.cfg, lambda cfg: {})
    assert again.status == STATUS


def test_page_before_first_collection():
    assert "Collecting the first status" in server.render(None)


def post(port, path, host="127.0.0.1"):
    con = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    con.request("POST", path, headers={"Host": host, "Content-Length": "0"})
    resp = con.getresponse()
    return resp.status, resp.getheader("Location"), resp.read()


def test_refresh_collects_now_and_returns_to_page(tmp_path):
    """Source: the owner's request of 2026-10-25 for a forced refresh."""
    calls = []
    state = server.State(make_cfg(tmp_path), lambda cfg: calls.append(1) or {**STATUS, "generated": f"2026-10-26T12:0{len(calls)}:00+00:00"})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(state))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    try:
        assert post(port, "/refresh")[:2] == (303, "/")
        assert post(port, "/refresh", host="evil.example.com")[0] == 421
        assert post(port, "/other")[0] == 404
        assert len(calls) == 1 and state.status["generated"].endswith("12:01:00+00:00")
        assert (state.cfg.state_dir / "status.json").exists()
    finally:
        httpd.shutdown()


def test_failed_refresh_keeps_last_page(tmp_path):
    state = server.State(make_cfg(tmp_path), lambda cfg: STATUS)
    state.refresh()
    state.collect = lambda cfg: (_ for _ in ()).throw(RuntimeError("gh down"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(state))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        assert post(httpd.server_address[1], "/refresh")[0] == 500
        assert state.status == STATUS
    finally:
        httpd.shutdown()


def test_page_has_refresh_button(live):
    page = get(live[0], "/")[1].decode()
    assert "<form method=post action=/refresh" in page and ">Refresh</button>" in page


def test_copy_prompt_only_on_red_and_amber_rows(live):
    """Source: the owner's request of 2026-10-25: a Copy fix prompt button on red and amber rows."""
    page = get(live[0], "/")[1].decode()
    assert page.count("Copy fix prompt</button>") == 1  # the red /health row; the green rows get none
    assert 'data-prompt="In alm: The ops dashboard shows `app :8700 /health`' in page

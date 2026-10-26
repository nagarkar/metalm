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

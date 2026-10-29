"""env-doctor 端點模式（原 ark-dashboard-health）：用本機 http.server 驗「會紅也不會亂紅」。"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
from endpoints import check_endpoint, load_endpoints, render  # noqa: E402


class _H(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        routes = {"/ok": (200, "application/json", b'{"status": "ok"}'),
                  "/boom": (500, "text/plain", b"err"),
                  "/events": (200, "text/event-stream", b"data: hi\n\n"),
                  "/html": (200, "text/html", b"<html></html>")}
        code, ctype, body = routes.get(self.path, (404, "text/plain", b"nope"))
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def base():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _closed_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_2xx_passes_and_contains_is_checked(base):
    assert check_endpoint({"name": "h", "url": f"{base}/ok", "contains": "ok"})["ok"]
    r = check_endpoint({"name": "h", "url": f"{base}/ok", "contains": "degraded"})
    assert not r["ok"] and "不含" in r["detail"]


def test_5xx_fails_with_actionable_detail(base):
    r = check_endpoint({"name": "b", "url": f"{base}/boom"})
    assert not r["ok"] and r["status"] == 500 and "預期 2xx" in r["detail"]


def test_expect_status_allows_non_2xx(base):
    """原 dashboard-health 的 POST /send 允許 404 —— 指定 expect_status 就要照它判。"""
    assert check_endpoint({"name": "n", "url": f"{base}/missing", "expect_status": [200, 404]})["ok"]


def test_sse_checks_content_type_only(base):
    assert check_endpoint({"name": "e", "url": f"{base}/events", "sse": True})["detail"] == "SSE OK"
    r = check_endpoint({"name": "e", "url": f"{base}/html", "sse": True})
    assert not r["ok"] and "text/event-stream" in r["detail"]


def test_unreachable_is_reported_not_raised():
    r = check_endpoint({"name": "x", "url": f"http://127.0.0.1:{_closed_port()}/health"}, timeout=2)
    assert not r["ok"] and r["status"] == 0 and "連不上" in r["detail"]


def test_render_score(base):
    res = [check_endpoint({"name": "a", "url": f"{base}/ok"}),
           check_endpoint({"name": "b", "url": f"{base}/boom"})]
    out = render(res)
    assert "Score: 50/100（1/2）" in out and "## 失敗" in out


def test_endpoints_file_requires_url(tmp_path):
    f = tmp_path / "eps.json"
    f.write_text(json.dumps([{"name": "no-url"}]), encoding="utf-8")
    with pytest.raises(SystemExit):
        load_endpoints(file=f)


def test_cli_exit_code_follows_results(base, tmp_path):
    cli = [sys.executable, str(SCRIPTS / "env_doctor.py")]
    ok = subprocess.run([*cli, "--endpoints", f"{base}/ok", "--sse", f"{base}/events",
                         "--output", str(tmp_path / "r.md")], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    bad = subprocess.run([*cli, "--endpoints", f"{base}/ok", f"{base}/boom",
                          "--output", str(tmp_path / "r2.md")], capture_output=True, text=True)
    assert bad.returncode == 1 and (tmp_path / "r2.md").is_file()

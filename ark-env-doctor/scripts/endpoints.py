"""已部署服務的端點檢查（2026-10-29 由 ark-dashboard-health 併入）。

只用標準庫 —— env-doctor 的使用時機常常就是「環境壞了」，不能再依賴 httpx 之類的套件。

檢查兩種端點：
- 一般端點：GET（或指定 method）→ 狀態碼符合 `expect_status`（預設 2xx）、可選 `contains` 字串
- SSE 端點：只驗 `content-type: text/event-stream`，**不等事件**（讀完標頭就斷線）

端點清單檔（`--endpoints-file`）格式，JSON 或 YAML（YAML 需要 PyYAML）：
    [{"name": "health", "url": "http://localhost:8888/health", "expect_status": 200,
      "contains": "ok"}, {"name": "events", "url": "http://localhost:8888/api/events", "sse": true}]
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path


def load_endpoints(urls: list[str] | None = None, sse: list[str] | None = None,
                   file: Path | None = None) -> list[dict]:
    """把命令列參數與清單檔合併成端點清單。"""
    eps = [{"name": u, "url": u} for u in (urls or [])]
    eps += [{"name": u, "url": u, "sse": True} for u in (sse or [])]
    if file:
        text = Path(file).read_text(encoding="utf-8")
        if Path(file).suffix in (".yaml", ".yml"):
            try:
                import yaml
            except ImportError as e:
                raise SystemExit(f"讀 {file} 需要 PyYAML；改用 JSON 清單或先 pip install pyyaml") from e
            data = yaml.safe_load(text) or []
        else:
            data = json.loads(text)
        for e in data:
            if "url" not in e:
                raise SystemExit(f"{file} 有一筆缺 url：{e}（每筆至少要 url）")
            eps.append({"name": e.get("name", e["url"]), **e})
    return eps


def _status_ok(code: int, expect) -> bool:
    if expect is None:
        return 200 <= code < 300
    if isinstance(expect, (list, tuple)):
        return code in expect
    return code == int(expect)


def check_endpoint(ep: dict, timeout: float = 5.0) -> dict:
    """檢查單一端點，回傳 {name, url, ok, status, ms, detail}。"""
    req = urllib.request.Request(ep["url"], method=ep.get("method", "GET").upper())
    if ep.get("sse"):
        req.add_header("Accept", "text/event-stream")
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ms = int((time.monotonic() - t0) * 1000)
            code, ctype = r.status, r.headers.get("content-type", "")
            if ep.get("sse"):
                ok = "text/event-stream" in ctype
                return {**_base(ep), "ok": ok, "status": code, "ms": ms,
                        "detail": "SSE OK" if ok else f"content-type 是 {ctype or '空'}，不是 text/event-stream"}
            body = r.read(65536).decode("utf-8", errors="replace") if ep.get("contains") else ""
    except urllib.error.HTTPError as e:   # 4xx/5xx 也是「有回應」，交給 expect_status 判
        code, ms, body = e.code, int((time.monotonic() - t0) * 1000), ""
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", e)
        return {**_base(ep), "ok": False, "status": 0, "ms": 0,
                "detail": f"連不上：{reason}（服務沒起、port 錯、或防火牆）"}
    if not _status_ok(code, ep.get("expect_status")):
        want = ep.get("expect_status") or "2xx"
        return {**_base(ep), "ok": False, "status": code, "ms": ms, "detail": f"預期 {want}，實際 {code}"}
    if ep.get("contains") and ep["contains"] not in body:
        return {**_base(ep), "ok": False, "status": code, "ms": ms,
                "detail": f"回應不含「{ep['contains']}」"}
    return {**_base(ep), "ok": True, "status": code, "ms": ms, "detail": ""}


def _base(ep: dict) -> dict:
    return {"name": ep["name"], "url": ep["url"]}


def check_all(eps: list[dict], timeout: float = 5.0) -> list[dict]:
    return [check_endpoint(ep, timeout) for ep in eps]


def render(results: list[dict]) -> str:
    """Markdown 報告：分數＋逐端點表＋失敗清單。"""
    passed = sum(r["ok"] for r in results)
    score = round(passed * 100 / len(results)) if results else 0
    lines = [f"# 🏥 Endpoint Health — Score: {score}/100（{passed}/{len(results)}）", "",
             "| 端點 | 狀態 | 回應時間 | 說明 |", "|---|---|---|---|"]
    for r in results:
        icon = "✅" if r["ok"] else "❌"
        status = "SSE OK" if r["detail"] == "SSE OK" else (r["status"] or "—")
        lines.append(f"| {icon} {r['name']} | {status} | {r['ms']}ms | {'' if r['ok'] else r['detail']} |")
    fails = [r for r in results if not r["ok"]]
    if fails:
        lines += ["", "## 失敗", ""] + [f"- `{r['url']}`：{r['detail']}" for r in fails]
    return "\n".join(lines) + "\n"

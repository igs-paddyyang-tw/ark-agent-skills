#!/usr/bin/env python3
"""ark-browser-tool：獨立的 Playwright 網頁操作與測試 CLI（不需要任何 LLM／API key）。

子命令：
  doctor [--url URL]                 環境檢查：playwright、Chromium 能否啟動、網址是否可達
  shot URL [選項]                    開頁 → 等待 → 截圖，附 console 錯誤、失敗請求、載入時間
  run SCENARIO [選項]                依劇本（YAML／JSON）逐步操作與斷言，產出報告與證據

判定全由本腳本決定（AI 只負責寫劇本、讀報告），exit code：
  0 PASS ／ 1 FAIL ／ 2 環境或輸入錯誤 ／ 3 BLOCK（離開允許網域等，要人處理）

劇本格式見 references/scenario-schema.md。
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

SCHEMA = "browser-scenario/1"
EXIT_PASS, EXIT_FAIL, EXIT_ENV, EXIT_BLOCK = 0, 1, 2, 3
# Canvas／WebGL 遊戲在 headless 需要軟體 GL（與 ark-web-game client e2e 相同參數）
GL_ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
ACTIONS = {
    "goto", "reload", "wait_for", "wait_until", "wait_stable", "sleep", "click", "fill", "press",
    "read", "eval", "set", "expect", "expect_text", "expect_visible", "expect_url", "shot", "offline", "repeat",
}


class ScenarioError(Exception):
    """劇本格式錯誤（exit 2）。"""


class Blocked(Exception):
    """需要人處理的狀況（exit 3）。"""


def _out(obj: dict) -> None:
    """輸出單一 JSON 到 stdout（UTF-8，避免 Windows cp950）。"""
    sys.stdout.buffer.write((json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _import_playwright():
    """延遲載入 playwright；缺套件回 None。"""
    try:
        from playwright.async_api import async_playwright  # noqa: PLC0415
        return async_playwright
    except ImportError:
        return None


# ----------------------------------------------------------------- 劇本載入與工具
def load_scenario(path: Path) -> dict:
    """讀 YAML／JSON 劇本並做基本驗證。"""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # noqa: PLC0415
        except ImportError as e:
            raise ScenarioError("讀 YAML 劇本需要 pyyaml（或改用 .json）") from e
        sc = yaml.safe_load(text) or {}
    else:
        sc = json.loads(text)
    if sc.get("schema") != SCHEMA:
        raise ScenarioError(f"schema 必須是 {SCHEMA}")
    if not isinstance(sc.get("steps"), list) or not sc["steps"]:
        raise ScenarioError("steps 必須是非空清單")
    validate_steps(sc["steps"])
    return sc


def validate_steps(steps: list, where: str = "steps") -> None:
    """每一步只能有一個動作鍵（另可帶 name／timeout／optional）。"""
    for i, st in enumerate(steps):
        if not isinstance(st, dict):
            raise ScenarioError(f"{where}[{i}] 必須是物件")
        keys = [k for k in st if k in ACTIONS]
        if len(keys) != 1:
            raise ScenarioError(f"{where}[{i}] 要剛好一個動作，支援：{sorted(ACTIONS)}")
        if keys[0] == "repeat":
            r = st["repeat"]
            if not isinstance(r, dict) or not isinstance(r.get("steps"), list):
                raise ScenarioError(f"{where}[{i}].repeat 需要 times 與 steps")
            validate_steps(r["steps"], f"{where}[{i}].repeat.steps")


_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def interp(value: Any, vars_: dict) -> Any:
    """把字串裡的 ${name} 換成變數值（遞迴處理 dict／list）。"""
    if isinstance(value, str):
        full = _VAR.fullmatch(value)
        if full:
            return vars_.get(full.group(1), value)
        return _VAR.sub(lambda m: str(vars_.get(m.group(1), m.group(0))), value)
    if isinstance(value, dict):
        return {k: interp(v, vars_) for k, v in value.items()}
    if isinstance(value, list):
        return [interp(v, vars_) for v in value]
    return value


def compare(actual: Any, spec: dict) -> tuple[bool, str]:
    """依 equals／gt／gte／lt／lte／contains／truthy 比對；沒寫條件時以真值判定。"""
    ops = {k: spec[k] for k in ("equals", "gt", "gte", "lt", "lte", "contains", "truthy") if k in spec}
    if not ops:
        return bool(actual), f"值={actual!r}"
    for op, exp in ops.items():
        try:
            ok = {
                "equals": lambda: actual == exp,
                "gt": lambda: actual > exp,
                "gte": lambda: actual >= exp,
                "lt": lambda: actual < exp,
                "lte": lambda: actual <= exp,
                "contains": lambda: exp in actual,
                "truthy": lambda: bool(actual) == bool(exp),
            }[op]()
        except TypeError:
            ok = False
        if not ok:
            return False, f"期望 {op} {exp!r}，實際 {actual!r}"
    return True, f"值={actual!r}"


def origin_of(url: str) -> str:
    """回傳 scheme://host:port。"""
    u = urlparse(url)
    return f"{u.scheme}://{u.netloc}" if u.netloc else u.scheme + ":"


def image_diff(a: bytes, b: bytes) -> float:
    """兩張截圖差異比例（0～1）；沒有 Pillow 時只比雜湊（相同 0、不同 1）。"""
    try:
        from PIL import Image, ImageChops, ImageStat  # noqa: PLC0415
    except ImportError:
        return 0.0 if hashlib.sha256(a).digest() == hashlib.sha256(b).digest() else 1.0
    ia = Image.open(io.BytesIO(a)).convert("L")
    ib = Image.open(io.BytesIO(b)).convert("L")
    if ia.size != ib.size:
        return 1.0
    return ImageStat.Stat(ImageChops.difference(ia, ib)).mean[0] / 255.0


# ----------------------------------------------------------------- 執行器
@dataclass
class Run:
    """一次劇本執行的狀態與證據。"""

    sc: dict
    out: Path
    base_url: str
    vars: dict = field(default_factory=dict)
    steps: list = field(default_factory=list)
    console: list = field(default_factory=list)
    page_errors: list = field(default_factory=list)
    failed_requests: list = field(default_factory=list)
    blocked: str | None = None
    shots: int = 0


async def _shot(page, run: Run, name: str) -> str:
    """截圖存到 shots/，回傳相對路徑。"""
    run.shots += 1
    safe = re.sub(r"[^\w.-]+", "_", name)[:60] or "shot"
    rel = f"shots/{run.shots:03d}-{safe}.png"
    await page.screenshot(path=str(run.out / rel))
    return rel


async def _js(page, expr: str, vars_: dict, body: bool = False) -> Any:
    """在頁面執行 JS；`v` 是劇本變數。body=True 時 expr 是函式本體（需自己 return）。"""
    fn = f"async (v) => {{ {expr} }}" if body else f"async (v) => {{ return await ({expr}); }}"
    return await page.evaluate(fn, vars_)


async def do_step(page, ctx, run: Run, st: dict, label: str) -> dict:
    """執行單一步驟，回傳結果；失敗丟 AssertionError，要人處理丟 Blocked。"""
    action = next(k for k in st if k in ACTIONS)
    arg = interp(st[action], run.vars)
    timeout = int(st.get("timeout", 15000))
    res: dict = {"step": label, "action": action, "name": st.get("name", ""), "ok": True, "detail": ""}
    t0 = time.perf_counter()

    if action == "goto":
        url = urljoin(run.base_url, arg)
        resp = await page.goto(url, wait_until=st.get("wait_until_state", "load"), timeout=timeout)
        res["detail"] = f"{url} → {resp.status if resp else '?'}"
        if resp and resp.status >= 400:
            raise AssertionError(f"HTTP {resp.status}：{url}")
    elif action == "reload":
        await page.reload(timeout=timeout)
    elif action == "wait_for":
        spec = arg if isinstance(arg, dict) else {"selector": arg}
        await page.wait_for_selector(spec["selector"], state=spec.get("state", "visible"), timeout=timeout)
        res["detail"] = spec["selector"]
    elif action == "wait_until":
        spec = arg if isinstance(arg, dict) else {"js": arg}
        interval = int(spec.get("interval", 200)) / 1000
        deadline = time.perf_counter() + timeout / 1000
        while True:
            val = await _js(page, spec["js"], run.vars)
            if val:
                res["detail"] = f"{spec['js']} 成立"
                break
            if time.perf_counter() > deadline:
                raise AssertionError(f"逾時 {timeout}ms：{spec['js']} 仍為 {val!r}")
            await asyncio.sleep(interval)
    elif action == "wait_stable":
        spec = arg if isinstance(arg, dict) else {}
        thr, need = float(spec.get("threshold", 0.004)), int(spec.get("frames", 2))
        interval = int(spec.get("interval", 300)) / 1000
        deadline, prev, calm = time.perf_counter() + timeout / 1000, None, 0
        while calm < need:
            cur = await page.screenshot()
            if prev is not None:
                calm = calm + 1 if image_diff(prev, cur) <= thr else 0
            prev = cur
            if time.perf_counter() > deadline:
                raise AssertionError(f"畫面 {timeout}ms 內未穩定")
            await asyncio.sleep(interval)
    elif action == "sleep":
        await asyncio.sleep(int(arg) / 1000)
    elif action == "click":
        spec = arg if isinstance(arg, dict) else {"selector": arg}
        if "selector" in spec:
            await page.click(spec["selector"], timeout=timeout)
            res["detail"] = spec["selector"]
        else:
            await page.mouse.click(float(spec["x"]), float(spec["y"]))
            res["detail"] = f"({spec['x']}, {spec['y']})"
    elif action == "fill":
        await page.fill(arg["selector"], str(arg["value"]), timeout=timeout)
        res["detail"] = arg["selector"]
    elif action == "press":
        await page.keyboard.press(str(arg))
    elif action == "read":
        if "js" in arg:
            val = await _js(page, arg["js"], run.vars)
        elif "attr" in arg:
            val = await page.get_attribute(arg["selector"], arg["attr"], timeout=timeout)
        else:
            val = await page.inner_text(arg["selector"], timeout=timeout)
        if arg.get("number"):
            val = float(re.sub(r"[^\d.\-]", "", str(val)) or "nan")
        run.vars[arg["as"]] = val
        res["detail"] = f"{arg['as']} = {val!r}"
    elif action == "eval":
        spec = arg if isinstance(arg, dict) else {"js": arg}
        val = await _js(page, spec["js"], run.vars, body=bool(spec.get("body")))
        if spec.get("as"):
            run.vars[spec["as"]] = val
        res["detail"] = f"→ {json.dumps(val, ensure_ascii=False, default=str)[:200]}"
    elif action == "set":
        run.vars.update(arg)
    elif action == "expect":
        val = await _js(page, arg["js"], run.vars) if "js" in arg else arg.get("value")
        ok, why = compare(val, arg)
        res["detail"] = f"{arg.get('msg', arg.get('js', ''))}：{why}"
        if not ok:
            raise AssertionError(res["detail"])
    elif action == "expect_text":
        txt = await page.inner_text(arg["selector"], timeout=timeout)
        ok, why = compare(txt, {k: v for k, v in arg.items() if k in ("equals", "contains")})
        res["detail"] = f"{arg['selector']}：{why}"
        if not ok:
            raise AssertionError(res["detail"])
    elif action == "expect_visible":
        await page.wait_for_selector(str(arg), state="visible", timeout=timeout)
        res["detail"] = str(arg)
    elif action == "expect_url":
        if str(arg) not in page.url:
            raise AssertionError(f"網址 {page.url} 不含 {arg}")
        res["detail"] = page.url
    elif action == "shot":
        res["shot"] = await _shot(page, run, str(arg))
    elif action == "offline":
        await ctx.set_offline(bool(arg))
        res["detail"] = "離線" if arg else "恢復連線"

    if run.blocked:
        raise Blocked(run.blocked)
    res["ms"] = round((time.perf_counter() - t0) * 1000)
    return res


async def run_steps(page, ctx, run: Run, steps: list, prefix: str = "") -> bool:
    """依序執行步驟；遇失敗截圖並停止（optional 的步驟失敗只記錄）。回傳是否全過。"""
    for i, st in enumerate(steps, 1):
        label = f"{prefix}{i}"
        if "repeat" in st:
            times = int(interp(st["repeat"].get("times", 1), run.vars))
            for k in range(1, times + 1):
                run.vars["i"] = k
                if not await run_steps(page, ctx, run, st["repeat"]["steps"], f"{label}.{k}."):
                    return False
            continue
        try:
            run.steps.append(await do_step(page, ctx, run, st, label))
        except Blocked:
            raise
        except Exception as e:  # noqa: BLE001 —— 任何步驟錯誤都要留證據、轉成 FAIL
            action = next(k for k in st if k in ACTIONS)
            rec = {"step": label, "action": action, "name": st.get("name", ""), "ok": False,
                   "detail": f"{type(e).__name__}: {str(e).splitlines()[0][:300]}"}
            try:
                rec["shot"] = await _shot(page, run, f"fail-{label}")
            except Exception:  # noqa: BLE001
                pass
            run.steps.append(rec)
            if not st.get("optional"):
                return False
    return True


async def run_scenario(sc: dict, out: Path, base_url: str | None, headed: bool, video: bool, trace: bool) -> dict:
    """執行整份劇本，寫出報告，回傳摘要。"""
    async_playwright = _import_playwright()
    if async_playwright is None:
        return {"verdict": "ENV", "error": "沒有 playwright：pip install playwright && python -m playwright install chromium"}
    base = base_url or sc.get("base_url", "")
    run = Run(sc=sc, out=out, base_url=base, vars=dict(sc.get("vars") or {}))
    (out / "shots").mkdir(parents=True, exist_ok=True)
    br = sc.get("browser") or {}
    allowed = set(sc.get("allowed_origins") or ([origin_of(base)] if base else []))
    allowed |= {"about:", "data:", "blob:"}
    checks = {"console_errors": "fail", "page_errors": "fail", "failed_requests": "fail", **(sc.get("checks") or {})}

    t0 = time.perf_counter()
    async with async_playwright() as p:
        args = list(br.get("args") or []) + (GL_ARGS if br.get("gl") else [])
        browser = await p.chromium.launch(headless=not headed, args=args, slow_mo=int(br.get("slow_mo", 0)))
        ctx_kw: dict = {}
        if sc.get("device"):
            ctx_kw.update(p.devices[sc["device"]])
        if sc.get("viewport"):
            ctx_kw["viewport"] = sc["viewport"]
        if video:
            ctx_kw["record_video_dir"] = str(out / "video")
        ctx = await browser.new_context(**ctx_kw)
        if trace:
            await ctx.tracing.start(screenshots=True, snapshots=True)
        page = await ctx.new_page()

        def on_console(msg):
            run.console.append({"type": msg.type, "text": msg.text[:500]})

        def on_response(resp):
            if resp.status >= 400:
                run.failed_requests.append({"url": resp.url, "status": resp.status})

        def on_nav(frame):
            if frame == page.main_frame and origin_of(frame.url) not in allowed and not frame.url.startswith(tuple(allowed)):
                run.blocked = f"離開允許網域：{frame.url}"

        page.on("console", on_console)
        page.on("pageerror", lambda e: run.page_errors.append(str(e)[:500]))
        page.on("response", on_response)
        page.on("requestfailed", lambda r: run.failed_requests.append({"url": r.url, "status": "failed", "error": r.failure}))
        page.on("framenavigated", on_nav)

        verdict = "PASS"
        try:
            ok = await run_steps(page, ctx, run, sc["steps"])
            verdict = "PASS" if ok else "FAIL"
        except Blocked as e:
            verdict, run.blocked = "BLOCK", str(e)
            try:
                await _shot(page, run, "blocked")
            except Exception:  # noqa: BLE001
                pass
        if trace:
            await ctx.tracing.stop(path=str(out / "trace.zip"))
        await ctx.close()
        await browser.close()

    console_errors = [c for c in run.console if c["type"] == "error"]
    findings = []
    for key, items in (("console_errors", console_errors), ("page_errors", run.page_errors), ("failed_requests", run.failed_requests)):
        if items and checks.get(key) != "off":
            findings.append({"check": key, "count": len(items), "level": checks.get(key), "sample": items[:5]})
            if checks.get(key) == "fail" and verdict == "PASS":
                verdict = "FAIL"

    summary = {
        "schema": "browser-report/1", "scenario": sc.get("name", ""), "verdict": verdict,
        "base_url": base, "blocked": run.blocked,
        "steps_total": len(run.steps), "steps_failed": sum(1 for s in run.steps if not s["ok"]),
        "duration_ms": round((time.perf_counter() - t0) * 1000), "vars": run.vars,
        "findings": findings, "steps": run.steps, "out": str(out),
        "trace": "trace.zip" if trace else None,
    }
    (out / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out / "console.jsonl").write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in run.console), encoding="utf-8")
    (out / "report.md").write_text(render_md(summary), encoding="utf-8")
    return summary


def render_md(s: dict) -> str:
    """產出給人／AI 看的 Markdown 報告。"""
    icon = {"PASS": "✅", "FAIL": "❌", "BLOCK": "⛔"}.get(s["verdict"], "⚠️")
    lines = [
        "---", f"scenario: {s['scenario']}", f"verdict: {s['verdict']}", f"base_url: {s['base_url']}",
        f"steps_failed: {s['steps_failed']}", "---", "",
        f"# {icon} {s['scenario'] or '瀏覽器測試'}：{s['verdict']}", "",
        f"- 步驟 {s['steps_total']}，失敗 {s['steps_failed']}，耗時 {s['duration_ms']} ms",
    ]
    if s.get("blocked"):
        lines.append(f"- ⛔ 要人處理：{s['blocked']}")
    if s.get("trace"):
        lines.append("- 重播：`python -m playwright show-trace trace.zip`")
    lines += ["", "| # | 動作 | 名稱 | 結果 | 說明 | 證據 |", "|---|---|---|---|---|---|"]
    for st in s["steps"]:
        detail = str(st.get("detail", "")).replace("|", "\\|")[:160]
        lines.append(f"| {st['step']} | {st['action']} | {st.get('name', '')} | {'✅' if st['ok'] else '❌'} | {detail} | {st.get('shot', '')} |")
    if s["findings"]:
        lines += ["", "## 頁面健康", "", "| 檢查 | 筆數 | 等級 | 範例 |", "|---|---:|---|---|"]
        for f in s["findings"]:
            sample = json.dumps(f["sample"][0], ensure_ascii=False)[:160].replace("|", "\\|")
            lines.append(f"| {f['check']} | {f['count']} | {f['level']} | {sample} |")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------- doctor／shot
async def cmd_doctor(url: str | None) -> dict:
    """檢查 playwright 套件、Chromium、目標網址。"""
    rep: dict = {"python": sys.version.split()[0], "playwright": None, "chromium": None, "url": None, "ok": False}
    async_playwright = _import_playwright()
    if async_playwright is None:
        rep["fix"] = "pip install playwright && python -m playwright install chromium"
        return rep
    from importlib.metadata import version  # noqa: PLC0415
    rep["playwright"] = version("playwright")
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch()
            rep["chromium"] = b.version
            if url:
                pg = await b.new_page()
                r = await pg.goto(url, timeout=15000)
                rep["url"] = {"url": url, "status": r.status if r else None, "title": await pg.title()}
            await b.close()
        rep["ok"] = not url or bool(rep["url"] and (rep["url"]["status"] or 0) < 400)
    except Exception as e:  # noqa: BLE001
        rep["error"] = str(e).splitlines()[0]
        rep["fix"] = "python -m playwright install chromium"
    return rep


async def cmd_shot(a) -> dict:
    """單頁截圖＋健康資訊。"""
    sc = {
        "schema": SCHEMA, "name": "shot", "base_url": a.url,
        "browser": {"gl": a.gl}, "checks": {"console_errors": "warn", "page_errors": "warn", "failed_requests": "warn"},
        "steps": [{"goto": a.url, "timeout": a.timeout}],
    }
    if a.device:
        sc["device"] = a.device
    elif a.viewport:
        w, h = a.viewport.lower().split("x")
        sc["viewport"] = {"width": int(w), "height": int(h)}
    if a.wait_selector:
        sc["steps"].append({"wait_for": a.wait_selector, "timeout": a.timeout})
    if a.wait_ms:
        sc["steps"].append({"sleep": a.wait_ms})
    sc["steps"].append({"shot": "page"})
    return await run_scenario(sc, a.out, None, a.headed, False, False)


def main() -> int:
    ap = argparse.ArgumentParser(description="ark-browser-tool：獨立 Playwright 網頁操作與測試")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("doctor", help="環境檢查")
    d.add_argument("--url")
    s = sub.add_parser("shot", help="單頁截圖＋健康資訊")
    s.add_argument("url")
    s.add_argument("--viewport", default="1280x720", help="寬x高")
    s.add_argument("--device", help="Playwright 裝置名，如 'iPhone 13'")
    s.add_argument("--wait-selector")
    s.add_argument("--wait-ms", type=int, default=0)
    s.add_argument("--timeout", type=int, default=20000)
    s.add_argument("--gl", action="store_true", help="Canvas／WebGL 頁面用軟體 GL")
    s.add_argument("--headed", action="store_true")
    s.add_argument("--out", type=Path)
    r = sub.add_parser("run", help="執行劇本")
    r.add_argument("scenario", type=Path)
    r.add_argument("--base-url", help="覆蓋劇本的 base_url")
    r.add_argument("--var", action="append", default=[], help="k=v，覆蓋劇本 vars")
    r.add_argument("--out", type=Path, help="預設 ./artifacts/browser/<名稱>-<時間>")
    r.add_argument("--headed", action="store_true")
    r.add_argument("--video", action="store_true")
    r.add_argument("--no-trace", action="store_true")
    a = ap.parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if a.cmd == "doctor":
        rep = asyncio.run(cmd_doctor(a.url))
        _out(rep)
        return EXIT_PASS if rep["ok"] else EXIT_ENV
    if a.cmd == "shot":
        a.out = a.out or Path("artifacts/browser") / f"shot-{stamp}"
        rep = asyncio.run(cmd_shot(a))
    else:
        try:
            sc = load_scenario(a.scenario)
        except (ScenarioError, OSError, ValueError) as e:
            _out({"verdict": "ENV", "error": str(e)})
            return EXIT_ENV
        for kv in a.var:
            k, _, v = kv.partition("=")
            sc.setdefault("vars", {})[k] = v
        name = re.sub(r"[^\w.-]+", "_", sc.get("name") or a.scenario.stem)[:40]
        out = a.out or Path("artifacts/browser") / f"{name}-{stamp}"
        rep = asyncio.run(run_scenario(sc, out, a.base_url, a.headed, a.video, not a.no_trace))
    _out({k: v for k, v in rep.items() if k != "steps"} | {"report": str(Path(rep.get("out", "")) / "report.md")})
    return {"PASS": EXIT_PASS, "FAIL": EXIT_FAIL, "BLOCK": EXIT_BLOCK}.get(rep.get("verdict"), EXIT_ENV)


if __name__ == "__main__":
    sys.exit(main())

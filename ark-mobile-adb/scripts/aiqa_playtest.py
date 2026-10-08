#!/usr/bin/env python3
"""aiqa playtest（v2.2）：給一份測試清單 md → Agent 親自操作（截圖 → 看圖判斷 → 點擊）→ 單檔 HTML 測試報告。

這支腳本不做判斷，只做三件事：
  1. 把清單 md 解析成「基本測試」項目（固定必測）與「探索重點」；
  2. 幫 Agent 操作裝置並留下可稽核的紀錄（每次點擊的原因、截圖、對帳、彈窗、發現、探索假設）；
  3. 呼叫 aiqa_playtest_report 把 run 目錄渲染成 HTML 報告（並做完整度檢查）。

    aiqa_playtest.py init --checklist 清單.md [--backend adb|fake] [--out artifacts/playtest]
    aiqa_playtest.py shot --label 大廳 [--item B-001] [--feature] [--caption ...]
    aiqa_playtest.py tap X Y --why "關付費窗" [--basis 540x960]      # 之後可 mark --outcome miss|early|noresp
    aiqa_playtest.py item B-001 --verdict PASS --shots S-0003 --note ...
    aiqa_playtest.py finding --severity 高 --category rules --title ... --shots ... --suggest ...
    aiqa_playtest.py explore --heuristic E1 --hypothesis ... --method ...   / explore --id X-001 --status issue --result ...
    aiqa_playtest.py ledger --label ... --before N --after N --bet B --spins K --win W
    aiqa_playtest.py report [--strict]        → <run>/report.html + summary.json

所有子命令 stdout 為單一 JSON envelope（contract "1"）；run 目錄記在 ./.ark-playtest.json（或 --run / ARK_PLAYTEST_RUN）。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import pathlib
import re
import shutil
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import aiqa_common as C  # noqa: E402

PLAYTEST_CONTRACT = "playtest/1"
POINTER = pathlib.Path(".ark-playtest.json")
VERDICTS = ("PASS", "FAIL", "FLAKY", "NEEDS_HUMAN", "BLOCK", "NA")
SEVERITY = {"高": "高", "high": "高", "h": "高", "p0": "高", "中": "中", "mid": "中", "medium": "中", "m": "中", "p1": "中",
            "低": "低", "low": "低", "l": "低", "p2": "低"}
CATEGORIES = {"stability": "穩定性", "newbie": "新手體驗", "rules": "規則說明與實際不一致", "ui": "操作與介面",
              "monetization": "付費與彈窗頻率", "economy": "數值與對帳", "test": "測試面", "other": "其他"}
POPUP_KINDS = {"free": "免費", "paid": "付費", "info": "資訊", "external": "對外"}
TAP_OUTCOMES = ("ok", "miss", "early", "noresp")
EXPLORE_STATUS = ("planned", "issue", "ok", "inconclusive", "skipped")

# 預設禁止動作：永遠生效，清單 frontmatter 的 forbid 只能追加不能移除
DEFAULT_FORBID = [
    "儲值 / 購買 / 任何標價（USD、NT$、¥）按鈕", "用遊戲幣兌換付費特色（Buy Bonus / PLAY BONUS）除非清單明寫",
    "評分 / 評價（會送到商店）", "綁定社群、登出、刪除帳號", "加好友、申請公會、送意見反饋、聊天（會接觸真人或客服）",
    "更新 App / 安裝其他 App / 點廣告的安裝", "斷開主機（電腦）網路", "刪除裝置上的檔案（需人同意）",
]

# ----------------------------------------------------------------- 時間 / 路徑


def now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def parse_ts(s: str) -> float:
    return _dt.datetime.fromisoformat(s).timestamp()


def slug(s: str, n: int = 40) -> str:
    s = re.sub(r"[^\w\-]+", "_", s or "").strip("_")
    return s[:n] or "shot"


def resolve_run(arg: str | None) -> pathlib.Path:
    cand = arg or os.getenv("ARK_PLAYTEST_RUN")
    if not cand and POINTER.exists():
        cand = json.loads(POINTER.read_text(encoding="utf-8")).get("run")
    if not cand:
        C.fail("BAD_INPUT", "找不到 run 目錄", "先跑 aiqa_playtest.py init --checklist <md>，或加 --run <dir>")
    run = pathlib.Path(cand)
    if not (run / "session.json").exists():
        C.fail("BAD_INPUT", f"不是 playtest run 目錄：{run}", "目錄裡要有 session.json")
    return run


# ----------------------------------------------------------------- 清單 md 解析

KEYLINE = re.compile(r"^\s*[-*+]?\s*(步驟|預期結果|預期|重複次數|重複|次數|證據|備註|前置|優先度|優先)\s*[:：]\s*(.*)$")
ID_RE = re.compile(r"^\s*([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{2,})[\s.:：、]+(.*)$")
BULLET = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?(.*)$")
SECTION_KEYS = [("explore", r"探索|explore|自我|自由|額外"), ("forbid", r"禁止|forbid|不要做|不可|安全"),
                ("notes", r"備註|notes?|背景|說明|環境"), ("base", r"基本|固定|basic|必測|測試清單|測試項|checklist")]


def split_frontmatter(text: str) -> tuple[dict, str]:
    text = text.lstrip("﻿")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
    if not m:
        return {}, text
    try:
        import yaml
        meta = yaml.safe_load(m.group(1)) or {}
    except Exception as e:  # noqa: BLE001
        C.fail("BAD_INPUT", f"清單 frontmatter 不是合法 YAML：{e}")
    return (meta if isinstance(meta, dict) else {}), text[m.end():]


def _section_of(title: str) -> str | None:
    for key, pat in SECTION_KEYS:
        if re.search(pat, title, re.I):
            return key
    return None


def _split_expect(text: str) -> tuple[str, str]:
    parts = re.split(r"\s*(?:[｜|;；—–]\s*)?預期(?:結果)?\s*[:：]\s*", text, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(" ｜|;；—–"), parts[1].strip()
    parts = re.split(r"\s*[｜|]\s*", text, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return text.strip(), ""


def _table_rows(lines: list[str]) -> list[list[str]]:
    rows = []
    for ln in lines:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        rows.append(cells)
    return rows


def parse_checklist(text: str) -> dict:
    """寬鬆解析：frontmatter（選配）+ 標題分段 + 三種項目寫法（勾選 / 條列、### 區塊、表格）。"""
    meta, body = split_frontmatter(text)
    blocks: list[dict] = [{"level": 0, "title": "", "lines": []}]
    for ln in body.splitlines():
        h = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", ln)
        if h:
            blocks.append({"level": len(h.group(1)), "title": h.group(2).strip(), "lines": []})
        else:
            blocks[-1]["lines"].append(ln)

    items, explore, forbid, notes = [], [], [], []
    mode, group, title_h1 = "base", "", ""

    def add_item(title, expect="", steps=None, iid=None, **kw):
        it = {"id": iid, "title": title.strip(), "group": group, "steps": steps or [], "expect": expect.strip(),
              "repeat": kw.get("repeat"), "evidence": kw.get("evidence", ""), "priority": kw.get("priority", ""),
              "precondition": kw.get("precondition", ""), "note": kw.get("note", "")}
        items.append(it)
        return it

    def table_items(tlines):
        rows = _table_rows(tlines)
        if len(rows) < 2:
            return
        hdr = rows[0]

        def col(*names):
            for i, h in enumerate(hdr):
                if any(n in h for n in names):
                    return i
            return None
        ci, ct, cs, ce = col("編號", "ID", "id"), col("測試目的", "項目", "測試項", "標題", "title"), col("步驟"), col("預期")
        if ct is None:
            ct = 0 if ci != 0 else 1
        for r in rows[1:]:
            g = lambda i: r[i] if i is not None and i < len(r) else ""  # noqa: E731
            if not g(ct):
                continue
            steps = [x.strip() for x in re.split(r"<br\s*/?>|；|→", g(cs)) if x.strip()] if cs is not None else []
            iid = g(ci) if ci is not None and re.fullmatch(r"[A-Z][A-Z0-9-]*-\d{2,}", g(ci)) else None
            add_item(g(ct), g(ce), steps, iid)

    for b in blocks:
        title, lines = b["title"], b["lines"]
        if b["level"] == 1 and not title_h1 and _section_of(title) is None:
            title_h1 = title
        has_keys = any(KEYLINE.match(x) for x in lines)
        idm = ID_RE.match(title) if title else None
        if title and not idm and not has_keys:
            sec = _section_of(title)
            if sec:
                mode, group = sec, ("" if sec == "base" else title)
            elif b["level"] > 1 or title != title_h1:
                group = title
        if title and (idm or (has_keys and mode == "base")):
            # ### 區塊項目
            iid, t = (idm.group(1), idm.group(2)) if idm else (None, title)
            fields, steps, cur, tlines = {}, [], None, []
            for ln in lines:
                if ln.strip().startswith("|"):
                    tlines.append(ln); continue
                km = KEYLINE.match(ln)
                if km:
                    cur = km.group(1)
                    if cur == "步驟":
                        if km.group(2).strip():
                            steps.append(km.group(2).strip())
                    else:
                        fields[cur] = km.group(2).strip()
                    continue
                bm = BULLET.match(ln)
                if bm and bm.group(2).strip():
                    if cur in (None, "步驟"):
                        steps.append(bm.group(2).strip())
                    else:
                        fields[cur] = (fields.get(cur, "") + "；" + bm.group(2).strip()).strip("；")
            rep = fields.get("重複") or fields.get("重複次數") or fields.get("次數")
            add_item(t, fields.get("預期") or fields.get("預期結果", ""), steps, iid,
                     repeat=int(re.sub(r"\D", "", rep) or 1) if rep else None, evidence=fields.get("證據", ""),
                     priority=fields.get("優先") or fields.get("優先度", ""), precondition=fields.get("前置", ""),
                     note=fields.get("備註", ""))
            if tlines:
                table_items(tlines)
            continue
        # 條列 / 表格
        table: list[str] = []
        last = None
        for ln in lines + [""]:
            if ln.strip().startswith("|"):
                table.append(ln); continue
            if table:
                if mode == "base":
                    table_items(table)
                table = []
            bm = BULLET.match(ln)
            if not bm or not bm.group(2).strip():
                if ln.strip() and mode == "notes":
                    notes.append(ln.strip())
                continue
            indent, text = len(bm.group(1).expandtabs(2)), bm.group(2).strip()
            if mode == "explore":
                explore.append(text); continue
            if mode == "forbid":
                forbid.append(text); continue
            if mode == "notes":
                notes.append(text); continue
            if indent >= 2 and last is not None:
                km = KEYLINE.match(ln)
                if km and km.group(1).startswith("預期"):
                    last["expect"] = (last["expect"] + "；" + km.group(2)).strip("；")
                else:
                    last["steps"].append(text)
                continue
            idm2 = ID_RE.match(text)
            iid, text = (idm2.group(1), idm2.group(2)) if idm2 else (None, text)
            t, e = _split_expect(text)
            last = add_item(t, e, [], iid)

    for f in meta.get("forbid") or []:
        forbid.append(str(f))
    for f in meta.get("explore_focus") or []:
        explore.append(str(f))
    # 補 ID、檢查重複
    used, n = set(), 0
    for it in items:
        if it["id"]:
            if it["id"] in used:
                C.fail("BAD_INPUT", f"清單 ID 重複：{it['id']}")
            used.add(it["id"])
    for it in items:
        if not it["id"]:
            n += 1
            while f"B-{n:03d}" in used:
                n += 1
            it["id"] = f"B-{n:03d}"; used.add(it["id"])
    return {"meta": meta, "title": meta.get("title") or title_h1 or "AI 試玩測試報告", "items": items,
            "explore_focus": explore, "forbid": forbid, "notes": notes}


# ----------------------------------------------------------------- 事件存取


class Run:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self.session = json.loads((path / "session.json").read_text(encoding="utf-8"))
        self.ev_path = path / "events.jsonl"

    # events
    def events(self, kind: str | None = None) -> list[dict]:
        if not self.ev_path.exists():
            return []
        out = [json.loads(x) for x in self.ev_path.read_text(encoding="utf-8").splitlines() if x.strip()]
        return [e for e in out if kind is None or e["kind"] == kind]

    def append(self, kind: str, **data) -> dict:
        ev = {"seq": len(self.events()) + 1, "ts": now_iso(), "kind": kind, **{k: v for k, v in data.items() if v is not None}}
        with self.ev_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return ev

    def next_id(self, kind: str, prefix: str, width: int = 3) -> str:
        ids = {e.get("id") for e in self.events(kind) if e.get("id")}
        return f"{prefix}-{len(ids) + 1:0{width}d}"

    def save_session(self):
        C.atomic_write(self.path / "session.json", json.dumps(self.session, ensure_ascii=False, indent=2))

    def decision(self, see: str, do: str, why: str):
        p = self.path / "decision-log.md"
        if not p.exists():
            p.write_text("# 決策紀錄\n\n| 時間 | 看到的畫面 / 情境 | 動作 | 原因 |\n|---|---|---|---|\n", encoding="utf-8")
        cell = lambda s: (s or "").replace("|", "／").replace("\n", " ")  # noqa: E731
        with p.open("a", encoding="utf-8") as f:
            f.write(f"| {now_iso()[11:19]} | {cell(see)} | {cell(do)} | {cell(why)} |\n")

    # device
    @property
    def fake(self) -> bool:
        return self.session.get("backend") == "fake"

    def device(self) -> str:
        return self.session.get("device") or ""


def merged(run: Run, kind: str) -> dict[str, dict]:
    """同一 id 的事件依序合併（後寫覆蓋）→ {id: 最終狀態}；保持首次出現順序。"""
    out: dict[str, dict] = {}
    for e in run.events(kind):
        i = e.get("id")
        if not i:
            continue
        base = out.get(i, {})
        out[i] = {**base, **{k: v for k, v in e.items() if v not in (None, "", [])}, "first_ts": base.get("first_ts", e["ts"])}
    return out


# ----------------------------------------------------------------- 裝置操作（adb / fake）


def _A():
    import ark_mobile_adb as A
    return A


def _adb_call(fn, *a, **kw):
    A = _A()
    try:
        return fn(*a, **kw)
    except A.ArkMobileError as e:
        C.fail(e.code, str(e), e.hint)


def fake_image(out: pathlib.Path, label: str, size=(720, 1280)):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", size, (24 + (hash(label) % 60), 40, 70))
    d = ImageDraw.Draw(im)
    d.rectangle([20, 20, size[0] - 20, size[1] - 20], outline=(220, 200, 120), width=4)
    d.text((40, 40), f"FAKE SCREEN\n{label}\n{now_iso()}", fill=(255, 255, 255))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)


def device_wh(run: Run) -> tuple[int, int]:
    r = run.session.get("resolution")
    if r:
        return int(r[0]), int(r[1])
    if run.fake:
        return 720, 1280
    return _adb_call(_A().device_size, run.device())


def take_shot(run: Run, label: str, src: str | None = None) -> pathlib.Path:
    sid = run.next_id("shot", "S", 4)
    out = run.path / "shots" / f"{sid}-{slug(label)}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    if src:
        shutil.copyfile(src, out)
    elif run.fake:
        fake_image(out, label, device_wh(run))
    else:
        _adb_call(_A().screenshot_to, run.device(), out)
    return out


def do_tap(run: Run, x: int, y: int, long_ms: int = 0):
    if run.fake:
        return
    A = _A()
    args = ["shell", "input", "swipe", str(x), str(y), str(x), str(y), str(long_ms)] if long_ms else ["shell", "input", "tap", str(x), str(y)]
    _adb_call(A.adb, args, run.device())


def app_in_foreground(run: Run) -> bool | None:
    pkg = run.session.get("package")
    if run.fake or not pkg:
        return None
    A = _A()
    try:
        out = A.adb(["shell", "dumpsys", "window"], run.device(), timeout=15).stdout
    except A.ArkMobileError:
        return None
    line = next((x for x in out.splitlines() if "mCurrentFocus" in x or "mFocusedApp" in x), "")
    return pkg in line if line else None


# ----------------------------------------------------------------- 子命令


def cmd_init(a):
    src = pathlib.Path(a.checklist)
    if not src.exists():
        C.fail("BAD_INPUT", f"清單不存在：{src}")
    text = src.read_text(encoding="utf-8")
    cl = parse_checklist(text)
    if not cl["items"] and not a.allow_empty:
        C.fail("GATE_BLOCKED", "清單解析不到任何基本測試項", "用 `- [ ] 項目 ｜ 預期：…`、`### B-001 標題` + 步驟/預期，或表格（項目 / 預期欄）；只做探索請加 --allow-empty")
    meta = cl["meta"]
    root = pathlib.Path(a.out)
    root.mkdir(parents=True, exist_ok=True)
    day = _dt.date.today().strftime("%Y%m%d")
    base = f"{day}-{slug(meta.get('game') or cl['title'], 24)}"
    seq = 1 + len([p for p in root.iterdir() if p.is_dir() and p.name.startswith(base)])
    run_dir = root / f"{base}-{seq:02d}"
    for sub in ("shots", "logs"):
        (run_dir / sub).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, run_dir / "checklist.md")
    C.atomic_write(run_dir / "checklist.json", json.dumps(cl, ensure_ascii=False, indent=2))

    backend = a.backend or meta.get("backend") or "adb"
    session = {"contract": PLAYTEST_CONTRACT, "skill_version": C.SKILL_VERSION, "title": a.title or cl["title"],
               "game": meta.get("game", ""), "package": a.package or meta.get("package", ""), "platform": meta.get("platform", ""),
               "account": meta.get("account", ""), "tester": meta.get("tester", "AI（Agent 親自操作）"),
               "backend": backend, "device": "", "resolution": None, "app_version": meta.get("app_version", ""),
               "device_model": "", "started": now_iso(), "finished": None, "checklist": "checklist.md",
               "checklist_sha256": C.sha_text(text), "budget_minutes": meta.get("budget_minutes"),
               "explore": meta.get("explore", True), "explore_budget": meta.get("explore_budget", "30%"),
               "balance_floor": meta.get("balance_floor"), "forbid": DEFAULT_FORBID + cl["forbid"],
               "source_dir": str(run_dir.resolve())}
    if backend == "adb":
        A = _A()
        dev = _adb_call(A.resolve_device, a.device)
        session["device"] = dev
        w, h = _adb_call(A.device_size, dev)
        session["resolution"] = [w, h]
        try:
            session["device_model"] = A.adb(["shell", "getprop", "ro.product.model"], dev, timeout=10).stdout.strip()
            if session["package"] and not session["app_version"]:
                out = A.adb(["shell", "dumpsys", "package", session["package"]], dev, timeout=20).stdout
                m = re.search(r"versionName=(\S+)", out)
                session["app_version"] = m.group(1) if m else ""
            if not a.keep_logcat:
                A.adb(["logcat", "-c"], dev, timeout=10)
        except A.ArkMobileError:
            pass
    else:
        session["device"] = "fake"
        session["resolution"] = [720, 1280]
        session["device_model"] = "fake"
    C.atomic_write(run_dir / "session.json", json.dumps(session, ensure_ascii=False, indent=2))
    narrative = run_dir / "narrative.md"
    if not narrative.exists():
        narrative.write_text(NARRATIVE_SKELETON, encoding="utf-8")
    run = Run(run_dir)
    run.append("init", checklist=str(src), items=len(cl["items"]))
    run.decision("—", "init", f"清單 {src.name}：基本測試 {len(cl['items'])} 項、探索重點 {len(cl['explore_focus'])} 條")
    POINTER.write_text(json.dumps({"run": str(run_dir.resolve())}, ensure_ascii=False), encoding="utf-8")
    C.emit({"run": str(run_dir.resolve()), "items": [{"id": i["id"], "title": i["title"], "group": i["group"], "expect": i["expect"]} for i in cl["items"]],
            "explore_focus": cl["explore_focus"], "forbid": session["forbid"], "backend": backend, "device": session["device"],
            "resolution": session["resolution"], "next": "依 references/playtest-sop.md：先跑基本測試，再做自我探索；每一步 shot → 看 → tap --why"})


def cmd_shot(a):
    run = Run(resolve_run(a.run))
    out = take_shot(run, a.label, a.src)
    sid = out.name.split("-", 2)[0] + "-" + out.name.split("-", 2)[1]
    data = {"id": sid, "path": str(out), "label": a.label}
    if a.crop:
        A = _A()
        rect = [int(v) for v in a.crop.split(",")]
        crop = out.with_name(out.stem + "-crop.png")
        _adb_call(A.crop_zoom, out, rect, a.zoom, crop)
        data["crop"] = str(crop)
    if a.thumb:
        A = _A()
        th = run.path / "shots" / "_thumb" / out.name
        th.parent.mkdir(parents=True, exist_ok=True)
        data["thumb"] = str(th)
        data["thumb_meta"] = _adb_call(A.make_thumb, out, a.thumb, th, device_wh(run))
        data["tap_hint"] = f"縮圖座標請加 --basis {data['thumb_meta']['thumb_size'][0]}x{data['thumb_meta']['thumb_size'][1]}"
    fg = None if a.no_fg else app_in_foreground(run)
    if fg is False:
        data["warning"] = "App 不在前景：可能閃退或跳到外部 App——先 logcat --save 再判斷"
    run.append("shot", id=sid, file=str(out.relative_to(run.path)), label=a.label, caption=a.caption or a.label,
               item=a.item, finding=a.finding, explore=a.explore, section=a.section, feature=bool(a.feature) or None, fg=fg)
    C.emit(data)


def _xy(run: Run, x: float, y: float, basis: str | None) -> tuple[int, int]:
    if basis:
        bw, bh = (int(v) for v in basis.lower().split("x"))
        w, h = device_wh(run)
        return int(round(x * w / bw)), int(round(y * h / bh))
    return int(x), int(y)


def cmd_tap(a):
    run = Run(resolve_run(a.run))
    if not a.why.strip():
        C.fail("BAD_INPUT", "--why 必填：每次點擊都要寫原因（報告的決策紀錄與有效點擊率靠它）")
    x, y = _xy(run, a.x, a.y, a.basis)
    tid = run.next_id("tap", "T", 4)
    do_tap(run, x, y, a.long or 0)
    run.append("tap", id=tid, x=x, y=y, why=a.why, target=a.target, expect=a.expect, item=a.item, explore=a.explore,
               outcome="ok", long_ms=a.long or None)
    run.decision(a.see or "", f"{'長按' if a.long else '點'} ({x},{y}) {a.target or ''}".strip(), a.why)
    if a.wait:
        time.sleep(a.wait)
    C.emit({"id": tid, "x": x, "y": y, "hint": "下一步先 shot 看結果；點偏 / 太早 / 沒反應請 mark --outcome miss|early|noresp"})


def cmd_swipe(a):
    run = Run(resolve_run(a.run))
    x1, y1 = _xy(run, a.x1, a.y1, a.basis)
    x2, y2 = _xy(run, a.x2, a.y2, a.basis)
    if not run.fake:
        _adb_call(_A().adb, ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(a.duration)], run.device())
    tid = run.next_id("tap", "T", 4)
    run.append("tap", id=tid, gesture="swipe", x=x1, y=y1, x2=x2, y2=y2, why=a.why, outcome="ok", item=a.item, explore=a.explore)
    run.decision(a.see or "", f"滑動 ({x1},{y1})→({x2},{y2})", a.why)
    C.emit({"id": tid, "from": [x1, y1], "to": [x2, y2]})


def cmd_key(a):
    run = Run(resolve_run(a.run))
    key = a.name.upper()
    key = {"BACK": "BACK", "HOME": "HOME", "RECENT": "APP_SWITCH"}.get(key, key)
    if not run.fake:
        _adb_call(_A().adb, ["shell", "input", "keyevent", f"KEYCODE_{key}"], run.device())
    tid = run.next_id("tap", "T", 4)
    run.append("tap", id=tid, gesture="key", key=key, why=a.why, outcome="ok", item=a.item, explore=a.explore)
    run.decision(a.see or "", f"按 {key}", a.why)
    C.emit({"id": tid, "key": key})


def cmd_mark(a):
    run = Run(resolve_run(a.run))
    taps = run.events("tap")
    if not taps:
        C.fail("BAD_INPUT", "還沒有任何點擊")
    tid = a.tap or taps[-1]["id"]
    if tid not in {t["id"] for t in taps}:
        C.fail("BAD_INPUT", f"找不到 {tid}")
    run.append("tap", id=tid, outcome=a.outcome, outcome_note=a.note)
    C.emit({"id": tid, "outcome": a.outcome})


def cmd_spin(a):
    """重複點同一個鈕（老虎機旋轉）。每 shot_every 把截一張；App 掉出前景立即停並存 logcat。"""
    run = Run(resolve_run(a.run))
    x, y = _xy(run, a.x, a.y, a.basis)
    t0, done, stopped, shots = now_iso(), 0, None, []
    floor = run.session.get("balance_floor")
    for k in range(1, a.times + 1):
        do_tap(run, x, y)
        done = k
        time.sleep(a.interval if not run.fake else 0)
        if a.shot_every and (k % a.shot_every == 0 or k == a.times):
            out = take_shot(run, f"{a.machine or 'spin'} {k}of{a.times}")
            sid = "-".join(out.name.split("-", 2)[:2])
            run.append("shot", id=sid, file=str(out.relative_to(run.path)), label=f"{a.machine or 'spin'} 第 {k}/{a.times} 把",
                       caption=f"{a.machine or ''} 第 {k} 把".strip(), item=a.item, explore=a.explore)
            shots.append(str(out))
            fg = app_in_foreground(run)
            if fg is False:
                stopped = "app_not_foreground"
                break
    if stopped:
        lc = _save_logcat(run, f"spin-stop-{a.machine or 'spin'}")
        run.append("crash_suspect", where=f"spin {a.machine or ''} 第 {done} 把", logcat=lc.get("file"), fatal=lc.get("fatal", [])[:10])
    run.append("spin", machine=a.machine, bet=a.bet, n=done, x=x, y=y, ts_start=t0, stopped=stopped, item=a.item, explore=a.explore)
    run.decision(f"{a.machine or ''} 押注 {a.bet or '?'}", f"連續旋轉 {done} 把 ({x},{y})", a.why or "累積把數 / 等特色遊戲")
    C.emit({"spins": done, "stopped": stopped, "shots": shots,
            "hint": "看最後幾張截圖：有沒有進特色遊戲、餘額是否合理；每 5–10 把用 ledger 對一次帳" + (f"；餘額低於 {floor} 要停" if floor else "")})


def cmd_decide(a):
    run = Run(resolve_run(a.run))
    run.append("decide", see=a.see, do=a.do, why=a.why, item=a.item, explore=a.explore)
    run.decision(a.see, a.do, a.why)
    C.emit({"ok": True})


def _shots_list(s: str | None) -> list[str] | None:
    return [x.strip() for x in s.split(",") if x.strip()] if s else None


def cmd_item(a):
    run = Run(resolve_run(a.run))
    cl = json.loads((run.path / "checklist.json").read_text(encoding="utf-8"))
    ids = [i["id"] for i in cl["items"]]
    if a.id not in ids:
        C.fail("BAD_INPUT", f"清單沒有 {a.id}", f"可用：{', '.join(ids[:20])}{'…' if len(ids) > 20 else ''}")
    v = a.verdict.upper()
    if v not in VERDICTS:
        C.fail("BAD_INPUT", f"verdict 必須是 {VERDICTS}")
    shots = _shots_list(a.shots)
    warn = None
    if v in ("PASS", "FAIL") and not shots and not merged(run, "item").get(a.id, {}).get("shots"):
        warn = "PASS / FAIL 沒附證據截圖（--shots S-xxxx）：報告會標「無證據」，--strict 會擋"
    run.append("item", id=a.id, verdict=v, note=a.note, actual=a.actual, shots=shots, finding=a.finding, block_reason=a.block_reason)
    run.decision(a.id, f"判定 {v}", a.note or a.actual or "")
    C.emit({"id": a.id, "verdict": v, "warning": warn})


def cmd_finding(a):
    run = Run(resolve_run(a.run))
    fid = a.id or run.next_id("finding", "F")
    exists = fid in merged(run, "finding")
    if not exists and not (a.title and a.severity):
        C.fail("BAD_INPUT", "新發現需要 --title 與 --severity")
    sev = SEVERITY.get((a.severity or "").lower(), a.severity) if a.severity else None
    if sev and sev not in ("高", "中", "低"):
        C.fail("BAD_INPUT", "--severity 用 高 / 中 / 低（或 high/mid/low）")
    cat = a.category
    if cat and cat not in CATEGORIES and cat not in CATEGORIES.values():
        C.fail("BAD_INPUT", f"--category 用 {', '.join(CATEGORIES)}")
    run.append("finding", id=fid, severity=sev, category=cat, title=a.title, detail=a.detail, shots=_shots_list(a.shots),
               suggest=a.suggest, confirm=True if a.confirm else (False if a.no_confirm else None), item=a.item, explore=a.explore, repro=a.repro,
               where=a.where, status=a.status)
    run.decision(a.where or "", f"記錄發現 {fid}（{sev or ''}）", a.title or a.detail or "")
    C.emit({"id": fid, "updated": exists})


def cmd_explore(a):
    run = Run(resolve_run(a.run))
    xid = a.id or run.next_id("explore", "X")
    exists = xid in merged(run, "explore")
    if not exists and not a.hypothesis:
        C.fail("BAD_INPUT", "新探索需要 --hypothesis（想驗證什麼）")
    if a.status and a.status not in EXPLORE_STATUS:
        C.fail("BAD_INPUT", f"--status 用 {EXPLORE_STATUS}")
    status = a.status or (None if exists else "planned")
    run.append("explore", id=xid, heuristic=a.heuristic, area=a.area, hypothesis=a.hypothesis, method=a.method,
               result=a.result, status=status, finding=a.finding, shots=_shots_list(a.shots))
    run.decision(a.area or "", f"探索 {xid} {status or ''}".strip(), a.hypothesis or a.result or "")
    C.emit({"id": xid, "status": status, "updated": exists})


def _num(s):
    if s is None:
        return None
    try:
        return float(str(s).replace(",", "").replace("_", ""))
    except ValueError:
        C.fail("BAD_INPUT", f"不是數字：{s}")


def cmd_ledger(a):
    run = Run(resolve_run(a.run))
    before, after = _num(a.before), _num(a.after)
    bet, spins, win, exp = _num(a.bet), _num(a.spins), _num(a.win), _num(a.expect_delta)
    if exp is None:
        if bet is None and win is None:
            C.fail("BAD_INPUT", "需要 --expect-delta，或 --bet/--spins/--win 讓我算")
        exp = (win or 0) - (bet or 0) * (spins or 0)
    delta = after - before
    match = abs(delta - exp) <= (a.tolerance or 0)
    lid = run.next_id("ledger", "L")
    run.append("ledger", id=lid, label=a.label, before=before, after=after, bet=bet, spins=spins, win=win,
               expect_delta=exp, delta=delta, diff=delta - exp, match=match, note=a.note, shots=_shots_list(a.shots),
               item=a.item, explore=a.explore)
    run.decision(a.label, f"對帳 {lid}", f"預期 {exp:+,.0f}、實際 {delta:+,.0f} → {'相符' if match else '不符'}")
    C.emit({"id": lid, "expect_delta": exp, "delta": delta, "diff": delta - exp, "match": match,
            "hint": None if match else "對不上：先找原因（延後退款、加成、稅、讀錯數字），確認是問題再記 finding"})


def cmd_popup(a):
    run = Run(resolve_run(a.run))
    if a.kind not in POPUP_KINDS:
        C.fail("BAD_INPUT", f"--kind 用 {', '.join(POPUP_KINDS)}")
    run.append("popup", name=a.name, ptype=a.kind, action=a.action, price=a.price, shots=_shots_list(a.shots), where=a.where)
    run.decision(a.where or "", f"彈窗「{a.name}」→ {a.action}", POPUP_KINDS[a.kind])
    n = len([e for e in run.events("popup") if e.get("name") == a.name])
    C.emit({"name": a.name, "count": n})


def cmd_game(a):
    run = Run(resolve_run(a.run))
    run.append("game", name=a.name, gtype=a.type, rules_read=True if a.rules_read else None, note=a.note,
               feature=a.feature, win=_num(a.win), shots=_shots_list(a.shots))
    C.emit({"name": a.name, "feature": a.feature})


def cmd_segment(a):
    run = Run(resolve_run(a.run))
    run.append("segment", action=a.action, name=a.name, note=a.note)
    C.emit({"segment": a.action, "name": a.name})


def _save_logcat(run: Run, label: str) -> dict:
    out = run.path / "logs" / f"logcat-{_dt.datetime.now().strftime('%m%d-%H%M%S')}-{slug(label, 24)}.txt"
    if run.fake:
        out.write_text("fake logcat\n", encoding="utf-8")
        return {"file": str(out.relative_to(run.path)), "fatal": [], "crash": False}
    A = _A()
    try:
        text = A.adb(["logcat", "-d"], run.device(), timeout=60).stdout or ""
    except A.ArkMobileError as e:
        return {"error": str(e)}
    out.write_text(text, encoding="utf-8")
    fatal = [ln for ln in text.splitlines() if "FATAL" in ln or "ANR in" in ln or " F DEBUG" in ln or "SIGABRT" in ln
             or "Abort message" in ln or "Il2CppExceptionWrapper" in ln or "backtrace:" in ln]
    return {"file": str(out.relative_to(run.path)), "fatal": fatal[:40], "crash": bool(fatal)}


def cmd_logcat(a):
    run = Run(resolve_run(a.run))
    if a.clear:
        if not run.fake:
            _adb_call(_A().adb, ["logcat", "-c"], run.device())
        run.append("logcat", action="clear")
        C.emit({"cleared": True})
    res = _save_logcat(run, a.label or "manual")
    run.append("logcat", action="save", label=a.label, file=res.get("file"), crash=res.get("crash"), fatal=res.get("fatal", [])[:10])
    C.emit(res)


def active_minutes(run: Run, idle_gap: float = 180.0) -> float:
    ts = []
    for e in run.events():
        ts.append(parse_ts(e["ts"]))
        if e.get("ts_start"):
            ts.append(parse_ts(e["ts_start"]))
    ts.sort()
    spans = [(parse_ts(e["ts_start"]), parse_ts(e["ts"])) for e in run.events("spin") if e.get("ts_start")]
    total = 0.0
    for a_, b_ in zip(ts, ts[1:]):
        inside = any(s <= a_ and b_ <= e for s, e in spans)  # 連續旋轉整段都算操作
        total += (b_ - a_) if inside else min(b_ - a_, idle_gap)
    return round(total / 60, 1)


def status_data(run: Run) -> dict:
    cl = json.loads((run.path / "checklist.json").read_text(encoding="utf-8"))
    items = merged(run, "item")
    by = {v: 0 for v in VERDICTS}
    pending = []
    for it in cl["items"]:
        v = items.get(it["id"], {}).get("verdict")
        if v:
            by[v] += 1
        else:
            pending.append(f"{it['id']} {it['title']}")
    ex = merged(run, "explore")
    fi = merged(run, "finding")
    started = parse_ts(run.session["started"])
    budget = run.session.get("budget_minutes")
    act = active_minutes(run)
    return {"base_total": len(cl["items"]), "verdicts": by, "pending": pending,
            "explore": {s: len([x for x in ex.values() if x.get("status") == s]) for s in EXPLORE_STATUS},
            "findings": {s: len([f for f in fi.values() if f.get("severity") == s]) for s in ("高", "中", "低")},
            "taps": len({t["id"] for t in run.events("tap")}), "shots": len(run.events("shot")),
            "spins": int(sum(e.get("n", 0) for e in run.events("spin"))), "ledger": len(run.events("ledger")),
            "ledger_mismatch": [e["id"] for e in run.events("ledger") if not e.get("match")],
            "elapsed_min": round((time.time() - started) / 60, 1), "active_min": act,
            "budget_left_min": round(budget - act, 1) if budget else None,
            "explore_focus_unvisited": [f for f in cl.get("explore_focus", []) if not any(f[:6] in (x.get("area") or "") + (x.get("hypothesis") or "") for x in ex.values())]}


def cmd_status(a):
    run = Run(resolve_run(a.run))
    C.emit(status_data(run))


def cmd_finish(a):
    run = Run(resolve_run(a.run))
    run.session["finished"] = now_iso()
    run.save_session()
    run.append("finish")
    C.emit({"finished": run.session["finished"], "next": "補 narrative.md → aiqa_playtest.py report"})


def cmd_report(a):
    run = Run(resolve_run(a.run))
    import aiqa_playtest_report as R
    res = R.build(run, out=pathlib.Path(a.out) if a.out else None, img_width=a.img_width, max_images=a.max_images)
    if a.strict and res["lint"]["errors"]:
        C.fail("GATE_BLOCKED", f"報告完整度檢查沒過（{len(res['lint']['errors'])} 項）", "；".join(res["lint"]["errors"][:6]), data=res)
    C.emit(res)


def cmd_promote(a):
    """把這輪的發現變成下一輪的回歸項，輸出 checklist.next.md（原基本測試 + 回歸）。"""
    run = Run(resolve_run(a.run))
    src = (run.path / "checklist.md").read_text(encoding="utf-8")
    fi = merged(run, "finding")
    lines = [src.rstrip(), "", f"## 回歸：上一輪發現（{run.path.name}）", ""]
    for f in fi.values():
        if f.get("status") == "wontfix":
            continue
        exp = f.get("suggest") or "問題不再發生"
        lines.append(f"- [ ] R-{f['id'][2:]} 〔{f.get('severity', '')}〕{f.get('title', '')} ｜ 預期：{exp}")
        if f.get("where"):
            lines.append(f"  - 位置：{f['where']}")
    out = pathlib.Path(a.out) if a.out else run.path / "checklist.next.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    C.emit({"out": str(out), "regression_items": len(fi)})


NARRATIVE_SKELETON = """<!-- narrative.md：報告中「只有人（Agent）寫得出來」的段落。aiqa_playtest.py report 會把它併進 HTML。
     規則：每段只寫有看過的事；數字要能對到 events / ledger；圖用 ![說明](S-0012)，連續多張自動排成圖牆。
     有序清單寫成「1. **步驟名** 說明」會排成流程卡；> 開頭的段落是警示框；表格照 markdown 寫。
     不需要的段落整段刪掉（只剩註解的段落不會出現在報告）。
     基本測試結果、發現的問題、探索、對帳、彈窗、優化建議、數據總覽都由事件自動產生，不用在這裡重寫。 -->

## 摘要
<!-- 2–4 句：測了什麼、整體結論、最重要的 1–2 個發現。 -->

## 流程（實際走過的順序）
<!-- 1. **開 App → 讀取畫面** 讀取條到 100%…
     2. **登入彈窗串** 依序看到… -->

## 規則與玩法（從遊戲內規則頁讀出）
<!-- 每個玩過的遊戲：盤面、怎麼進特色遊戲、實際玩到什麼；可用表格。 -->

## 功能巡覽
<!-- 大廳 / 共用按鈕 / 各功能：看到什麼、試了什麼、結果。 -->

## 做法與限制
<!-- 自動段已寫基本做法；這裡補本輪特有的：自己的失誤、沒能驗證的、錄影 / 紀錄的缺口。 -->

## 待辦
<!-- 需要人決定的事、還沒試的、下一輪要補的。 -->
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aiqa_playtest", description="清單 md → Agent 親自試玩 → HTML 測試報告")
    p.add_argument("--run", help="run 目錄（預設讀 ./.ark-playtest.json）")
    sub = p.add_subparsers(dest="cmd", required=True)

    def ctx(s):
        s.add_argument("--item"); s.add_argument("--explore")

    s = sub.add_parser("init"); s.add_argument("--checklist", required=True)
    s.add_argument("--out", default=os.getenv("ARK_PLAYTEST_OUT", "artifacts/playtest"), help="run 根目錄（預設 ./artifacts/playtest，可用 ARK_PLAYTEST_OUT 改）")
    s.add_argument("--backend", choices=["adb", "fake"]); s.add_argument("--device"); s.add_argument("--package"); s.add_argument("--title")
    s.add_argument("--keep-logcat", action="store_true"); s.add_argument("--allow-empty", action="store_true"); s.set_defaults(fn=cmd_init)

    s = sub.add_parser("parse", help="只解析清單，不建 run（檢查清單寫法）"); s.add_argument("checklist")
    s.set_defaults(fn=lambda a: C.emit(parse_checklist(pathlib.Path(a.checklist).read_text(encoding="utf-8"))))

    s = sub.add_parser("shot"); s.add_argument("--label", required=True); s.add_argument("--caption"); s.add_argument("--section")
    s.add_argument("--feature", action="store_true", help="放進報告圖牆"); s.add_argument("--finding"); ctx(s)
    s.add_argument("--src", help="登記一張已存在的圖"); s.add_argument("--crop", help="x,y,w,h 另存放大圖"); s.add_argument("--zoom", type=float, default=3.0)
    s.add_argument("--thumb", type=int, default=540, help="給 Agent 看的縮圖寬（0 = 不產）"); s.add_argument("--no-fg", action="store_true")
    s.set_defaults(fn=cmd_shot)

    s = sub.add_parser("tap"); s.add_argument("x", type=float); s.add_argument("y", type=float); s.add_argument("--why", required=True)
    s.add_argument("--basis", help="座標來源尺寸，如 540x960（縮圖座標）"); s.add_argument("--target"); s.add_argument("--expect")
    s.add_argument("--see", help="點之前看到的畫面（寫進決策紀錄）"); s.add_argument("--long", type=int, help="長按毫秒")
    s.add_argument("--wait", type=float, default=0.0); ctx(s); s.set_defaults(fn=cmd_tap)

    s = sub.add_parser("swipe"); [s.add_argument(n, type=float) for n in ("x1", "y1", "x2", "y2")]
    s.add_argument("--duration", type=int, default=300); s.add_argument("--basis"); s.add_argument("--why", required=True); s.add_argument("--see"); ctx(s)
    s.set_defaults(fn=cmd_swipe)

    s = sub.add_parser("key"); s.add_argument("name", help="back / home / recent / 任意 KEYCODE 名"); s.add_argument("--why", required=True)
    s.add_argument("--see"); ctx(s); s.set_defaults(fn=cmd_key)

    s = sub.add_parser("mark", help="修正最近一次點擊的結果"); s.add_argument("--outcome", choices=TAP_OUTCOMES, required=True)
    s.add_argument("--tap"); s.add_argument("--note"); s.set_defaults(fn=cmd_mark)

    s = sub.add_parser("spin", help="連續點同一顆鈕（旋轉）"); s.add_argument("x", type=float); s.add_argument("y", type=float)
    s.add_argument("--times", type=int, required=True); s.add_argument("--interval", type=float, default=3.0); s.add_argument("--basis")
    s.add_argument("--shot-every", type=int, default=10); s.add_argument("--machine"); s.add_argument("--bet"); s.add_argument("--why"); ctx(s)
    s.set_defaults(fn=cmd_spin)

    s = sub.add_parser("decide"); s.add_argument("--see", default=""); s.add_argument("--do", required=True); s.add_argument("--why", required=True); ctx(s)
    s.set_defaults(fn=cmd_decide)

    s = sub.add_parser("item", help="基本測試項判定"); s.add_argument("id"); s.add_argument("--verdict", required=True)
    s.add_argument("--note"); s.add_argument("--actual"); s.add_argument("--shots"); s.add_argument("--finding"); s.add_argument("--block-reason")
    s.set_defaults(fn=cmd_item)

    s = sub.add_parser("finding"); s.add_argument("--id"); s.add_argument("--severity"); s.add_argument("--category")
    s.add_argument("--title"); s.add_argument("--detail"); s.add_argument("--shots"); s.add_argument("--suggest")
    s.add_argument("--confirm", action="store_true", help="看不出是設計還是錯誤 → 標「需確認」")
    s.add_argument("--no-confirm", action="store_true", help="人已確認（取消「需確認」）"); s.add_argument("--repro", help="如 1/12")
    s.add_argument("--where"); s.add_argument("--status", choices=["open", "wontfix"], help="wontfix = 人確認為設計如此（報告標示、不進回歸清單）")
    ctx(s); s.set_defaults(fn=cmd_finding)

    s = sub.add_parser("explore", help="自我探索：先立假設，做完回填結果"); s.add_argument("--id"); s.add_argument("--heuristic")
    s.add_argument("--area"); s.add_argument("--hypothesis"); s.add_argument("--method"); s.add_argument("--result")
    s.add_argument("--status"); s.add_argument("--finding"); s.add_argument("--shots"); s.set_defaults(fn=cmd_explore)

    s = sub.add_parser("ledger", help="對帳：after−before 應等於 win − bet×spins（或 --expect-delta）")
    s.add_argument("--label", required=True); s.add_argument("--before", required=True); s.add_argument("--after", required=True)
    s.add_argument("--bet"); s.add_argument("--spins"); s.add_argument("--win"); s.add_argument("--expect-delta")
    s.add_argument("--tolerance", type=float, default=0); s.add_argument("--note"); s.add_argument("--shots"); ctx(s)
    s.set_defaults(fn=cmd_ledger)

    s = sub.add_parser("popup"); s.add_argument("--name", required=True); s.add_argument("--kind", required=True)
    s.add_argument("--action", required=True); s.add_argument("--price"); s.add_argument("--shots"); s.add_argument("--where")
    s.set_defaults(fn=cmd_popup)

    s = sub.add_parser("game", help="登記玩過的遊戲 / 觸發的特色玩法"); s.add_argument("--name", required=True)
    s.add_argument("--type", default="slot", help="slot / fish / keno / card / other"); s.add_argument("--rules-read", action="store_true")
    s.add_argument("--feature", help="觸發的特色（免費遊戲…）"); s.add_argument("--win"); s.add_argument("--note"); s.add_argument("--shots")
    s.set_defaults(fn=cmd_game)

    s = sub.add_parser("segment"); s.add_argument("action", choices=["start", "end"]); s.add_argument("--name"); s.add_argument("--note")
    s.set_defaults(fn=cmd_segment)

    s = sub.add_parser("logcat"); s.add_argument("--clear", action="store_true"); s.add_argument("--label"); s.set_defaults(fn=cmd_logcat)
    s = sub.add_parser("status"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("finish"); s.set_defaults(fn=cmd_finish)
    s = sub.add_parser("report"); s.add_argument("--out"); s.add_argument("--img-width", type=int, default=720)
    s.add_argument("--max-images", type=int, default=80); s.add_argument("--strict", action="store_true"); s.set_defaults(fn=cmd_report)
    s = sub.add_parser("promote"); s.add_argument("--out"); s.set_defaults(fn=cmd_promote)
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    try:
        a.fn(a)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        C.fail("QUERY_FAILED", f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    main()

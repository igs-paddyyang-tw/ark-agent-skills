#!/usr/bin/env python3
"""gdd_build — gdd-pack → 素材總覽.html（企劃樣板十段 IA）＋ todo.md（給美術的待補/待修清單）。

deterministic：同 pack 重編 bit-identical（無時間戳）；HTML 尾端戳記記錄各來源檔 sha16，
`--check` 驗戳記與現況是否一致（STALE → exit 3）。linked 模式：圖片以相對路徑指向 assets 夾，不複製、不 inline。

用法:
    python gdd_build.py --pack gdd/<slug> [--out <html>] [--style <style.yaml>]
    python gdd_build.py --pack gdd/<slug> --check
"""
from __future__ import annotations

import argparse
import html as htmlmod
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdd_common as C  # noqa: E402

STAMP_RE = re.compile(r"<!-- gdd-src: (.+?) -->")


def _q(*parts) -> str:
    return " ".join(str(x) for x in parts if x)


def prepare(p: dict) -> dict:
    """把 pack 資料整理成模板變數：url、gallery index、搜尋字串、INFO 三語 HTML。"""
    gallery: list[dict] = []
    symbols = []
    for s in p["symbols"]:
        s = dict(s)
        s.setdefault("role", "symbol"); s.setdefault("ref_files", []); s.setdefault("odds", None)
        s.setdefault("sym_id", None); s.setdefault("soft", True)
        s["_url"] = C.asset_url(p, "symbols", s["file"]) if s.get("file") else None
        s["_q"] = _q(s["code"], s["name"], s["file"], s.get("art_name"), s.get("ref"), s.get("desc"), s.get("scene"))
        s["_gi"] = len(gallery)
        gallery.append({"type": "sym", "src": s["_url"] or "", "title": f"{s['code']}｜{s['name']}", "rows": [
            ["SymID", s["sym_id"]], ["軟體命名", s["file"] if s["soft"] else "無（表演示意）"], ["美術原檔名", s.get("art_name")],
            ["賠付 5/4/3", " / ".join(map(str, s["odds"])) if s["odds"] else None], ["場景", s.get("scene")],
            ["說明", s.get("desc")], ["備註", s.get("flag")]]})
        symbols.append(s)
    screens = []
    file_gi: dict[str, int] = {}
    for s in p["screens"]:
        s = dict(s)
        s["_q"] = _q(s["title"], s.get("desc"), s.get("file") or "待補", s.get("lang"))
        if s.get("file"):
            s["_url"] = C.asset_url(p, "screens", s["file"])
            s["_gi"] = len(gallery)
            file_gi.setdefault(s["file"], s["_gi"])
            gallery.append({"type": "scr", "src": s["_url"], "title": s["title"], "rows": [
                ["語系", s.get("lang")], ["說明", s.get("desc")], ["檔名", s["file"]], ["備註", s.get("issue")]]})
        screens.append(s)

    # rules → html
    rules_html = {k: C.md_to_html(v) for k, v in p["rules"].items()}

    # INFO
    info = p["info"] or {}
    sym_idx = C.symbol_index(p)
    ph = info.get("placeholders", {}) or {}

    def with_icons(t: str) -> str:
        def rep(m):
            k = m.group(1)
            if k in ph and ph[k] in sym_idx:
                s = sym_idx[ph[k]]
                return f'<img class="inl" src="{C.asset_url(p, "symbols", s["file"])}" alt="{htmlmod.escape(k)}" title="{htmlmod.escape(k)}">'
            return f"<b>{htmlmod.escape(k)}</b>"
        return C.PLACEHOLDER_RE.sub(rep, htmlmod.escape(t, quote=False))

    def odds_grid() -> str:
        cells = []
        for code in p["gdd"].get("odds_order", []):
            s = sym_idx.get(str(code))
            if not s or not s.get("odds"):
                continue
            lines = "".join(f"<div><i>{5 - k}</i>{v}</div>" for k, v in enumerate(s["odds"]))
            cells.append(f'<div class="odds-cell"><img loading="lazy" src="{C.asset_url(p, "symbols", s["file"])}" alt="{htmlmod.escape(s["name"])}" title="{htmlmod.escape(s["name"])}"><div class="oline">{lines}</div></div>')
        return '<div class="odds-grid">' + "".join(cells) + "</div>"

    slots_at: dict[str, list] = {}
    for sl in info.get("slots", []) or []:
        slots_at.setdefault(sl["after"], []).extend(sl.get("items", []))

    def slot_html(items) -> str:
        out = []
        for it in items:
            if it.get("file"):
                gi = file_gi.get(it["file"])
                if gi is None:
                    gi = len(gallery)
                    gallery.append({"type": "scr", "src": C.asset_url(p, "screens", it["file"]), "title": it.get("label", ""), "rows": [["檔名", it["file"]]]})
                    file_gi[it["file"]] = gi
                out.append(f'<figure class="slot" data-gi="{gi}"><img loading="lazy" src="{C.asset_url(p, "screens", it["file"])}" alt="{htmlmod.escape(it.get("label", ""))}"><figcaption>{htmlmod.escape(it.get("label", ""))}</figcaption></figure>')
            else:
                out.append(f'<figure class="slot empty"><div class="ph">待補</div><figcaption>{htmlmod.escape(it.get("label", ""))}</figcaption></figure>')
        return '<div class="slots">' + "".join(out) + "</div>"

    info_html: dict[str, str] = {}
    for l in info.get("langs", []):
        lid = l["id"]
        parts = []
        for b in info.get("blocks", []):
            t = b.get(lid) or b.get("en") or ""
            if b.get("t") == "h":
                parts.append(f"<h4>{with_icons(t)}</h4>" + (odds_grid() if b.get("widget") == "odds_grid" else ""))
            elif b.get("t") == "s":
                parts.append(f"<h5>{with_icons(t)}</h5>")
            else:
                parts.append(f"<p>{with_icons(t)}</p>")
            if b.get("id") in slots_at:
                parts.append(slot_html(slots_at[b["id"]]))
        info_html[lid] = "\n".join(parts)

    return {"symbols": symbols, "screens": screens, "rules_html": rules_html, "info_html": info_html,
            "gallery_json": json.dumps(gallery, ensure_ascii=False, separators=(",", ":")),
            "ref_url": lambda f: C.asset_url(p, "reference", f)}


def source_stamp(p: dict) -> str:
    d = p["dir"]
    parts = []
    for name in ["gdd.yaml", "symbols.yaml", "screens.yaml", "info.yaml", "i18n.csv"]:
        if (d / name).exists():
            parts.append(f"{name}:{C.sha256_file(d / name)[:16]}")
    for f in p["gdd"].get("features", []):
        rp = f.get("rules")
        if rp and (d / rp).exists():
            parts.append(f"{rp}:{C.sha256_file(d / rp)[:16]}")
    return "<!-- gdd-src: " + " ".join(parts) + " -->"


def todo_md(p: dict, lint_report: dict | None) -> str:
    L = [f"# {p['gdd'].get('short_title') or p['gdd'].get('title')} — 待補 / 待修清單", "",
         "> 由 gdd_build 從 screens.yaml / info.yaml / lint-report.json 產生；給美術與企劃對表用。", ""]
    todo = [s for s in p["screens"] if s.get("file") is None]
    L += ["## 缺示意圖", "", "| 玩法 | 項目 | 來源 | 說明 |", "|------|------|------|------|"]
    feat_title = {f["id"]: f["title"] for f in p["gdd"].get("features", [])}
    for s in todo:
        L.append(f"| {feat_title.get(s['feature'], s['feature'])} | {s['title']} | {s.get('from', '')} | {s.get('desc', '')} |")
    L.append("")
    issues = [s for s in p["screens"] if s.get("issue")]
    L += ["## 待美術修正", "", "| 玩法 | 項目 | 問題 | 檔名 |", "|------|------|------|------|"]
    for s in issues:
        L.append(f"| {feat_title.get(s['feature'], s['feature'])} | {s['title']} | {s['issue']} | {s.get('file', '')} |")
    L.append("")
    if lint_report:
        hy = [w for w in lint_report.get("warnings", []) if w["rule"].startswith("GDD-SCR-HYGIENE")]
        L += ["## 檔名衛生", ""] + [f"- {w['msg']}" for w in hy] + ([""] if hy else ["（無）", ""])
        it = [w for w in lint_report.get("warnings", []) if w["rule"] == "GDD-INFO-TODO"]
        L += ["## INFO 頁插圖待補", ""] + [f"- {w['msg']}" for w in it] + ([""] if it else ["（無）", ""])
    oq = p["gdd"].get("open_questions") or []
    if oq:
        L += ["## 規格待決問題（spec UNKNOWN）", ""] + [f"- {q.get('q')} `{q.get('key')}`（{q.get('section')}）" for q in oq] + [""]
    L += ["## 統計", "", f"- 示意圖 {len(p['screens'])} 項，待補 {len(todo)}，待修 {len(issues)}",
          f"- 圖騰 {len(p['symbols'])} 筆", ""]
    return "\n".join(L)


def build(pack: pathlib.Path, out: pathlib.Path | None, style_path: pathlib.Path | None,
          assets: dict | None = None, write_todo: bool = True) -> dict:
    """assets：覆寫資產位置（gdd_export 用：root=輸出夾、root_rel='.'、三夾英文名），讓 HTML 以樣板相對路徑引用。"""
    try:
        import jinja2  # type: ignore
        import yaml  # type: ignore
    except ImportError:
        C.fail("MISSING_DEP", "需要 jinja2 與 pyyaml", "pip install jinja2 pyyaml")
    p = C.load_pack(pack)
    if assets:
        p["assets"] = {**p["assets"], **assets}
    style_path = style_path or C.SKILL_DIR / "assets" / "gdd-default-style.yaml"
    style = yaml.safe_load(style_path.read_text(encoding="utf-8"))
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(C.SKILL_DIR / "assets")), autoescape=True,
                             trim_blocks=False, lstrip_blocks=False, keep_trailing_newline=True)
    tpl = env.get_template("gdd-template.html.j2")
    ctx = prepare(p)
    html = tpl.render(g=p["gdd"], info=p["info"], i18n_rows=p["i18n_rows"], style=style, stamp=source_stamp(p), **ctx)
    out = out or (pack / (p["gdd"].get("build", {}) or {}).get("output", "素材總覽.html"))
    C.atomic_write(out, html)
    todo_p = pack / "todo.md"
    if write_todo:
        lint_p = pack / "lint-report.json"
        lint = json.loads(lint_p.read_text(encoding="utf-8")) if lint_p.exists() else None
        C.atomic_write(todo_p, todo_md(p, lint))
    return {"html": str(out), "todo": str(todo_p) if write_todo else None, "bytes": out.stat().st_size, "gallery": ctx["gallery_json"].count('"type"'),
            "sections": 3 + len(p["gdd"].get("features", [])) + 3, "stamp": source_stamp(p)[14:-4]}


def check(pack: pathlib.Path) -> tuple[str, str]:
    p = C.load_pack(pack)
    out = pack / (p["gdd"].get("build", {}) or {}).get("output", "素材總覽.html")
    if not out.exists():
        return "NO-HTML", str(out)
    m = STAMP_RE.search(out.read_text(encoding="utf-8"))
    if not m:
        return "NO-STAMP", str(out)
    return ("OK" if m.group(0) == source_stamp(p) else "STALE"), str(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    ap.add_argument("--out")
    ap.add_argument("--style")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    pack = C.pack_dir(a.pack)
    if a.check:
        st, path = check(pack)
        if st != "OK":
            C.fail("GATE_BLOCKED", f"{st}：{path}", "重跑 gdd_build", {"status": st})
        C.emit({"status": st, "html": path}, {"stage": "gdd_check"})
        return
    r = build(pack, pathlib.Path(a.out) if a.out else None, pathlib.Path(a.style) if a.style else None)
    C.emit(r, {"stage": "gdd_build"})


if __name__ == "__main__":
    main()

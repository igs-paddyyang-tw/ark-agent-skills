"""gdd_common — ark-game-gdd 共用：契約常數、pack 載入、envelope、mini-markdown。

gdd-pack = 企劃習慣的「素材總覽」樣板的資料層（見 references/gdd-contract.md）。
本模組不呼叫 LLM；所有守門與渲染都是 deterministic。
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import pathlib
import re
import sys

CONTRACT = "1"
SKILL_VERSION = "1.0.0"
EXIT = {"BAD_INPUT": 2, "GATE_BLOCKED": 3, "QUERY_FAILED": 6, "MISSING_DEP": 8}
HERE = pathlib.Path(__file__).resolve().parent
SKILL_DIR = HERE.parent.parent  # scripts/gdd → ark-game-spec 根

SYMBOL_GROUPS_DEFAULT = ["normal", "special", "fg", "jp"]
SYMBOL_ROLES = ("symbol", "performance")
SCREEN_REQUIRED = ("feature", "step", "title", "desc")
INFO_BLOCK_TYPES = ("h", "s", "p")
PLACEHOLDER_RE = re.compile(r"\{([^{}]+)\}")
BAD_EXT_RE = re.compile(r"\.(png|jpg|jpeg|webp)\.(png|jpg|jpeg|webp)$", re.I)
GENERIC_NAME_RE = re.compile(r"^(Snipaste_|圖層 ?\d|screenshot|未命名|image\d*)", re.I)
INVISIBLE_RE = re.compile("[​‌‍⁠﻿­]")
INJECT_RE = re.compile(r"<\s*(script|iframe|object|embed)\b|javascript:|on\w+\s*=", re.I)


def _utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass


def emit(data, meta=None) -> None:
    _utf8()
    print(json.dumps({"success": True, "contract": CONTRACT, "data": data,
                      "meta": {"skill_version": SKILL_VERSION, **(meta or {})}}, ensure_ascii=False))


def fail(code: str, message: str, hint: str = "", data=None) -> None:
    _utf8()
    print(json.dumps({"success": False, "contract": CONTRACT, "error": {"code": code, "message": message, "hint": hint},
                      "data": data}, ensure_ascii=False))
    sys.exit(EXIT.get(code, 1))


def yaml_load(p: pathlib.Path):
    try:
        import yaml  # type: ignore
    except ImportError:
        fail("MISSING_DEP", "需要 pyyaml", "pip install pyyaml")
    if not p.exists():
        fail("BAD_INPUT", f"缺 {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha16_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]


def atomic_write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


# ── pack 載入 ─────────────────────────────────────────────────────────────

def pack_dir(path: str) -> pathlib.Path:
    p = pathlib.Path(path).resolve()
    if p.is_file() and p.name == "gdd.yaml":
        p = p.parent
    if not (p / "gdd.yaml").exists():
        fail("BAD_INPUT", f"{p} 不是 gdd-pack（缺 gdd.yaml）")
    return p


def load_pack(pack: pathlib.Path) -> dict:
    """載入整包（不驗證；驗證在 gdd_lint）。回傳 dict 含 gdd/symbols/screens/info/i18n/rules/assets 路徑。"""
    gdd = yaml_load(pack / "gdd.yaml")
    symbols = yaml_load(pack / "symbols.yaml").get("symbols", []) if (pack / "symbols.yaml").exists() else []
    screens = yaml_load(pack / "screens.yaml").get("screens", []) if (pack / "screens.yaml").exists() else []
    info = yaml_load(pack / "info.yaml") if (pack / "info.yaml").exists() else {}
    i18n_rows: list[list[str]] = []
    i18n_header: list[str] = []
    if (pack / "i18n.csv").exists():
        with (pack / "i18n.csv").open(encoding="utf-8", newline="") as f:
            r = list(csv.reader(f))
        if r:
            i18n_header, i18n_rows = r[0], r[1:]
    rules: dict[str, str] = {}
    for feat in gdd.get("features", []):
        rp = feat.get("rules")
        if rp and (pack / rp).exists():
            rules[feat["id"]] = (pack / rp).read_text(encoding="utf-8")
    a = gdd.get("assets", {}) or {}
    root = (pack / (a.get("root") or ".")).resolve()
    assets = {
        "root": root,
        "root_rel": (a.get("root") or ".").replace("\\", "/").rstrip("/"),
        "symbols": a.get("symbols", "圖騰"), "screens": a.get("screens", "全示意圖"), "reference": a.get("reference", "規格書競品圖"),
    }
    return {"dir": pack, "gdd": gdd, "symbols": symbols, "screens": screens, "info": info,
            "i18n_header": i18n_header, "i18n_rows": i18n_rows, "rules": rules, "assets": assets}


def asset_path(p: dict, kind: str, name: str) -> pathlib.Path:
    return p["assets"]["root"] / p["assets"][kind] / name


def asset_url(p: dict, kind: str, name: str) -> str:
    """HTML 內的相對路徑（linked 模式）；相對於輸出 HTML 所在的 pack 目錄。"""
    from urllib.parse import quote
    base = p["assets"]["root_rel"]
    prefix = "" if base in (".", "") else base + "/"
    return f"{prefix}{p['assets'][kind]}/{quote(name)}"


def symbol_index(p: dict) -> dict[str, dict]:
    """code → 第一個 role=symbol 的紀錄（佔位符解析用）。"""
    idx: dict[str, dict] = {}
    for s in p["symbols"]:
        if s.get("role", "symbol") == "symbol":
            idx.setdefault(str(s["code"]), s)
    return idx


# ── mini markdown（rules/*.md 用；只支援 ###、- 清單、表格、> note、**粗體**、`code`）───

def _inline(t: str) -> str:
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


def md_to_html(md: str) -> str:
    out: list[str] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("<!--") and ln.rstrip().endswith("-->"):
            out.append(ln.strip())  # 錨點註解原樣（spec:<section> sha16）
        elif ln.startswith("### "):
            out.append(f"<h3>{_inline(ln[4:].strip())}</h3>")
        elif ln.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{_inline(lines[i][2:].strip())}</li>")
                i += 1
            out.append("<ul class=\"rules\">" + "".join(items) + "</ul>")
            continue
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            if len(rows) >= 2:
                head, body = rows[0], [r for r in rows[2:]]
                out.append("<div class=\"tbl-wrap\"><table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) +
                           "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body) +
                           "</tbody></table></div>")
            continue
        elif ln.startswith("> "):
            out.append(f"<p class=\"note\">{_inline(ln[2:].strip())}</p>")
        elif ln.strip():
            out.append(f"<p>{_inline(ln.strip())}</p>")
        i += 1
    return "\n".join(out)


def md_tables(md: str) -> list[list[list[str]]]:
    """回傳所有表格的 rows（lint 用）。"""
    tables, cur = [], []
    for ln in md.splitlines() + [""]:
        if ln.startswith("|"):
            cur.append([c.strip() for c in ln.strip().strip("|").split("|")])
        elif cur:
            tables.append(cur)
            cur = []
    return tables

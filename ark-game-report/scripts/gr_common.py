"""gr_common — ark-game-report 共用：JSON envelope、設定載入、CSV 讀取、小工具。不呼叫 LLM。"""
from __future__ import annotations

import csv
import datetime as dt
import json
import pathlib
import re
import sys

CONTRACT = "1"
EXIT = {"BAD_INPUT": 2, "GATE_BLOCKED": 3, "QUERY_FAILED": 6, "MISSING_DEP": 8}
HERE = pathlib.Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
ASSETS = SKILL_DIR / "assets"
SKILLS_ROOT = SKILL_DIR.parent
DB_QUERY = SKILLS_ROOT / "ark-db-query" / "scripts"
WIKI = SKILLS_ROOT / "ark-wiki-engine" / "scripts"

# 標準資料集（gr_query 產出、gr_build 讀取）；欄位名是契約，見 references/data-contract.md
DATASETS = {
    "game_user_daily": {"required": ["d", "uid", "bet", "spins"], "optional_prefix": ["win", "trig_"], "must": True},
    "slot_daily": {"required": ["d", "view", "slot_bet", "slot_players"], "optional_prefix": ["game_rank"], "must": True},
    "slot_users": {"required": ["uid"], "optional_prefix": [], "must": False},
    "erosion": {"required": ["game", "pre_bet", "post_bet"], "optional_prefix": [], "must": False},
    "hours": {"required": ["bucket", "bet"], "optional_prefix": [], "must": False},
    "benchmark": {"required": ["metric", "day", "p30", "p50", "p60"], "optional_prefix": [], "must": False},
}


def _skill_version() -> str:
    m = re.search(r"^\s+version:\s*\"([^\"]+)\"", (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "0"


SKILL_VERSION = _skill_version()


def _utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass


def emit(data, meta=None) -> None:
    _utf8()
    print(json.dumps({"success": True, "contract": CONTRACT, "data": data,
                      "meta": {"skill_version": SKILL_VERSION, **(meta or {})}}, ensure_ascii=False, default=str))


def fail(code: str, message: str, hint: str = "", data=None) -> None:
    _utf8()
    print(json.dumps({"success": False, "contract": CONTRACT, "error": {"code": code, "message": message, "hint": hint},
                      "data": data}, ensure_ascii=False, default=str))
    sys.exit(EXIT.get(code, 1))


def yaml_load(p: pathlib.Path):
    try:
        import yaml
    except ImportError:
        fail("MISSING_DEP", "需要 pyyaml", "pip install pyyaml")
    return yaml.safe_load(pathlib.Path(p).read_text(encoding="utf-8"))


def yaml_dump(obj) -> str:
    import yaml
    return yaml.safe_dump(obj, allow_unicode=True, sort_keys=False)


def load_config(path) -> dict:
    p = pathlib.Path(path)
    if not p.is_file():
        fail("BAD_INPUT", f"找不到設定檔 {p}", "先跑 gr_run.py init")
    cfg = yaml_load(p) or {}
    cfg["_path"] = str(p)
    for k in ("game", "stage"):
        if k not in cfg:
            fail("BAD_INPUT", f"report.yaml 缺 {k}")
    g = cfg["game"]
    for k in ("name", "launch_date"):
        if k not in g:
            fail("BAD_INPUT", f"report.yaml game.{k} 缺少")
    cfg.setdefault("views", [{"name": "全體"}])
    cfg.setdefault("composition", [])
    cfg.setdefault("depth", {})
    cfg.setdefault("health", {})
    cfg.setdefault("spec", {})
    cfg.setdefault("units", {"bet_scale": 1, "bet_unit": ""})
    return cfg


def adapter_path(cfg: dict):
    """adapter 可寫名稱（assets/adapters/<名稱>.yaml）或直接給 yaml 路徑；csv 模式回 None。"""
    a = cfg.get("adapter", "csv")
    if not a or a == "csv":
        return None
    p = pathlib.Path(a)
    return p if p.suffix in (".yaml", ".yml") else ASSETS / "adapters" / f"{a}.yaml"


def data_dir(cfg: dict) -> pathlib.Path:
    return pathlib.Path(cfg.get("data_dir") or (pathlib.Path(cfg["_path"]).parent / "data"))


def read_csv(path: pathlib.Path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def header(path: pathlib.Path) -> list:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return next(csv.reader(f), [])


def num(v, default=0.0) -> float:
    try:
        return float(v) if v not in (None, "") else default
    except ValueError:
        return default


def to_date(s) -> dt.date:
    return dt.date.fromisoformat(str(s)[:10])


def stage_days(cfg: dict) -> list:
    st = int(cfg["stage"])
    return list(range(1, 8)) if st <= 7 else ([1, 2, 3, 5, 7, 10, 14] if st <= 14 else [1, 2, 3, 5, 7, 10, 14, 21, 30])


def bucket_of(value, dim: dict):
    """依 composition 維度設定把原始值分組；回傳組名或 None。"""
    if value in (None, ""):
        return None
    if "buckets" in dim:
        x = num(value, None)
        if x is None:
            return None
        for name, (lo, hi) in dim["buckets"].items():
            if lo <= x <= hi:
                return name
        return None
    cats = dim.get("categories") or []
    return value if value in cats else (dim.get("other") if dim.get("other") else None)


def groups_of(dim: dict) -> list:
    if "buckets" in dim:
        return list(dim["buckets"].keys())
    return list(dim.get("categories") or []) + ([dim["other"]] if dim.get("other") else [])


def in_view(row: dict, view: dict) -> bool:
    col = view.get("column")
    if not col:
        return True
    v = row.get(col)
    if "values" in view:
        return v in [str(x) for x in view["values"]]
    if "not_values" in view:
        return v not in [str(x) for x in view["not_values"]]
    return True


def fmt_money(v: float, cfg: dict) -> str:
    u = cfg.get("units") or {}
    scale, unit = float(u.get("bet_scale", 1) or 1), u.get("bet_unit", "")
    x = v / scale
    return (f"{x:,.2f}" if x < 1000 else f"{x:,.0f}") + unit


def pct(v, d=1) -> str:
    return "—" if v is None else f"{v * 100:.{d}f}%"

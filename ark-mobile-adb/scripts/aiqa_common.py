"""aiqa 共用：envelope / exit code、yaml、gamepack 載入與合併、安全表達式求值、run 目錄。

所有 aiqa_* 腳本 stdout 為單一 JSON envelope（與 ark-mobile-adb --json 相同契約）。
"""
from __future__ import annotations

import ast
import datetime as _dt
import hashlib
import json
import os
import pathlib
import re
import sys
import time

CONTRACT = "1"
SKILL_VERSION = "2.0.0"
PROTOCOL_VERSION = "aiqa-protocol/1"
EXIT = {"BAD_INPUT": 2, "GATE_BLOCKED": 3, "CONN_FAILED": 5, "QUERY_FAILED": 6, "TIMEOUT": 7, "DRIVER_MISSING": 8, "BUDGET_EXCEEDED": 9}
HERE = pathlib.Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
GAMEPACKS_DIR = pathlib.Path(os.getenv("ARK_AIQA_GAMEPACKS", str(SKILL_ROOT / "gamepacks")))
VERDICTS = ("PASS", "FAIL", "FLAKY", "NEEDS_HUMAN", "BLOCK", "NA")
TIERS = ("T1", "T2", "T3", "T4", "T5", "NA")
ORACLES = ("ocr_number", "text", "state", "sequence", "timing", "no_crash", "visual", "expr")


def _utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass


def emit(data, meta=None) -> None:
    _utf8()
    print(json.dumps({"success": True, "contract": CONTRACT, "data": data, "meta": {"skill_version": SKILL_VERSION, **(meta or {})}},
                     ensure_ascii=False, default=str))
    sys.exit(0)


def fail(code: str, message: str, hint: str = "", data=None) -> None:
    _utf8()
    body = {"success": False, "contract": CONTRACT, "error": {"code": code, "message": message, "hint": hint}}
    if data is not None:
        body["data"] = data
    print(json.dumps(body, ensure_ascii=False, default=str))
    sys.exit(EXIT.get(code, 1))


class Timer:
    def __enter__(self):
        self.t0 = time.perf_counter(); return self

    def __exit__(self, *a):
        self.elapsed_ms = round((time.perf_counter() - self.t0) * 1000, 1)


def now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def yaml_load(p: pathlib.Path):
    try:
        import yaml
    except ImportError:
        fail("DRIVER_MISSING", "缺 pyyaml", "pip install pyyaml")
    return yaml.safe_load(pathlib.Path(p).read_text(encoding="utf-8")) or {}


def yaml_dump(obj) -> str:
    import yaml
    return yaml.safe_dump(obj, allow_unicode=True, sort_keys=False, width=120)


def atomic_write(path: pathlib.Path, text: str) -> None:
    path = pathlib.Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8"); os.replace(tmp, path)


def sha_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def sha_file(p: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def deep_merge(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            out[k] = deep_merge(a.get(k), v) if k in a else v
        return out
    return b if b is not None else a


# ---------------------------------------------------------------- gamepack
class PackError(Exception):
    pass


def list_games(root: pathlib.Path | None = None) -> list[str]:
    root = root or GAMEPACKS_DIR
    return sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("_") and (p / "game.yaml").exists()) if root.exists() else []


def load_pack(game: str, machine: str | None = None, root: pathlib.Path | None = None) -> dict:
    """game.yaml（+ machines/<m>/machine.yaml deep-merge）→ resolved pack；模板路徑轉為絕對路徑字串。"""
    root = root or GAMEPACKS_DIR
    gdir = root / game
    if not (gdir / "game.yaml").exists():
        raise PackError(f"gamepack 不存在: {gdir}")
    pack = yaml_load(gdir / "game.yaml")
    pack["_dir"] = str(gdir)
    pack["_files"] = {"game": str(gdir / "game.yaml")}
    if machine:
        mdir = gdir / "machines" / machine
        if not (mdir / "machine.yaml").exists():
            raise PackError(f"machine 不存在: {mdir}")
        m = yaml_load(mdir / "machine.yaml")
        m_abs = _abs_templates(m, mdir)
        pack = deep_merge(pack, m_abs)
        pack["machine"] = machine
        pack["_files"]["machine"] = str(mdir / "machine.yaml")
    pack = _abs_templates(pack, gdir)
    pack["game"] = game
    bpath = gdir / "bindings.yaml"
    pack["bindings"] = yaml_load(bpath).get("bindings", []) if bpath.exists() else []
    if machine and (gdir / "machines" / machine / "bindings.yaml").exists():
        pack["bindings"] = yaml_load(gdir / "machines" / machine / "bindings.yaml").get("bindings", []) + pack["bindings"]
    pack["_sha256"] = sha_text(json.dumps({k: v for k, v in pack.items() if not k.startswith("_")}, sort_keys=True, default=str))
    return pack


def _abs_templates(obj, base: pathlib.Path):
    """把 screens/buttons 的 template 相對路徑轉絕對（只處理尚未是絕對路徑的）。"""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "template" and isinstance(v, str) and not os.path.isabs(v):
                out[k] = str((base / v).resolve())
            else:
                out[k] = _abs_templates(v, base)
        return out
    if isinstance(obj, list):
        return [_abs_templates(x, base) for x in obj]
    return obj


def pack_target(pack: dict, ref: str) -> dict:
    """'btn:spin' / 'roi:win' / 'screen:main_game' / 'state:reels_settled' → 定義 dict；找不到 → PackError。"""
    kind, _, name = ref.partition(":")
    table = {"btn": "buttons", "roi": "rois", "screen": "screens", "state": "states"}.get(kind)
    if not table or name not in (pack.get(table) or {}):
        raise PackError(f"pack 未定義 {ref}")
    v = pack[table][name]
    return {"rect": v} if kind == "roi" and isinstance(v, list) else dict(v)


# ---------------------------------------------------------------- 安全表達式
_ALLOWED_NODES = (ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare, ast.Call, ast.Name, ast.Load, ast.Constant,
                  ast.List, ast.Tuple, ast.Subscript, ast.Slice, ast.And, ast.Or, ast.Not, ast.Add, ast.Sub, ast.Mult, ast.Div,
                  ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In,
                  ast.NotIn, ast.IfExp, ast.ListComp, ast.GeneratorExp, ast.comprehension, ast.Store, ast.Is, ast.IsNot)


def _pairs(xs):
    return list(zip(xs, xs[1:]))


def _seq_multiplier(mults, wins):
    """乘倍規則（每手停輪後同時讀 win 與 mult）：mult[i] == mult[i-1]+1 若 win[i]>0，否則 1。"""
    for i in range(1, min(len(mults), len(wins))):
        exp = mults[i - 1] + 1 if (wins[i] or 0) > 0 else 1
        if mults[i] != exp:
            return False
    return True


def _approx(a, b, tol=0.5):
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def _nonempty(xs):
    return xs is not None and xs != [] and xs != ""


SAFE_FUNCS = {"sum": sum, "len": len, "all": all, "any": any, "abs": abs, "min": min, "max": max, "round": round,
              "pairs": _pairs, "seq_multiplier": _seq_multiplier, "approx": _approx, "nonempty": _nonempty,
              "float": float, "int": int, "str": str, "sorted": sorted}


def safe_eval(expr: str, names: dict):
    tree = ast.parse(expr, mode="eval")
    bound = {t.id for n in ast.walk(tree) if isinstance(n, ast.comprehension) for t in ast.walk(n.target) if isinstance(t, ast.Name)}
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"表達式含不允許的節點 {type(node).__name__}")
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id in SAFE_FUNCS):
            raise ValueError("只允許白名單函數")
        if isinstance(node, ast.Name) and node.id not in names and node.id not in SAFE_FUNCS and node.id not in bound and node.id not in ("True", "False", "None"):
            raise KeyError(node.id)
    return eval(compile(tree, "<expr>", "eval"), {"__builtins__": {}}, {**SAFE_FUNCS, **names})


# ---------------------------------------------------------------- run 目錄
def new_run_dir(root: pathlib.Path, game: str, machine: str | None) -> pathlib.Path:
    day = _dt.date.today().strftime("%Y%m%d")
    base = f"{day}-{game}" + (f"-{machine}" if machine else "")
    root.mkdir(parents=True, exist_ok=True)
    seq = 1 + len([p for p in root.iterdir() if p.is_dir() and p.name.startswith(base)])
    run = root / f"{base}-{seq:02d}"
    (run / "items").mkdir(parents=True)
    return run


def item_id_regex() -> re.Pattern:
    return re.compile(r"^[A-Z0-9]+(-[A-Z0-9]+)*-\d{3,}$")

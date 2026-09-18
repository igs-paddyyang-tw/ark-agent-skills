"""ark-game-analysis 共用：JSON envelope、run 目錄與 manifest、resolved pack 載入、ffmpeg 包裝。

Run 目錄契約（所有引擎共用）：
  artifacts/cva/<run_id>/manifest.json  video/  transcript/  frames/{motion_timeline.json,events.json,keyframes/,sheets/}
  evidence.jsonl（本 skill 產出後唯讀）  pack/resolved.json（pack 快照）
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

CONTRACT = "1"
SKILL_VERSION = "1.0.0"
EXIT = {"BAD_INPUT": 2, "GATE_BLOCKED": 3, "BUDGET_EXCEEDED": 9, "CONN_FAILED": 5,
        "QUERY_FAILED": 6, "TIMEOUT": 7, "DRIVER_MISSING": 8}
HERE = pathlib.Path(__file__).resolve().parent


def _utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass


def emit(data, meta=None) -> None:
    _utf8()
    print(json.dumps({"success": True, "contract": CONTRACT, "data": data,
                      "meta": {"skill_version": SKILL_VERSION, **(meta or {})}}, ensure_ascii=False, default=str))
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
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *a):
        self.elapsed_ms = round((time.perf_counter() - self.t0) * 1000, 1)


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fmt_ts(sec: float) -> str:
    ms = int(round((sec - int(sec)) * 1000))
    s = int(sec)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}.{ms:03d}"


def ts_slug(sec: float) -> str:
    return fmt_ts(sec).replace(":", "-")


# ---------------------------------------------------------------- run / manifest
def run_dir(path: str) -> pathlib.Path:
    p = pathlib.Path(path)
    if not (p / "manifest.json").exists():
        fail("BAD_INPUT", f"不是 run 目錄（缺 manifest.json）: {p}", "先跑 vu_fetch.py 建立 run")
    return p


def load_manifest(run: pathlib.Path) -> dict:
    return json.loads((run / "manifest.json").read_text(encoding="utf-8"))


def save_manifest(run: pathlib.Path, m: dict) -> None:
    m["updated_at"] = _dt.datetime.now().isoformat(timespec="seconds")
    tmp = run / ".manifest.tmp"
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, run / "manifest.json")


def stage_record(run: pathlib.Path, stage: str, elapsed_ms: float, **extra) -> None:
    m = load_manifest(run)
    m.setdefault("stages", {})[stage] = {"elapsed_ms": elapsed_ms, "at": _dt.datetime.now().isoformat(timespec="seconds"), **extra}
    save_manifest(run, m)


def atomic_write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------- pack
def _domains_skill_dir() -> pathlib.Path | None:
    cands = [os.getenv("ARK_GAME_DOMAINS_SKILL"), str(HERE.parent.parent / "ark-game-domains"),
             str(pathlib.Path.cwd() / "ark-game-domains")]
    for c in cands:
        if c and (pathlib.Path(c) / "scripts" / "pack_common.py").exists():
            return pathlib.Path(c)
    return None


def pack_common():
    d = _domains_skill_dir()
    if d is None:
        fail("DRIVER_MISSING", "找不到 ark-game-domains skill",
             "設 ARK_GAME_DOMAINS_SKILL=/path/to/ark-game-domains，或把兩個 skill 放同一個 skills 目錄")
    sys.path.insert(0, str(d / "scripts"))
    import pack_common as P  # noqa: E402
    return P


def list_domains() -> list[str]:
    return pack_common().list_packs()


def resolve_pack(domain: str) -> dict:
    P = pack_common()
    try:
        return P.resolve(domain)
    except P.PackError as e:
        fail("BAD_INPUT", f"pack 解析失敗: {e}", "python ark-game-domains/scripts/pack_lint.py --domain " + domain)


def load_resolved(run: pathlib.Path) -> dict:
    p = run / "pack" / "resolved.json"
    if not p.exists():
        fail("BAD_INPUT", "run 尚未綁定 domain（缺 pack/resolved.json）",
             "vu_run.py --domain <d> 或先跑 ga_detect.py 再 vu_bind_domain")
    return json.loads(p.read_text(encoding="utf-8"))


def snapshot_pack(run: pathlib.Path, domain: str) -> dict:
    r = resolve_pack(domain)
    atomic_write(run / "pack" / "resolved.json", json.dumps(r, ensure_ascii=False, indent=1, default=str))
    m = load_manifest(run)
    m.update(domain=domain, pack_version=r["version"], pack_sha256=r["pack_sha256"])
    save_manifest(run, m)
    return r


# ---------------------------------------------------------------- evidence
def load_evidence(run: pathlib.Path) -> list[dict]:
    p = run / "evidence.jsonl"
    if not p.exists():
        fail("BAD_INPUT", "缺 evidence.jsonl", "先跑 ark-video-understanding/scripts/vu_run.py")
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_observations(run: pathlib.Path) -> dict:
    p = run / "observations.jsonl"
    if not p.exists():
        return {}
    out = {}
    for l in p.read_text(encoding="utf-8").splitlines():
        if l.strip():
            o = json.loads(l)
            out[o["evidence_id"]] = o
    return out


def evidence_view(run: pathlib.Path) -> list[dict]:
    """evidence（唯讀、deterministic）⋈ observations（llm）。"""
    obs = load_observations(run)
    out = []
    for e in load_evidence(run):
        o = obs.get(e["evidence_id"], {})
        out.append({**e, "observation": o.get("observation", e.get("observation", [])),
                    "numbers": o.get("numbers", []), "ui_elements": o.get("ui_elements", []),
                    "confidence": o.get("confidence", e.get("confidence"))})
    return out


def yaml_dump(obj) -> str:
    try:
        import yaml
    except ImportError:
        fail("DRIVER_MISSING", "缺 pyyaml", "pip install pyyaml --break-system-packages")
    return yaml.safe_dump(obj, allow_unicode=True, sort_keys=False, width=120)


def yaml_load(p: pathlib.Path):
    try:
        import yaml
    except ImportError:
        fail("DRIVER_MISSING", "缺 pyyaml", "pip install pyyaml --break-system-packages")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


PROVENANCE = ("OBSERVED", "INFERRED", "FROM_KB", "PROPOSED", "UNKNOWN", "NOT_OBSERVED", "DECIDED")
CONFIDENCE = ("high", "medium", "low", "unknown")

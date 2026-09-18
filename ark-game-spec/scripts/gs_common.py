"""ark-game-spec 共用：JSON envelope、run 目錄與 manifest、resolved pack 載入、ffmpeg 包裝。

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


# ---------------------------------------------------------------- spec markdown 契約
import re as _re  # noqa: E402

_FM_RE = _re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", _re.S)


def split_frontmatter(text: str):
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    try:
        import yaml
        return (yaml.safe_load(m.group(1)) or {}), m.group(2)
    except Exception:  # noqa: BLE001
        return {}, m.group(2)


TAGS = ("OBSERVED", "INFERRED", "FROM_KB", "PROPOSED", "UNKNOWN", "DECIDED")
SEC_RE = _re.compile(r"^## (\d\d)\. (.+?)\s*$")
MARK_RE = _re.compile(r"^<!-- section:(\S+)(?: items:(\S*))?(?: special:(\S+))? -->$")
TAG_RE = _re.compile(r"^### (OBSERVED|INFERRED|FROM_KB|PROPOSED|UNKNOWN|DECIDED)\s*$")
BULLET_RE = _re.compile(r"^- (.+)$")
FIELD_RE = _re.compile(r"\s+—\s+(evidence|reasoning|confidence|question|kb|tags|trust|rationale|basis|decision|entity|competitor|value):\s*")
TICK_RE = _re.compile(r"`([^`]+)`")
E_RE = _re.compile(r"^E\d{3,}$")
Q_RE = _re.compile(r"^Q\d{3,}$")
D_RE = _re.compile(r"^D\d{3,}$")
KB_RE = _re.compile(r"^GKB-[A-Z0-9]+-[A-Z0-9]+-\d{3,}$")


def parse_bullet(text: str) -> dict:
    """`- \\`key\\` = value — evidence: E001, E002 — confidence: high` → dict。"""
    parts = FIELD_RE.split(text)
    head, fields = parts[0], {}
    for i in range(1, len(parts) - 1, 2):
        fields[parts[i]] = parts[i + 1].strip()
    m = _re.match(r"^(?:entity\s+)?`([^`]+)`(?:\s*=\s*(.*))?$", head.strip())
    key = m.group(1) if m else None
    value = m.group(2).strip() if m and m.group(2) is not None else None
    lst = lambda s: [x.strip() for x in s.split(",") if x.strip()] if s else []  # noqa: E731
    return {"key": key, "value": value, "is_entity": head.strip().startswith("entity "),
            "evidence": lst(fields.get("evidence")), "basis": lst(fields.get("basis")), "kb": lst(fields.get("kb")),
            "question": fields.get("question"), "decision": fields.get("decision"),
            "confidence": fields.get("confidence"), "reasoning": fields.get("reasoning"), "rationale": fields.get("rationale"),
            "raw": text, "ticks": TICK_RE.findall(text)}


def parse_spec(md: str) -> dict:
    """→ {frontmatter, sections:[{number,title,id,items,special,blocks:{TAG:[bullet]},lines:[(lineno,text)],fence_lines}]}"""
    fm, body = split_frontmatter(md)
    sections, cur, tag, in_fence = [], None, None, False
    for ln, line in enumerate(body.splitlines(), 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            if cur:
                cur["fence_lines"].add(ln)
            continue
        if in_fence:
            if cur:
                cur["fence_lines"].add(ln)
            continue
        m = SEC_RE.match(line)
        if m:
            cur = {"number": m.group(1), "title": m.group(2), "id": None, "items": [], "special": None,
                   "blocks": {t: [] for t in TAGS}, "lines": [], "fence_lines": set(), "start": ln}
            sections.append(cur)
            tag = None
            continue
        if cur is None:
            continue
        mm = MARK_RE.match(line.strip())
        if mm:
            cur["id"], cur["items"], cur["special"] = mm.group(1), [x for x in (mm.group(2) or "").split(",") if x], mm.group(3)
            continue
        mt = TAG_RE.match(line)
        if mt:
            tag = mt.group(1)
            continue
        if line.startswith("### "):
            tag = None
        mb = BULLET_RE.match(line)
        if mb and tag:
            cur["blocks"][tag].append({**parse_bullet(mb.group(1)), "line": ln, "tag": tag})
            continue
        cur["lines"].append((ln, line, tag))
    return {"frontmatter": fm, "sections": sections}

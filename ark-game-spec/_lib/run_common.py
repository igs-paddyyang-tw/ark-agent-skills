"""ark-game-spec 2.0 共用（_lib/run_common）：JSON envelope、run 目錄與 manifest、pack 載入、evidence、spec markdown 契約、atlas 目錄、ffmpeg 包裝。

由 ark-video-understanding / ark-game-analysis / ark-game-spec / ark-game-atlas 四份 *_common.py 合併（atlas_common 為超集 + vu 的 ffmpeg helper）。

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
import re
import subprocess
import sys
import time

CONTRACT = "1"
SKILL_ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL_NAME = "ark-game-spec"


def skill_version() -> str:
    """從 SKILL.md frontmatter 讀 version，不再寫死（F-P1-6）。"""
    try:
        for line in (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").splitlines()[:40]:
            m = re.match(r'\s*version:\s*"?([0-9][^"\s]*)"?', line)
            if m:
                return m.group(1)
    except OSError:
        pass
    return "2.0.0"


SKILL_VERSION = skill_version()
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
    """舊介面相容：回傳 skill 根（domains/ 在其下）。舊 env ARK_GAME_DOMAINS_SKILL 仍可用，但建議改 ARK_GAME_DOMAINS_DIR。"""
    legacy = os.getenv("ARK_GAME_DOMAINS_SKILL")
    if legacy and not os.getenv("ARK_GAME_DOMAINS_DIR"):
        import warnings
        warnings.warn("ARK_GAME_DOMAINS_SKILL 已棄用，改設 ARK_GAME_DOMAINS_DIR=<dir>/domains", DeprecationWarning, stacklevel=2)
        cand = pathlib.Path(legacy) / "domains"
        if cand.exists():
            os.environ["ARK_GAME_DOMAINS_DIR"] = str(cand)
    return SKILL_ROOT


def pack_common():
    _domains_skill_dir()
    from _lib import pack_common as P  # noqa: E402
    if not P.domains_dir().exists():
        fail("DRIVER_MISSING", f"找不到 domains 目錄：{P.domains_dir()}",
             "設 ARK_GAME_DOMAINS_DIR=/path/to/ark-game-spec/domains（預設為本 skill 的 domains/）")
    return P


def list_domains() -> list[str]:
    return pack_common().list_packs()


def resolve_pack(domain: str) -> dict:
    P = pack_common()
    try:
        return P.resolve(domain)
    except P.PackError as e:
        fail("BAD_INPUT", f"pack 解析失敗: {e}", "python scripts/pack/pack_lint.py --domain " + domain)


def load_resolved(run: pathlib.Path) -> dict:
    p = run / "pack" / "resolved.json"
    if not p.exists():
        fail("BAD_INPUT", "run 尚未綁定 domain（缺 pack/resolved.json）",
             "scripts/video/vu_run.py --domain <d>，或 gs_run.py --stage detect")
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
        fail("BAD_INPUT", "缺 evidence.jsonl", "先跑 scripts/video/vu_run.py（或 gs_run.py --stage video）")
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


# ---------------------------------------------------------------- atlas 目錄
import hashlib as _hashlib  # noqa: E402

FIG_RE = _re.compile(r"^<!-- figure:(F\d{3,}) evidence:([E\d, ]+) -->$")
IMG_RE = _re.compile(r"^!\[(.*?)\]\((.+?)\)$")
ATLAS_SECTIONS = ("一句話", "畫面", "規則", "未知與決議", "相關機制")
PREFACE_SECTIONS = ("這是什麼遊戲", "這本書怎麼讀", "來源與版本", "全書地圖")
NO_FIGURE_SENTENCE = "影片未拍到本章對應畫面。"


def atlas_dir(path: str) -> pathlib.Path:
    p = pathlib.Path(path)
    if not (p / "atlas.yaml").exists():
        fail("BAD_INPUT", f"不是 atlas 目錄（缺 atlas.yaml）: {p}", "先跑 atlas_compile.py")
    return p


def sha_text(t: str) -> str:
    return _hashlib.sha256(t.encode("utf-8")).hexdigest()


def sha_file(p: pathlib.Path) -> str:
    return _hashlib.sha256(p.read_bytes()).hexdigest()


def chapter_files(book: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in book.glob("[0-9][0-9]-*.md"))


def parse_chapter(md: str) -> dict:
    fm, body = split_frontmatter(md)
    sections: dict[str, list[str]] = {}
    cur = None
    for line in body.splitlines():
        m = _re.match(r"^## (.+?)\s*$", line)
        if m:
            cur = m.group(1)
            sections[cur] = []
            continue
        if cur is not None:
            sections[cur].append(line)
    return {"frontmatter": fm, "sections": sections, "body": body}


def load_atlas_pack(run: pathlib.Path) -> tuple[dict, dict, bool]:
    """回 (resolved, atlas_section, snapshot_stale)。run 的 pack 快照沒有 atlas 區塊時，以現行 pack 的 atlas 補（additive，不影響 spec）。"""
    resolved = load_resolved(run)
    if resolved.get("atlas", {}).get("chapters"):
        return resolved, resolved["atlas"], False
    live = resolve_pack(resolved["domain"])
    return resolved, live.get("atlas", {}), True


# ---------------------------------------------------------------- ffmpeg
def which(bin_name: str) -> str:
    from shutil import which as _w
    p = _w(bin_name)
    if not p:
        fail("DRIVER_MISSING", f"缺 {bin_name}", "apt-get install ffmpeg（或對應套件）")
    return p


def ffprobe(path: pathlib.Path) -> dict:
    which("ffprobe")
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                         capture_output=True, text=True)
    if out.returncode != 0:
        fail("QUERY_FAILED", f"ffprobe 失敗: {out.stderr.strip()[:200]}", "確認檔案是有效影片")
    j = json.loads(out.stdout)
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not v:
        fail("BAD_INPUT", "檔案沒有 video stream", "")
    num, den = (v.get("avg_frame_rate") or "0/1").split("/")
    fps = float(num) / float(den) if float(den) else 0.0
    return {"duration_s": float(j.get("format", {}).get("duration", 0) or 0), "width": v.get("width"),
            "height": v.get("height"), "fps": round(fps, 3), "codec": v.get("codec_name"), "has_audio": a is not None}

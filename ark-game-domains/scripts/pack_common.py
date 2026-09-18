"""ark-game-domains 共用：JSON envelope、exit code、pack 載入與 _core 合併。

契約（與 ark-db-query / ark-video-understanding 相同）：
  stdout 永遠是單一 JSON object；成功 {"success":true,"contract":"1","data":...,"meta":...}
  失敗 {"success":false,"error":{"code","message","hint"}}，exit code 依 EXIT 表。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

CONTRACT = "1"
SKILL_VERSION = "1.0.0"
EXIT = {"BAD_INPUT": 2, "GATE_BLOCKED": 3, "BUDGET_EXCEEDED": 9, "CONN_FAILED": 5,
        "QUERY_FAILED": 6, "TIMEOUT": 7, "DRIVER_MISSING": 8}

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_DOMAINS_DIR = HERE.parent / "domains"
RESERVED = {"_core", "_template"}


def domains_dir() -> pathlib.Path:
    return pathlib.Path(os.getenv("ARK_GAME_DOMAINS_DIR", str(DEFAULT_DOMAINS_DIR)))


def _utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass


def emit(data, meta=None) -> None:
    _utf8()
    print(json.dumps({"success": True, "contract": CONTRACT, "data": data,
                      "meta": {"skill_version": SKILL_VERSION, **(meta or {})}},
                     ensure_ascii=False, default=str))
    sys.exit(0)


def fail(code: str, message: str, hint: str = "") -> None:
    _utf8()
    print(json.dumps({"success": False, "contract": CONTRACT,
                      "error": {"code": code, "message": message, "hint": hint}},
                     ensure_ascii=False))
    sys.exit(EXIT.get(code, 1))


def need_yaml():
    if yaml is None:
        fail("DRIVER_MISSING", "缺 pyyaml", "pip install pyyaml --break-system-packages")


def load_yaml(p: pathlib.Path):
    need_yaml()
    with p.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def read_text(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")


_FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)


def split_frontmatter(text: str):
    m = _FM.match(text)
    if not m:
        return {}, text
    need_yaml()
    return (yaml.safe_load(m.group(1)) or {}), m.group(2)


def parse_tag_table(md: str) -> list[str]:
    """從 schema.md 的 `| tag | 定義 |` 表抓 tag 名。"""
    tags = []
    for line in md.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or cells[0] in ("tag", "") or set(cells[0]) <= set("-: "):
            continue
        tags.append(cells[0])
    return tags


def parse_aliases(md: str) -> dict:
    out = {}
    for line in md.splitlines():
        m = re.match(r"^-\s*([\w-]+)\s*→\s*([\w-]+)", line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def list_packs(root: pathlib.Path | None = None) -> list[str]:
    root = root or domains_dir()
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir()
                  if p.is_dir() and p.name not in RESERVED and (p / "domain.yaml").exists())


def pack_sha256(*dirs: pathlib.Path) -> str:
    h = hashlib.sha256()
    for d in dirs:
        for p in sorted(d.rglob("*")):
            if p.is_file():
                h.update(str(p.relative_to(d)).encode())
                h.update(p.read_bytes())
    return h.hexdigest()


def deep_merge(base, over):
    if isinstance(base, dict) and isinstance(over, dict):
        out = dict(base)
        for k, v in over.items():
            out[k] = deep_merge(base.get(k), v) if k in base else v
        return out
    return over if over is not None else base


# ---------------------------------------------------------------- pack loading
class PackError(Exception):
    pass


def load_raw(domain: str, root: pathlib.Path | None = None) -> dict:
    """讀一個 pack 目錄（不合併）。回傳 dict，所有文字檔已載入。"""
    root = root or domains_dir()
    d = root / domain
    if not (d / "domain.yaml").exists():
        raise PackError(f"pack 不存在: {d}")
    man = load_yaml(d / "domain.yaml")
    raw = {"dir": str(d), "manifest": man, "files": {}}

    ext = d / man.get("files", {}).get("extraction", "extraction.yaml")
    raw["extraction"] = load_yaml(ext) if ext.exists() else {}

    adir = d / man.get("files", {}).get("analysis", "analysis/")
    items = load_yaml(adir / "items.yaml").get("items", []) if (adir / "items.yaml").exists() else []
    for it in items:
        pf = adir / it.get("prompt", "")
        it["prompt_text"] = read_text(pf) if pf.is_file() else None
        it["prompt_exists"] = pf.is_file()
    raw["items"] = items

    kdir = d / man.get("files", {}).get("kb", "kb/")
    schema_md = read_text(kdir / "schema.md") if (kdir / "schema.md").exists() else ""
    raw["kb"] = {"schema_md": schema_md, "tags": parse_tag_table(schema_md),
                 "aliases": parse_aliases(schema_md), "seed": []}
    for sp in sorted((kdir / "seed").glob("*.md")) if (kdir / "seed").exists() else []:
        fm, body = split_frontmatter(read_text(sp))
        raw["kb"]["seed"].append({**fm, "body": body.strip(), "path": str(sp)})

    sdir = d / man.get("files", {}).get("spec", "spec/")
    raw["sections"] = load_yaml(sdir / "sections.yaml").get("sections", []) if (sdir / "sections.yaml").exists() else []
    smm = sdir / "state-machine.skeleton.mmd"
    raw["state_machine"] = read_text(smm) if smm.exists() else None
    css = sdir / "config-structure.schema.json"
    raw["config_structure_schema"] = json.loads(read_text(css)) if css.exists() else None
    raw["dev_templates"] = {p.name[:-3]: read_text(p) for p in sorted((sdir / "dev").glob("*.j2"))} if (sdir / "dev").exists() else {}

    lf = d / man.get("files", {}).get("lint", "lint/rules.yaml")
    raw["lint_rules"] = load_yaml(lf).get("rules", []) if lf.exists() else []

    edir = d / man.get("files", {}).get("eval", "eval/")
    raw["eval"] = {}
    if (edir / "answer-key.template.yaml").exists():
        raw["eval"]["answer_key_template"] = load_yaml(edir / "answer-key.template.yaml")
    if (edir / "dataset.md").exists():
        raw["eval"]["dataset_md"] = read_text(edir / "dataset.md")

    cdir = d / "atlas"
    raw["atlas"] = {"outline": load_yaml(cdir / "outline.yaml").get("chapters", []) if (cdir / "outline.yaml").exists() else [],
                    "figures": load_yaml(cdir / "figures.yaml") if (cdir / "figures.yaml").exists() else {},
                    "style": load_yaml(cdir / "style.yaml") if (cdir / "style.yaml").exists() else {}}

    rdir = d / "references"
    raw["references"] = {p.name: read_text(p) for p in sorted(rdir.glob("*.md"))} if rdir.exists() else {}
    return raw


def _insert_sections(core_sections: list, domain_sections: list) -> list:
    out = [dict(s) for s in core_sections]
    ids = lambda: [s["id"] for s in out]  # noqa: E731
    pending = list(domain_sections)
    guard = 0
    while pending and guard < 100:
        guard += 1
        rest = []
        for s in pending:
            after = s.get("insert_after")
            if after in ids():
                out.insert(ids().index(after) + 1, dict(s))
            else:
                rest.append(s)
        if len(rest) == len(pending):
            raise PackError(f"sections 的 insert_after 找不到錨點: {[s.get('insert_after') for s in rest]}")
        pending = rest
    final = [s for s in out if not s.get("anchor")]
    for n, s in enumerate(final, 1):
        s["number"] = f"{n:02d}"
        s.pop("anchor", None)
    return final


def resolve(domain: str, root: pathlib.Path | None = None) -> dict:
    """_core + domain → resolved pack（deterministic）。"""
    root = root or domains_dir()
    if domain in RESERVED:
        raise PackError(f"{domain} 不是可解析的 domain")
    core = load_raw("_core", root)
    dom = load_raw(domain, root)
    man = dom["manifest"]
    if str(man.get("contract")) != CONTRACT:
        raise PackError(f"pack contract {man.get('contract')!r} 與引擎 {CONTRACT!r} 不符")
    if man.get("extends") not in ("_core", None):
        raise PackError("v1 只支援 extends: _core")

    # extraction：domain 有 detectors 就整組取代；其餘 deep merge；hard_max 以 core 為準
    ext = deep_merge(core["extraction"], dom["extraction"])
    if dom["extraction"].get("detectors"):
        ext["detectors"] = dom["extraction"]["detectors"]
    core_hard = core["extraction"].get("budget", {}).get("hard_max", {})
    ext.setdefault("budget", {})["hard_max"] = core_hard
    for k, v in core_hard.items():
        if ext["budget"].get(k, 0) > v:
            raise PackError(f"budget.{k}={ext['budget'][k]} 超過 core hard_max {v}")

    items = sorted(core["items"] + dom["items"], key=lambda i: (i.get("order", 0), i["id"]))
    entities = [i["entity"]["type"] for i in items if i.get("entity")]

    core_tags = core["kb"]["tags"]
    dom_tags = dom["kb"]["tags"]
    clash = sorted(set(core_tags) & set(dom_tags))
    if clash:
        raise PackError(f"pack 重定義了 core tags: {clash}")
    kb = {"domains": [domain, "game-core"], "core_tags": core_tags, "domain_tags": dom_tags,
          "tags": core_tags + dom_tags, "aliases": {**core["kb"]["aliases"], **dom["kb"]["aliases"]},
          "seed": core["kb"]["seed"] + dom["kb"]["seed"]}

    sections = _insert_sections(core["sections"], dom["sections"])
    atlas_chapters = _insert_sections(core["atlas"]["outline"], dom["atlas"]["outline"])
    atlas_style = deep_merge(core["atlas"]["style"], dom["atlas"]["style"])
    atlas_figures = deep_merge(core["atlas"]["figures"], dom["atlas"]["figures"])
    dev_templates = {**core["dev_templates"], **dom["dev_templates"]}

    resolved = {
        "contract": CONTRACT, "domain": domain,
        "display_name": man.get("display_name", domain), "version": str(man.get("version", "")),
        "detect": man.get("detect", {}),
        "extraction": ext,
        "analysis": {"items": items, "entities": entities, "item_ids": [i["id"] for i in items]},
        "kb": kb,
        "spec": {"sections": sections,
                 "state_machine": dom["state_machine"] or core["state_machine"],
                 "config_structure_schema": dom["config_structure_schema"],
                 "dev_templates": dev_templates},
        "lint": {"rules": core["lint_rules"] + dom["lint_rules"]},
        "atlas": {"chapters": atlas_chapters, "figures": atlas_figures, "style": atlas_style},
        "eval": dom["eval"], "references": dom["references"],
        "pack_sha256": pack_sha256(root / "_core", root / domain),
    }
    return resolved

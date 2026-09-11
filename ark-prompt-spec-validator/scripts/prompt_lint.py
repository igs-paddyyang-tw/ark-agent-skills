#!/usr/bin/env python3
"""prompt_lint.py — L1 deterministic lint for AI-facing Markdown (SKILL.md / prompt / content).

Usage:
  python prompt_lint.py <path-or-dir> [--type skill|prompt|content] [--repo <ark-agent-skills>]
                        [--config .ark-prompt-validator.yaml] [--json out.json] [--quiet]

Exit code: 0 = no P0/P1, 1 = P1 present, 2 = P0 present.
Rule IDs (PL-xxx) are stable; see references/lint-rules.md.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("需要 PyYAML：pip install pyyaml", file=sys.stderr)
    sys.exit(3)

# ---------------------------------------------------------------- vocab (same as audit_skills.py)
CATEGORIES = {"process", "scaffolder", "pipeline", "view", "document", "domain", "ops"}
OUTPUT_FORMATS = {"md", "html", "png", "pdf", "code", "data", "office"}
AUDIENCES = {"ai", "human", "both"}

DEFAULT_EXCLUSIVE_TRIGGERS = {
    "覆蓋率": "ark-test-runner", "line coverage": "ark-test-runner", "pytest --cov": "ark-test-runner",
    "爬蟲": "ark-web-scraper", "反爬": "ark-web-scraper",
    "瀏覽器測試": "ark-browser-tool", "截圖": "ark-browser-tool",
    "寫 spec": "ark-superpowers", "產 spec": "ark-superpowers",
    "派工": "ark-project-planning", "共筆": "ark-doc-coauthoring",
    "chatbot": "ark-agent-builder", "聊天機器人": "ark-agent-builder",
    "博奕": "ark-html-dashboard", "老虎機": "ark-html-dashboard", "遊戲面板": "ark-html-dashboard",
    "CLI 骨架": "ark-llm-cli",
    "驗證提詞": "ark-prompt-spec-validator", "prompt drift": "ark-prompt-spec-validator",
    "drift report": "ark-code-spec-validator",
}

DEFAULT_IGNORE_PATHS = ["**/node_modules/**", "**/fixtures/**", "**/templates/**", "**/examples/**", "**/.git/**"]
DEFAULT_TYPE_OVERRIDES = {"**/assets/**": "content", "**/templates/**": "content"}
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\ufe0f\U0001F3FB-\U0001F3FF]")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
STOP_NOUNS = {"使用", "skill", "Skill", "必須", "不得", "not", "try", "depend", "the", "and", "with", "this", "that", "from", "have", "should"}

DEFAULT_REQUIRED_SECTIONS = {
    "prompt": [["角色", "職責", "role", "你是"], ["邊界", "不做", "不得", "boundar", "限制"], ["輸出格式", "回覆格式", "output", "format"]],
}

FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
INVISIBLE_RE = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u202a-\u202e\u2066-\u2069]")
INJECTION_RES = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    re.compile(r"忽略(以上|之前|先前|上面)(所有|全部)?(的)?(指令|指示|規則)"),
    re.compile(r"\byou are now\b", re.I),
    re.compile(r"^\s*system\s*:", re.I | re.M),
    re.compile(r"disregard\s+(your|the)\s+(system|guidelines)", re.I),
]
PLACEHOLDER_RES = [
    re.compile(r"\{\{[^}]*\}\}"), re.compile(r"\{(TODO|TBD|FIXME)\}", re.I), re.compile(r"\[(TODO|TBD)\]", re.I),
    re.compile(r"<填入[^>]*>"), re.compile(r"\bXXX\b"), re.compile(r"\blorem ipsum\b", re.I),
]
PATH_RE = re.compile(r"(?<![\w/])((?:scripts|references|assets|evals)/[\w./\-]+)")
SKILL_REF_RE = re.compile(r"(?<![\w./\-])(ark-[a-z0-9]+(?:-[a-z0-9]+)*)(?![\w./\-])")
TRIGGER_QUOTE_RE = re.compile(r"「([^」]{2,40})」")
MUST_RE = re.compile(r"(必須|一律|永遠|務必|always|must)\s*", re.I)
FORBID_RE = re.compile(r"(不得|禁止|絕不|不可|never|must not)\s*", re.I)
NOUN_RE = re.compile(r"[\u4e00-\u9fff]{2,6}|[A-Za-z_][\w\-]{2,}")
CHUNK_FORBIDDEN = ["如上所述", "前者", "後者", "上面提到", "見上", "如前述"]
VAGUE_WORDS = ["適當地", "盡量", "可能的話", "視情況", "等等", "適度", "大概"]
FINDING_ID_RE = re.compile(r"\b([FDAE])-(\d+)\b")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.M)


@dataclass
class Finding:
    rule: str
    severity: str  # P0..P3
    file: str
    line: int
    message: str
    confidence: str = "high"


@dataclass
class Report:
    findings: list = field(default_factory=list)
    ignored: list = field(default_factory=list)
    files: list = field(default_factory=list)

    def add(self, f: Finding, ignore_rules: set):
        (self.ignored if f.rule in ignore_rules else self.findings).append(asdict(f))


# ---------------------------------------------------------------- helpers
def parse_frontmatter(text: str):
    m = FM_RE.match(text)
    if not m:
        return None, text, 0
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        return {"__error__": str(e)}, text[m.end():], m.group(0).count("\n")
    return data, text[m.end():], m.group(0).count("\n")


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def infer_type(path: Path, overrides: dict) -> str:
    rel = path.as_posix()
    for pat, t in overrides.items():
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(path.name, pat):
            return t
    if path.name == "SKILL.md":
        return "skill"
    parts = {p.lower() for p in path.parts}
    if parts & {"steering", "prompts", "personas"} or path.name.endswith(".prompt.md"):
        return "prompt"
    return "content"


def skill_root(path: Path) -> Path | None:
    for p in [path.parent, *path.parents]:
        if (p / "SKILL.md").exists():
            return p
    return None


def strip_fences(text: str) -> str:
    """Replace fenced code blocks with same-line-count blanks so line numbers stay valid."""
    return FENCE_RE.sub(lambda m: "\n" * m.group().count("\n"), text)


def load_repo_skills(repo: Path | None) -> dict:
    """name -> {'description': str, 'deprecated': bool}"""
    out = {}
    if not repo or not repo.exists():
        return out
    for sk in repo.glob("*/SKILL.md"):
        fm, _, _ = parse_frontmatter(sk.read_text(encoding="utf-8", errors="replace"))
        if not fm or "__error__" in fm:
            continue
        desc = str(fm.get("description", ""))
        status = (fm.get("metadata") or {}).get("status", "active")
        out[sk.parent.name] = {"description": desc, "deprecated": status == "deprecated" or desc.startswith("[DEPRECATED")}
    for readme in repo.glob("*/README.md"):
        if not (readme.parent / "SKILL.md").exists() and "DEPRECATED" in readme.read_text(encoding="utf-8", errors="replace"):
            out[readme.parent.name] = {"description": "", "deprecated": True}
    return out


# ---------------------------------------------------------------- rules
def lint_file(path: Path, dtype: str, cfg: dict, repo_skills: dict, rep: Report):
    path = path.resolve()
    text = path.read_text(encoding="utf-8", errors="replace")
    rel = path.as_posix()
    # 檔內指令：<!-- prompt-lint: ignore-file --> 或 <!-- prompt-lint: ignore PL-011,PL-013 -->
    if re.search(r"prompt-lint:\s*ignore-file", text):
        rep.files.append({"file": rel, "type": dtype, "skipped": "ignore-file directive"})
        return
    ign = set(cfg.get("ignore_rules") or [])
    for m in re.finditer(r"prompt-lint:\s*ignore\s+([\w,\- ]+)", text):
        ign |= {x.strip() for x in m.group(1).split(",") if x.strip()}
    sroot = skill_root(path)
    my = sroot.name if sroot else path.parent.name
    add = lambda rule, sev, line, msg, conf="high": rep.add(Finding(rule, sev, rel, line, msg, conf), ign)

    fm, body, fm_lines = parse_frontmatter(text)

    # ---- P0
    if fm is None:
        if dtype != "content":
            add("PL-001", "P0", 1, "缺少 frontmatter（--- … ---）")
        elif text.startswith("---"):
            add("PL-001", "P0", 1, "frontmatter 起始標記存在但未閉合")
        fm = {}
    elif "__error__" in fm:
        add("PL-001", "P0", 1, f"frontmatter YAML 不可解析：{fm['__error__'].splitlines()[0]}")
        fm = {}
    if dtype == "skill" and fm.get("name") and fm.get("name") != path.parent.name:
        add("PL-002", "P0", 2, f"name '{fm.get('name')}' != 目錄名 '{path.parent.name}'")
    for m in INVISIBLE_RE.finditer(text):
        ch = m.group()
        if ch == "\u200d" and (EMOJI_RE.match(text, m.end()) or (m.start() and EMOJI_RE.match(text[m.start() - 1]))):
            continue  # emoji ZWJ sequence
        if ch == "\ufeff" and m.start() == 0:
            add("PL-003", "P2", 1, "檔首 BOM（U+FEFF），建議移除")
            continue
        add("PL-003", "P0", line_of(text, m.start()), f"隱形/雙向控制字元 U+{ord(ch):04X}")
    for rx in INJECTION_RES:
        for m in rx.finditer(text):
            add("PL-004", "P0", line_of(text, m.start()), f"疑似提詞注入樣式：'{m.group().strip()[:40]}'")

    prose = strip_fences(body)  # heuristics run on prose only（code fence 內為範例/模板）
    meta = fm.get("metadata") or {}
    desc = str(fm.get("description") or "")
    deprecated = desc.startswith("[DEPRECATED") or meta.get("status") == "deprecated"

    # ---- P1
    if dtype == "skill" and not deprecated:
        if "schema_version" not in meta:
            add("PL-010", "P2", 2, "metadata.schema_version 缺失")
        if meta.get("category") not in CATEGORIES:
            add("PL-010", "P1", 2, f"metadata.category 缺失或不在受控詞彙：{meta.get('category')!r}")
        outs = meta.get("outputs")
        if not isinstance(outs, list) or not outs:
            add("PL-010", "P1", 2, "metadata.outputs 缺失")
        else:
            for o in outs:
                if not isinstance(o, dict) or o.get("format") not in OUTPUT_FORMATS or o.get("audience") not in AUDIENCES:
                    add("PL-010", "P1", 2, f"outputs 項目不合法：{o!r}")
    for rx in (PLACEHOLDER_RES if dtype != "content" else PLACEHOLDER_RES[1:]):  # content 允許 {{var}} 模板變數
        for m in rx.finditer(prose):
            add("PL-011", "P1", fm_lines + line_of(prose, m.start()), f"殘留 placeholder：'{m.group()}'")
    root = skill_root(path)
    if root:  # 路徑引用以 skill 根目錄為準，其次檔案所在目錄
        for m in PATH_RE.finditer(body):
            p = m.group(1).rstrip(".,;:)")
            if "*" in p or "{" in p or "<" in p:
                continue
            if not (root / p).exists() and not (path.parent / p).exists():
                add("PL-012", "P1", fm_lines + line_of(body, m.start()), f"引用路徑不存在：{p}")
    # contradictions (heuristic)
    lines = body.splitlines()
    plines = prose.splitlines()
    must_nouns, forbid_nouns = {}, {}
    for i, ln in enumerate(plines, 1):
        if MUST_RE.search(ln):
            for n in NOUN_RE.findall(MUST_RE.split(ln, 1)[-1][:40]):
                must_nouns.setdefault(n, []).append(i)
        if FORBID_RE.search(ln):
            for n in NOUN_RE.findall(FORBID_RE.split(ln, 1)[-1][:40]):
                forbid_nouns.setdefault(n, []).append(i)
    for n in set(must_nouns) & set(forbid_nouns):
        is_cjk = bool(re.match(r"[\u4e00-\u9fff]", n))
        if n in STOP_NOUNS or (not is_cjk and len(n) < 4):
            continue
        for a in must_nouns[n]:
            for b in forbid_nouns[n]:
                if abs(a - b) <= 2:
                    add("PL-013", "P1", fm_lines + min(a, b), f"疑似指令矛盾：'{n}' 同時被必須/禁止修飾（L{fm_lines + a}/L{fm_lines + b}）", "medium")
    if dtype == "prompt":
        req = (cfg.get("required_sections") or {}).get("prompt") or DEFAULT_REQUIRED_SECTIONS["prompt"]
        headings = [h[1].lower() for h in HEADING_RE.findall(body)]
        for group in req:
            keys = group if isinstance(group, list) else [group]
            if not any(any(k.lower() in h for k in keys) for h in headings):
                add("PL-014", "P1", 1, f"缺少必要章節：{'/'.join(keys)}")
    if dtype == "skill" and not deprecated:
        triggers = dict(DEFAULT_EXCLUSIVE_TRIGGERS)
        triggers.update(cfg.get("exclusive_triggers") or {})
        my = path.parent.name
        dlow = desc.lower()
        for word, owner in triggers.items():
            if word.lower() in dlow and owner != my:
                # allowed if it's in an exclusion clause pointing to the owner
                if re.search(rf"(不適用|請用|改用|交給|→)[^。\n]*{re.escape(owner)}", desc) and word.lower() in dlow:
                    continue
                add("PL-015", "P1", 3, f"description 含獨占詞「{word}」但 owner 是 {owner}")
        mine = {t for t in TRIGGER_QUOTE_RE.findall(desc)}
        for other, info in repo_skills.items():
            if other == my or info["deprecated"]:
                continue
            common = mine & set(TRIGGER_QUOTE_RE.findall(info["description"]))
            if common:
                add("PL-015", "P1", 3, f"觸發詞與 {other} 重疊：{sorted(common)}", "medium")
        if not re.search(r"(不適用於|請用|改用|不用此 skill)", desc):
            add("PL-016", "P1", 3, "description 缺少排除段（不適用於… / 請用 <skill>）")
        if not re.search(r"(使用此 ?[sS]kill 當|當使用者)", desc):
            add("PL-025", "P2", 3, "description 缺少「使用此 skill 當…」觸發句")
        if len(desc) > 1024:
            add("PL-020", "P2", 3, f"description {len(desc)} 字元 > 1024")
        if len(lines) > 500:
            add("PL-020", "P2", fm_lines + 501, f"SKILL.md 本體 {len(lines)} 行 > 500")
    if repo_skills:
        for m in SKILL_REF_RE.finditer(text):
            name = m.group(1)
            if name == my or name in {"ark-agent-skills", "ark-agent-cli"}:
                continue
            if name not in repo_skills:
                add("PL-017", "P2", line_of(text, m.start()), f"引用的 skill 不存在於 repo：{name}", "medium")
            elif repo_skills[name]["deprecated"]:
                add("PL-017", "P1", line_of(text, m.start()), f"引用的 skill 已 deprecated：{name}")

    # ---- P2
    if dtype in {"content", "prompt"}:
        for w in CHUNK_FORBIDDEN:
            for m in re.finditer(re.escape(w), prose):
                add("PL-021", "P2", fm_lines + line_of(prose, m.start()), f"chunk 自足禁詞：「{'·'.join(w)}」")
    if dtype == "content":
        ids = FINDING_ID_RE.findall(body)
        by_prefix = {}
        for pfx, num in ids:
            by_prefix.setdefault(pfx, []).append(int(num))
        for pfx, nums in by_prefix.items():
            uniq = sorted(set(nums))
            if uniq and uniq != list(range(1, uniq[-1] + 1)):
                add("PL-022", "P2", 1, f"{pfx}-n ID 不連續：{uniq}")
    if dtype in {"skill", "prompt"} and re.search(r"(產出|輸出|回覆使用者)", body):
        if not re.search(r"^#{1,4}\s*.*(輸出|回覆|格式|output|format)", body, re.I | re.M) and "```" not in body:
            add("PL-023", "P2", 1, "宣告會產出/輸出，但無「輸出格式」章節或範例區塊")
    prev = 0
    for m in HEADING_RE.finditer(body):
        lvl = len(m.group(1))
        if prev and lvl > prev + 1:
            add("PL-024", "P2", fm_lines + line_of(body, m.start()), f"標題跳級：H{prev} → H{lvl}")
        prev = lvl

    # ---- P3
    if dtype in {"skill", "prompt"}:
        cnt = sum(prose.count(w) for w in VAGUE_WORDS)
        if cnt > 5:
            add("PL-030", "P3", 1, f"模糊修飾詞 {cnt} 次（>5）")
    # table column consistency
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            block, j = [], i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                block.append(lines[j]); j += 1
            cols = {ln.strip().strip("|").replace("\\|", "").count("|") for ln in block}
            if len(cols) > 1:
                add("PL-032", "P3", fm_lines + i + 1, f"表格欄數不一致：{sorted(cols)}")
            i = j
        else:
            i += 1

    rep.files.append({"file": rel, "type": dtype})


# ---------------------------------------------------------------- scoring
def score(findings: list) -> dict:
    c = Counter(f["severity"] for f in findings)
    p0, p1, p2, p3 = c["P0"], c["P1"], c["P2"], c["P3"]
    s = 0 if p0 else max(0, 100 - p1 * 15 - p2 * 5 - p3 * 1)
    verdict = "broken" if p0 or s < 70 else ("sound" if s >= 90 else "needs-work")
    return {"p0": p0, "p1": p1, "p2": p2, "p3": p3, "score": s, "verdict": verdict, "scoring_version": 1}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--type", choices=["skill", "prompt", "content"])
    ap.add_argument("--repo", help="ark-agent-skills repo 根目錄（跨庫觸發詞 / skill 引用比對）")
    ap.add_argument("--config", default=".ark-prompt-validator.yaml")
    ap.add_argument("--json")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    cfg = {}
    cp = Path(a.config)
    if cp.exists():
        try:
            cfg = yaml.safe_load(cp.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            print(f"⚠️ config 解析失敗，改用預設：{e}", file=sys.stderr)

    root = Path(a.path)
    files = [root] if root.is_file() else sorted(root.rglob("*.md"))
    ign_paths = DEFAULT_IGNORE_PATHS + (cfg.get("ignore_paths") or [])
    files = [f for f in files if not any(fnmatch.fnmatch(f.as_posix(), p) for p in ign_paths)]
    repo_skills = load_repo_skills(Path(a.repo)) if a.repo else {}
    rep = Report()
    for f in files:
        overrides = {**DEFAULT_TYPE_OVERRIDES, **(cfg.get("type_overrides") or {})}
        lint_file(f, a.type or infer_type(f, overrides), cfg, repo_skills, rep)

    sc = score(rep.findings)
    out = {"tool": "prompt_lint", "files": rep.files, "findings": rep.findings, "ignored": rep.ignored, "summary": sc}
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    if not a.quiet:
        order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        for f in sorted(rep.findings, key=lambda x: (order[x["severity"]], x["file"], x["line"])):
            conf = "" if f["confidence"] == "high" else f" ({f['confidence']})"
            print(f"[{f['severity']}] {f['rule']} {f['file']}:{f['line']} {f['message']}{conf}")
        for f in rep.ignored:
            print(f"[⏭️ ignored] {f['rule']} {f['file']}:{f['line']} {f['message']}")
        emoji = {"sound": "✅", "needs-work": "⚠️", "broken": "❌"}[sc["verdict"]]
        print(f"\n{emoji} L1 score {sc['score']}/100 · {sc['verdict']} · P0:{sc['p0']} P1:{sc['p1']} P2:{sc['p2']} P3:{sc['p3']} · files:{len(files)}")
    sys.exit(2 if sc["p0"] else (1 if sc["p1"] else 0))


if __name__ == "__main__":
    main()

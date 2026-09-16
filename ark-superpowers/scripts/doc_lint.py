#!/usr/bin/env python3
"""doc_lint.py — 文件內容守門（ADR-001）。

取代 check_doc_completeness.py 的形狀檢查，改用「模板指紋 + placeholder token + 規則 ID」。
W0 階段先實作兩條 P0 規則（讓骨架必 FAIL）：
  SP-001 template_residue —— 正文行/表格 cell 正規化後命中 fingerprints.json（還是模板原文）
  SP-002 placeholder_token —— 正文含 {…} / [NEEDS CLARIFICATION] / TODO / TBD / （待填）

exit：0 無 P0/P1；1 有 P1；2 有 P0。`--json` 輸出結構化。
W1+ 再加 sections/id/frontmatter/lifecycle/chain 規則。

指紋新鮮度：啟動時比對 templates 最新 mtime 與 fingerprints.json，指紋較舊即 exit 2
要求重建（不靜默用舊指紋）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
TEMPLATES_DIR = SKILL_ROOT / "references" / "templates"
FINGERPRINTS = SKILL_ROOT / "references" / "fingerprints.json"
SECTIONS_YAML = SKILL_ROOT / "references" / "sections.yaml"


def infer_type(path: Path, fm: dict) -> str:
    """doc_type ← frontmatter type，其次檔名後綴。"""
    t = (fm.get("type") or "").strip()
    if t in ("spec", "design", "plan", "adr", "one-pager"):
        return t
    for suf, dt in (("-spec.md", "spec"), ("-design.md", "design"), ("-plan.md", "plan")):
        if path.name.endswith(suf):
            return dt
    return t or "unknown"


def load_sections() -> dict:
    """讀 sections.yaml（PyYAML 選用，否則極簡解析）。回 {type: [{key,zh,en,required}]}。"""
    if not SECTIONS_YAML.exists():
        return {}
    text = SECTIONS_YAML.read_text(encoding="utf-8")
    try:
        import yaml
        types = (yaml.safe_load(text) or {}).get("types", {})
        return {t: (v.get("sections", []) if isinstance(v, dict) else v)
                for t, v in types.items()}
    except Exception:
        pass
    out: dict = {}
    cur = None
    for ln in text.splitlines():
        m = re.match(r"^  ([\w-]+):\s*$", ln)
        if m:
            cur = m.group(1); out[cur] = []; continue
        m = re.search(r"key:\s*([\w-]+).*?zh:\s*(.+?)\s*,.*?en:\s*(.+?)\s*,.*?required:\s*(true|false)", ln)
        if m and cur is not None:
            out[cur].append({"key": m.group(1), "zh": m.group(2).strip(),
                             "en": m.group(3).strip(), "required": m.group(4) == "true"})
    return out


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    fm = {}
    for ln in text[3:end].splitlines():
        if ":" in ln and not ln.startswith((" ", "\t", "-")):
            k, _, v = ln.partition(":")
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def h2_keys(text: str) -> set[str]:
    """正規化 H2 標題：去編號、去括號註記。回 H2 標題集合（用於精確鍵比對）。"""
    keys = set()
    for ln in text.splitlines():
        m = re.match(r"^##\s+(.+)$", ln)
        if m:
            h = re.sub(r"^\d+\.?\s*", "", m.group(1))       # 去 "3. "
            h = re.sub(r"[（(].*", "", h).strip()            # 去括號註記
            keys.add(h)
    return keys


def anchor_keys(text: str) -> set[str]:
    return set(re.findall(r"<!--\s*sec:([\w-]+)\s*-->", text))


# 與 build_fingerprints.normalize 必須一致
_MIN_LEN = 8
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
PLACEHOLDER_RE = re.compile(r"\{[^{}\n]{1,40}\}|\[NEEDS CLARIFICATION\]|\bTODO\b|\bTBD\b|（待填）|\(TBD\)")


def normalize(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(".,;:。，；：")
    return s


def _sha(s: str) -> str:
    import hashlib
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def strip_fences(text: str) -> str:
    return FENCE_RE.sub(lambda m: "\n" * m.group().count("\n"), text)


def load_fingerprints() -> dict:
    if not FINGERPRINTS.exists():
        print("❌ fingerprints.json 不存在，請先跑 build_fingerprints.py", file=sys.stderr)
        sys.exit(2)
    # 新鮮度：指紋不得舊於任一模板
    fp_mtime = FINGERPRINTS.stat().st_mtime
    for md in TEMPLATES_DIR.rglob("*.md"):
        if md.stat().st_mtime > fp_mtime:
            print(f"❌ fingerprints.json 落後於模板 {md.name}，請重跑 build_fingerprints.py",
                  file=sys.stderr)
            sys.exit(2)
    return json.loads(FINGERPRINTS.read_text(encoding="utf-8"))


def lint(path: Path, fp: dict, sections: dict | None = None) -> list[dict]:
    findings: list[dict] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    prose = strip_fences(text)
    line_set = set(fp["lines"])
    cell_set = set(fp["cells"])
    fm = parse_frontmatter(text)
    dtype = infer_type(path, fm)
    lang = (fm.get("language") or "zh-TW").strip()

    # SP-006 frontmatter_required
    for req in ("title", "type", "status", "created", "language", "version"):
        if req not in fm:
            findings.append({"id": "SP-006", "severity": "P0", "line": 1,
                             "msg": f"frontmatter 缺必填欄位：{req}"})
    # SP-007 frontmatter_enum（language）
    if fm.get("language") and fm["language"] not in ("zh-TW", "en"):
        findings.append({"id": "SP-007", "severity": "P1", "line": 1,
                         "msg": f"language 非 zh-TW/en：{fm['language']}"})

    # SP-032 approved 內容雜湊一致（手改 approved 文件被抓，ADR-003）
    if fm.get("status") == "approved" and fm.get("approved_hash"):
        import hashlib
        body = text.split("\n---", 2)[-1]
        actual = hashlib.sha1(body.encode("utf-8")).hexdigest()[:12]
        if actual != fm["approved_hash"]:
            findings.append({"id": "SP-032", "severity": "P0", "line": 1,
                             "msg": "status:approved 但內容雜湊 ≠ approved_hash（未走新版本而手改）"})

    # SP-004 section_missing（精確鍵或錨點，取代子字串比對）
    if sections and dtype in sections:
        present = h2_keys(text)
        anchors = anchor_keys(text)
        for sec in sections[dtype]:
            if not sec.get("required"):
                continue
            want = sec["en"] if lang == "en" else sec["zh"]
            if want not in present and sec["key"] not in anchors:
                findings.append({"id": "SP-004", "severity": "P0", "line": 1,
                                 "msg": f"缺必要章節：{want}（key={sec['key']}）"})

    for i, raw in enumerate(prose.splitlines(), 1):
        # SP-002 placeholder（正文，不含 fenced code）
        for m in PLACEHOLDER_RE.finditer(raw):
            findings.append({"id": "SP-002", "severity": "P0", "line": i,
                             "msg": f"未替換 placeholder：{m.group()}"})
        # SP-001 template_residue（整行）
        n = normalize(raw)
        if len(n) >= _MIN_LEN and "{" not in n and _sha(n) in line_set:
            findings.append({"id": "SP-001", "severity": "P0", "line": i,
                             "msg": "整行仍是模板原文（未填實質內容）"})
            continue
        # SP-001 cell 粒度
        if "|" in raw:
            for cell in raw.split("|"):
                cn = normalize(cell)
                if len(cn) >= _MIN_LEN and "{" not in cn and _sha(cn) in cell_set:
                    findings.append({"id": "SP-001", "severity": "P0", "line": i,
                                     "msg": f"表格 cell 仍是模板原文：{cell.strip()[:30]}"})
    return findings


def exit_code(findings: list[dict]) -> int:
    if any(f["severity"] == "P0" for f in findings):
        return 2
    if any(f["severity"] == "P1" for f in findings):
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="文件內容守門（SP-xxx）")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    fp = load_fingerprints()
    sections = load_sections()
    worst = 0
    for f in args.files:
        p = Path(f)
        findings = lint(p, fp, sections)
        rc = exit_code(findings)
        worst = max(worst, rc)
        p0 = sum(1 for x in findings if x["severity"] == "P0")
        p1 = sum(1 for x in findings if x["severity"] == "P1")
        if args.json:
            print(json.dumps({"file": str(p), "findings": findings,
                              "counts": {"p0": p0, "p1": p1}}, ensure_ascii=False))
        else:
            for x in findings:
                print(f"[{x['severity']}] {x['id']} {p}:{x['line']} {x['msg']}")
            verdict = "broken" if rc == 2 else "needs-work" if rc == 1 else "sound"
            print(f"{'❌' if rc==2 else '⚠️' if rc==1 else '✅'} {p.name}: {verdict} · P0:{p0} P1:{p1}")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())

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


def lint(path: Path, fp: dict) -> list[dict]:
    findings: list[dict] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    prose = strip_fences(text)
    line_set = set(fp["lines"])
    cell_set = set(fp["cells"])

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
    worst = 0
    for f in args.files:
        p = Path(f)
        findings = lint(p, fp)
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

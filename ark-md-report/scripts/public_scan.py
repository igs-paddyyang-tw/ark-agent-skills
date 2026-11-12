#!/usr/bin/env python3
"""公開版敏感字串掃描：對外發佈前，所有檔案都必須 0 命中。

兩層規則：
- 通用規則（內建）：疑似 commit 編號、IP、本機家目錄路徑、金鑰與 token、email、審查報告評等欄位。
  任何專案的公開版都不該出現這些。
- 專案規則（`--rules <json>`）：內部 repo／分支／主機名、正式資料庫名稱、缺陷編號格式、
  營運數值說法……這些詞本身就是內部資訊，**放在專案自己的 repo，不放進共用技能**。

專案規則檔格式：
    {"rules": [{"name": "內部 repo", "pattern": "slot-server|fish_go"}, ...]}

用法：
    python public_scan.py <檔案或目錄>... [--rules rules.json] [--no-generic] [--json]

回傳碼：0 = 全部 0 命中；1 = 有命中，或掃到 0 個檔案（掃不到東西不算通過）；2 = 參數或規則檔錯誤。

🔴 第一輪就 0 命中要當成可疑：再用 grep 抽查 commit、資料庫名、缺陷編號是否真的不在了。
新的敏感詞（新主機、新 repo、新缺陷編號格式）一發現就加進專案規則檔。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

GENERIC_RULES: list[tuple[str, str]] = [
    # 7～40 位十六進位、同時含字母與數字（排除純數字與 CSS 色碼 #0b66c3）
    ("commit 編號", r"(?<![0-9A-Za-z#_\-])(?=[0-9a-f]*[a-f])(?=[0-9a-f]*[0-9])[0-9a-f]{7,40}(?![0-9A-Za-z_\-])"),
    ("IP 位址", r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])"),
    ("本機路徑", r"/home/[A-Za-z0-9_.-]+|/Users/[A-Za-z0-9_.-]+|[A-Za-z]:\\+Users\\+"),
    ("金鑰或 token", r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-/+=]{8,}"
                    r"|\bgh[pousr]_[A-Za-z0-9]{20,}|\bsk-[A-Za-z0-9_\-]{20,}|\b\d{8,10}:[A-Za-z0-9_\-]{35}\b"),
    ("email", r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+\.[A-Za-z0-9.\-]*[A-Za-z]{2,}"),
    # 審查報告的評等值（frontmatter-contract 的 verdict 枚舉；「verdict」這個詞本身不算，介紹報告契約時會提到它）
    ("審查報告評等", r"(?m)\bneeds-work\b|\bverdict\s*(?:[:：=]|</?b>|<b>)\s*['\"]?(?:sound|needs-work|broken|ahead|parity|behind|divergent|resolved|mitigated|open|decided|partially-decided|blocked|confirmed|rejected|inconclusive)"
                   r"|^#{1,3}\s*(?:Verdict|Findings|Evidence|Actions)\b"),
]

TEXT_SUFFIXES = {".md", ".html", ".htm", ".txt", ".json", ".csv", ".svg", ".yaml", ".yml"}


def load_rules(rules_path: str | None, generic: bool) -> list[tuple[str, re.Pattern]]:
    """組合通用與專案規則並編譯；規則檔格式錯誤時拋 ValueError。"""
    pairs = list(GENERIC_RULES) if generic else []
    if rules_path:
        data = json.loads(Path(rules_path).read_text(encoding="utf-8"))
        items = data.get("rules") if isinstance(data, dict) else None
        if not isinstance(items, list) or not items:
            raise ValueError(f"{rules_path}：需要非空的 rules 陣列")
        for i, r in enumerate(items):
            if not isinstance(r, dict) or not r.get("name") or not r.get("pattern"):
                raise ValueError(f"{rules_path}：第 {i + 1} 條規則缺 name 或 pattern")
            pairs.append((str(r["name"]), str(r["pattern"])))
    if not pairs:
        raise ValueError("沒有任何規則（用了 --no-generic 卻沒給 --rules）")
    return [(name, re.compile(pat)) for name, pat in pairs]


def collect(paths: list[str]) -> list[Path]:
    """展開目錄；目錄內只取文字類副檔名。"""
    files: list[Path] = []
    for a in paths:
        p = Path(a)
        if p.is_dir():
            files += sorted(x for x in p.rglob("*") if x.is_file() and x.suffix.lower() in TEXT_SUFFIXES)
        elif p.is_file():
            files.append(p)
    return files


def scan_text(text: str, rules: list[tuple[str, re.Pattern]]) -> list[dict]:
    """回傳命中清單：規則名、行號、命中字串、前後文。"""
    hits = []
    for name, rx in rules:
        for m in rx.finditer(text):
            hits.append({
                "rule": name,
                "line": text.count("\n", 0, m.start()) + 1,
                "match": m.group(0),
                "context": text[max(0, m.start() - 30): m.end() + 30].replace("\n", " "),
            })
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="公開版敏感字串掃描（0 命中才可對外發佈）")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--rules", help="專案規則 JSON（放在專案 repo）")
    ap.add_argument("--no-generic", action="store_true", help="不套用內建通用規則")
    ap.add_argument("--json", action="store_true", help="機器可讀輸出")
    a = ap.parse_args(argv)
    try:
        rules = load_rules(a.rules, not a.no_generic)
    except (OSError, ValueError, re.error) as exc:
        print(f"❌ 規則錯誤：{exc}", file=sys.stderr)
        return 2
    files = collect(a.paths)
    if not files:
        msg = "沒有檔案可掃 —— 掃到 0 個檔案不算通過"
        print(json.dumps({"ok": False, "files": 0, "error": msg}, ensure_ascii=False) if a.json else f"❌ {msg}")
        return 1
    report = []
    for f in files:
        report.append({"file": str(f), "hits": scan_text(f.read_text(encoding="utf-8", errors="replace"), rules)})
    total = sum(len(r["hits"]) for r in report)
    if a.json:
        print(json.dumps({"ok": total == 0, "files": len(files), "rules": len(rules), "hits": total,
                          "report": report}, ensure_ascii=False))
    else:
        for r in report:
            print(f"{'✅' if not r['hits'] else '❌'} {r['file']}：{len(r['hits'])} 命中")
            for h in r["hits"][:20]:
                print(f"   L{h['line']} [{h['rule']}] {h['match']!r} …{h['context']}…")
        print(f"檔案 {len(files)}｜規則 {len(rules)}｜命中合計 {total}")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

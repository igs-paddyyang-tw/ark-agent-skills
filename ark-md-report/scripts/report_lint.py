"""report_lint.py — Content 軌（ark-md-report）契約驗證器。

Deterministic 守門：agent 產出報告後必須跑過此 lint 才能宣告完成。
驗證 frontmatter 契約、受控詞彙、ID 連續性、統計一致性、chunk 自足禁詞、必要章節。

用法：
    python report_lint.py docs/reports/review/2026-08-11-xxx.md
    python report_lint.py docs/reports/**/*.md
    python report_lint.py --wiki-schema knowledge/myproj/schema.md report.md   # 加驗 tags 白名單

Exit code：0 全過 / 1 有 FAIL（WARN 不影響 exit code）
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# ── 契約定義（與 ark-md-report/references/frontmatter-contract.md 同步）──────

REQUIRED_FIELDS = ["title", "type", "subject", "date", "author",
                   "source_skill", "verdict", "confidence", "tags", "sources"]

VERDICT_ENUM = {
    "review":      {"sound", "needs-work", "broken"},
    "competitive": {"ahead", "parity", "behind", "divergent"},
    "incident":    {"resolved", "mitigated", "open"},
    "decision":    {"decided", "partially-decided", "blocked"},
    "data":        {"confirmed", "rejected", "inconclusive"},
}
CONFIDENCE_ENUM = {"high", "medium", "low"}
SEVERITY_ENUM = {"P0", "P1", "P2", "P3"}

# 必要章節（依 type）；decision 型 Findings 換成 Decisions
REQUIRED_SECTIONS = {
    "review":      ["Verdict", "Findings", "Evidence", "Actions", "邊界聲明"],
    "competitive": ["Verdict", "Findings", "Evidence", "Actions", "邊界聲明"],
    "incident":    ["Verdict", "時間軸", "Findings", "Evidence", "Actions", "邊界聲明"],
    "decision":    ["Verdict", "Decisions", "Open Questions", "邊界聲明"],
    "data":        ["Verdict", "假設與方法", "Findings", "Evidence", "邊界聲明"],
}

# chunk 自足禁詞（ai-writing-rules 第 2 條）
FORBIDDEN_PHRASES = ["如上所述", "如前所述", "前述問題", "上文提到", "詳見上文", "（見上）"]
# 前者/後者 允許出現在同一句的即時對比，但跨段指涉危險 → 一律 WARN
WARN_PHRASES = ["前者", "後者", "該問題", "此問題"]

FILENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── 解析工具 ─────────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    try:
        import yaml  # type: ignore
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        # 無 yaml 時的簡易 fallback（不支援巢狀，findings 另行 regex）
        fm: dict = {}
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith(" ") and not line.startswith("-"):
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip().strip('"')
        fmm = re.search(r"findings:\s*\{([^}]*)\}", m.group(1))
        if fmm:
            fm["findings"] = {
                kv.split(":")[0].strip(): int(kv.split(":")[1])
                for kv in fmm.group(1).split(",") if ":" in kv
            }
        return fm


def body_after_frontmatter(text: str) -> str:
    m = re.match(r"^---\s*\n.*?\n---\s*\n", text, re.DOTALL)
    return text[m.end():] if m else text


def sections(body: str) -> dict[str, str]:
    """以 ## 標題切分章節，回傳 {標題: 內容}。"""
    result: dict[str, str] = {}
    parts = re.split(r"^##\s+(.+)$", body, flags=re.MULTILINE)
    for i in range(1, len(parts) - 1, 2):
        result[parts[i].strip()] = parts[i + 1]
    return result


def table_rows(section_text: str) -> list[dict[str, str]]:
    """解析章節內第一個 markdown 表格為 list[dict]。"""
    lines = [l for l in section_text.splitlines() if l.strip().startswith("|")]
    if len(lines) < 3:
        return []
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells)))
    return rows


def find_section(secs: dict[str, str], keyword: str) -> str | None:
    for title, content in secs.items():
        if keyword in title:
            return content
    return None


# ── 檢查項 ───────────────────────────────────────────────────────────────

def check_file(path: Path, wiki_tags: set[str] | None = None) -> tuple[list[str], list[str]]:
    """回傳 (fails, warns)。"""
    fails: list[str] = []
    warns: list[str] = []
    text = path.read_text(encoding="utf-8")

    # 0. 檔名約定
    if not FILENAME_RE.match(path.name):
        warns.append(f"檔名不符 YYYY-MM-DD-slug.md 約定：{path.name}")

    # 1. frontmatter 必要欄位
    fm = parse_frontmatter(text)
    if not fm:
        return ["缺少 frontmatter"], warns
    for field in REQUIRED_FIELDS:
        if field not in fm or fm[field] in (None, "", []):
            fails.append(f"frontmatter 缺少必要欄位：{field}")

    rtype = str(fm.get("type", ""))
    if rtype not in VERDICT_ENUM:
        fails.append(f"type 不在枚舉：{rtype}（允許：{sorted(VERDICT_ENUM)}）")
        return fails, warns

    # 2. 受控詞彙
    verdict = str(fm.get("verdict", ""))
    if verdict not in VERDICT_ENUM[rtype]:
        fails.append(f"verdict '{verdict}' 不在 {rtype} 型枚舉 {sorted(VERDICT_ENUM[rtype])}")
    if str(fm.get("confidence", "")) not in CONFIDENCE_ENUM:
        fails.append(f"confidence 必須是 high/medium/low，目前：{fm.get('confidence')}")
    if not DATE_RE.match(str(fm.get("date", ""))):
        fails.append(f"date 必須為 YYYY-MM-DD：{fm.get('date')}")

    # 3. tags 白名單（有提供 wiki schema 才驗）
    tags = fm.get("tags") or []
    if wiki_tags is not None:
        unknown = [t for t in tags if t not in wiki_tags]
        if unknown:
            fails.append(f"tags 不在受控詞彙表：{unknown}（新 tag 走「詞彙表建議」章節，人工審核入表）")

    # 4. 必要章節
    body = body_after_frontmatter(text)
    secs = sections(body)
    for req in REQUIRED_SECTIONS[rtype]:
        if find_section(secs, req) is None:
            fails.append(f"缺少必要章節：## {req}")

    # 5. Findings / Decisions 統計一致性 + ID 連續性
    if rtype == "decision":
        dsec = find_section(secs, "Decisions")
        if dsec is not None:
            rows = table_rows(dsec)
            ids = [r.get("ID", "") for r in rows]
            _check_ids(ids, "D", fails)
            declared = fm.get("decisions")
            if declared is not None and int(declared) != len(rows):
                fails.append(f"frontmatter decisions={declared} 與 Decisions 表 {len(rows)} 列不一致")
    else:
        fsec = find_section(secs, "Findings")
        if fsec is not None:
            rows = table_rows(fsec)
            ids = [r.get("ID", "") for r in rows]
            _check_ids(ids, "F", fails)
            sev_count = {"p0": 0, "p1": 0, "p2": 0, "p3": 0}
            for r in rows:
                sev = r.get("嚴重度", r.get("Severity", ""))
                if sev not in SEVERITY_ENUM:
                    fails.append(f"{r.get('ID','?')} 嚴重度 '{sev}' 不在 P0/P1/P2/P3")
                else:
                    sev_count[sev.lower()] += 1
            declared = fm.get("findings") or {}
            if isinstance(declared, dict):
                for k in ("p0", "p1", "p2", "p3"):
                    d = int(declared.get(k, 0))
                    if d != sev_count[k]:
                        fails.append(
                            f"frontmatter findings.{k}={d} 與 Findings 表實際 {sev_count[k]} 不一致")

            # 6. P0/P1 必須有 Evidence 支持
            esec = find_section(secs, "Evidence") or ""
            supported: set[str] = set()
            for m in re.finditer(r"支持\s*((?:F-\d+[、,\s和]*)+)", esec):
                supported.update(re.findall(r"F-\d+", m.group(1)))
            for r in rows:
                if r.get("嚴重度", "") in ("P0", "P1") and r.get("ID", "") not in supported:
                    fails.append(f"{r['ID']}（{r.get('嚴重度')}）無對應 Evidence 支持（E-x 標註「支持 {r['ID']}」）")

            # 7. Actions 的對應 Finding 必須存在
            asec = find_section(secs, "Actions")
            if asec is not None:
                fid_set = set(ids)
                for ar in table_rows(asec):
                    ref = ar.get("對應 Finding", "")
                    for fid in re.findall(r"F-\d+", ref):
                        if fid not in fid_set:
                            fails.append(f"{ar.get('ID','?')} 引用不存在的 {fid}")

    # 8. chunk 自足禁詞
    for phrase in FORBIDDEN_PHRASES:
        if phrase in body:
            fails.append(f"含跨章指涉禁詞：「{phrase}」（chunk 自足規則）")
    for phrase in WARN_PHRASES:
        if phrase in body:
            warns.append(f"含高風險指涉詞：「{phrase}」——確認未跨段指涉")

    return fails, warns


def _check_ids(ids: list[str], prefix: str, fails: list[str]) -> None:
    nums = []
    for i in ids:
        m = re.match(rf"^{prefix}-(\d+)$", i)
        if not m:
            fails.append(f"ID 格式錯誤：'{i}'（應為 {prefix}-N）")
            return
        nums.append(int(m.group(1)))
    if len(set(nums)) != len(nums):
        fails.append(f"{prefix}-x ID 重複")
    if nums and nums != list(range(1, len(nums) + 1)):
        fails.append(f"{prefix}-x ID 不連續：{nums}（withdrawn 不回收編號，但發布時應連續）")


def load_wiki_tags(schema_path: Path) -> set[str]:
    """從 wiki schema.md 提取 tags 白名單（``tags:`` 區塊或表格中的 tag 清單）。"""
    text = schema_path.read_text(encoding="utf-8")
    tags: set[str] = set()
    m = re.search(r"(?:tags 白名單|allowed_tags|受控詞彙)[^\n]*\n((?:\s*[-|].*\n)+)", text)
    if m:
        tags.update(re.findall(r"[-|]\s*`?([a-z0-9-]+)`?", m.group(1)))
    return tags


def main() -> int:
    args = sys.argv[1:]
    wiki_tags: set[str] | None = None
    if "--wiki-schema" in args:
        idx = args.index("--wiki-schema")
        wiki_tags = load_wiki_tags(Path(args[idx + 1]))
        args = args[:idx] + args[idx + 2:]

    if not args:
        print(__doc__)
        return 1

    all_pass = True
    for arg in args:
        path = Path(arg)
        fails, warns = check_file(path, wiki_tags)
        if fails:
            all_pass = False
            print(f"\n❌ FAIL: {path}")
            for f in fails:
                print(f"   - {f}")
        else:
            print(f"✅ PASS: {path}")
        for w in warns:
            print(f"   ⚠ WARN: {w}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

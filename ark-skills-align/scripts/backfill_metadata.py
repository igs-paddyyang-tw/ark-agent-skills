#!/usr/bin/env python3
"""backfill_metadata.py — schema v1 metadata 半自動回填

只「新增」metadata 欄位（category/outputs/render/status/schema_version），
絕不修改 name、description 或既有欄位值。

**單一真相：frontmatter。**（2026-08-12 決策 C）
skill 已有的 `metadata.category` 一律優先；下方 FALLBACK_CATEGORY_MAP
僅供「category 完全缺失」的新 skill 起始推薦，不是歸屬的權威來源。
`references/taxonomy.md` 只定義受控詞彙與 outputs 預設值，不再維護歸屬名冊。

⚠️ 舊版在檢查「是否真的有欄位要填」**之前**就用歸屬表早退，
   導致 7 個 metadata 完全齊全的 skill 被誤報 UNMAPPED。
   現在只有「category 缺失且推薦表也查不到」才回報 NEEDS-CATEGORY。

用法：
  python backfill_metadata.py --repo <repo> [--dry-run]
"""
import argparse
import re
from pathlib import Path

import yaml

# 新 skill 的 category 起始推薦（**非權威**）——
# 權威是各 skill 自己的 frontmatter。此表只在 category 完全缺失時參考。
FALLBACK_CATEGORY_MAP = {
    "process": ["ark-grill-me", "ark-superpowers", "ark-spec-executor",
             "ark-code-spec-validator", "ark-ux-spec-validator",
             "ark-project-planning", "ark-planning-with-files",
             "ark-doc-coauthoring", "ark-skill-creator"],
    "scaffolder": ["ark-agent-team-builder", "ark-agent-builder",
                 "ark-webapp-generator", "ark-chatbot-generator", "ark-kiro-init",
                 "ark-llm-cli", "ark-mcp-builder", "ark-scheduler-generator",
                 "ark-telegram-bot", "ark-docker-deploy", "ark-ai-bot-builder"],
    "pipeline": ["ark-db-query", "ark-etl-pipeline", "ark-chart-generator",
                 "ark-kpi-calculator", "ark-anomaly-detector", "ark-cost-tracker",
                 "ark-file-export", "ark-test-runner", "ark-security-audit",
                 "ark-code-review", "ark-translator", "ark-llm-tools",
                 "ark-web-scraper", "ark-browser-tool", "ark-wiki-engine"],
    "view": ["ark-html-dashboard", "ark-data-dashboard", "ark-news-daily",
                "ark-landing-page", "ark-frontend-design", "ark-ui-design-system",
                "ark-theme-factory", "ark-canvas-design", "ark-html-report"],
    "document": ["ark-report-template", "ark-markdown-formatter", "ark-game-design-doc",
            "ark-internal-comms", "ark-uml-generator", "ark-docx-tool",
            "ark-pptx-tool", "ark-xlsx-tool", "ark-pdf-tool", "ark-md-report"],
    "domain": ["ark-marketing", "ark-community-ops", "ark-retention-analysis",
            "ark-executive-assistant"],
    "ops": ["ark-env-doctor", "ark-dashboard-health", "ark-skills-align"],
}
SKILL_TO_CAT = {s: c for c, lst in FALLBACK_CATEGORY_MAP.items() for s in lst}

DEFAULT_OUTPUTS = {
    "process": [{"format": "md", "audience": "ai"}],
    "scaffolder": [{"format": "code", "audience": "both"}],
    "pipeline": [{"format": "data", "audience": "ai"}],
    "view": [{"format": "html", "audience": "human"}],
    "document": [{"format": "md", "audience": "both"}],
    "domain": [{"format": "md", "audience": "both"}],
    "ops": [{"format": "md", "audience": "ai"}],
}
OUTPUT_OVERRIDES = {
    "ark-chart-generator": [{"format": "png", "audience": "both"}],
    "ark-canvas-design": [{"format": "png", "audience": "human"},
                          {"format": "pdf", "audience": "human"}],
    "ark-docx-tool": [{"format": "office", "audience": "human"}],
    "ark-pptx-tool": [{"format": "office", "audience": "human"}],
    "ark-xlsx-tool": [{"format": "office", "audience": "human"}],
    "ark-pdf-tool": [{"format": "office", "audience": "human"}],
}
RENDER_HTML = {"ark-report-template", "ark-news-daily", "ark-md-report"}

FM_RE = re.compile(r"\A(---\s*\n)(.*?)(\n---\s*\n)", re.DOTALL)


def fmt_outputs(outs) -> str:
    lines = ["  outputs:"]
    for o in outs:
        lines.append(f"    - {{ format: {o['format']}, audience: {o['audience']} }}")
    return "\n".join(lines)


def backfill_one(path: Path, dry: bool) -> str:
    """外科手術式插入：只在 frontmatter 文字層新增缺少的 metadata 欄位，
    不做 yaml round-trip，description 與既有欄位的排版一字不動。"""
    text = path.read_text(encoding="utf-8")
    m = FM_RE.match(text)
    if not m:
        return "PARSE_FAIL"
    raw_fm = m.group(2)
    fm = yaml.safe_load(raw_fm) or {}
    name = fm.get("name", path.parent.name)
    meta = fm.get("metadata") or {}
    # frontmatter 為單一真相；推薦表只在 category 缺失時當起始值
    cat = meta.get("category") or SKILL_TO_CAT.get(name)

    add_lines, changed = [], []
    if "schema_version" not in meta:
        add_lines.append("  schema_version: 1"); changed.append("schema_version")
    if "category" not in meta:
        if cat is None:
            # 真正需要人工的情況：沒有 category，推薦表也查不到
            return "NEEDS-CATEGORY"
        add_lines.append(f"  category: {cat}"); changed.append("category")
    if "outputs" not in meta:
        if cat not in DEFAULT_OUTPUTS:
            return "NEEDS-CATEGORY"   # 無法推導 outputs 預設值
        add_lines.append(fmt_outputs(OUTPUT_OVERRIDES.get(name, DEFAULT_OUTPUTS[cat])))
        changed.append("outputs")
    if name in RENDER_HTML and "render" not in meta:
        add_lines.append("  render: html"); changed.append("render")
    if "status" not in meta:
        add_lines.append("  status: active"); changed.append("status")
    if not changed:
        return "OK"

    block = "\n".join(add_lines)
    if re.search(r"^metadata:\s*$", raw_fm, re.MULTILINE):
        # 插在 metadata: 區塊尾（frontmatter 結尾或下一個頂層 key 之前）
        lines = raw_fm.split("\n")
        idx = next(i for i, ln in enumerate(lines) if re.match(r"^metadata:\s*$", ln))
        end = idx + 1
        while end < len(lines) and (lines[end].startswith((" ", "\t")) or not lines[end].strip()):
            end += 1
        lines.insert(end, block)
        new_fm = "\n".join(lines)
    else:
        new_fm = raw_fm.rstrip("\n") + "\nmetadata:\n  author: paddyyang\n" + block

    if not dry:
        path.write_text(m.group(1) + new_fm + m.group(3) +
                        text[m.end():], encoding="utf-8")
    return "+" + ",".join(changed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    repo = Path(args.repo)
    for d in sorted(repo.iterdir()):
        sk = d / "SKILL.md"
        if d.is_dir() and d.name.startswith("ark-") and sk.exists():
            print(f"{d.name}: {backfill_one(sk, args.dry_run)}")


if __name__ == "__main__":
    main()

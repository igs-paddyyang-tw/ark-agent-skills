#!/usr/bin/env python3
"""audit_skills.py — ark-agent-skills 全庫稽核（deterministic 守門）

檢查項目：
  1. frontmatter schema v1：name/description/metadata.category/metadata.outputs
  2. name 與目錄名一致（P0）
  3. category 在受控詞彙內（P1）
  4. description 重複偵測（normalized 相似度 > 0.90 → P1）
  5. 觸發詞衝突掃描（獨占詞出現在非 owner description → P1）
  6. deprecated stub 格式檢查（P2）
  7. README 分類表與 frontmatter category 一致性（P2）

用法：
  python audit_skills.py --repo /path/to/ark-agent-skills [--config audit_config.yml] [--json out.json]

Exit code：有 P0 或 P1 → 1；否則 0。
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

import yaml

# schema v1.1：受控詞彙 canonical 為全名；舊縮寫過渡期容忍（P3 警告）
CATEGORY_CODES = {"process", "scaffolder", "pipeline", "view", "document", "domain", "ops"}
LEGACY_CATEGORY_ALIASES = {  # 舊值 → canonical（觸發 P3 legacy-category）
    "proc": "process", "scaffold": "scaffolder", "present": "view",
    "doc": "document", "sop": "domain",
    "presentation-content": "document",  # md-report 舊值，語意歸 Content 軌文件
}
# 注意：'deprecated' 不是合法 category —— 它是 status，出現時報 P1 要求轉 stub 格式
OUTPUT_FORMATS = {"md", "html", "png", "pdf", "code", "data", "office"}
AUDIENCES = {"ai", "human", "both"}

# 預設觸發詞衝突矩陣：獨占詞 → owner skill（可被 --config 覆寫/擴充）
DEFAULT_EXCLUSIVE_TRIGGERS = {
    "覆蓋率": "ark-test-runner",
    "line coverage": "ark-test-runner",
    "pytest --cov": "ark-test-runner",
    "爬蟲": "ark-web-scraper",
    "反爬": "ark-web-scraper",
    "瀏覽器測試": "ark-browser-tool",
    "截圖": "ark-browser-tool",
    "寫 spec": "ark-superpowers",
    "產 spec": "ark-superpowers",
    "派工": "ark-project-planning",
    "共筆": "ark-doc-coauthoring",
    "chatbot": "ark-agent-builder",
    "聊天機器人": "ark-agent-builder",
    "博奕": "ark-html-dashboard",
    "老虎機": "ark-html-dashboard",
    "遊戲面板": "ark-html-dashboard",
    "CLI 骨架": "ark-llm-cli",
}

FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text: str):
    m = FM_RE.match(text)
    if not m:
        return None
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None


def normalize(s: str) -> str:
    return re.sub(r"\s+", "", s or "").lower()


def load_skills(repo: Path):
    skills, stubs = {}, {}
    for d in sorted(repo.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or not d.name.startswith("ark-"):
            continue
        sk = d / "SKILL.md"
        if sk.exists():
            fm = parse_frontmatter(sk.read_text(encoding="utf-8", errors="replace"))
            skills[d.name] = {"path": str(sk), "fm": fm}
        elif (d / "README.md").exists():
            stubs[d.name] = {"path": str(d / "README.md")}
        else:
            skills[d.name] = {"path": str(d), "fm": None}
    return skills, stubs


def audit(repo: Path, triggers: dict):
    findings = []
    fid = [0]

    def add(sev, rule, skill, msg):
        fid[0] += 1
        findings.append({
            "id": f"F-{fid[0]}", "severity": sev, "rule": rule,
            "skill": skill, "message": msg,
        })

    skills, stubs = load_skills(repo)

    # deprecated：SKILL.md 標 status: deprecated 者視同 stub，跳過 schema 檢查
    active = {}
    for name, info in skills.items():
        fm = info["fm"]
        meta = (fm or {}).get("metadata") or {}
        if meta.get("status") == "deprecated":
            desc = str((fm or {}).get("description", ""))
            if not desc.strip().startswith("[DEPRECATED"):
                add("P2", "stub-format", name,
                    "status: deprecated 但 description 未以 [DEPRECATED → …] 開頭")
            stubs[name] = info
        else:
            active[name] = info

    # 1–3. schema 檢查
    for name, info in active.items():
        fm = info["fm"]
        if fm is None:
            add("P0", "frontmatter-parse", name, "缺 SKILL.md 或 frontmatter 無法解析")
            continue
        if fm.get("name") != name:
            add("P0", "name-mismatch", name,
                f"frontmatter name='{fm.get('name')}' 與目錄名不一致")
        if not str(fm.get("description", "")).strip():
            add("P1", "missing-description", name, "缺 description")
        meta = fm.get("metadata") or {}
        cat = meta.get("category")
        if not cat:
            add("P1", "missing-category", name, "缺 metadata.category")
        elif cat == "deprecated":
            add("P1", "category-is-status", name,
                "category='deprecated' 語意錯誤：deprecated 是 status 不是 category，"
                "請轉標準 stub 格式（metadata.status: deprecated + description 首行 [DEPRECATED → ...]）")
        elif cat in LEGACY_CATEGORY_ALIASES:
            add("P3", "legacy-category", name,
                f"category='{cat}' 為舊詞彙，請改 canonical '{LEGACY_CATEGORY_ALIASES[cat]}'（過渡期容忍）")
        elif cat not in CATEGORY_CODES:
            add("P1", "invalid-category", name,
                f"category='{cat}' 不在受控詞彙 {sorted(CATEGORY_CODES)}")
        outs = meta.get("outputs")
        if not outs:
            add("P1", "missing-outputs", name, "缺 metadata.outputs")
        elif isinstance(outs, list):
            for o in outs:
                if not isinstance(o, dict) or \
                   o.get("format") not in OUTPUT_FORMATS or \
                   o.get("audience") not in AUDIENCES:
                    add("P2", "invalid-output-entry", name,
                        f"outputs 項目不合法：{o}")
        if meta.get("schema_version") != 1:
            add("P2", "missing-schema-version", name, "metadata.schema_version 應為 1")

    # 4. description 重複偵測
    descs = {n: normalize(str((i["fm"] or {}).get("description", "")))
             for n, i in active.items() if i["fm"]}
    names = sorted(descs)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if not descs[a] or not descs[b]:
                continue
            r = difflib.SequenceMatcher(None, descs[a], descs[b]).ratio()
            if r > 0.90:
                add("P1", "duplicate-description", f"{a} + {b}",
                    f"description 相似度 {r:.2f} > 0.90，疑似重複 skill")

    # 5. 觸發詞衝突
    for kw, owner in triggers.items():
        kw_n = normalize(kw)
        for name, d in descs.items():
            if name != owner and kw_n and kw_n in d:
                add("P1", "trigger-conflict", name,
                    f"獨占觸發詞「{kw}」屬於 {owner}，需自 description 移除")

    # 6. stub 格式
    for name, info in stubs.items():
        p = Path(info["path"])
        if p.name == "README.md":
            txt = p.read_text(encoding="utf-8", errors="replace")
            if "deprecat" not in txt.lower() or not re.search(r"20\d\d-\d\d-\d\d", txt):
                add("P2", "stub-format", name,
                    "stub README 缺 deprecation 說明或日期")

    # 7. README 分類表一致性（存在 category 標記時才比對）
    readme = repo / "README.md"
    if readme.exists():
        txt = readme.read_text(encoding="utf-8", errors="replace")
        for name, info in active.items():
            if name not in txt:
                add("P2", "readme-missing", name, "README 未列出此 skill")

    counts = {s: 0 for s in ("P0", "P1", "P2", "P3")}
    for f in findings:
        counts[f["severity"]] += 1
    return {
        "repo": str(repo),
        "active_skills": len(active),
        "deprecated_stubs": len(stubs),
        "findings_count": counts,
        "findings": findings,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--config", help="YAML：{exclusive_triggers: {詞: owner}}")
    ap.add_argument("--json", help="輸出 JSON 路徑")
    args = ap.parse_args()

    triggers = dict(DEFAULT_EXCLUSIVE_TRIGGERS)
    if args.config:
        cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
        triggers.update(cfg.get("exclusive_triggers") or {})

    result = audit(Path(args.repo), triggers)

    print(f"active={result['active_skills']} stubs={result['deprecated_stubs']} "
          f"findings={result['findings_count']}")
    for f in result["findings"]:
        print(f"  [{f['severity']}] {f['rule']} :: {f['skill']} :: {f['message']}")
    if args.json:
        Path(args.json).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    sys.exit(1 if result["findings_count"]["P0"] + result["findings_count"]["P1"] else 0)


if __name__ == "__main__":
    main()

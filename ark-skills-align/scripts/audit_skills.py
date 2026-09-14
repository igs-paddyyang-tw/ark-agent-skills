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
  8. empty-skill-dir：目錄存在但無有效內容或 SKILL.md < 5 行（P2）
  9. dangling-desc-ref：description **文字內容**裡的 ark-* 必須存在（P1）
 10. missing-e2e-test：scaffolder/executor 有可執行 script 就必須有測試（P1）

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
# 'executor'（2026-09-04 補登記）：捆綁可執行 scripts/、agent 直接以 bash 呼叫的 skill
# （非「產碼食譜」）。新增 category 必須同時登記到 scripts/gen_readme.py 的 SECTIONS，
# 否則該 skill 會落到 README 的「⚠️ 未分類」一節。
CATEGORY_CODES = {"process", "scaffolder", "pipeline", "view", "document", "domain", "ops",
                  "executor"}
LEGACY_CATEGORY_ALIASES = {  # 舊值 → canonical（觸發 P3 legacy-category）
    "proc": "process", "scaffold": "scaffolder", "present": "view",
    "doc": "document", "sop": "domain",
    "presentation-content": "document",  # md-report 舊值，語意歸 Content 軌文件
}
# 注意：'deprecated' 不是合法 category —— 它是 status，出現時報 P1 要求轉 stub 格式
OUTPUT_FORMATS = {"md", "html", "png", "pdf", "code", "data", "office"}
#: 合法 schema_version（字串比對 —— frontmatter 寫 1 是 int、1.1 會被 YAML 讀成 str）
SCHEMA_VERSIONS = {"1", "1.1"}
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
    "chatbot": "ark-agent-bot-builder",
    "聊天機器人": "ark-agent-bot-builder",
    "博奕": "ark-html-dashboard",
    "老虎機": "ark-html-dashboard",
    "遊戲面板": "ark-html-dashboard",
    # 🔴 owner 曾寫 ark-llm-cli —— 那個 skill 已被 ark-agent-cli 取代並移除，
    #    於是這條規則實際上「永遠不會有 owner 命中」→ 只要有人在 description
    #    寫「CLI 骨架」就會被判衝突，而真正的 owner 反而也會被判。
    #    現在 unknown-trigger-owner（P2）會擋住這種死 owner。
    "CLI 骨架": "ark-agent-cli",
}

#: description 裡容許出現、但不是 skill 的 `ark-*` 名字（repo 名、套件名）
NON_SKILL_ARK_NAMES = {"ark-agent-skills", "ark-team-agent", "ark-bot-agent"}

#: 需要端到端測試的 category —— 它們的**產出別人會直接拿去用**，錯了會擴散
E2E_REQUIRED_CATEGORIES = {"scaffolder", "executor"}

DESC_ARK_REF_RE = re.compile(r"ark-[a-z0-9]+(?:-[a-z0-9]+)*")

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

    # 0. empty-skill-dir：目錄存在但無有效內容
    for name, info in list(skills.items()):
        sk = Path(info["path"])
        if info["fm"] is None and sk.is_dir():
            # 目錄存在但無 SKILL.md 也無 README.md
            add("P2", "empty-skill-dir", name,
                "目錄存在但無 SKILL.md 也無 README.md（空殼）")
            del skills[name]
        elif info["fm"] is not None:
            # SKILL.md 存在但內容不足 5 行
            sk_file = Path(info["path"])
            if sk_file.is_file():
                lines = sk_file.read_text(encoding="utf-8", errors="replace").splitlines()
                if len(lines) < 5:
                    add("P2", "empty-skill-dir", name,
                        f"SKILL.md 僅 {len(lines)} 行（< 5），疑似空殼或未完成")

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

    # 目錄層級的所有 skill 名稱（active + deprecated stub 都算「存在」——
    # stub 存在的目的就是讓舊名仍可被指向）
    all_names = set(active) | set(stubs)

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
        # `updated` 必填 —— 2026-09-11 加。
        #
        # 🔴 為什麼需要：本 repo 的通則是「引用超過一個月的記載前先實測確認它還成立」，
        # 而當時 **40/59 個 active skill 連 `updated` 都沒有** → 那條通則根本無法執行。
        #
        # ⚠️ 語意是「**最後修改**」，不是「最後驗證過」。回填時刻意用該 skill 目錄的
        # git 最後變更日（有來源），而**沒有**用那次全庫 frontmatter 批次回填的日期
        # （`f0e6125` 2026-08-19）—— 那會宣稱一個從未建立過的新鮮度。
        # 真正的「跑得起來嗎」由 scripts/tests/test_cli_contract.py 驗。
        if not meta.get("updated"):
            add("P2", "missing-updated", name,
                "缺 metadata.updated（語意＝最後修改日；別填批次操作的日期）")

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
        # 引用其他 skill 的欄位必須指向存在的 skill。
        #
        # [2026-09-09 新增] 這類欄位原本**完全沒有守門** —— 掃全庫交叉比對才發現
        # `ark-wiki-engine: consumed_by → ark-news-daily`（正確名是 ark-daily-news）
        # 寫錯很久沒人發現，而 paddy-bot 的 sync 清單也踩同一個名字，
        # 導致那個 skill **從來沒有被同步過**（每次只印一行「來源缺 xxx，跳過」）。
        #
        # `replaces` 刻意不驗：它的語意就是「取代了已移除的東西」，
        # 指向不存在的名字是正確的（例：ark-agent-cli replaces ark-llm-cli）。
        #
        # [2026-09-14 F-2] `consumed_by` 已廢除 —— 全庫 60 個 active skill 只有 1 個填，
        # 而 11 對 `A depends_on B` 沒有一對在 B 補了反向宣告。
        # 守門在守一個沒人維護的欄位，比沒有守門更誤導（會讓人以為依賴關係有被管理）。
        # 反向關係改由 depends_on **單向真相推導**（見 reverse_deps）。
        for ref in (meta.get("depends_on") or []):
            base = str(ref).split(".")[0].strip()
            if base.startswith("ark-") and base not in all_names:
                add("P1", "dangling-skill-ref", name,
                    f"depends_on 指向不存在的 skill：{ref}（依賴斷鏈）")
        if meta.get("consumed_by"):
            add("P3", "deprecated-field", name,
                "metadata.consumed_by 已廢除（2026-09-14）：反向關係由 depends_on 推導，"
                "請改在下游 skill 宣告 depends_on")

        if str(meta.get("schema_version")) not in SCHEMA_VERSIONS:
            add("P2", "missing-schema-version", name,
                f"metadata.schema_version 應為 {sorted(SCHEMA_VERSIONS)} 之一，"
                f"實際為 {meta.get('schema_version')!r}")

    # 3.5 description **文字內容**裡的 ark-* 必須存在
    #
    # 🔴 [2026-09-14 F-1] 為什麼是獨立一條：dangling-skill-ref 只驗 metadata 欄位，
    # 而 **agent 讀的是 description**。實例：ark-llm-tools 相鄰兩行同時寫著
    #   「CLI 整合請用 ark-llm-cli。」（已移除的舊名）
    #   「不適用於：CLI 整合/閘道開發請用 ark-agent-cli。」（正確的）
    # 有人補了對的那行但沒刪舊的 —— 同一份文件裡有新舊兩種說法時，舊的那條會被引用。
    #
    # 兩種豁免（都不是「清單」，是語意上本來就不該存在的名字）：
    #   ① 自己 metadata.replaces 列的舊名 —— 「我取代了它」本來就要提到它
    #   ② NON_SKILL_ARK_NAMES —— repo 名與套件名不是 skill
    for name, info in active.items():
        fm = info["fm"] or {}
        meta = fm.get("metadata") or {}
        allowed = {str(r).split(".")[0].strip() for r in (meta.get("replaces") or [])}
        for ref in sorted(set(DESC_ARK_REF_RE.findall(str(fm.get("description", ""))))):
            if ref in all_names or ref in allowed or ref in NON_SKILL_ARK_NAMES:
                continue
            add("P1", "dangling-desc-ref", name,
                f"description 內文指向不存在的 skill：{ref}"
                "（agent 讀的是 description —— 舊名沒刪就會被引用）")

    # 3.6 scaffolder / executor 必須有端到端測試
    #
    # 🔴 [2026-09-14 F-3] 為什麼只擋這兩類：它們的**產出別人會直接拿去用**，
    # 一個缺陷會複製到每個用它建出來的專案。實例：ark-webapp-generator 的
    # scaffold_project.py 產出**過不了自己的 validate_output.py**（缺 3 個檔），
    # 而在加這條之前沒有任何東西在跑它。
    #
    # 前提是「有東西可以跑」：只在該 skill 有非測試的 .py 時才要求
    # （ark-docker-deploy 是純食譜、0 個 script → 本規則不適用，不是豁免）。
    #
    # ⚠️ 這條的價值在於**新 skill 會自動帶上** —— 第一輪加了 `updated` 守門之後
    # 新 skill 就自動有 updated；測試沒有守門，所以新 skill 就自動沒有測試。
    for name, info in active.items():
        meta = (info["fm"] or {}).get("metadata") or {}
        if meta.get("category") not in E2E_REQUIRED_CATEGORIES:
            continue
        d = repo / name
        pys = [p for p in d.rglob("*.py") if not p.name.startswith("test_")]
        tests = [p for p in d.rglob("test_*.py")]
        if pys and not tests:
            add("P1", "missing-e2e-test", name,
                f"category={meta.get('category')} 且有 {len(pys)} 支 script，"
                "但沒有任何 test_*.py（要求：產出 → 立刻用自己的驗證器驗）")

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
    #
    # ⚠️ owner 本身必須存在 —— owner 若指向已移除的 skill，這條規則會變成
    #    「所有人都是衝突方，而沒有人是正主」（"CLI 骨架" → ark-llm-cli 就是這樣）。
    for kw, owner in sorted(triggers.items()):
        if owner not in all_names:
            add("P2", "unknown-trigger-owner", owner,
                f"觸發詞「{kw}」的 owner 不存在 —— 這條規則會把正主也判成衝突")
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

    # 反向依賴：由 depends_on 單向推導（取代已廢除的 consumed_by 欄位）
    reverse_deps: dict[str, list[str]] = {}
    for name, info in active.items():
        for ref in ((info["fm"] or {}).get("metadata") or {}).get("depends_on") or []:
            base = str(ref).split(".")[0].strip()
            reverse_deps.setdefault(base, []).append(name)
    reverse_deps = {k: sorted(v) for k, v in sorted(reverse_deps.items())}

    counts = {s: 0 for s in ("P0", "P1", "P2", "P3")}
    for f in findings:
        counts[f["severity"]] += 1
    return {
        "repo": str(repo),
        "active_skills": len(active),
        "deprecated_stubs": len(stubs),
        "findings_count": counts,
        "findings": findings,
        "reverse_deps": reverse_deps,
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

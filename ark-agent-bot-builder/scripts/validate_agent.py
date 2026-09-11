"""validate_agent.py — 驗證 ark_bot_agent 消費端骨架的**產出契約**。

用法：python validate_agent.py <project_dir>

## 為什麼不只檢查「檔案存在」

v1 只驗四件事（必要檔案／目錄存在、start.py 含 run_bot、無殘留佔位符）。
2026-09-11 實建 slot-server 時抓到 **12 條缺陷，全部通過 v1 的驗證**——
因為它們不是「東西不見了」，而是**「兩份各自演化的真相對不上」**：

- `bot.yaml` 說報告寫 `output/reports`，而 scaffold 建的是 `artifacts/reports`
- `agents.yaml` 的 `group_members` 指向從未定義的 `worker-b`
- `worker-a.dir` 指向一個 scaffold 根本不建的目錄
- `knowledge/shared/` 只有空目錄，沒有 schema.md → tags 白名單空集合
  → **fail-closed，ingest 全部被擋**

所以 v2 驗的是**交叉引用**：每個「A 說會有 B」的地方，B 是否真的在。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_FILES = ["start.py", "bot.yaml", "agents.yaml", ".env", "requirements.txt"]
REQUIRED_DIRS = [
    ".kiro/steering",
    "knowledge/shared/wiki",
    "knowledge/shared/raw",
    "knowledge/raw/memory-archive",
    "memory/daily",
    "artifacts/reports",
]
#: 知識庫五件套 —— 少了 schema.md，tags 白名單會是空集合（fail-closed，ingest 全擋）
KNOWLEDGE_FIVE = ["schema.md", "index.md", "log.md", "wiki/overview.md"]


def _load_yaml(p: Path):
    """讀 YAML；缺 pyyaml 時回 (None, 原因) 而不是靜默跳過。"""
    try:
        import yaml
    except ImportError:
        return None, "缺 pyyaml，無法驗證 YAML 交叉引用（請 pip install pyyaml）"
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")), None
    except Exception as e:                                  # noqa: BLE001
        return None, f"{p.name} 解析失敗：{type(e).__name__}: {e}"


def _whitelist_size(schema: Path) -> int:
    """算 schema.md 的 tags 白名單有幾個（與 wiki_taxonomy.load_whitelist 同規則）。

    🔴 `- ` 清單必須**緊接**在「## tags 白名單」標題後；中間插入 `>` 說明或表格
    會讓它解析成空集合，而空集合的語意是 fail-closed：**所有 tag 都不合法**。
    """
    lines = schema.read_text(encoding="utf-8").splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().startswith("#") and "tags 白名單" in ln:
            n = 0
            for nxt in lines[i + 1:]:
                s = nxt.strip()
                if not s:
                    if n:
                        break
                    continue
                if s.startswith("- "):
                    n += 1
                else:
                    break
            return n
    return 0


def validate(root: Path) -> list[str]:                      # noqa: C901
    issues: list[str] = []
    add = issues.append

    for f in REQUIRED_FILES:
        if not (root / f).is_file():
            add(f"缺檔案：{f}")
    for d in REQUIRED_DIRS:
        if not (root / d).is_dir():
            add(f"缺目錄：{d}/")

    # ── start.py 必須走套件入口 ──
    sp = root / "start.py"
    sp_text = sp.read_text(encoding="utf-8") if sp.is_file() else ""
    if sp.is_file() and "run_bot" not in sp_text:
        add("start.py 未使用 run_bot（套件入口）")

    # ── 佔位符殘留 ──
    for f in ("bot.yaml", "agents.yaml"):
        p = root / f
        if p.is_file() and "{" in p.read_text(encoding="utf-8"):
            add(f"{f} 仍有未替換的佔位符 {{...}}")

    # ── 契約 1：run_bot(skills=[...]) 指向的目錄必須真的有 SKILL.md ──
    # 指向空目錄會讓啟動橫幅永遠印「⚠️ 注入了 skills 但一個都沒載到」，
    # 而常駐假警報會讓人習慣性忽略整個橫幅。
    # 🔴 只看實際程式碼 —— 骨架的註解裡就寫著 run_bot(skills=["skills"]) 當反例，
    #    不去註解會把「叫你別這樣寫」的那行當成「你這樣寫了」。
    sp_code = "\n".join(l for l in sp_text.splitlines() if not l.lstrip().startswith("#"))
    if "skills=[" in sp_code.replace(" ", ""):
        import re
        for d in re.findall(r'["\']([^"\']+)["\']', sp_code.split("skills=[", 1)[1].split("]", 1)[0]):
            sd = root / d
            if not sd.is_dir():
                add(f"start.py 注入了 skills=['{d}']，但該目錄不存在")
            elif not list(sd.glob("*/SKILL.md")):
                add(f"start.py 注入了 skills=['{d}']，但目錄裡沒有任何 SKILL.md"
                    "（會造成永久假警報；沒有業務 skill 時請用 run_bot()）")

    # ── 契約 2：bot.yaml 的 report.md_dir 指向的目錄必須被建出來 ──
    bot_p = root / "bot.yaml"
    if bot_p.is_file():
        bot, err = _load_yaml(bot_p)
        if err:
            add(err)
        elif isinstance(bot, dict):
            md_dir = ((bot.get("report") or {}).get("md_dir") or "").strip()
            if md_dir and not (root / md_dir).is_dir():
                add(f"bot.yaml 的 report.md_dir = '{md_dir}'，但該目錄不存在"
                    "（報告會寫不出去，且不會在啟動時報錯）")
            # web_ui 與 server 段的一致性
            feats = bot.get("features") or {}
            if feats.get("web_ui") and not (bot.get("server") or {}).get("port"):
                add("features.web_ui: true 但沒有 server.port —— 會吃套件預設 port，可能撞港")

    # ── 契約 3：agents.yaml 的 dir 與 group_members 交叉引用 ──
    ag_p = root / "agents.yaml"
    if ag_p.is_file():
        ag, err = _load_yaml(ag_p)
        if err:
            add(err)
        elif isinstance(ag, dict):
            for key, val in ag.items():
                if not isinstance(val, dict):
                    continue
                d = val.get("dir")
                if d and not (root / d).is_dir():
                    add(f"agents.yaml 的 {key}.dir = '{d}'，但該目錄不存在")
                for m in (val.get("group_members") or []):
                    if m not in ag:
                        add(f"agents.yaml 的 {key}.group_members 含 '{m}'，"
                            "但 agents.yaml 沒有定義這個成員")

    # ── 契約 4：knowledge/shared 五件套齊備，且白名單解析後非空 ──
    kb = root / "knowledge" / "shared"
    if kb.is_dir():
        for f in KNOWLEDGE_FIVE:
            if not (kb / f).is_file():
                add(f"knowledge/shared/ 缺 {f}（知識庫五件套）")
        schema = kb / "schema.md"
        if schema.is_file():
            n = _whitelist_size(schema)
            if n == 0:
                add("knowledge/shared/schema.md 的 tags 白名單解析為空集合 —— "
                    "空集合是 fail-closed：所有 tag 都不合法，ingest 會全部被擋。"
                    "檢查「## tags 白名單」標題後是否**緊接** `- ` 清單")

    # ── 契約 5：每個 agent.json 的 prompt 指向的檔案要解析得到 ──
    # file:// 的基準是 .kiro/agents/，引用專案根資源要往上兩層。
    for aj in sorted(root.rglob(".kiro/agents/*.json")):
        try:
            data = json.loads(aj.read_text(encoding="utf-8"))
        except Exception as e:                              # noqa: BLE001
            add(f"{aj.relative_to(root)} 不是合法 JSON：{type(e).__name__}")
            continue
        if data.get("allowedTools") == ["*"]:
            add(f"{aj.relative_to(root)} 的 allowedTools 用了 ['*']（不被接受，請省略此欄）")
        pr = str(data.get("prompt") or "")
        if pr.startswith("file://"):
            target = (aj.parent / pr[len("file://"):]).resolve()
            if not target.is_file():
                add(f"{aj.relative_to(root)} 的 prompt 指向 '{pr}'，解析後不存在"
                    f"（file:// 基準是 .kiro/agents/，指向專案根資源要用 ../../）")

    return issues


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：python validate_agent.py <project_dir>")
        return 2
    root = Path(sys.argv[1]).resolve()
    issues = validate(root)
    if issues:
        print(f"❌ {len(issues)} 個問題：")
        for i in issues:
            print(f"   - {i}")
        return 1
    print(f"✅ 骨架完整（產出契約全數通過）：{root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

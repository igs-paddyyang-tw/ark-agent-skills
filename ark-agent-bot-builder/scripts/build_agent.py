"""build_agent.py — 產出 ark_bot_agent 消費端 Bot workspace 骨架。

定位（v3.0）：裝 wheel + 產設定檔骨架，**不手搭架構**（套件內建 runtime/UI/記憶/TG）。

用法：
    python build_agent.py <output_dir> [--name NAME] [--codename 娜娜] [--admin-chat-id ID]

產出：start.py + bot.yaml + agents.yaml + .env + requirements.txt + 目錄骨架
      （knowledge/shared + memory + artifacts）。人格 steering 交給 ark-agent-init。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# 產出目錄骨架（含三缺口：shared / memory / artifacts）
DIRS = [
    ".kiro/steering",
    "knowledge/shared/wiki",
    "knowledge/shared/raw",
    "knowledge/raw/memory-archive",
    "memory/daily",
    "artifacts/reports",
    "skills",
]

#: assets/agents.yaml 定義了哪些 agent（除了 dir="." 的 default/manager）。
#: 🔴 這份清單必須與 assets/agents.yaml 的 dir 欄位一致 —— 不一致的話
#: 產出的 agents.yaml 會指向不存在的目錄，而派工當下才會發現。
#: validate_agent.py 的「契約 3」會交叉驗證這件事。
AGENT_DIRS = ["admin-agent", "leader-agent", "worker-a-agent"]

#: 每個 agent 工作目錄底下的骨架
AGENT_SUBDIRS = [".kiro/steering", ".kiro/agents", ".kiro/settings",
                 "knowledge/raw", "memory/daily", "artifacts", "docs"]

# assets 檔名 → 產出檔名
COPY = {
    "start.py": "start.py",
    "bot.yaml": "bot.yaml",
    "agents.yaml": "agents.yaml",
    "requirements.txt": "requirements.txt",
    "env.example": ".env",
    "gitignore.txt": ".gitignore",
}


def _fill(text: str, subs: dict[str, str]) -> str:
    for k, v in subs.items():
        text = text.replace(k, v)
    return text


def _scaffold_knowledge(out: Path) -> list[str]:
    """產 knowledge/shared 的五件套（schema/index/log/wiki/overview）。

    🔴 委派給 ark-wiki-engine 的 build_wiki.py，**不要在這裡寫第二份模板** ——
    schema.md 的 tags 白名單格式很脆弱（`- ` 清單必須緊接標題），
    兩份模板各自演化的結果就是「白名單解析成空集合」，
    而空集合是 fail-closed：所有 tag 都不合法 → ingest 全部被擋、且不報錯。
    """
    engine = _find_wiki_engine()
    if engine is None:
        return []
    r = subprocess.run([sys.executable, str(engine), str(out), "shared"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return []
    return [f"knowledge/shared/{f}" for f in
            ("schema.md", "index.md", "log.md", "wiki/overview.md")]


def _find_wiki_engine() -> Path | None:
    """找同一個 skills 庫裡的 ark-wiki-engine/scripts/build_wiki.py。"""
    for base in (ASSETS.parent.parent, Path.cwd()):
        cand = base / "ark-wiki-engine" / "scripts" / "build_wiki.py"
        if cand.is_file():
            return cand
    return None


def build(out: Path, subs: dict[str, str]) -> list[str]:
    created: list[str] = []
    for d in DIRS:
        (out / d).mkdir(parents=True, exist_ok=True)
        created.append(f"{d}/")

    # agents.yaml 提到的每個 agent 目錄都要真的存在
    for a in AGENT_DIRS:
        for sub in AGENT_SUBDIRS:
            (out / "agents" / a / sub).mkdir(parents=True, exist_ok=True)
        (out / "agents" / a / ".kiro" / "settings" / "mcp.json").write_text(
            '{"mcpServers": {}}\n', encoding="utf-8")
        created.append(f"agents/{a}/")

    created += _scaffold_knowledge(out)

    for src_name, dst_name in COPY.items():
        src = ASSETS / src_name
        if not src.exists():
            continue
        content = _fill(src.read_text(encoding="utf-8"), subs)
        (out / dst_name).write_text(content, encoding="utf-8")
        created.append(dst_name)

    return created


def main() -> int:
    ap = argparse.ArgumentParser(description="產出 ark_bot_agent 消費端骨架")
    ap.add_argument("output_dir")
    ap.add_argument("--name", default="my-bot")
    ap.add_argument("--codename", default="娜娜")
    ap.add_argument("--admin-chat-id", default="0")
    args = ap.parse_args()

    out = Path(args.output_dir).resolve()
    subs = {
        "{PROJECT_NAME}": args.name,
        "{BOT_NAME}": args.name,
        "{CODENAME}": args.codename,
        "{ADMIN_CHAT_ID}": args.admin_chat_id,
    }
    created = build(out, subs)

    print(f"✅ Bot 骨架已產出：{out}")
    for c in created:
        print(f"   + {c}")
    print("\n下一步：")
    print("  1. 裝套件（🔴 extras 不可省，否則四層搜尋與排程會靜默降級）：")
    print("     uv pip install --python .venv/bin/python "
          "'<ark_bot_agent-*.whl>[search,skills]'")
    print("  2. 補人格：用 ark-agent-init 產 .kiro/steering（SOUL + AGENTS + 多 CLI 入口）")
    print("  3. 填 .env（TELEGRAM_BOT_TOKEN / GEMINI_API_KEY）")
    print("  4. 驗骨架：python validate_agent.py %s" % out)
    print("  5. 啟動：.venv/bin/python start.py  →  診斷：python -m ark_bot_agent paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

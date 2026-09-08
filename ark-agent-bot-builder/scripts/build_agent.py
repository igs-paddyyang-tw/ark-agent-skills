"""build_agent.py — 產出 ark_bot_agent 消費端 Bot workspace 骨架。

定位（v3.0）：裝 wheel + 產設定檔骨架，**不手搭架構**（套件內建 runtime/UI/記憶/TG）。

用法：
    python build_agent.py <output_dir> [--name NAME] [--codename 娜娜] [--admin-chat-id ID]

產出：start.py + bot.yaml + agents.yaml + .env + requirements.txt + 目錄骨架
      （knowledge/shared + memory + artifacts）。人格 steering 交給 ark-agent-init。
"""
from __future__ import annotations

import argparse
import shutil
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


def build(out: Path, subs: dict[str, str]) -> list[str]:
    created: list[str] = []
    for d in DIRS:
        (out / d).mkdir(parents=True, exist_ok=True)
        created.append(f"{d}/")

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
    print("  1. 裝套件：uv pip install --python .venv/bin/python <ark_bot_agent-*.whl>")
    print("  2. 補人格：用 ark-agent-init 產 .kiro/steering（SOUL + AGENTS + 多 CLI 入口）")
    print("  3. 填 .env（TELEGRAM_BOT_TOKEN / GEMINI_API_KEY）")
    print("  4. 啟動：.venv/bin/python start.py  →  診斷：python -m ark_bot_agent paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

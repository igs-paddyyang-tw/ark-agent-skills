"""Session 啟動時生成 recent.md：合併今+昨 daily log 作為 context。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

# recent.md 的 token 上限（以字元粗估：1 token ≈ 2 中文字 or 4 英文字元）
MAX_CHARS = 8000  # ~4000 tokens


def prepare_recent(agent_name: str, agents_dir: Path | None = None) -> Path:
    """合併今+昨 daily log → 寫入 memory/recent.md，回傳檔案路徑。

    如果今天沒有 daily log，往前回溯最多 7 天。
    合計超過 MAX_CHARS 時，昨日內容先截斷。
    """
    if agents_dir is None:
        agents_dir = Path(__file__).resolve().parents[2] / "agents"

    memory_dir = agents_dir / agent_name / "memory"
    daily_dir = memory_dir / "daily"
    recent_file = memory_dir / "recent.md"

    today = datetime.now().date()
    today_content = _read_daily(daily_dir, today)
    yesterday_content = ""

    # 回溯找昨天（或更早）的 daily
    for i in range(1, 8):
        past_date = today - timedelta(days=i)
        content = _read_daily(daily_dir, past_date)
        if content:
            yesterday_content = content
            break

    # 組合
    parts: list[str] = ["# 最近經驗\n"]
    parts.append(f"> 自動生成於 {datetime.now().strftime('%Y-%m-%d %H:%M')}，供 session context 使用。\n")

    if today_content:
        parts.append(f"## 今天（{today}）\n")
        parts.append(today_content)

    if yesterday_content:
        # 計算剩餘空間
        current_len = sum(len(p) for p in parts)
        remaining = MAX_CHARS - current_len
        if remaining > 200:
            if len(yesterday_content) > remaining:
                yesterday_content = yesterday_content[:remaining] + "\n\n（...已截斷）"
            past_label = (today - timedelta(days=1)).isoformat()
            parts.append(f"\n## 前次（{past_label}）\n")
            parts.append(yesterday_content)

    if not today_content and not yesterday_content:
        parts.append("\n（尚無記錄）\n")

    output = "\n".join(parts)
    recent_file.write_text(output, encoding="utf-8")
    log.info("recent.md updated for %s (%d chars)", agent_name, len(output))
    return recent_file


def _read_daily(daily_dir: Path, date) -> str:
    """讀取指定日期的 daily log，不存在回傳空字串。"""
    filename = f"{date.isoformat()}.md"
    filepath = daily_dir / filename
    if filepath.exists():
        return filepath.read_text(encoding="utf-8")
    return ""


# CLI 入口：python -m src.memory.prepare_context --agent coder-agent
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate recent.md for an agent")
    parser.add_argument("--agent", required=True, help="Agent name (e.g. coder-agent)")
    parser.add_argument("--agents-dir", default=None, help="Path to agents/ directory")
    args = parser.parse_args()

    agents_path = Path(args.agents_dir) if args.agents_dir else None
    result = prepare_recent(args.agent, agents_path)
    print(f"✅ Generated: {result}")

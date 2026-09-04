#!/usr/bin/env python3
"""weknora_agent_chat.py — 走 WeKnora /agent-chat（智能體問答）。

範圍由 agent 配置決定（agent 自己找它綁定的知識庫），適合 ReAct 多步推理、工具、web search。
查「指定的自建知識庫」請改用 weknora_kb_chat.py。

用法：
  python weknora_agent_chat.py --query "海狗機 RTP 是多少"
  python weknora_agent_chat.py --query "..." --agent-id <id> --new-session
  python weknora_agent_chat.py --query "..." --kb-id kb1 --kb-id kb2   # 動態覆蓋 agent 的 KB 範圍

env：WEKNORA_API_URL / WEKNORA_API_KEY / WEKNORA_AGENT_ID
輸出：{answer, references, session_id, agent_id} envelope。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _weknora_chat import chat, emit_error, emit_success, resolve_kb

_DEFAULT_AGENT_ID = "0d9333e6-6c9b-4210-a519-59b7cfaa00eb"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--query", required=True)
    p.add_argument("--agent-id", default="", help="智能體 ID；未帶用 WEKNORA_AGENT_ID")
    p.add_argument("--kb-id", action="append", default=[],
                   help="可選：動態覆蓋 agent 的知識庫範圍（別名或 UUID，可多個）")
    p.add_argument("--session-id", default=None, help="續接既有 session")
    p.add_argument("--new-session", action="store_true", help="開新 session（不帶 session-id）")
    args = p.parse_args()

    agent_id = args.agent_id or os.getenv("WEKNORA_AGENT_ID", _DEFAULT_AGENT_ID)
    if not agent_id:
        emit_error("BAD_INPUT", "未指定 agent-id", "帶 --agent-id 或設 WEKNORA_AGENT_ID")

    payload = {"query": args.query, "agent_id": agent_id}
    if args.kb_id:
        payload["knowledge_base_ids"] = [resolve_kb(k) for k in args.kb_id]

    sid = None if args.new_session else args.session_id
    answer, refs, session_id, elapsed = chat("agent-chat", payload, sid, collect_refs=True)
    if not answer.strip():
        emit_error("RUNTIME", "WeKnora 回覆為空", "確認 agent 已配置模型與知識庫")
    emit_success(
        {"answer": answer, "references": refs, "session_id": session_id, "agent_id": agent_id},
        {"elapsed_ms": elapsed, "ref_count": len(refs)},
    )


if __name__ == "__main__":
    main()

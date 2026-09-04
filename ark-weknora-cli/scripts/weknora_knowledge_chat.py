#!/usr/bin/env python3
"""weknora_kb_chat.py — 走 WeKnora /knowledge-chat（知識庫純 RAG）。

範圍由請求指定的知識庫決定（不綁 agent）。這是「查自建知識庫」的正確路徑。
--kb-id 接受兩種輸入：kb_registry.json 的別名（自動解析成 UUID）或直接 UUID（fallback）。
可帶多個 --kb-id 跨庫檢索；未帶則用 WEKNORA_KB_ID。

用法：
  python weknora_kb_chat.py --query "玩家畫像系統有幾個模組" --kb-id player-profile
  python weknora_kb_chat.py --query "..." --kb-id a32f7777-...            # 直接 UUID
  python weknora_kb_chat.py --query "..." --kb-id player-profile --kb-id other-kb
  python weknora_kb_chat.py --query "..." --new-session

env：WEKNORA_API_URL / WEKNORA_API_KEY / WEKNORA_KB_ID
輸出：{answer, references(citation), session_id, kb_ids} envelope。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _weknora_chat import chat, emit_error, emit_success, resolve_kb


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--query", required=True)
    p.add_argument("--kb-id", action="append", default=[],
                   help="知識庫別名或 UUID（可多個跨庫）；未帶用 WEKNORA_KB_ID")
    p.add_argument("--session-id", default=None, help="續接既有 session")
    p.add_argument("--new-session", action="store_true", help="開新 session")
    args = p.parse_args()

    raw = args.kb_id or ([os.getenv("WEKNORA_KB_ID")] if os.getenv("WEKNORA_KB_ID") else [])
    if not raw:
        emit_error("BAD_INPUT", "未指定知識庫", "帶 --kb-id <別名|UUID> 或設 WEKNORA_KB_ID")
    kb_ids = [resolve_kb(k) for k in raw]

    payload = {"query": args.query, "knowledge_base_ids": kb_ids}
    sid = None if args.new_session else args.session_id
    answer, refs, session_id, elapsed = chat("knowledge-chat", payload, sid, collect_refs=True)
    if not answer.strip():
        emit_error("RUNTIME", "WeKnora 回覆為空", "確認該 KB 有已解析（completed）的知識")
    emit_success(
        {"answer": answer, "references": refs, "session_id": session_id, "kb_ids": kb_ids},
        {"elapsed_ms": elapsed, "ref_count": len(refs)},
    )


if __name__ == "__main__":
    main()

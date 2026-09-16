#!/usr/bin/env python3
"""fake_client.py — W0 回歸測試用的假底層客戶端。

模擬 weknora_agent_chat.py / weknora_knowledge_chat.py 的 stdout envelope，
不連 WeKnora。回放內容由環境變數 FAKE_ENVELOPE（JSON 字串）提供。
用途：讓 weknora_sql_query.py 在無服務、無 cwd 相依的情況下可被 deterministic 測試。

被測腳本以 ARK_WEKNORA_CMD="python <this> " 覆蓋 default_cmd 後呼叫；
本腳本忽略所有 --query/--session-id 等參數，直接印出 FAKE_ENVELOPE。
"""
from __future__ import annotations

import json
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main() -> int:
    envelope = os.environ.get("FAKE_ENVELOPE", "")
    if not envelope:
        # 預設：一個帶 1 筆 reference 的成功回應
        envelope = json.dumps({
            "success": True,
            "data": {"answer": "營收為 12345 USD", "references": [
                {"knowledge_title": "caliber:daily-revenue",
                 "knowledge_id": "kid-1", "score": 4.0, "chunk_index": 0}],
             "session_id": "sess-1"},
            "meta": {"ref_count": 1, "elapsed_ms": 10},
        })
    print(envelope)
    return 0


if __name__ == "__main__":
    sys.exit(main())

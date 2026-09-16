#!/usr/bin/env python3
"""test_w0.py — ark-weknora-cli v2 W0 止血回歸測試。

不需要 WeKnora 服務：以 ARK_WEKNORA_CMD 覆蓋底層客戶端為 fake_client.py，
回放錄製 envelope。驗證 cwd 相依（AC-410）與 references 信任訊號（AC-411）。

執行：pytest .kiro/skills/ark-weknora-cli/tests/test_w0.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL / "scripts"
FAKE = SKILL / "tests" / "fake_client.py"
REPO_ROOT = SKILL.parents[2]  # <root>/.kiro/skills/ark-weknora-cli → <root>


def _run(script: str, argv: list[str], envelope: dict | None, cwd: Path) -> subprocess.CompletedProcess:
    """從指定 cwd 呼叫 scripts/<script>，以 fake_client 覆蓋底層客戶端。"""
    env = dict(os.environ)
    env["ARK_WEKNORA_CMD"] = f"{sys.executable} {FAKE}"
    if envelope is not None:
        env["FAKE_ENVELOPE"] = json.dumps(envelope, ensure_ascii=False)
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script)] + argv,
        capture_output=True, encoding="utf-8", env=env, cwd=str(cwd),
    )


def _envelope(answer: str, refs: list[dict]) -> dict:
    return {
        "success": True,
        "data": {"answer": answer, "references": refs, "session_id": "s1"},
        "meta": {"ref_count": len(refs), "elapsed_ms": 5},
    }


# ── AC-410：cwd 相依修正 ──────────────────────────────────────────────

def test_route_query_from_repo_root_not_exit4():
    """AC: AC-410 — 從專案根執行 route_query.py 不因 cwd 出現 exit 4（找不到檔案）。"""
    ref_env = _envelope("營收 12345 USD", [{"knowledge_title": "t", "knowledge_id": "k", "chunk_index": 0, "score": 4.0}])
    proc = _run("route_query.py", ["--query", "2026-08-30 昨日營收是多少 USD"], ref_env, cwd=REPO_ROOT)
    # 不得是「找不到檔案」造成的降級：stdout 應是合法 JSON 決策，且底層被成功呼叫到
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert "can't open file" not in json.dumps(out), f"cwd 相依未修：{out}"
    assert proc.returncode != 4, f"從專案根執行不應 exit 4，實際 {proc.returncode}：{out}"


def test_sql_query_from_repo_root_reaches_client():
    """AC: AC-410 — 從專案根直接呼叫 weknora_sql_query.py，底層客戶端可被定位（非 exit 4 cwd 錯）。"""
    proc = _run("weknora_sql_query.py", ["--query", "test", "--mode", "direct"],
                _envelope("純敘事回答，無數字", []), cwd=REPO_ROOT)
    out = json.loads(proc.stdout.strip())
    assert "can't open file" not in json.dumps(out["flags"]), f"cwd 相依未修：{out['flags']}"
    # 非數字回答 + 無 refs → 仍可 accept（exit 0）
    assert proc.returncode == 0, f"預期 exit 0，實際 {proc.returncode}：{out}"


# ── AC-411：references 信任訊號 ───────────────────────────────────────

def test_direct_numeric_with_references_exit0():
    """AC: AC-411 — direct 模式含數字且有 references → exit 0（非一律 exit 3）。"""
    env = _envelope("2026-08-30 營收為 12345 USD",
                    [{"knowledge_title": "caliber", "knowledge_id": "k1", "chunk_index": 0, "score": 4.0}])
    proc = _run("weknora_sql_query.py", ["--query", "q", "--mode", "direct"], env, cwd=REPO_ROOT)
    out = json.loads(proc.stdout.strip())
    assert out["ref_count"] == 1, f"應讀到 1 筆 reference：{out}"
    assert "kb_citation_present" in out["flags"], f"應標記有引用：{out['flags']}"
    assert proc.returncode == 0, f"含數字且有引用應 exit 0，實際 {proc.returncode}：{out}"


def test_direct_numeric_no_references_exit3():
    """AC: AC-411 — 反證：direct 模式含數字但無 references → exit 3（reverify）。"""
    env = _envelope("2026-08-30 營收為 12345 USD", [])  # 無 references
    proc = _run("weknora_sql_query.py", ["--query", "q", "--mode", "direct"], env, cwd=REPO_ROOT)
    out = json.loads(proc.stdout.strip())
    assert out["ref_count"] == 0, f"應為 0 筆 reference：{out}"
    assert "numeric_without_citation_must_reverify" in out["flags"], f"應標記須重驗：{out['flags']}"
    assert proc.returncode == 3, f"含數字但無引用應 exit 3，實際 {proc.returncode}：{out}"


def test_sqlonly_with_references_accepts_sources():
    """AC: AC-411 — sql-only 模式：內層有 SQL 且有 references → exit 0。"""
    inner = json.dumps({"answer": "營收 12345", "sql": "SELECT SUM(x) FROM t WHERE d='2026-08-30'",
                        "caliber": "台灣時間切日", "sources": [], "confidence": "high"}, ensure_ascii=False)
    env = _envelope(inner, [{"knowledge_title": "caliber", "knowledge_id": "k1", "chunk_index": 0, "score": 4.0}])
    proc = _run("weknora_sql_query.py", ["--query", "q", "--mode", "sql-only"], env, cwd=REPO_ROOT)
    out = json.loads(proc.stdout.strip())
    assert out["sql"].startswith("SELECT"), f"應解析出 SQL：{out}"
    assert proc.returncode == 0, f"SQL 過門且有 references 應 exit 0，實際 {proc.returncode}：{out}"

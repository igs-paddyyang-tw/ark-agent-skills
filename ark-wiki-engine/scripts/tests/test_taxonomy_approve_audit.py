"""反證測試 —— wiki_taxonomy approve 的稽核軌跡（aidev-agent 回報 F-6）

## 回報的問題（修前這些測試必須紅）

- F-6（P1）：`approve` 是治理關鍵動作，卻無 `--by`、不自動寫 log.md；
  相對地 `propose` 有 `--by`。approve 後 log.md 無記錄 → 治理動作無稽核軌跡。

修法：cmd_approve 加 by 參數、argparse approve 子命令加 --by；
approve 成功後 append 一行到 schema 同層的 log.md（與 ingest 的 log 格式平行）。
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
TAXONOMY = SCRIPTS / "wiki_taxonomy.py"

SCHEMA_TEMPLATE = """# Schema

## tags 白名單

- existing-tag

## tags 提案佇列

| tag | 提案原因 | 提案者 | 日期 |
|---|---|---|---|
| new-tag | 測試 | qa-agent | 2026-10-01 |
"""


def _run(*args):
    r = subprocess.run([sys.executable, str(TAXONOMY), *args],
                       capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout, r.stderr


def _setup(tmp_path: Path) -> Path:
    schema = tmp_path / "schema.md"
    schema.write_text(SCHEMA_TEMPLATE, encoding="utf-8")
    return schema


def test_approve_appends_log_with_by(tmp_path):
    """F-6：approve --by 後，schema 同層的 log.md 應新增一行含 tag/by/date。"""
    schema = _setup(tmp_path)
    rc, out, err = _run("approve", "--schema", str(schema), "new-tag", "--by", "qa-agent")
    assert rc == 0, f"approve 應成功 rc=0，得 {rc}；stderr={err}"

    log = tmp_path / "log.md"
    assert log.exists(), "approve 後應自動建立/append log.md（稽核軌跡）"
    content = log.read_text(encoding="utf-8")
    assert "new-tag" in content, f"log 應記錄被核准的 tag；log={content!r}"
    assert "qa-agent" in content, f"log 應記錄執行者 by；log={content!r}"
    assert "approve" in content, f"log 應標明操作為 approve；log={content!r}"
    assert date.today().isoformat() in content, "log 應記錄日期"


def test_approve_without_by_defaults_unknown_but_still_logs(tmp_path):
    """approve 不帶 --by 時用預設 unknown，仍要寫 log（不靜默）。"""
    schema = _setup(tmp_path)
    rc, out, err = _run("approve", "--schema", str(schema), "new-tag")
    assert rc == 0
    log = tmp_path / "log.md"
    assert log.exists() and "new-tag" in log.read_text(encoding="utf-8")


def test_approve_already_whitelisted_no_duplicate_log(tmp_path):
    """tag 已在白名單 → approve 回 0 不重複寫 log（避免噪音）。"""
    schema = _setup(tmp_path)
    rc, out, err = _run("approve", "--schema", str(schema), "existing-tag", "--by", "qa-agent")
    assert rc == 0
    log = tmp_path / "log.md"
    # 已在白名單是 no-op：不應產生 approve 記錄
    if log.exists():
        assert "existing-tag" not in log.read_text(encoding="utf-8"), "已存在的 tag 不該再寫 log"


def test_approve_json_still_works_with_by(tmp_path):
    """--json 模式帶 --by 仍回合法 JSON、exit 0。"""
    import json
    schema = _setup(tmp_path)
    rc, out, err = _run("approve", "--schema", str(schema), "new-tag", "--by", "qa-agent", "--json")
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True and payload["action"] == "approve"

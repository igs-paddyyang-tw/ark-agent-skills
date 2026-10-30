"""ark-code-spec-validator 行為測試 —— run_validator.py（套件模組的薄包裝）。

## 驗什麼

本 skill 的驗證邏輯在 `ark_team_agent.code_spec_validator`（套件），skill 自己只帶一支
wrapper。SKILL.md 明文「🚫 禁止跳過驗證步驟直接回報通過」，所以 wrapper 的契約是：

1. 參數正確轉給模組（`--full`、project_root，預設 `.`）
2. 模組的 exit code **原封不動**往外傳 —— 非 0 不能被吞成 0
3. 模組不存在時必須非 0 結束（不能假裝通過）

不實際跑驗證器（本機不一定裝套件），以 monkeypatch 攔 subprocess.run 檢查組出的指令。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "run_validator.py"
MODULE = "ark_team_agent.code_spec_validator"


def _load():
    spec = importlib.util.spec_from_file_location("csv_run_validator_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def captured(monkeypatch):
    """攔截 subprocess.run：記下指令，回傳可設定的 returncode（預設 0）。"""
    box: dict = {"rc": 0}

    def fake_run(cmd, **kw):
        box["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, box["rc"])

    mod = _load()
    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    def call(*argv: str) -> int:
        monkeypatch.setattr(sys, "argv", ["run_validator.py", *argv])
        with pytest.raises(SystemExit) as ei:
            mod.main()
        return ei.value.code

    box["call"] = call
    return box


# ── 正常路徑 ─────────────────────────────────────────────────

def test_default_root_is_cwd(captured):
    """不給參數 → 以同一個 interpreter 跑模組，project_root 預設 `.`，exit 0。"""
    rc = captured["call"]()
    assert rc == 0
    assert captured["cmd"] == [sys.executable, "-m", MODULE, "."]


def test_full_flag_and_root_forwarded_in_any_order(captured):
    """`--full` 放在 root 前或後都要轉成 `-m 模組 --full <root>`。"""
    captured["call"]("--full", "proj")
    assert captured["cmd"][3:] == ["--full", "proj"]
    captured["call"]("proj", "--full")
    assert captured["cmd"][3:] == ["--full", "proj"]


# ── 反例：失敗不能被吞掉 ──────────────────────────────────────

def test_nonzero_exit_code_propagates(captured):
    """模組回報 drift（非 0）→ wrapper 必須以同一個 code 結束，不能變成 0。"""
    captured["rc"] = 3
    assert captured["call"](".") == 3


def test_missing_module_fails_loudly(tmp_path):
    """套件沒裝時真的跑 wrapper → 必須非 0，不能「看起來通過」。

    本機若已裝套件，這條就不是在測「缺模組」了 → 明說跳過。
    """
    if importlib.util.find_spec("ark_team_agent") is not None:
        pytest.skip("本機已安裝 ark_team_agent，無法測缺模組路徑")
    r = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode != 0
    assert "ark_team_agent" in r.stderr


# ── 邊界 ─────────────────────────────────────────────────────

def test_extra_positional_args_use_first_as_root(captured):
    """多個位置參數時只取第一個當 root（其餘忽略）—— 記錄現行行為，改了要有意識。"""
    captured["call"]("a", "b")
    assert captured["cmd"][3:] == ["a"]


@pytest.mark.xfail(strict=True, reason=(
    "SKILL.md 降級模式示範 `run_validator.py --target .`，但 wrapper 不認得 --target，"
    "會把字串 '--target' 當成 project_root 傳給模組（'.' 被丟掉）"))
def test_documented_target_flag_is_honoured(captured):
    """SKILL.md 寫的用法 `--target .` 應該讓 root = `.`。"""
    captured["call"]("--target", ".")
    assert captured["cmd"][3:] == ["."]

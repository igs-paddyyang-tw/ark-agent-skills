"""完成驗收（Verifier）— agent 回報後自動驗證是否通過 AC。

功能：
  - 判斷是否需要驗證（依檔案路徑 / 任務類型）
  - 執行測試（pytest）驗證產出
  - 解析測試結果，回傳結構化報告

使用方式：
  verifier = Verifier(test_dir="tests", timeout=30)
  if verifier.should_verify("src/module.py"):
      result = await verifier.verify()
      if result.passed:
          ...  # 驗收通過
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class VerifyResult:
    """驗證結果。

    Attributes:
        passed: 是否全部通過
        total: 測試總數
        failed: 失敗數
        output: 完整 stdout
        error_summary: 錯誤摘要（≤200 字）
    """
    passed: bool
    total: int = 0
    failed: int = 0
    output: str = ""
    error_summary: str = ""


class Verifier:
    """自動驗收器：跑測試套件驗證 agent 產出。

    可覆寫 should_verify() 自訂觸發條件，
    或覆寫 _build_command() 改用其他測試框架。
    """

    def __init__(self, test_dir: str = "tests", timeout: int = 30) -> None:
        self._test_dir = test_dir
        self._timeout = timeout

    def should_verify(self, file_path: str) -> bool:
        """判斷是否需要驗證。

        預設：只有 src/**/*.py 才觸發。可覆寫此方法自訂。
        """
        return file_path.startswith("src/") and file_path.endswith(".py")

    def _build_command(self) -> list[str]:
        """組裝測試指令。覆寫此方法可改用 jest / cargo test 等。"""
        return ["python", "-m", "pytest", self._test_dir, "--tb=short", "-q"]

    async def verify(self) -> VerifyResult:
        """執行測試，回傳結構化結果。"""
        cmd = self._build_command()
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self._timeout
            )
            output = stdout.decode("utf-8").strip() if stdout else ""
            err_output = stderr.decode("utf-8").strip() if stderr else ""

            if process.returncode == 0:
                total = self._parse_passed_count(output)
                return VerifyResult(passed=True, total=total, output=output)
            else:
                total, failed = self._parse_failure(output)
                error_summary = self._extract_error(output + "\n" + err_output)
                return VerifyResult(
                    passed=False, total=total, failed=failed,
                    output=output, error_summary=error_summary,
                )
        except asyncio.TimeoutError:
            return VerifyResult(passed=False, error_summary="測試超時（%ds）" % self._timeout)
        except FileNotFoundError:
            return VerifyResult(passed=False, error_summary="測試框架未安裝")
        except Exception as e:
            return VerifyResult(passed=False, error_summary="驗證錯誤: %s" % e)

    # ── 解析輔助 ─────────────────────────────────────────

    def _parse_passed_count(self, output: str) -> int:
        """從 'N passed' 提取通過數。"""
        match = re.search(r"(\d+) passed", output)
        return int(match.group(1)) if match else 0

    def _parse_failure(self, output: str) -> tuple[int, int]:
        """從 'N passed, M failed' 提取數字。"""
        passed = 0
        failed = 0
        m = re.search(r"(\d+) passed", output)
        if m:
            passed = int(m.group(1))
        m = re.search(r"(\d+) failed", output)
        if m:
            failed = int(m.group(1))
        return passed + failed, failed

    def _extract_error(self, output: str) -> str:
        """提取最關鍵的錯誤行（≤200 字）。"""
        lines = output.split("\n")
        for line in reversed(lines):
            if "FAILED" in line or "Error" in line or "assert" in line.lower():
                return line.strip()[:200]
        return lines[-1][:200] if lines else ""

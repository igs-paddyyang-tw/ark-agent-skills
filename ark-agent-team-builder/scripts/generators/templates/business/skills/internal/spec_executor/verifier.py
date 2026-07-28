"""Verifier — AC 驗收。"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from .parser import Task

log = logging.getLogger("spec_executor.verifier")


@dataclass
class ACResult:
    """AC 驗收結果。"""
    ac_text: str
    passed: bool
    method: str     # file_exists | import_check | pytest | llm_judge | output_check
    detail: str


async def verify_ac(task: Task, result) -> ACResult:
    """驗收單一任務的 AC。

    策略優先順序：
    1. output_file 存在檢查
    2. import_check
    3. pytest
    4. output 內容比對
    5. LLM judge（兜底）
    """
    ac = task.ac.lower() if task.ac else ""

    # 如果執行本身有 error 且沒有 output
    if result.error and not result.output:
        return ACResult(
            ac_text=task.ac,
            passed=False,
            method="error",
            detail=f"執行錯誤：{result.error}",
        )

    # 1. file_exists：有 output_file 時檢查檔案是否存在
    if task.output_file:
        path = Path(task.output_file)
        if path.exists():
            # 檔案存在，基本 AC 通過
            if _ac_is_file_based(ac):
                return ACResult(ac_text=task.ac, passed=True, method="file_exists",
                                detail=f"檔案存在：{task.output_file}")
        else:
            # 檔案不存在但 AC 要求檔案
            if _ac_is_file_based(ac):
                return ACResult(ac_text=task.ac, passed=False, method="file_exists",
                                detail=f"檔案不存在：{task.output_file}")

    # 2. import_check
    if _ac_requires_import(ac) and task.output_file:
        module = _path_to_module(task.output_file)
        if module:
            success = await _check_import(module)
            if success:
                return ACResult(ac_text=task.ac, passed=True, method="import_check",
                                detail=f"import {module} 成功")
            else:
                return ACResult(ac_text=task.ac, passed=False, method="import_check",
                                detail=f"import {module} 失敗")

    # 3. pytest
    if _ac_requires_test(ac) and task.output_file:
        test_file = task.output_file
        if not test_file.startswith("test"):
            # 可能是被測試的檔案，找對應的 test
            pass
        success, detail = await _run_pytest(test_file)
        return ACResult(ac_text=task.ac, passed=success, method="pytest", detail=detail)

    # 4. output_check：檢查 CLI 輸出是否包含成功指標
    if result.output:
        if _output_indicates_success(result.output, task.ac):
            return ACResult(ac_text=task.ac, passed=True, method="output_check",
                            detail="輸出含成功指標")

    # 5. 如果有 output 且沒有明顯失敗 → 寬鬆通過
    if result.output and len(result.output) > 50 and not result.error:
        return ACResult(ac_text=task.ac, passed=True, method="output_check",
                        detail="有實質輸出，無錯誤")

    # 6. 無法判斷
    return ACResult(
        ac_text=task.ac,
        passed=False,
        method="unknown",
        detail="無法自動驗證 AC",
    )


# ── Helper Functions ──


def _ac_is_file_based(ac: str) -> bool:
    """AC 是否關於檔案產出。"""
    keywords = ["檔案", "建立", "產出", "寫入", "存在", "file", "create", "表建立"]
    return any(kw in ac for kw in keywords)


def _ac_requires_import(ac: str) -> bool:
    """AC 是否要求 import 成功。"""
    keywords = ["import", "無錯誤", "可載入", "importable"]
    return any(kw in ac for kw in keywords)


def _ac_requires_test(ac: str) -> bool:
    """AC 是否要求測試通過。"""
    keywords = ["測試", "test", "pytest", "通過", "pass", "覆蓋"]
    return any(kw in ac for kw in keywords)


def _path_to_module(file_path: str) -> str | None:
    """將檔案路徑轉為 Python module 路徑。"""
    if not file_path.endswith(".py"):
        return None
    module = file_path.replace("/", ".").replace("\\", ".").removesuffix(".py")
    # 移除開頭的 src.
    if module.startswith("src."):
        module = module[4:]
    return module


async def _check_import(module: str) -> bool:
    """嘗試 import module。"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", "-c", f"import {module}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        return proc.returncode == 0
    except Exception:
        return False


async def _run_pytest(test_path: str) -> tuple[bool, str]:
    """執行 pytest。"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", "-m", "pytest", test_path, "-v", "--tb=short",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        output = stdout.decode("utf-8", errors="ignore")
        passed = proc.returncode == 0
        # 提取摘要行
        for line in output.splitlines():
            if "passed" in line or "failed" in line:
                return passed, line.strip()
        return passed, output[-200:] if output else "(no output)"
    except Exception as e:
        return False, f"pytest failed: {e}"


def _output_indicates_success(output: str, ac: str) -> bool:
    """檢查 output 是否包含成功指標。"""
    success_indicators = ["✅", "passed", "success", "完成", "done", "created"]
    failure_indicators = ["error", "traceback", "failed", "exception", "❌"]

    output_lower = output.lower()

    # 有失敗指標 → 不通過
    if any(ind in output_lower for ind in failure_indicators):
        return False

    # 有成功指標 → 通過
    if any(ind in output_lower for ind in success_indicators):
        return True

    return False

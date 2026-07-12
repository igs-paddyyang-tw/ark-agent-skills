"""execute_code — 直接執行 Python 程式碼片段。"""
from __future__ import annotations

import asyncio
from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class ExecuteCodeParams(SkillParam):
    code: str = ""
    timeout: int = 10


class ExecuteCodeSkill(BaseSkill):
    skill_id = "execute_code"
    skill_type = SkillType.PYTHON
    description = "執行 Python 程式碼片段，回傳 stdout"
    version = "1.0.0"
    input_schema = ExecuteCodeParams

    async def execute(self, params: dict) -> SkillResult:
        try:
            p = ExecuteCodeParams(**params)
            if not p.code:
                return SkillResult(success=False, error="需提供 code")
            proc = await asyncio.create_subprocess_exec(
                "python3", "-c", p.code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=p.timeout)
            out = stdout.decode("utf-8").strip()
            err = stderr.decode("utf-8").strip()
            if proc.returncode == 0:
                return SkillResult(success=True, data={"output": out or "(無輸出)", "returncode": 0})
            return SkillResult(success=False, error=f"Exit {proc.returncode}: {err[:300]}")
        except asyncio.TimeoutError:
            return SkillResult(success=False, error=f"超時（{params.get('timeout', 10)}s）")
        except Exception as e:
            return SkillResult(success=False, error=str(e))

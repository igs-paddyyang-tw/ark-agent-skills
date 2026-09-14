"""webapp-generator 端到端守門 —— 產出必須過得了本 skill 自己的驗證器。

## 為什麼需要這支

2026-09-14 加 F-3 守門時實測：`scaffold_project.py` 產完 **26/29**，
`validate_output.py` 直接紅 —— 缺 `src/skills/marketplace/__init__.py`、
`src/server/models/slot_mechanics.py`、`src/server/models/vibe_score.py`。

> 🔴 三份文件（SKILL.md、file-manifest.md、validate_output.py）都列了那 3 個檔，
> 只有產生腳本沒產。**多數決不能決定真相，但「三對一」足以指出誰沒跟上。**
> 同型於 bot-builder 那 12 條：模板與產生器兩份各自演化，沒有守門就會漂移。

另外，`validate_output.py` 的說明同時寫著 29 與 31 兩種數量 ——
手寫統計會漂，數量以清單長度為準（本檔在驗）。
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
SKILL_ROOT = SCRIPTS.parent
SCAFFOLD = SCRIPTS / "scaffold_project.py"
VALIDATE = SCRIPTS / "validate_output.py"


def _required_files() -> list[str]:
    """直接從驗證器讀清單（不 import —— 避免執行到它的 main）"""
    tree = ast.parse(VALIDATE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "REQUIRED_FILES":
            return ast.literal_eval(node.value)
    raise AssertionError("validate_output.py 找不到 REQUIRED_FILES")


@pytest.fixture()
def project(tmp_path):
    r = subprocess.run([sys.executable, str(SCAFFOLD), str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return tmp_path


# ── 端到端：產出 → 立刻驗 ──────────────────────────────────────

def test_scaffold_passes_its_own_validate(project):
    r = subprocess.run([sys.executable, str(VALIDATE), str(project)],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"產出過不了自己的 validate：\n{r.stdout}"


def test_generated_python_files_compile(project):
    """產出的 .py 必須真的能編譯 —— 語法錯的骨架比缺檔更難查

    用 compile() 不用 ast.parse()：後者**不檢查 `from __future__` 必須在最前面**
    （本 repo 2026-09-11 踩過，3 支 SyntaxError 被 ast.parse 判為正確）。
    """
    broken = []
    for py in sorted(project.rglob("*.py")):
        try:
            compile(py.read_text(encoding="utf-8"), str(py), "exec")
        except SyntaxError as e:
            broken.append(f"{py.relative_to(project)}: {e}")
    assert not broken, "\n".join(broken)


def test_scaffold_is_idempotent(project):
    """第二次跑必須 0 新增 —— 否則重跑會覆寫使用者改過的檔案"""
    r = subprocess.run([sys.executable, str(SCAFFOLD), str(project)],
                       capture_output=True, text=True)
    assert "產出 0 個檔案" in r.stdout, r.stdout


# ── 清單本身的一致性 ───────────────────────────────────────────

def test_required_list_has_no_duplicates():
    files = _required_files()
    dupes = {f for f in files if files.count(f) > 1}
    assert not dupes, f"REQUIRED_FILES 有重複項：{dupes}"


def test_docstring_count_matches_the_list():
    """🔴 手寫統計會漂：說明曾同時寫著 29 與 31，而清單是 29。

    同型於本 repo README 手寫統計漂掉那次 —— 產生器只保證自己產的那段，
    手寫區塊要另外有東西在驗。
    """
    n = len(_required_files())
    text = VALIDATE.read_text(encoding="utf-8")
    head = text[:text.index("REQUIRED_FILES")]
    stale = [tok for tok in ("29", "31") if tok != str(n) and tok in head]
    assert not stale, f"說明區塊寫著 {stale}，但清單長度是 {n}"


# ── 反證：驗證器要真的會紅 ──────────────────────────────────────

@pytest.mark.parametrize("victim", [
    "src/skills/marketplace/__init__.py",
    "src/server/models/slot_mechanics.py",
    "src/server/main.py",
])
def test_validate_actually_catches_a_missing_file(project, victim):
    (project / victim).unlink()
    r = subprocess.run([sys.executable, str(VALIDATE), str(project)],
                       capture_output=True, text=True)
    assert r.returncode == 1, f"刪了 {victim} 卻仍然通過：\n{r.stdout}"
    assert victim in r.stdout

"""Generator: Phase 1-4 功能（task lifecycle + multi-runtime + kanban + multica）"""
from pathlib import Path
import shutil

# Phase 1-4 程式碼來源（從 ai-team-agent 實際專案複製）
SOURCE_ROOT = Path(__file__).resolve().parents[5] / "ai-team-agent" / "src"
BOARD_HTML_SOURCE = Path(__file__).resolve().parents[5] / "ai-team-agent" / "apps" / "web" / "board.html"


def write_phase1_4(output_dir: Path) -> list[str]:
    """產出 Phase 1-4 新增的所有檔案。"""
    created: list[str] = []

    # Phase 1: task lifecycle
    _copy(SOURCE_ROOT / "coordinator" / "db" / "migrations" / "002_task_lifecycle.sql",
          output_dir / "src" / "coordinator" / "db" / "migrations" / "002_task_lifecycle.sql", created)
    _copy(SOURCE_ROOT / "coordinator" / "task_lifecycle.py",
          output_dir / "src" / "coordinator" / "task_lifecycle.py", created)
    _copy(SOURCE_ROOT / "coordinator" / "services" / "autopilot.py",
          output_dir / "src" / "coordinator" / "services" / "autopilot.py", created)

    # Phase 1+3: board API
    _copy(SOURCE_ROOT / "gateway" / "api" / "board.py",
          output_dir / "src" / "gateway" / "api" / "board.py", created)

    # Phase 2+4: runtime
    _copy(SOURCE_ROOT / "runtime" / "registry.py",
          output_dir / "src" / "runtime" / "registry.py", created)
    _copy(SOURCE_ROOT / "runtime" / "multica_provider.py",
          output_dir / "src" / "runtime" / "multica_provider.py", created)

    # Phase 3: board.html
    if BOARD_HTML_SOURCE.exists():
        dst = output_dir / "apps" / "web" / "board.html"
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(BOARD_HTML_SOURCE, dst)
            created.append("apps/web/board.html")

    return created


def _copy(src: Path, dst: Path, created: list[str]) -> None:
    """複製檔案（來源不存在時跳過）。"""
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(src, dst)
        created.append(str(dst.relative_to(dst.parents[2] if "src" in str(dst) else dst.parents[1])))

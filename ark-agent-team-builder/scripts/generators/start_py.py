"""Generator: start.py — 根目錄入口。"""
from pathlib import Path

CONTENT = '"""Ark Agent Platform — 入口。"""\nfrom __future__ import annotations\n\nimport asyncio\nimport sys\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).resolve().parent / "src"))\n\nfrom dotenv import load_dotenv\nload_dotenv()\n\nfrom bootstrap import main\n\nif __name__ == "__main__":\n    try:\n        asyncio.run(main())\n    except KeyboardInterrupt:\n        print("\\n平台已停止。")\n'


def write_start_py(output_dir: Path) -> None:
    (output_dir / "start.py").write_text(CONTENT, encoding="utf-8")

"""ark_layout.py — 工作區佈局判定（.ark 工具中立佈局；ark-agent-os 3.0 前雙讀）。

契約（ark-agent-os 計畫 §3）：
- 有 `.ark/ark.yaml` → `ark` 佈局，設定層在 `.ark/`
- 否則 → `legacy_kiro` 佈局，照舊用 `.kiro/`
- 只看 manifest 是否存在，不看 `.ark/` 目錄 —— 遷移到一半（只建了目錄）仍算 legacy

| 檔 | ark | legacy_kiro |
|---|---|---|
| 技能複本 | `.ark/skills/` | `.kiro/skills/` |
| 版本鎖（align_sync） | `.ark/skills.lock` | `.kiro/skills.lock.json` |
| 驗證狀態（/api/health 讀） | `.ark/runtime/skills.verify.json` | `.kiro/skills.verify.json` |

`skills.verify.json` 是機器狀態，ark 佈局放 `.ark/runtime/`（gitignore）；
套件端的讀取點要跟著改（ark-agent-os `skills_verify.py`）。
"""
from __future__ import annotations

from pathlib import Path

ARK = "ark"
LEGACY = "legacy_kiro"


def find_ark_dirs(root: Path) -> tuple[str, Path]:
    """回傳 (佈局, 設定層目錄)。"""
    root = Path(root)
    if (root / ".ark" / "ark.yaml").is_file():
        return ARK, root / ".ark"
    return LEGACY, root / ".kiro"


def skills_dir(root: Path) -> Path:
    """技能複本目錄。"""
    return find_ark_dirs(root)[1] / "skills"


def lock_path(root: Path) -> Path:
    """align_sync 版本鎖。"""
    layout, base = find_ark_dirs(root)
    return base / ("skills.lock" if layout == ARK else "skills.lock.json")


def verify_path(root: Path) -> Path:
    """align_sync verify 寫給 /api/health 的狀態檔。"""
    layout, base = find_ark_dirs(root)
    return base / "runtime" / "skills.verify.json" if layout == ARK else base / "skills.verify.json"


def layout_note(root: Path) -> str:
    """給報告輸出用的一行說明；legacy 佈局要明說，不能看起來像已遷移。"""
    layout, base = find_ark_dirs(root)
    return f"佈局 {layout}（{base.name}/）" + ("" if layout == ARK else " —— 尚未遷移到 .ark")

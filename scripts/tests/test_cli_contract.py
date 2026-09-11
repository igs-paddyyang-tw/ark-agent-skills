"""repo 級 CLI 契約守門 —— 每支 script 的 `--help` 必須安全且可用。

## 為什麼需要這支

repo 原有兩道守門（`audit_skills.py` 驗 metadata、`gen_readme --check` 驗目錄一致），
但**沒有任何東西在跑這些 script**。2026-09-11 全庫實測 74 支 CLI：

| | 數 |
|---|--:|
| `--help` 回非 0 | **16** |
| `--help` **rc=0 卻在當下目錄建檔案** | **6** |
| `--help` 因缺第三方依賴而 import 就炸 | 16 |

🔴 最嚴重的是那 6 支：它們把 `--help` 當成**輸出目錄參數**，
於是 `scaffold_project.py --help` 會產出**一整個專案骨架（47 個項目）**
到一個叫 `--help/` 的資料夾。而「先看 help」是所有人面對陌生 CLI 的第一個動作，
所有人都預期它是**唯讀**的。

> 這次分析自己就踩到：在 repo 根目錄掃描，當場產生 `--help/`（100+ 檔）
> 污染了版控目錄。**掃有副作用的東西要先隔離 cwd** —— 本測試因此一律用 tmp_path。

## 這支驗兩件事（缺一不可）

1. `--help` 的 **exit code 必須是 0** —— CI 裡 `script --help` 是最便宜的 smoke test
2. `--help` **不得在 cwd 產生任何檔案** —— help 是唯讀操作
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

#: 這些 script 在 import 期就需要第三方套件，本機沒裝 → `--help` 也跑不起來。
#:
#: 🔴 這不是「豁免」，是**分批**：本清單裡的每一支，測試仍會驗它失敗的原因
#: **確實是缺依賴**（ModuleNotFoundError/ImportError）。若它因為別的原因紅了，
#: 這支測試照樣會抓到 —— 豁免清單最常見的失敗模式就是「順便蓋掉別的問題」。
#:
#: 正解（批次 ④）：`--help` 不該需要第三方依賴（延後 import），
#: 且缺依賴時要印一行人話說明要裝什麼，而不是吐 traceback。
#: 修好一支就從這裡刪一行。
NEEDS_DEPS = {
    "ark-docx-tool/comment.py",
    "ark-mcp-builder/connections.py",
    "ark-mcp-builder/evaluation.py",
    "ark-pdf-tool/check_fillable_fields.py",
    "ark-pdf-tool/convert_pdf_to_images.py",
    "ark-pdf-tool/extract_form_field_info.py",
    "ark-pdf-tool/extract_form_structure.py",
    "ark-pdf-tool/fill_fillable_fields.py",
    "ark-pdf-tool/fill_pdf_form_with_annotations.py",
    "ark-pptx-tool/clean.py",
    "ark-pptx-tool/thumbnail.py",
    "ark-skill-creator/improve_description.py",
    "ark-skill-creator/package_skill.py",
    "ark-skill-creator/run_eval.py",
    "ark-skill-creator/run_loop.py",
    "ark-xlsx-tool/recalc.py",
}


def _scripts() -> list[str]:
    """所有 skill 的 CLI script —— **由掃描產生，不手寫清單**。

    🔴 手寫清單會漏。本 repo 記過一次：`ark-wiki-engine` 的 `--help` 測試
    參數化清單只列 8 支、實際有 10 支，而 `validate_wiki.py --help` 壞掉是
    「逐條驗完成定義」才抓到的，不是測試抓到的。
    """
    out = []
    for p in sorted(REPO.glob("*/scripts/*.py")):
        if p.name.startswith(("test_", "_")):
            continue
        out.append(f"{p.parts[-3]}/{p.name}")
    return out


SCRIPTS = _scripts()


@pytest.mark.parametrize("rel", SCRIPTS)
def test_help_is_safe_and_works(rel, tmp_path):
    """`<script> --help` → exit 0，且不在 cwd 產生任何檔案。"""
    script = REPO / rel.split("/")[0] / "scripts" / rel.split("/")[1]
    r = subprocess.run([sys.executable, str(script), "--help"],
                       cwd=tmp_path, capture_output=True, text=True, timeout=30)
    created = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))

    # ── 副作用：對每一支都適用，連 NEEDS_DEPS 也不例外 ──
    assert not created, (
        f"{rel} 執行 `--help` 在 cwd 產生了 {len(created)} 個項目：{created[:8]}\n"
        "🔴 help 是唯讀操作。這支把 --help 當成輸出目錄參數了 —— 改用 argparse。")

    if rel in NEEDS_DEPS:
        blob = (r.stderr or "") + (r.stdout or "")
        assert ("ModuleNotFoundError" in blob or "ImportError" in blob), (
            f"{rel} 在 NEEDS_DEPS 清單裡，但它這次的失敗**不是缺依賴**：\n"
            f"rc={r.returncode}\n{blob[-600:]}\n"
            "→ 要嘛它已修好（從 NEEDS_DEPS 刪掉），要嘛是新問題（要修）。")
        return

    assert r.returncode == 0, (
        f"{rel} 的 `--help` 回 {r.returncode}（應為 0）\n"
        f"{((r.stderr or '') + (r.stdout or ''))[-600:]}\n"
        "🔴 `script --help` 是 CI 裡最便宜的 smoke test，別放棄它。改用 argparse。")


def test_needs_deps_list_has_no_stale_entries():
    """NEEDS_DEPS 不得列到已不存在的 script —— 否則清單會慢慢變成謊言。"""
    missing = sorted(r for r in NEEDS_DEPS if r not in SCRIPTS)
    assert not missing, f"NEEDS_DEPS 列了不存在的 script：{missing}"

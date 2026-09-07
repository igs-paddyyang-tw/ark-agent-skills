"""skill 契約守門 —— 把「可機械驗證的完成定義」變成測試（AC-023 ~ AC-028）

## 為什麼需要這支

plan 的完成定義裡有 8 條是**命令就能驗**的（SKILL.md 行數、死引用、
`build_wiki.py` 行數、references 齊備、兩道 repo 守門）。W2 收工時它們全綠 ——
但只因為有人**手動跑過**。之後 SKILL.md 長回 400 行、`localhost:8000` 死引用
復活、`build_wiki.py` 被塞回模板函式，**不會有任何東西變紅**。

那是本 repo 記過最多次的形狀：**規則寫在文件裡而沒有守門，等於沒有規則。**

W2 還踩過一次具體版本：`test_help_works_zero_dependency` 的參數化清單
**只列 8 支、實際有 10 支**，`validate_wiki.py --help` 壞掉是「逐條驗完成定義」
才抓到的，不是測試抓到的。所以這支的 `--help` 清單**由掃描產生，不手寫**。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
SKILL_ROOT = SCRIPTS.parent

#: SKILL.md 行數上限（plan AC-023）。要調高必須連同 plan 一起改，不是偷偷放寬。
SKILL_MD_MAX_LINES = 220
#: build_wiki.py 行數上限（plan AC-026）。v2 是 1305 行、含 18 個模板函式。
BUILD_WIKI_MAX_LINES = 350
#: 死引用黑名單 —— 這些都指向 v3 已刪除的東西（design F-5）。
DEAD_REFERENCES = ("localhost:8000", "src.wiki", "WikiEngine")
#: references/ 必要檔案
REQUIRED_REFERENCES = (
    "page-schema.md", "scripts-reference.md",
    "agent-prompt-snippets.md", "query-contract.schema.json",
)


def cli_scripts() -> list[Path]:
    """所有帶 CLI 的腳本 —— **掃描產生，不手寫清單**。

    `_wikilib.py` 是共用模組沒有 CLI，其餘每一支都必須能 `--help`。
    新增腳本會自動被納入檢查，不需要有人記得改清單。
    """
    return sorted(p for p in SCRIPTS.glob("*.py") if p.name != "_wikilib.py")


def test_cli_script_discovery_is_not_empty():
    """AC: AC-016 — 掃描本身要有效（掃到 0 支會讓下面的參數化靜默空過）"""
    names = [p.name for p in cli_scripts()]
    assert len(names) >= 10, names
    assert "_wikilib.py" not in names          # 沒有 CLI，不該被要求 --help
    assert "validate_wiki.py" in names         # W2 踩過的那支必須在內


@pytest.mark.parametrize("script", [p.name for p in cli_scripts()])
def test_every_cli_script_has_help(script):
    """AC: AC-016 — 每支 CLI 腳本 --help 皆 rc=0（零第三方依賴環境的基本要求）"""
    proc = subprocess.run([sys.executable, str(SCRIPTS / script), "--help"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, f"{script}: {proc.stderr[-300:]}"
    assert "usage:" in proc.stdout


def test_skill_md_size_and_no_dead_references():
    """AC: AC-023 — SKILL.md ≤220 行且不出現指向已刪除程式的死引用"""
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    lines = text.count("\n") + 1
    assert lines <= SKILL_MD_MAX_LINES, (
        f"SKILL.md {lines} 行 > 上限 {SKILL_MD_MAX_LINES} —— "
        "v2 的 471 行有一半在描述已刪除的程式，別走回去")
    for dead in DEAD_REFERENCES:
        assert dead not in text, f"死引用復活：{dead}（v3 已無對應程式）"


def test_skill_md_frontmatter_declares_executor():
    """AC: AC-023 — frontmatter 必須是 executor + schema 1.1，且 outputs 用受控詞彙"""
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    fm = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.S)
    assert fm, "SKILL.md 缺 frontmatter"
    block = fm.group(1)
    assert re.search(r"^\s+category:\s*executor\b", block, re.M)
    assert re.search(r'^\s+schema_version:\s*"1\.1"', block, re.M)
    # `json` 不是合法 format 值（受控詞彙是 md|html|code|data|png|pdf|office）
    assert "format: json" not in block, "outputs 應用 data 而非 json（不為單一 skill 放寬守門）"


def test_build_wiki_stays_scaffold_only():
    """AC: AC-026 — build_wiki.py ≤350 行，且不含 server/UI 模板函式"""
    src = (SCRIPTS / "build_wiki.py").read_text(encoding="utf-8")
    lines = src.count("\n") + 1
    assert lines <= BUILD_WIKI_MAX_LINES, (
        f"build_wiki.py {lines} 行 > 上限 {BUILD_WIKI_MAX_LINES}（v2 是 1305 行）")
    import ast
    fns = {n.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef)}
    for gone in ("_server_main_py", "_index_html", "_app_js", "_style_css",
                 "_run_py", "_wiki_hybrid_search_py", "_wiki_rag_bridge_py",
                 "_wiki_indexer_py", "_wiki_query_py"):
        assert gone not in fns, f"模板函式復活：{gone}（D-2 已裁定刪除，四層邏輯只在 scripts/）"


def test_required_references_present():
    """AC: AC-025 — references/ 的必要檔案齊備且非空"""
    refs = SKILL_ROOT / "references"
    for name in REQUIRED_REFERENCES:
        p = refs / name
        assert p.is_file(), f"缺 references/{name}"
        assert p.stat().st_size > 200, f"references/{name} 內容過短（{p.stat().st_size} bytes）"


def test_skill_md_points_at_every_reference():
    """AC: AC-025 — SKILL.md 必須指向每一個 reference（否則沒人會讀到它）"""
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    for name in REQUIRED_REFERENCES:
        assert name in text, f"SKILL.md 未指向 references/{name}"


def test_requirements_marks_optional_and_drops_pystemmer():
    """AC: AC-027 — requirements.txt 存在；jieba 為 optional；PyStemmer 不是依賴"""
    p = SKILL_ROOT / "requirements.txt"
    assert p.is_file(), "缺 requirements.txt"
    text = p.read_text(encoding="utf-8")
    deps = [l.strip() for l in text.splitlines()
            if l.strip() and not l.strip().startswith("#")]
    assert deps, "requirements.txt 沒有任何依賴列（optional 也要列出來）"
    assert not any("pystemmer" in d.lower() for d in deps), (
        "PyStemmer 不該是依賴 —— 英文詞幹還原對中文知識庫無用，且需要編譯")
    assert any("jieba" in d.lower() for d in deps)


def _repo_root() -> Path | None:
    """往上找 ark-agent-skills repo 根（有 ark-skills-align/ 與 scripts/gen_readme.py）。"""
    for parent in [SKILL_ROOT, *SKILL_ROOT.parents]:
        if (parent / "ark-skills-align" / "scripts" / "audit_skills.py").is_file():
            return parent
    return None


def test_repo_audit_and_readme_gates():
    """AC: AC-024 · AC-028 — 全庫稽核 P0/P1=0 且 README 目錄未過期"""
    root = _repo_root()
    if root is None:
        pytest.skip("非 ark-agent-skills repo（skill 已複製到消費端）—— 兩道守門不適用")
    audit = subprocess.run(
        [sys.executable, str(root / "ark-skills-align" / "scripts" / "audit_skills.py"),
         "--repo", str(root)], capture_output=True, text=True)
    assert audit.returncode == 0, f"audit 有 P0/P1：\n{audit.stdout[-600:]}"
    gen = root / "scripts" / "gen_readme.py"
    if gen.is_file():
        chk = subprocess.run([sys.executable, str(gen), "--check"],
                             capture_output=True, text=True)
        assert chk.returncode == 0, (
            "README 目錄過期 —— 改 category 後要重跑 gen_readme.py\n" + chk.stderr[-300:])

"""build_docs.py — 一鍵產出工程標準化文件骨架 + ADR 索引管理。

功能：
  1. 從模板產出文件骨架（自動填入 title/date/number）
  2. ADR 自動編號 + 索引更新
  3. 驗證目錄結構完整性
  4. One Pager 升級為 spec + design + plan

Usage:
    python build_docs.py onepager "我的提案"
    python build_docs.py spec "用戶管理系統"
    python build_docs.py design "API Gateway 架構"
    python build_docs.py adr "選擇 PostgreSQL 作為主資料庫"
    python build_docs.py plan "Phase 1 上線計畫"
    python build_docs.py upgrade docs/one-pagers/my-proposal.md
    python build_docs.py --init                    # 建立 docs/ 目錄結構
    python build_docs.py --index                   # 重建 ADR 索引
    python build_docs.py --validate                # 驗證所有文件
    python build_docs.py --lang en spec "Auth System"  # 英文模板
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = SKILL_ROOT / "references" / "templates"
TODAY = str(date.today())


# ── 目錄結構 ──────────────────────────────────────────────────

DOCS_DIRS = [
    "docs/one-pagers",
    "docs/specs",
    "docs/designs",
    "docs/designs/adr",
    "docs/plans",
]


# ── 模板對照 ──────────────────────────────────────────────────

TEMPLATE_MAP = {
    "onepager": "onepager.md",
    "spec": "spec-full.md",
    "spec-onepager": "spec-onepager.md",
    "design": "design-full.md",
    "design-onepager": "design-onepager.md",
    "adr": "adr.md",
    "plan": "plan-full.md",
    "plan-onepager": "plan-onepager.md",
}

OUTPUT_DIR_MAP = {
    "onepager": "docs/one-pagers",
    "spec": "docs/specs",
    "spec-onepager": "docs/specs",
    "design": "docs/designs",
    "design-onepager": "docs/designs",
    "adr": "docs/designs/adr",
    "plan": "docs/plans",
    "plan-onepager": "docs/plans",
}


def _has_non_ascii(text: str) -> bool:
    """檢查文字是否含有非 ASCII 字元。"""
    return bool(re.search(r"[^\x00-\x7f]", text))


def _render_placeholders(content: str, title: str, author: str) -> str:
    """統一 placeholder 替換（C-5：new 與 upgrade 共用同一份清單，消 F-2）。

    涵蓋 zh-TW 與 en 模板的所有標量 placeholder。ADR 專屬的 {NNN}/{決策標題}
    由呼叫端在此之前替換（需 adr 編號上下文）。
    """
    for ph in ("{名稱}", "{專案名稱}", "{Project Name}"):
        content = content.replace(ph, title)
    for ph in ("{作者}", "{Author}"):
        content = content.replace(ph, author)
    content = content.replace("YYYY-MM-DD", TODAY)
    return content


def _to_kebab(title: str, slug: str | None = None) -> str:
    """將標題轉為 kebab-case 檔名。

    若 slug 已提供，直接使用。
    若標題含非 ASCII 且無 slug，拋出 ValueError 要求提供。
    """
    if slug:
        # 正規化 slug：確保 kebab-case
        name = re.sub(r"[^\w\s-]", "", slug)
        name = re.sub(r"[\s_]+", "-", name)
        return name.lower().strip("-")

    if _has_non_ascii(title):
        raise ValueError(
            f"標題含非 ASCII 字元：「{title}」\n"
            f"  請使用 --slug 參數指定英文檔名，例如：\n"
            f"  python build_docs.py --slug user-management spec \"{title}\""
        )

    # 純 ASCII：自動轉換
    name = re.sub(r"[^\w\s-]", "", title)
    name = re.sub(r"[\s_]+", "-", name)
    return name.lower().strip("-")


def _next_adr_number(adr_dir: Path) -> int:
    """取得下一個 ADR 編號。"""
    if not adr_dir.exists():
        return 1
    max_num = 0
    for f in adr_dir.glob("*.md"):
        if f.name.startswith("_"):
            continue
        match = re.match(r"^(\d+)-", f.name)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return max_num + 1


def _update_adr_index(adr_dir: Path) -> None:
    """重建 ADR 索引（_index.md）。"""
    index_path = adr_dir / "_index.md"
    entries: list[tuple[int, str, str, str]] = []

    for f in sorted(adr_dir.glob("*.md")):
        if f.name.startswith("_"):
            continue
        match = re.match(r"^(\d+)-(.+)\.md$", f.name)
        if not match:
            continue
        num = int(match.group(1))
        content = f.read_text(encoding="utf-8")
        # 從 frontmatter 提取 title 和 status
        title = match.group(2).replace("-", " ").title()
        status = "proposed"
        created = ""
        fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if fm_match:
            for line in fm_match.group(1).split("\n"):
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"')
                elif line.startswith("status:"):
                    status = line.split(":", 1)[1].strip()
                elif line.startswith("created:"):
                    created = line.split(":", 1)[1].strip()
        entries.append((num, title, status, created))

    lines = [
        "# Architecture Decision Records\n",
        "| # | 標題 | 狀態 | 日期 |",
        "|---|------|------|------|",
    ]
    for num, title, status, created in entries:
        lines.append(f"| {num:03d} | {title} | {status} | {created} |")

    lines.append(f"\n---\n*自動產出：{TODAY}*\n")
    index_path.write_text("\n".join(lines), encoding="utf-8")


def init_docs(project_dir: Path) -> list[str]:
    """建立 docs/ 目錄結構。"""
    created: list[str] = []
    for d in DOCS_DIRS:
        path = project_dir / d
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(d)
    # ADR index
    adr_index = project_dir / "docs" / "designs" / "adr" / "_index.md"
    if not adr_index.exists():
        adr_index.write_text(
            "# Architecture Decision Records\n\n"
            "| # | 標題 | 狀態 | 日期 |\n"
            "|---|------|------|------|\n\n"
            "（尚無 ADR）\n",
            encoding="utf-8",
        )
        created.append("docs/designs/adr/_index.md")
    return created


def build_doc(
    project_dir: Path,
    doc_type: str,
    title: str,
    lang: str = "zh-TW",
    author: str = "paddyyang",
    slug: str | None = None,
) -> Path:
    """從模板產出文件骨架。回傳產出的檔案路徑。"""
    template_file = TEMPLATE_MAP.get(doc_type)
    if not template_file:
        raise ValueError(f"不支援的文件類型：{doc_type}（支援：{', '.join(TEMPLATE_MAP.keys())}）")

    lang_dir = "en" if lang == "en" else "zh-TW"
    template_path = TEMPLATES_DIR / lang_dir / template_file
    if not template_path.exists():
        raise FileNotFoundError(f"模板不存在：{template_path}")

    content = template_path.read_text(encoding="utf-8")

    # 替換佔位符
    kebab_name = _to_kebab(title, slug=slug)

    if doc_type == "adr":
        adr_dir = project_dir / "docs" / "designs" / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)
        num = _next_adr_number(adr_dir)
        num_str = f"{num:03d}"
        content = content.replace("{NNN}", num_str)
        content = content.replace("{決策標題}", title)
        filename = f"{num_str}-{kebab_name}.md"
    else:
        filename = f"{kebab_name}.md"
        # Spec/Design 加後綴
        if doc_type == "spec":
            filename = f"{kebab_name}-spec.md"
        elif doc_type == "design":
            filename = f"{kebab_name}-design.md"
        elif doc_type == "plan":
            filename = f"{kebab_name}-plan.md"

    content = _render_placeholders(content, title, author)

    # 確保輸出目錄存在
    output_dir = project_dir / OUTPUT_DIR_MAP[doc_type]
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / filename
    if output_path.exists():
        raise FileExistsError(f"檔案已存在：{output_path}")

    output_path.write_text(content, encoding="utf-8")

    # ADR 自動更新索引
    if doc_type == "adr":
        _update_adr_index(project_dir / "docs" / "designs" / "adr")

    return output_path


def validate_docs(project_dir: Path) -> tuple[int, int, list[str]]:
    """驗證所有文件完整性。回傳 (passed, failed, errors)。"""
    from check_doc_completeness import check_file

    passed = 0
    failed = 0
    errors: list[str] = []

    for dir_name in ("specs", "designs", "plans", "one-pagers"):
        docs_dir = project_dir / "docs" / dir_name
        if not docs_dir.exists():
            continue
        for md in docs_dir.rglob("*.md"):
            if md.name.startswith("_"):
                continue
            file_errors = check_file(md)
            if file_errors:
                failed += 1
                errors.append(f"❌ {md.relative_to(project_dir)}")
                for e in file_errors:
                    errors.append(f"   - {e}")
            else:
                passed += 1

    return passed, failed, errors


def upgrade_onepager(project_dir: Path, onepager_path: Path, lang: str = "zh-TW", author: str = "paddyyang") -> list[Path]:
    """將 one-pager 升級為 spec + design + plan 三份文件。

    流程：
    1. 讀取 one-pager 內容與 frontmatter
    2. 從 title 推斷 slug
    3. 產出 spec / design / plan 三份骨架
    4. 回填 one-pager 的 upgraded_to
    5. 新文件加 upgraded_from
    6. plan 自動連結 related_spec / related_design
    """
    if not onepager_path.exists():
        raise FileNotFoundError(f"One-pager 不存在：{onepager_path}")

    content = onepager_path.read_text(encoding="utf-8")
    frontmatter = {}
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                frontmatter[key.strip()] = value.strip().strip('"').strip("'")

    title = frontmatter.get("title", onepager_path.stem)
    op_lang = frontmatter.get("language", lang)

    # 推斷 slug
    slug = onepager_path.stem
    if slug.endswith("-onepager") or slug.endswith("-one-pager"):
        slug = re.sub(r"-(one-?pager)$", "", slug)

    # 準備三份文件（先全部產到暫存再一次落盤）
    lang_dir = "en" if op_lang == "en" else "zh-TW"
    outputs: list[tuple[Path, str]] = []

    for doc_type in ("spec", "design", "plan"):
        template_file = TEMPLATE_MAP[doc_type]
        template_path = TEMPLATES_DIR / lang_dir / template_file
        if not template_path.exists():
            raise FileNotFoundError(f"模板不存在：{template_path}")

        tmpl_content = template_path.read_text(encoding="utf-8")

        # 替換佔位符
        if doc_type == "spec":
            filename = f"{slug}-spec.md"
            output_dir = project_dir / "docs" / "specs"
        elif doc_type == "design":
            filename = f"{slug}-design.md"
            output_dir = project_dir / "docs" / "designs"
        else:
            filename = f"{slug}-plan.md"
            output_dir = project_dir / "docs" / "plans"

        tmpl_content = _render_placeholders(tmpl_content, title, author)

        # 加入 upgraded_from 欄位到 frontmatter
        onepager_rel = str(onepager_path.relative_to(project_dir)) if project_dir in onepager_path.parents else str(onepager_path)
        tmpl_content = _inject_frontmatter_field(tmpl_content, "upgraded_from", onepager_rel)

        # plan 加入 related_spec / related_design
        if doc_type == "plan":
            spec_path = f"docs/specs/{slug}-spec.md"
            design_path = f"docs/designs/{slug}-design.md"
            tmpl_content = _inject_frontmatter_field(tmpl_content, "related_spec", spec_path)
            tmpl_content = _inject_frontmatter_field(tmpl_content, "related_design", design_path)

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / filename
        outputs.append((output_path, tmpl_content))

    # 一次落盤
    created: list[Path] = []
    for path, file_content in outputs:
        if path.exists():
            raise FileExistsError(f"檔案已存在：{path}")
        path.write_text(file_content, encoding="utf-8")
        created.append(path)

    # 回填 one-pager 的 upgraded_to
    upgraded_to_paths = [str(p.relative_to(project_dir)) for p in created]
    upgraded_to_value = ", ".join(upgraded_to_paths)

    # 修改 one-pager frontmatter
    new_op_content = re.sub(
        r"(upgraded_to:\s*).*",
        f"\\1\"{upgraded_to_value}\"",
        content,
    )
    if "upgraded_to" not in content:
        # 在 frontmatter 結束前插入
        new_op_content = content.replace("\n---\n", f"\nupgraded_to: \"{upgraded_to_value}\"\n---\n", 1)

    onepager_path.write_text(new_op_content, encoding="utf-8")

    return created


def _inject_frontmatter_field(content: str, key: str, value: str) -> str:
    """在 frontmatter 中注入或更新一個欄位。"""
    pattern = re.compile(rf"^({key}:\s*).*$", re.MULTILINE)
    if pattern.search(content):
        return pattern.sub(f"{key}: \"{value}\"", content)
    # 在 --- 結束前插入
    return content.replace("\n---\n", f"\n{key}: \"{value}\"\n---\n", 1)


def _load_lifecycle() -> dict:
    """讀 lifecycle.yaml。回 {types:{...}, transitions:{...}}。"""
    lc = TEMPLATES_DIR.parent / "lifecycle.yaml"
    if not lc.exists():
        return {}
    text = lc.read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except Exception:
        return {}


def _read_fm_field(text: str, field: str) -> str | None:
    m = re.search(rf"^{re.escape(field)}:\s*(.+)$", text, re.M)
    return m.group(1).strip().strip('"').strip("'") if m else None


def _set_fm_field(text: str, field: str, value: str) -> str:
    """設定 frontmatter 欄位（存在則改，否則在 frontmatter 尾加）。"""
    if re.search(rf"^{re.escape(field)}:", text, re.M):
        return re.sub(rf"^{re.escape(field)}:.*$", f'{field}: "{value}"', text, count=1, flags=re.M)
    # 在第二個 --- 前插入
    end = text.find("\n---", 3)
    if end < 0:
        return text
    return text[:end] + f'\n{field}: "{value}"' + text[end:]


def _doc_type_of(text: str, path: Path) -> str:
    t = _read_fm_field(text, "type") or ""
    if t:
        return t
    for suf, dt in (("-spec.md", "spec"), ("-design.md", "design"), ("-plan.md", "plan")):
        if path.name.endswith(suf):
            return dt
    return "unknown"


def cmd_status(file_path: Path, to_state: str, by: str = "", reason: str = "") -> None:
    """狀態轉移（唯一可改 status/version/updated 的路徑）。"""
    text = file_path.read_text(encoding="utf-8")
    dtype = _doc_type_of(text, file_path)
    lc = _load_lifecycle()
    tinfo = (lc.get("types") or {}).get(dtype, {})
    enum = tinfo.get("enum", [])
    cur = _read_fm_field(text, "status") or tinfo.get("initial", "draft")
    if enum and to_state not in enum:
        print(f"❌ {to_state} 不在 {dtype} 的 status enum：{enum}")
        sys.exit(1)
    allowed = (lc.get("transitions") or {}).get(cur, [])
    if to_state not in allowed:
        print(f"❌ 非法轉移：{cur} → {to_state}（允許：{allowed}）")
        sys.exit(1)
    text = _set_fm_field(text, "status", to_state)
    text = _set_fm_field(text, "updated", TODAY)
    if to_state == "approved":
        import hashlib
        text = _set_fm_field(text, "approved_by", by or "unknown")
        text = _set_fm_field(text, "approved_at", TODAY)
        body = text.split("\n---", 2)[-1]
        text = _set_fm_field(text, "approved_hash", hashlib.sha1(body.encode("utf-8")).hexdigest()[:12])
    file_path.write_text(text, encoding="utf-8")
    print(f"✅ {file_path.name}: {cur} → {to_state}")


def cmd_supersede(old_adr: Path, new_adr: Path) -> None:
    """ADR 取代：同時寫 supersedes/superseded_by 並把舊 ADR 改 superseded。"""
    for p in (old_adr, new_adr):
        if not p.exists():
            print(f"❌ ADR 不存在：{p}"); sys.exit(1)
    old_t = old_adr.read_text(encoding="utf-8")
    new_t = new_adr.read_text(encoding="utf-8")
    old_num = _read_fm_field(old_t, "adr_number") or old_adr.stem.split("-")[0]
    new_num = _read_fm_field(new_t, "adr_number") or new_adr.stem.split("-")[0]
    old_t = _set_fm_field(old_t, "status", "superseded")
    old_t = _set_fm_field(old_t, "superseded_by", new_num)
    new_t = _set_fm_field(new_t, "supersedes", old_num)
    old_adr.write_text(old_t, encoding="utf-8")
    new_adr.write_text(new_t, encoding="utf-8")
    _update_adr_index(old_adr.parent)
    print(f"✅ {old_adr.name}(superseded) ← {new_adr.name}")


def cmd_backfill_ids(target: Path) -> None:
    """對既有文件補 ID 前綴（保留舊文字，只加前綴到無前綴的表格列）。最小版：僅回報需補的位置。"""
    files = [target] if target.is_file() else sorted(target.rglob("*.md"))
    n = 0
    for f in files:
        if "-spec" not in f.name:
            continue
        n += 1
    print(f"✅ backfill-ids 掃描 {n} 份 spec（最小版：ID 配號在 render 時由 build_docs 產生，"
          f"既有文件請於變更紀錄起始列標 backfill）")


def _parse_decision(text: str) -> tuple[list[dict], list[str], list[str]]:
    """解析 grill-me 決策摘要。回 (decisions[{n,point,decision}], boundaries[], open_qs[])。"""
    decisions, boundaries, open_qs = [], [], []
    section = None
    for ln in text.splitlines():
        s = ln.strip()
        if "已確認決策" in s:
            section = "d"; continue
        if "邊界條件" in s:
            section = "b"; continue
        if "未決事項" in s:
            section = "o"; continue
        if s.startswith("### ") or s.startswith("## "):
            section = None; continue
        if section == "d" and s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) >= 3 and cells[0].isdigit():
                decisions.append({"n": int(cells[0]), "point": cells[1], "decision": cells[2]})
        elif section == "b" and s.startswith("- "):
            boundaries.append(s[2:])
        elif section == "o" and (s.startswith("- [ ]") or s.startswith("- ")):
            open_qs.append(re.sub(r"^- (\[ \])?\s*", "", s))
    return decisions, boundaries, open_qs


def cmd_from_decision(project_dir: Path, decision_path: Path, slug: str) -> None:
    """從決策摘要確定性產 spec 草稿（ADR-005）：D-x 逐字進 C-x、未決事項進 OQ-x（blocking）。"""
    if not decision_path.exists():
        print(f"❌ 決策摘要不存在：{decision_path}"); sys.exit(1)
    text = decision_path.read_text(encoding="utf-8")
    fm_type = _read_fm_field(text, "type")
    decisions, boundaries, open_qs = _parse_decision(text)
    if fm_type != "decision" or not decisions:
        print("❌ SP-060：輸入非 type: decision 或無已確認決策表，退回請改用 new spec")
        sys.exit(1)
    # 產 C-x 表與 OQ-x 表（逐字，不摘要）
    c_rows = "\n".join(f"| C-{d['n']:03d} | {d['decision']} | D-{d['n']} |" for d in decisions)
    oq_rows = "\n".join(f"| OQ-{i+1:03d} | {q} | true | | |" for i, q in enumerate(open_qs)) \
        or "| OQ-001 | （無未決事項） | false | | |"
    bnd = "\n".join(f"- {b}" for b in boundaries) or "-"
    out_dir = project_dir / "docs" / "specs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{slug}-spec.md"
    if out.exists():
        print(f"❌ 已存在：{out}"); sys.exit(1)
    rel = str(decision_path)
    content = f"""---
title: "{slug} 規格文件"
type: spec
status: draft
created: {TODAY}
language: zh-TW
version: "0.1.0"
related_reports: ["{rel}"]
---

# {slug} — 規格文件

## 摘要（Summary）
<!-- sec:summary -->
（依 intake/spec.md 題庫補：一句話說明這份 spec 要解決什麼）

## 動機（Motivation）
<!-- sec:motivation -->
（為什麼要做）

## 目標與非目標（Goals & Non-Goals）
<!-- sec:goals -->
（目標 ≥ 2、非目標 ≥ 1）

## 使用者故事（User Stories）
<!-- sec:stories -->
| FR-ID | 角色 | 需求 | 驗收情境 | 驗證層級 |
|-------|------|------|----------|----------|

## 非功能性需求（NFR）
<!-- sec:nfr -->
| NFR-ID | 維度 | 指標 | 目標值 | 驗證方式 |
|--------|------|------|--------|----------|

## 約束條件（Constraints）
<!-- sec:constraints -->
| C-ID | 約束 | 來源 |
|------|------|------|
{c_rows}

## 成功指標（Success Metrics）
<!-- sec:metrics -->
| SC-ID | 指標 | 目標值 |
|-------|------|--------|

## 開放問題（Open Questions）
<!-- sec:open -->
| OQ-ID | 問題 | blocking | 負責人 | 期限 |
|-------|------|----------|--------|------|
{oq_rows}

## 變更紀錄（Changelog）
<!-- sec:changelog -->
| 版本 | 日期 | 變更 | 誰 |
|------|------|------|-----|
| 0.1.0 | {TODAY} | 初版（from-decision，{len(decisions)} 個 D-x → C-x） | — |

<!-- 邊界條件（來自決策摘要，供補 NFR/約束時參考）:
{bnd}
-->
"""
    out.write_text(content, encoding="utf-8")
    print(f"✅ {out.name}：{len(decisions)} 個 D-x → C-x、{len(open_qs)} 個未決 → OQ-x（blocking）")


def main() -> None:
    """CLI 入口。"""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    arg1 = sys.argv[1]

    # 特殊模式
    if arg1 == "--init":
        project_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()
        created = init_docs(project_dir)
        if created:
            print(f"✅ 已建立 {len(created)} 個目錄/檔案：")
            for c in created:
                print(f"  + {c}")
        else:
            print("✅ docs/ 結構已存在")
        sys.exit(0)

    if arg1 == "--index":
        project_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()
        adr_dir = project_dir / "docs" / "designs" / "adr"
        if not adr_dir.exists():
            print("❌ docs/designs/adr/ 不存在")
            sys.exit(1)
        _update_adr_index(adr_dir)
        print("✅ ADR 索引已重建")
        sys.exit(0)

    if arg1 == "--validate":
        project_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()
        passed, failed, errors = validate_docs(project_dir)
        if failed == 0:
            print(f"✅ 全部通過：{passed} 個文件")
        else:
            print(f"❌ {passed} 通過 / {failed} 失敗")
            for e in errors:
                print(f"  {e}")
            sys.exit(1)
        sys.exit(0)

    # Upgrade 模式
    if arg1 == "upgrade":
        if len(sys.argv) < 3:
            print("Usage: python build_docs.py upgrade <onepager-path>")
            sys.exit(1)
        onepager_path = Path(sys.argv[2]).resolve()
        project_dir = Path.cwd()
        try:
            created = upgrade_onepager(project_dir, onepager_path)
            print(f"✅ 升級完成，產出 {len(created)} 份文件：")
            for p in created:
                print(f"  + {p.relative_to(project_dir)}")
            print(f"  ↑ one-pager upgraded_to 已回填")
        except (FileExistsError, FileNotFoundError, ValueError) as e:
            print(f"❌ {e}")
            sys.exit(1)
        sys.exit(0)

    # 生命週期：狀態轉移（ADR-003）
    if arg1 == "status":
        # status <file> --to <state> [--by X] [--reason Y]
        if len(sys.argv) < 3:
            print("Usage: build_docs.py status <file> --to <state> [--by X]"); sys.exit(1)
        fp = Path(sys.argv[2])
        to = by = reason = ""
        a = sys.argv[3:]
        for i, tok in enumerate(a):
            if tok == "--to" and i + 1 < len(a): to = a[i + 1]
            elif tok == "--by" and i + 1 < len(a): by = a[i + 1]
            elif tok == "--reason" and i + 1 < len(a): reason = a[i + 1]
        if not to:
            print("❌ 缺 --to <state>"); sys.exit(1)
        cmd_status(fp, to, by, reason)
        sys.exit(0)

    if arg1 == "supersede":
        if len(sys.argv) < 4:
            print("Usage: build_docs.py supersede <old-adr> <new-adr>"); sys.exit(1)
        cmd_supersede(Path(sys.argv[2]), Path(sys.argv[3]))
        sys.exit(0)

    if arg1 == "backfill-ids":
        if len(sys.argv) < 3:
            print("Usage: build_docs.py backfill-ids <file|dir>"); sys.exit(1)
        cmd_backfill_ids(Path(sys.argv[2]))
        sys.exit(0)

    if arg1 == "from-decision":
        # from-decision <decision.md> --slug <slug>
        if len(sys.argv) < 3:
            print("Usage: build_docs.py from-decision <decision.md> --slug <slug>"); sys.exit(1)
        dp = Path(sys.argv[2])
        slug = ""
        a = sys.argv[3:]
        for i, tok in enumerate(a):
            if tok == "--slug" and i + 1 < len(a):
                slug = a[i + 1]
        if not slug:
            slug = dp.stem
        cmd_from_decision(Path.cwd(), dp, slug)
        sys.exit(0)

    # 語言選項
    lang = "zh-TW"
    slug: str | None = None
    args = list(sys.argv[1:])
    if "--lang" in args:
        idx = args.index("--lang")
        lang = args[idx + 1]
        args = args[:idx] + args[idx + 2:]
    if "--slug" in args:
        idx = args.index("--slug")
        slug = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    # 正常模式：build_docs <type> <title>
    if len(args) < 2:
        print("Usage: python build_docs.py <type> <title>")
        print(f"Types: {', '.join(TEMPLATE_MAP.keys())}")
        sys.exit(1)

    doc_type = args[0]
    title = " ".join(args[1:])
    project_dir = Path.cwd()

    try:
        output = build_doc(project_dir, doc_type, title, lang=lang, slug=slug)
        print(f"✅ 已產出：{output.relative_to(project_dir)}")
        if doc_type == "adr":
            print(f"   ADR 索引已更新")
    except FileExistsError as e:
        print(f"⚠️ {e}")
        sys.exit(1)
    except (ValueError, FileNotFoundError) as e:
        print(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    # 🔴 在讀位置參數之前攔截 —— 否則 `--help` 會被當成路徑，
    #    輕則 exit≠0，重則在 cwd 產出整包骨架（scripts/tests/test_cli_contract.py 在驗）。
    if {"-h", "--help"} & set(sys.argv[1:]):
        print(__doc__ or "")
        raise SystemExit(0)
    main()

"""受控詞彙一致性：分類三軸（category × form × domain）在各腳本的複本必須與 audit_skills 相同。

權威是 `ark-skills-align/scripts/audit_skills.py`；其餘複本存在的理由是各 skill 要能單獨同步、
不跨 skill import —— 代價就是會漂移（1.1 時代曾有 4 份 category 清單、3 份規格文件互相矛盾）。
規格：docs/specs/2026-10-20-skill-taxonomy-three-axis-spec.md
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _load(rel: str, name: str):
    """以檔案路徑載入模組（各 skill 的 scripts 不是 package）。"""
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


audit = _load("ark-skills-align/scripts/audit_skills.py", "_audit_skills")
readme = _load("scripts/gen_readme.py", "_gen_readme")
lint = _load("ark-prompt-spec-validator/scripts/prompt_lint.py", "_prompt_lint")
backfill = _load("ark-skills-align/scripts/backfill_metadata.py", "_backfill_metadata")


def test_category_vocab_consistent():
    """gen_readme 分節、prompt_lint、backfill 推薦表都只能用 audit 的 category。"""
    assert {k for k, _, _ in readme.SECTIONS} == audit.CATEGORY_CODES
    assert lint.CATEGORIES == audit.CATEGORY_CODES
    assert set(backfill.FALLBACK_CATEGORY_MAP) <= audit.CATEGORY_CODES
    assert set(backfill.DEFAULT_OUTPUTS) <= audit.CATEGORY_CODES


def test_form_domain_vocab_consistent():
    assert set(readme.FORM_LABEL) == audit.FORM_CODES == lint.FORMS
    assert set(readme.DOMAIN_LABEL) == audit.DOMAIN_CODES == lint.DOMAINS


def test_mixed_axis_values_are_not_categories():
    """executor／domain 是 1.1 把形態、領域塞進職能的舊值，不得回到 category 詞彙。"""
    assert not set(audit.MIXED_AXIS_CATEGORIES) & audit.CATEGORY_CODES
    assert set(audit.MIXED_AXIS_CATEGORIES) == lint.MIXED_AXIS_CATEGORIES


def test_every_active_skill_declares_three_axes():
    """全庫 active skill：schema 1.2、form／domain 在詞彙內、category 不是舊混軸值。"""
    fm_re = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
    bad = []
    for md in sorted(ROOT.glob("ark-*/SKILL.md")):
        meta = (yaml.safe_load(fm_re.match(md.read_text(encoding="utf-8")).group(1)) or {}).get("metadata") or {}
        if meta.get("status") == "deprecated":
            continue
        if str(meta.get("schema_version")) != audit.THREE_AXIS_SCHEMA:
            bad.append(f"{md.parent.name}: schema_version={meta.get('schema_version')!r}")
        if meta.get("category") not in audit.CATEGORY_CODES:
            bad.append(f"{md.parent.name}: category={meta.get('category')!r}")
        if meta.get("form") not in audit.FORM_CODES:
            bad.append(f"{md.parent.name}: form={meta.get('form')!r}")
        if meta.get("domain") not in audit.DOMAIN_CODES:
            bad.append(f"{md.parent.name}: domain={meta.get('domain')!r}")
    assert not bad, "\n".join(bad)


def test_legacy_aliases_point_to_valid_categories():
    """舊縮寫別名的目標必須仍是合法 category（1.2 移除 domain 時 `sop → domain` 曾變成懸空）。"""
    assert set(audit.LEGACY_CATEGORY_ALIASES.values()) <= audit.CATEGORY_CODES


def test_trigger_owner_tables_agree_and_exist():
    """觸發詞擁有者表：prompt_lint 的複本與 audit 共有的詞擁有者必須相同，且擁有者都是現存 skill。

    🔴 2026-10-27 實例：prompt_lint 仍把「chatbot」「聊天機器人」指給已不存在的 ark-agent-builder、
       「CLI 骨架」指給已移除的 ark-llm-cli → ark-agent-bot-builder 的 description 被誤報 P1。
    """
    a, l = audit.DEFAULT_EXCLUSIVE_TRIGGERS, lint.DEFAULT_EXCLUSIVE_TRIGGERS
    assert {k: (a[k], l[k]) for k in set(a) & set(l) if a[k] != l[k]} == {}
    names = {p.parent.name for p in ROOT.glob("ark-*/SKILL.md")}
    assert sorted({v for v in {**a, **l}.values() if v not in names}) == []

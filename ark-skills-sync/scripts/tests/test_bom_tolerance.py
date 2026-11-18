"""3.1.0：SKILL.md 開頭有 UTF-8 BOM 不能被判壞（game 2.2.6 心跳把 99 個好的 skill 判 BROKEN）。

反證：真正壞掉的（沒有 name、沒有 frontmatter）不管有沒有 BOM 都還是 BROKEN。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audit_skills  # noqa: E402
import skilltree  # noqa: E402

GOOD = "---\nname: ark-demo\ndescription: demo\nmetadata:\n  version: \"1.0.0\"\n---\n\n# demo\n"
NO_NAME = "---\ndescription: demo\n---\n\n# demo\n"
BOM = "﻿"


def _skill(tmp: Path, name: str, text: str, crlf: bool = False) -> Path:
    d = tmp / name
    d.mkdir()
    (d / "SKILL.md").write_bytes(text.replace("\n", "\r\n" if crlf else "\n").encode("utf-8"))
    return d


def test_bom_skill_is_ok(tmp_path):
    assert skilltree.skill_state(_skill(tmp_path, "plain", GOOD)) == skilltree.OK
    assert skilltree.skill_state(_skill(tmp_path, "bom", BOM + GOOD)) == skilltree.OK
    assert skilltree.skill_state(_skill(tmp_path, "bom-crlf", BOM + GOOD, crlf=True)) == skilltree.OK


def test_really_broken_stays_broken_with_or_without_bom(tmp_path):
    assert skilltree.skill_state(_skill(tmp_path, "noname", NO_NAME)) == skilltree.BROKEN
    assert skilltree.skill_state(_skill(tmp_path, "bom-noname", BOM + NO_NAME)) == skilltree.BROKEN
    assert skilltree.skill_state(_skill(tmp_path, "bom-nofm", BOM + "# just a title\n")) == skilltree.BROKEN


def test_parse_paths_tolerate_bom(tmp_path):
    d = _skill(tmp_path, "bom", BOM + GOOD)
    assert skilltree.parse_frontmatter(BOM + GOOD).get("name") == "ark-demo"
    assert skilltree.parse_meta(d / "SKILL.md")                       # 不是 {}
    assert (audit_skills.parse_frontmatter(BOM + GOOD) or {}).get("name") == "ark-demo"

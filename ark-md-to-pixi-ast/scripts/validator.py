"""Validator — 7 項驗證規則。"""
from __future__ import annotations

import json

VALID_FONTS = {"MSDF_Bold", "MSDF_Regular", "MSDF_Mono", "MSDF_Italic", ""}


def validate(output: str) -> list[str]:
    """驗證 JSON 輸出，回傳錯誤清單（空 = 通過）。"""
    errors: list[str] = []

    # 1. json_valid
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return ["json_invalid"]

    nodes = data.get("nodes", [])

    # 2. nodes_not_empty（空輸入 → 空輸出是合法的，跳過後續檢查）
    if not nodes:
        return []

    # 3. no_nested_structure
    for i, n in enumerate(nodes):
        for v in n.values():
            if isinstance(v, (dict, list)):
                errors.append(f"node_{i}_nested_structure")
                break

    # 4. all_nodes_have_yOffset
    for i, n in enumerate(nodes):
        if "yOffset" not in n:
            errors.append(f"node_{i}_missing_yOffset")

    # 5. font_mapping_correct
    for i, n in enumerate(nodes):
        if n.get("fontFamily", "") not in VALID_FONTS:
            errors.append(f"node_{i}_invalid_font: {n.get('fontFamily')}")

    # 6. id_sequential
    for i, n in enumerate(nodes):
        expected_id = f"n{i + 1}"
        if n.get("id") != expected_id:
            errors.append(f"node_{i}_id_expected_{expected_id}_got_{n.get('id')}")

    # 7. yOffset_monotonic
    prev_y = -1
    for i, n in enumerate(nodes):
        y = n.get("yOffset", 0)
        if i > 0 and y <= prev_y:
            errors.append(f"node_{i}_yOffset_not_monotonic: {y} <= {prev_y}")
        prev_y = y

    return errors

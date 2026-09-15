#!/usr/bin/env python3
"""
profile_lint.py — role-profile.yaml 守門腳本。

用法：
  python profile_lint.py role-profile.yaml [--skills-root ../skills]
  python profile_lint.py --all-roles [--skills-root ../skills]
  python profile_lint.py --list-roles            # 導出角色一覽（唯一合法列表來源）

Exit code：0 = P0/P1 清零；1 = 有 P0/P1；2 = 檔案/參數錯誤。
依賴：pyyaml；jsonschema（選用，缺時退化為手寫必填欄位檢查）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("需要 pyyaml：pip install pyyaml", file=sys.stderr)
    sys.exit(2)

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
SCHEMA_PATH = SKILL_ROOT / "references" / "role-profile.schema.json"
ROLES_DIR = SKILL_ROOT / "assets" / "roles"

# 空話字典：出現在 voice 或 stance 即 P1（OpenClaw SOUL 指南判準：這種規則只會產生 mush）
MUSH_WORDS = ["保持專業", "全面協助", "正向體驗", "竭誠", "盡力協助", "友善且專業",
              "提供全面", "維持高品質", "professional at all times", "comprehensive assistance"]

# 立場句必須含動詞（粗略啟發：常見中文動詞／否定詞 + 英文動詞尾）
VERB_HINTS = re.compile(r"(不|先|再|必|視|當|做|寫|發|問|查|上報|拒|頂|附|給|用|改|停|留|交|走|讀|驗|"
                        r"派|定|放|接|升報|承諾|審核|回覆|處理|判|認|要|得|把|讓|以|列|代表|測|算|報|送|寫清|補|催|標|記)")


class Findings:
    def __init__(self) -> None:
        self.items: list[tuple[str, str]] = []

    def add(self, level: str, msg: str) -> None:
        self.items.append((level, msg))

    def count(self, level: str) -> int:
        return sum(1 for lv, _ in self.items if lv == level)

    def blocking(self) -> bool:
        return self.count("P0") + self.count("P1") > 0


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: 頂層必須是 mapping")
    return data


def schema_check(profile: dict, fx: Findings) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        import jsonschema  # type: ignore
    except ImportError:
        # 退化：只查必填欄位
        for key in schema["required"]:
            if key not in profile:
                fx.add("P0", f"缺必填欄位 `{key}`（jsonschema 未安裝，僅做必填檢查）")
        return
    validator = jsonschema.Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(profile), key=lambda e: list(e.path)):
        loc = ".".join(str(p) for p in err.path) or "<root>"
        fx.add("P0", f"schema 不符 @ {loc}: {err.message}")


def semantic_check(profile: dict, fx: Findings, skills_root: Path | None) -> None:
    stance = profile.get("stance") or []
    for i, s in enumerate(stance):
        if not isinstance(s, str):
            continue
        if len(s) < 12:
            fx.add("P1", f"stance[{i}] 太短（<12 字），疑似形容詞而非立場句：「{s}」")
        elif not VERB_HINTS.search(s):
            fx.add("P1", f"stance[{i}] 不含動詞，無法據以做決策：「{s}」")
        if "、" in s and len(s.replace("、", "")) < 10:
            fx.add("P1", f"stance[{i}] 是頓號串接的形容詞清單：「{s}」")
        for w in MUSH_WORDS:
            if w in s:
                fx.add("P1", f"stance[{i}] 含空話「{w}」")

    voice = profile.get("voice") or {}
    voice_text = " ".join(str(v) for v in voice.values() if not isinstance(v, list))
    for w in MUSH_WORDS:
        if w in voice_text:
            fx.add("P1", f"voice 含空話「{w}」")

    examples = profile.get("examples") or []
    has_pushback = any(
        (ex.get("kind") == "pushback") or re.search(r"(頂回|拒絕|不做|不發|不接|不能|轉給|升報)", ex.get("response", ""))
        for ex in examples if isinstance(ex, dict)
    )
    if examples and not has_pushback:
        fx.add("P1", "examples 無頂回情境（至少 1 則要展示這個角色在什麼情境會說不）")

    hard_stops = profile.get("hard_stops") or []
    does_not = set(profile.get("scope", {}).get("does_not") or [])
    for hs in hard_stops:
        if hs in does_not:
            fx.add("P2", f"「{hs}」同時在 hard_stops 與 scope.does_not——兩者權限模型不同，擇一")

    if len(profile.get("metrics") or []) < 3:
        fx.add("P2", "metrics < 3 項")
    if not profile.get("anti_patterns"):
        fx.add("P2", "anti_patterns 為空——只有立場沒有反模式，模型讀了不會自我修正")
    one_liner = profile.get("identity", {}).get("one_liner", "")
    if len(one_liner) > 40:
        fx.add("P2", f"one_liner 超過 40 字（{len(one_liner)}）")

    for path_word in ("output/",):
        blob = json.dumps(profile, ensure_ascii=False)
        if path_word in blob:
            fx.add("P1", f"出現已廢棄路徑 `{path_word}`（套件 1.2.19 起為 artifacts/）")

    if skills_root:
        for sk in profile.get("skills") or []:
            if not (skills_root / sk / "SKILL.md").exists():
                fx.add("P1", f"skills 含不存在項 `{sk}`（{skills_root}）")


def lint_file(path: Path, skills_root: Path | None) -> Findings:
    fx = Findings()
    try:
        profile = load_yaml(path)
    except Exception as e:  # noqa: BLE001
        fx.add("P0", f"讀取失敗：{e}")
        return fx
    schema_check(profile, fx)
    semantic_check(profile, fx, skills_root)
    return fx


def report(path: Path, fx: Findings) -> None:
    print(f"\n== {path} ==")
    for lv, msg in fx.items:
        print(f"  [{lv}] {msg}")
    print(f"  → P0 {fx.count('P0')} · P1 {fx.count('P1')} · P2 {fx.count('P2')}")


def list_roles() -> None:
    rows = []
    for p in sorted(ROLES_DIR.glob("*.yaml")):
        d = load_yaml(p)
        rows.append((d["role_id"], d["identity"]["emoji"], d["identity"]["one_liner"],
                     len(d.get("stance", [])), len(d.get("hard_stops", [])), ",".join(d.get("skills", []))))
    print("| role_id | emoji | one_liner | stance | hard_stops | skills |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(f"| `{r[0]}` | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("profile", nargs="?", help="role-profile.yaml")
    ap.add_argument("--all-roles", action="store_true")
    ap.add_argument("--list-roles", action="store_true")
    ap.add_argument("--skills-root", type=Path, default=None,
                    help="ark-agent-skills 根目錄；給了才檢查 skills 欄位是否存在")
    args = ap.parse_args()

    if args.list_roles:
        list_roles()
        return 0

    targets: list[Path]
    if args.all_roles:
        targets = sorted(ROLES_DIR.glob("*.yaml"))
    elif args.profile:
        targets = [Path(args.profile)]
    else:
        ap.print_help()
        return 2

    blocking = False
    for t in targets:
        fx = lint_file(t, args.skills_root)
        report(t, fx)
        blocking |= fx.blocking()
    print("\n" + ("❌ P0/P1 未清零，不得渲染" if blocking else "✅ P0/P1 清零，可渲染"))
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())

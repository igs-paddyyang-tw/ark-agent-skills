#!/usr/bin/env python3
"""gs_publish — 把 ①② 定版件從 run 目錄（output 工作檯）收進一款遊戲的 data 家：`data/slot/<slug>/{analysis, spec}`。

設計文件 game-pipeline-output-layout v2 §4 G-1。只複製、不改內容、不刪 run；每檔記 sha，供 ps_layout / 交付對帳。

  ① analysis/  ← game-analysis.yaml · kb-refs.yaml · evidence.jsonl · report/（ga_report 的 md / html）
  ② spec/      ← game-spec.v1.md · decisions.yaml · decisions-applied.json · config-spec.yaml（自 dev-spec/ 提到 spec/ 規範位置）
                 spec/dev-spec/ ← dev-spec 其餘五檔（game-spec / feature-spec / state-machine / ui-spec / qa-checklist）
  <dest>/publish-manifest.json ← 來源 run、每檔 sha256_16、被取代檔的舊 sha

--dest 未給時：讀環境變數 `ARK_GAME_ROOT`（例 data/slot）→ `<ARK_GAME_ROOT>/<slug>`；兩者皆無 → BAD_INPUT。
守門：
  - run 缺 game-analysis.yaml → BAD_INPUT（沒有 ① 就沒有可收的定版件）
  - dest 的 spec/config-spec.yaml 是 `mode: restore-live`（還原模式遊戲）而要用設計鏈 config-spec 覆蓋 → GATE_BLOCKED（`--force` 才放行）
用法:
  python gs_publish.py --run <run> [--dest data/slot/<slug>] [--slug <slug>] [--dry-run] [--force]
交付格式：publish <slug>｜analysis N 檔｜spec M 檔｜取代 K｜缺 [...]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import pathlib
import re
import shutil
import stat
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))  # skill root（_lib）
from _lib import run_common as C  # noqa: E402

ANALYSIS_FILES = ("game-analysis.yaml", "kb-refs.yaml", "evidence.jsonl")
SPEC_FILES = ("game-spec.v1.md", "decisions.yaml", "decisions-applied.json")
DEV_SPEC_DOCS = ("game-spec.md", "feature-spec.md", "state-machine.md", "ui-spec.md", "qa-checklist.md")
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,48}$")


def plan(run: pathlib.Path) -> tuple[list[tuple[pathlib.Path, str]], list[str]]:
    """列出（來源檔, dest 相對路徑）與缺漏清單。"""
    pairs: list[tuple[pathlib.Path, str]] = []
    missing: list[str] = []

    def take(src: pathlib.Path, dst: str) -> None:
        if src.is_file():
            pairs.append((src, dst))
        else:
            missing.append(src.relative_to(run).as_posix())

    for f in ANALYSIS_FILES:
        take(run / f, f"analysis/{f}")
    rep = run / "report"
    if rep.is_dir():
        for f in sorted(rep.iterdir()):
            if f.is_file() and f.suffix in (".md", ".html"):
                pairs.append((f, f"analysis/report/{f.name}"))
    else:
        missing.append("report/")
    for f in SPEC_FILES:
        take(run / f, f"spec/{f}")
    take(run / "dev-spec" / "config-spec.yaml", "spec/config-spec.yaml")
    for f in DEV_SPEC_DOCS:
        take(run / "dev-spec" / f, f"spec/dev-spec/{f}")
    return pairs, missing


def main() -> None:
    ap = argparse.ArgumentParser(description="①② 定版件 run → data/slot/<slug>")
    ap.add_argument("--run", required=True)
    ap.add_argument("--dest", help="遊戲 data 家（預設 $ARK_GAME_ROOT/<slug>）")
    ap.add_argument("--slug", help="預設取 dest 目錄名，否則取 run 目錄名")
    ap.add_argument("--dry-run", action="store_true", help="只列出會複製的檔，不寫入")
    ap.add_argument("--force", action="store_true", help="允許以設計鏈 config-spec 覆蓋 restore-live 的 config-spec")
    a = ap.parse_args()
    run = C.run_dir(a.run)
    if not (run / "game-analysis.yaml").is_file():
        C.fail("BAD_INPUT", f"run 缺 game-analysis.yaml：{run}", "先跑 gs_run --stage analyze")

    root = os.environ.get("ARK_GAME_ROOT")
    if a.dest:
        dest = pathlib.Path(a.dest)
        slug = a.slug or dest.name
    else:
        slug = a.slug or run.name
        if not root:
            C.fail("BAD_INPUT", "需要 --dest，或設定環境變數 ARK_GAME_ROOT（例 data/slot）", "python gs_publish.py --run <run> --dest data/slot/<slug>")
        dest = pathlib.Path(root) / slug
    if not SLUG_RE.match(slug):
        C.fail("BAD_INPUT", f"slug 需 kebab-case：{slug}", "加 --slug <slug>")

    pairs, missing = plan(run)
    cs_dst = dest / "spec" / "config-spec.yaml"
    if cs_dst.is_file() and any(d == "spec/config-spec.yaml" for _, d in pairs) and not a.force:
        cur = C.yaml_load(cs_dst) or {}
        if cur.get("mode") == "restore-live":
            C.fail("GATE_BLOCKED", f"{cs_dst} 是還原模式（restore-live），不可被設計鏈 config-spec 覆蓋",
                   "確認要改走設計鏈再加 --force；否則這款遊戲只發 ①（移除 run/dev-spec 或另開 slug）")

    files, replaced = [], []
    for src, rel in pairs:
        dst = dest / rel
        sha = C.sha256_file(src)[:16]
        entry = {"path": rel, "source": src.relative_to(run).as_posix(), "sha256_16": sha}
        if dst.is_file():
            old = C.sha256_file(dst)[:16]
            if old != sha:
                entry["replaced_sha256_16"] = old
                replaced.append(rel)
        files.append(entry)
        if not a.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.is_file() and not os.access(dst, os.W_OK):   # copy2 會帶上來源的唯讀屬性（evidence.jsonl）→ 重發前解除
                dst.chmod(dst.stat().st_mode | stat.S_IWRITE)
            shutil.copy2(src, dst)

    manifest = {"kind": "game-publish", "skill": "ark-game-spec", "skill_version": C.SKILL_VERSION, "slug": slug,
                "run": run.as_posix(), "run_id": C.load_manifest(run).get("run_id", run.name),
                "published_at": _dt.datetime.now().isoformat(timespec="seconds"), "files": files, "missing": missing}
    if not a.dry_run:
        C.atomic_write(dest / "publish-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")
    n_a = sum(1 for f in files if f["path"].startswith("analysis/"))
    n_s = len(files) - n_a
    delivery = f"publish {slug}｜analysis {n_a} 檔｜spec {n_s} 檔｜取代 {len(replaced)}｜缺 {missing or '無'}" + ("｜dry-run" if a.dry_run else "")
    C.emit({"dest": dest.as_posix(), "slug": slug, "files": files, "replaced": replaced, "missing": missing,
            "dry_run": a.dry_run, "delivery": delivery,
            "next": f"ark-game-prob ps_layout --game {dest.as_posix()}"}, {"stage": "publish"})


if __name__ == "__main__":
    main()

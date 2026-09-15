#!/usr/bin/env python3
"""check_consumers.py — 移除／改名 skill 前後，反向掃描「誰還在指著它」。

## 為什麼需要這支

消費端各自有 `sync_skills.py --check`，而且它**本來就會**在來源不存在時回 1。
問題不是偵測不到，是**沒有人會去跑它** —— 移除 skill 的人在上游 repo，
消費端在別的 repo、甚至別台機器上，要等到某天有人手動同步才會發現。

2026-09-14 一天內就發生兩次：兩個 skill 被併掉之後，3 個 sync 矩陣共 10 處、
9 份 SOUL.md、12 份已部署複本、1 份蒸餾設定仍指著舊名 ——
全部是**靜默失效**（sync 印一行「跳過」、蒸餾掃出零筆），沒有任何東西會變紅。

> 🔴 判準：**上游做移除，就要由上游負責掃消費端。**
> 「消費端自己會檢查」在多 repo／多機器的情況下等於沒有檢查。

## 掃描面（都是今天實際踩到的形態）

| 面 | 檔案 | 失效樣態 |
|---|---|---|
| 角色矩陣 | `*/scripts/sync_skills.py` 的 `MATRIX` / `COMMON` | sync 印「來源缺 X，跳過」 |
| 已部署複本 | `**/.kiro/skills/<name>/` | agent 讀到上游已刪的舊版 |
| 人格清單 | `**/steering/SOUL.md` 的 skill 條列 | agent 以為自己有這個能力 |
| 蒸餾來源 | `**/distill-sources.yaml` 的 `scan_paths` | 掃不存在的目錄 → 零筆，不報錯 |

用法：
    python check_consumers.py                      # 掃預設消費端根目錄
    python check_consumers.py --consumers ~/kiro-cli/projects
    python check_consumers.py --name ark-foo       # 只查某個名字（移除前先問「誰在用」）

Exit code：有懸空引用回 1；消費端根目錄不存在回 0（明說跳過，不假裝通過）。
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

SKILLS_REPO = Path(__file__).resolve().parent.parent
DEFAULT_CONSUMERS = SKILLS_REPO.parent.parent / "projects"

#: SOUL.md 的 skill 條列格式：- `ark-x` — `.kiro/skills/ark-x/SKILL.md`
SOUL_BULLET = re.compile(r"^-\s+`(ark-[a-z0-9-]+)`\s+—")
#: 蒸餾設定的 scan_paths 條目：  - ark-x/    # 註解
YAML_PATH = re.compile(r"^\s*-\s+(ark-[a-z0-9-]+)/\s*(?:#.*)?$")

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "state", ".index"}


def upstream_skills(repo: Path) -> set[str]:
    """上游現有的 skill（有 SKILL.md 才算 —— 只有 references/ 的目錄不是 skill）。"""
    return {d.name for d in repo.glob("ark-*") if (d / "SKILL.md").is_file()}


def _walk(root: Path, pattern: str):
    for p in root.rglob(pattern):
        if SKIP_DIRS & set(p.parts):
            continue
        yield p


def scan_matrices(root: Path) -> list[tuple[Path, str, set[str]]]:
    """讀每個 sync_skills.py 的 MATRIX / COMMON，扣掉它自己宣告的 LOCAL_ONLY。

    ⚠️ `MATRIX: dict[str, list[str]] = {...}` 是 **AnnAssign**（帶型別註記），
    只判 `ast.Assign` 會整個矩陣掃不到而回報「0 個引用」——
    2026-09-14 我第一版就是這樣，靠「引用 1 個」這個不合理的數字才發現。
    """
    out = []
    for f in _walk(root, "sync_skills.py"):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        vals: dict[str, object] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                tgt = getattr(node.targets[0], "id", "")
            elif isinstance(node, ast.AnnAssign):
                tgt = getattr(node.target, "id", "")
            else:
                continue
            if tgt in ("MATRIX", "COMMON", "LOCAL_ONLY", "ROOT_SOURCED"):
                try:
                    vals[tgt] = ast.literal_eval(node.value)
                except ValueError:
                    pass
        names: set[str] = set(vals.get("COMMON") or [])
        matrix = vals.get("MATRIX") or {}
        if isinstance(matrix, dict):
            names |= {s for lst in matrix.values() for s in lst}
        # LOCAL_ONLY 是「上游沒有的自建 skill」—— 不算懸空
        names -= set(vals.get("LOCAL_ONLY") or set())
        out.append((f, "matrix", {n for n in names if n.startswith("ark-")}))
    return out


def scan_deployed(root: Path) -> list[tuple[Path, str, set[str]]]:
    out = []
    for d in _walk(root, ".kiro"):
        sk = d / "skills"
        if not sk.is_dir():
            continue
        names = {p.name for p in sk.iterdir() if p.is_dir() and p.name.startswith("ark-")}
        if names:
            out.append((sk, "deployed", names))
    return out


def scan_souls(root: Path) -> list[tuple[Path, str, set[str]]]:
    out = []
    for f in _walk(root, "SOUL.md"):
        names = {m.group(1) for line in f.read_text(encoding="utf-8", errors="replace").splitlines()
                 if (m := SOUL_BULLET.match(line))}
        if names:
            out.append((f, "soul", names))
    return out


def scan_yaml_paths(root: Path) -> list[tuple[Path, str, set[str]]]:
    out = []
    for f in _walk(root, "*.yaml"):
        if "distill" not in f.name and "skill" not in f.name:
            continue
        names = {m.group(1) for line in f.read_text(encoding="utf-8", errors="replace").splitlines()
                 if (m := YAML_PATH.match(line))}
        if names:
            out.append((f, "yaml-path", names))
    return out


def self_built_skills(root: Path) -> set[str]:
    """各專案 `sync_skills.py` 宣告的自建 skill（上游沒有是正常的）。

    🔴 少了這一層，`ark-fish-daily-report`／`ark-policy-translate` 這種
    「唯一權威來源就在專案自己」的 skill 會被report成懸空 ——
    39 處假警報足以讓人直接忽略整份輸出。
    ⚠️ 收集成**全庫一份**而非專案級：`ark-policy-translate` 只在 slotverse／fish
    宣告 LOCAL_ONLY，卻也部署到 hoyeah 等專案（自建 skill 跨專案共用）。
    照專案切會讓沒宣告的那幾個專案繼續假警報。
    """
    out: set[str] = set()
    for f in _walk(root, "sync_skills.py"):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            tgt = (getattr(node.targets[0], "id", "") if isinstance(node, ast.Assign)
                   else getattr(node.target, "id", "") if isinstance(node, ast.AnnAssign)
                   else None)
            if tgt in ("LOCAL_ONLY", "ROOT_SOURCED"):
                try:
                    out.update(ast.literal_eval(node.value))
                except ValueError:
                    pass
    return out


def ever_upstream(repo: Path, names: set[str]) -> set[str]:
    """哪些名字**曾經**在上游存在過（查 git 歷史）。

    🔴 這是「殘留」與「專案自建」的分水嶺，而且沒有它整支工具沒法用：
    沒有 `sync_skills.py` 的專案不會宣告 `LOCAL_ONLY`，
    於是它們自己寫的 skill（`ark-slot-math`／`ark-pixi-slot`／`ark-go-game-server`…）
    看起來全都像懸空。2026-09-14 實測：95 個「懸空」名字裡 **74 個是自建的**，
    照著刪等於毀掉別人的東西。

    判準：上游 git 歷史裡出現過 `<name>/` 這個路徑 → 是被移除的殘留（可清，內容留在歷史）；
    從來沒出現過 → 是專案自建（**不可清**，這裡是唯一的一份）。

    ⚠️ 查不到歷史時**不能靜默把全部當自建** —— 那會讓工具在沒有 git 的環境
    （或淺 clone）回報「懸空 0」，又一個「掃描回報成功而範圍是空的」。
    此時大聲警告並退回保守判定：全部視為殘留（寧可多報，不可漏報）。
    """
    probe = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                           capture_output=True, text=True, cwd=repo)
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        print(f"⚠️  {repo} 不是 git work tree → 無法分辨「被移除的殘留」與「專案自建」，"
              "以下一律視為殘留（保守）")
        return set(names)

    out = set()
    for n in sorted(names):
        r = subprocess.run(["git", "log", "--all", "--oneline", "--", f"{n}/"],
                           capture_output=True, text=True, cwd=repo)
        if r.returncode == 0 and r.stdout.strip():
            out.add(n)
    return out


#: 移除 commit 訊息裡「明確的」接手宣告。**只認箭頭／併入式**——
#: 批次移除的 commit 會在同一行並列好幾個名字，靠「同行出現」推斷會得到錯的接手者
#: （2026-09-15 實測：ark-executive-assistant 被推成 ark-community-ops，兩個都只是同批被刪）。
#: 猜錯的接手者比「不知道」更糟，所以推不出來就明說不確定並指向那個 commit。
_ARROW = re.compile(r"(ark-[a-z0-9-]+)\s*(?:→|->)\s*(ark-[a-z0-9-]+)")
_MERGE = re.compile(r"(ark-[a-z0-9-]+)\s*(?:併入|整合進|已由)\s*(ark-[a-z0-9-]+)")


def _removal_msg(repo: Path, name: str) -> tuple[str, str]:
    out = subprocess.run(
        ["git", "log", "--all", "--diff-filter=D", "--format=%h%x01%s%x01%b", "-n", "1",
         "--", f"{name}/SKILL.md"], capture_output=True, text=True, cwd=repo).stdout
    parts = (out.split("\x01") + ["", "", ""])[:3]
    return parts[0].strip(), (parts[1] + "\n" + parts[2])


def resolve_successors(repo: Path, names: set[str], existing: set[str]) -> dict:
    """舊名 → (接手者 | None, 說明)。三段判準的第②段。

    來源優先序：
      ① 現存 skill 的 `metadata.replaces`（權威，但全庫只有 3 個 skill 有填）
      ② 移除 commit 訊息裡的箭頭／併入式宣告（接手者自己也被移除時追一層）
      ③ 都推不出來 → 不確定，附上移除 commit 讓人自己看
    """
    replaces: dict[str, str] = {}
    for d in sorted(repo.glob("ark-*")):
        sk = d / "SKILL.md"
        if not sk.is_file():
            continue
        head = sk.read_text(encoding="utf-8", errors="replace")[:2000]
        m = re.search(r"^\s*replaces:\s*\[([^\]]*)\]", head, re.M)
        if m:
            for old in m.group(1).split(","):
                old = old.strip().strip("'\"").split(".")[0]
                if old.startswith("ark-"):
                    replaces[old] = d.name

    out = {}
    for n in sorted(names):
        if n in replaces:
            out[n] = (replaces[n], "replaces 欄位")
            continue
        h, msg = _removal_msg(repo, n)
        succ = next((y for pat in (_ARROW, _MERGE) for x, y in pat.findall(msg) if x == n), None)
        hops = 0
        while succ and succ not in existing and hops < 3:   # 接手者自己也被移除 → 追一層
            _, m2 = _removal_msg(repo, succ)
            nxt = next((y for pat in (_ARROW, _MERGE) for x, y in pat.findall(m2) if x == succ), None)
            if not nxt:
                break
            succ, hops = nxt, hops + 1
        out[n] = (succ, "移除 commit" + (f"（追 {hops} 層）" if hops else "")) if succ \
            else (None, f"不確定 —— 見移除 commit {h}")
    return out


def collect(root: Path):
    return (scan_matrices(root) + scan_deployed(root)
            + scan_souls(root) + scan_yaml_paths(root))


def collect_self_examples(repo: Path):
    """上游**自己的 `examples/`** 也是消費面 —— 而且是傳染力最強的那個。

    🔴 2026-09-15 漏過一次：`ark-ingest-guard` 併入 `ark-wiki-engine` 時，
    三個真實消費端的矩陣都改了，**唯獨 `ark-agent-team-builder/examples/` 的
    範例沒改** —— 而範例正是新專案照抄的東西，留著等於量產斷鏈。
    那次是靠 nana 剛好有一份 skill 複本才反向命中，**下次未必有複本**。

    只掃 `ark-*/examples/`：skill 目錄本身就是這個庫，不能當成「已部署複本」。
    """
    sites = []
    for ex in sorted(repo.glob("ark-*/examples")):
        if not ex.is_dir():
            continue
        for p, kind, names in collect(ex):
            sites.append((p, f"self-{kind}"[:8], names))
    return sites


def _show(p: Path, args) -> str:
    """站點可能在 consumers 底下，也可能在上游自己的 examples/ 底下。"""
    for base, tag in ((args.consumers, ""), (args.repo, "«上游範例» ")):
        try:
            return tag + str(p.relative_to(base))
        except ValueError:
            continue
    return str(p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--consumers", type=Path, default=DEFAULT_CONSUMERS,
                    help=f"消費端根目錄（預設 {DEFAULT_CONSUMERS}）")
    ap.add_argument("--repo", type=Path, default=SKILLS_REPO, help="上游 skill 庫")
    ap.add_argument("--name", help="只查這個 skill 名字（移除前先問「誰在用」）")
    args = ap.parse_args()

    if not args.consumers.is_dir():
        # 明說跳過，不假裝通過 —— 「掃描回報成功而範圍是空的」是本 repo 記過的事故形態
        print(f"⏭  消費端根目錄不存在，跳過：{args.consumers}")
        return 0

    upstream = upstream_skills(args.repo)
    print(f"上游 {len(upstream)} 個 skill · 消費端根目錄 {args.consumers}")

    sites = collect(args.consumers) + collect_self_examples(args.repo)
    if not sites:
        print("⏭  沒有掃到任何消費端引用面（矩陣／複本／SOUL／蒸餾設定）")
        return 0

    if args.name:
        users = [(p, kind) for p, kind, names in sites if args.name in names]
        print(f"\n「{args.name}」的使用者：{len(users)} 處")
        for p, kind in users:
            print(f"  [{kind:8}] {_show(p, args)}")
        return 0

    allowed = upstream | self_built_skills(args.consumers)
    unknown = {n for _, _, names in sites for n in names} - allowed
    removed = ever_upstream(args.repo, unknown)          # 曾在上游 → 殘留，可清
    self_built = unknown - removed                        # 從未在上游 → 專案自建，不可清

    dangling: dict[str, list[tuple[str, Path]]] = {}
    for p, kind, names in sites:
        for n in sorted(names & removed):
            dangling.setdefault(n, []).append((kind, p))

    scanned = len(sites)
    if self_built:
        print(f"ℹ️  {len(self_built)} 個名字上游從來沒有過 → 判定為專案自建，不列入懸空"
              f"（{', '.join(sorted(self_built)[:5])}{' …' if len(self_built) > 5 else ''}）")
    if not dangling:
        print(f"✅ 掃了 {scanned} 個引用面，懸空引用 0")
        return 0

    succ_map = resolve_successors(args.repo, set(dangling), upstream)
    print(f"\n🔴 {len(dangling)} 個名字在上游已不存在，但消費端還指著它：")
    gaps = 0
    for n, where in sorted(dangling.items()):
        succ, why = succ_map[n]
        tag = f"接手者 {succ}（{why}）" if succ else f"{why}"
        print(f"\n  {n}（{len(where)} 處）· {tag}")
        for kind, p in where:
            mark = ""
            if succ and kind == "deployed":
                if (p / succ).is_dir():
                    mark = "  ✅ 接手者已在同一個 agent"
                else:
                    mark = "  🔴 接手者未安裝 —— 刪掉等於少一個能力"
                    gaps += 1
            print(f"    [{kind:8}] {_show(p, args)}{mark}")

    print(f"\n掃了 {scanned} 個引用面。")
    print("移除前照三段判準走，只做第①段會靜默掉能力：")
    print("  ① 該不該刪 —— 上游歷史有過＝殘留；沒有過＝專案自建，不可動")
    print("  ② 接手者是誰 —— 改名／併入 vs 純淘汰（上面已標，不確定的請看那個 commit）")
    print("  ③ 這個 agent 該不該有接手者 —— 接手者是 scaffolder 而這個 agent 是職人／管家，"
          "或舊名本來就是套件無差別 bundle 的，那就是刪、不是換")
    if gaps:
        print(f"\n⚠️ 其中 {gaps} 處的接手者不在同一個 agent —— 第③段要逐一判，別無差別補裝。")
    return 1


if __name__ == "__main__":
    if {"-h", "--help"} & set(sys.argv[1:]):
        print(__doc__ or "")
        raise SystemExit(0)
    raise SystemExit(main())

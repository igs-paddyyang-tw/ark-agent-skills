#!/usr/bin/env python3
"""mirror_sync.py — 消費端技能複本（`.ark/skills`；未遷移的 `.kiro/skills`）整份對齊上游（規格：references/mirror-sync.md）。

適用沒有接 align_sync（無 skills-matrix / lock）的 team。逐檔以 git blob hash 判定：
本地內容曾存在於上游歷史 → 過期，可對齊；從未存在 → 本地修改，不覆蓋、列出待審。

用法:
    python mirror_sync.py plan  --upstream <skills repo> --target <team 根> [--root-only] [--keep PATH ...] [--json]
    python mirror_sync.py apply --upstream <skills repo> --target <team 根> [--root-only] [--keep PATH ...] [--only SKILL ...]
                                [--accept-upstream SKILL ...] --yes

exit: 0 正常；2 參數錯誤／apply 未帶 --yes；3 上游不是 git repo。
"""
from __future__ import annotations

import sys

if __name__ == "__main__" and any(a in ("-h", "--help") for a in sys.argv[1:]):
    print(__doc__)
    sys.exit(0)

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ark_layout import ARK, find_ark_dirs, lock_path, skills_dir  # noqa: E402

IGNORE_DIRS = {"__pycache__"}
IGNORE_SUFFIXES = {".pyc"}


@dataclass
class SkillReport:
    """單一 skill 複本的判定結果。"""

    base: str                                    # 複本所在 team（相對 target）
    name: str
    status: str = "SAME"                         # SAME / STALE / LOCAL / NEWER
    local_version: str | None = None
    upstream_version: str | None = None
    stale: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    obsolete: list[str] = field(default_factory=list)
    local_data: list[str] = field(default_factory=list)
    keep: list[str] = field(default_factory=list)
    local_mod: list[str] = field(default_factory=list)
    ignored_local: list[str] = field(default_factory=list)   # 消費端 gitignored，不報告但保留


def _files(root: Path) -> dict[str, Path]:
    """列出 skill 目錄內的檔案（相對路徑 → 實體），略過快取。"""
    out = {}
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix in IGNORE_SUFFIXES:
            continue
        rel = p.relative_to(root)
        if IGNORE_DIRS.intersection(rel.parts):
            continue
        out[rel.as_posix()] = p
    return out


def _git(args: list[str], **kw) -> subprocess.CompletedProcess:
    """跑 git；文字輸入輸出一律 UTF-8（Windows 預設 cp950 遇中文路徑會解碼失敗 → stdout 為 None）。"""
    if kw.get("text"):
        kw.setdefault("encoding", "utf-8")
        kw.setdefault("errors", "replace")
    return subprocess.run(["git", *args], **kw)


def _blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _normalize_eol(data: bytes) -> bytes:
    """文字檔 CRLF → LF（含 NUL 視為二進位，不動）。Windows checkout 的 CRLF 不算內容差異。"""
    return data if b"\0" in data else data.replace(b"\r\n", b"\n")


def blob_hash(path: Path) -> str:
    """與 `git hash-object` 相同的 blob sha1。"""
    return _blob_sha(path.read_bytes())


def blob_hashes(path: Path) -> set[str]:
    """原始、LF、CRLF 三種換行版本的 blob sha1（任一在上游歷史即視為上游曾有）。
    上游 blob 可能以 LF 或 CRLF 存，消費端 checkout 也可能被轉換。二進位檔只算原始內容。"""
    data = path.read_bytes()
    lf = _normalize_eol(data)
    if lf is data:                                 # 二進位
        return {_blob_sha(data)}
    return {_blob_sha(data), _blob_sha(lf), _blob_sha(lf.replace(b"\n", b"\r\n"))}


def _check_ignore(cwd: Path, paths: list[str], extra: list[str]) -> tuple[int, list[str]]:
    """`git check-ignore --stdin -z`：以 NUL 分隔、位元組收送。
    （Windows 文字模式會把 stdin 的 \\n 轉成 \\r\\n，git 收到尾帶 \\r 的路徑而全部比對不到。）"""
    r = _git(["-C", str(cwd), "check-ignore", *extra, "--stdin", "-z"],
             input=b"\0".join(p.encode("utf-8") for p in paths), capture_output=True)
    return r.returncode, [x.decode("utf-8", "replace") for x in r.stdout.split(b"\0") if x]


def same_content(a: Path, b: Path) -> bool:
    """逐位元組相同，或僅換行（CRLF／LF）不同。"""
    da, db = a.read_bytes(), b.read_bytes()
    return da == db or _normalize_eol(da) == _normalize_eol(db)


def _version(skill_md: Path) -> tuple[int, ...] | None:
    """讀 SKILL.md 的 metadata.version；缺則 None（視為最舊）。"""
    if not skill_md.exists():
        return None
    m = re.search(r'^\s+version:\s*"?(\d+(?:\.\d+)*)', skill_md.read_text(encoding="utf-8", errors="ignore"), re.M)
    if not m:
        return None
    nums = [int(x) for x in m.group(1).split(".")]
    return tuple((nums + [0, 0, 0])[:3])


def _fmt(v: tuple[int, ...] | None) -> str | None:
    return ".".join(map(str, v)) if v else None


def export_upstream(upstream: Path, dest: Path) -> set[str]:
    """把上游 HEAD 匯出到 dest（只含已追蹤檔），回傳上游歷史的 blob 集合。"""
    if _git(["-C", str(upstream), "rev-parse", "--git-dir"], capture_output=True).returncode != 0:
        raise NotADirectoryError(f"上游不是 git repo：{upstream}")
    tar = _git(["-C", str(upstream), "archive", "--format=tar", "HEAD"],
               capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as tf:
        try:
            tf.extractall(dest, filter="data")
        except TypeError:                          # Python < 3.11.4 無 filter 參數
            tf.extractall(dest)
    objs = _git(["-C", str(upstream), "rev-list", "--all", "--objects"],
                capture_output=True, text=True, check=True).stdout
    return {line.split(" ", 1)[0] for line in objs.splitlines() if line}


def _kept(rel: str, keep: list[str]) -> bool:
    return any(rel == k or rel.startswith(k.rstrip("/") + "/") for k in keep)


def skill_dirs(target: Path, root_only: bool = False) -> list[Path]:
    """team 根與 projects/* 底下的技能複本（symlink 跳過）。

    每個目錄各自判佈局：有 `.ark/ark.yaml` → `.ark/skills`，否則 `.kiro/skills`
    （ark-agent-os 3.0 前雙讀；同一目錄只取一處，不會兩份都寫）。
    `root_only`：只看 target 本身 —— target 的 projects/ 底下是**別的 repo** 時（例：kiro-cli）必須帶，
    否則會越界改寫他人的複本。`agents/*` 一律不掃，要逐個 agent 目錄當 target。
    """
    roots = [target] if root_only else [target] + sorted(p for p in (target / "projects").glob("*") if p.is_dir())
    cands = [skills_dir(r) for r in roots]
    return [d for d in cands if d.is_dir() and not d.is_symlink()]


def ignored_by_upstream(upstream: Path, name: str, rels: list[str]) -> set[str]:
    """本地獨有檔中，符合上游 .gitignore 者（測試產物等）—— 不算本地資料、對齊時不保留。"""
    if not rels:
        return set()
    _, hits = _check_ignore(upstream, [f"{name}/{x}" for x in rels], ["--no-index"])
    return {h.replace("\\", "/").split("/", 1)[1] for h in hits if "/" in h.replace("\\", "/")}


def ignored_by_consumer(local: Path, rels: list[str]) -> set[str]:
    """本地獨有檔中，被消費端 repo 的 .gitignore 命中者（含執行時才產生的巢狀 .gitignore，
    如 wiki 索引 `.index/.gitignore`）。這類檔不列入本地資料報告，但 apply 時**照樣保留**
    （可能是 .env、本機設定，不能因對齊而刪）。消費端不是 git repo 時回空集合。"""
    if not rels:
        return set()
    code, hits = _check_ignore(local, rels, ["--no-index"])
    if code not in (0, 1):                         # 128：不是 git repo
        return set()
    return {h.replace("\\", "/") for h in hits}


def classify(local: Path, up: Path, history: set[str], keep: list[str], base: str,
             ignored: set[str] = frozenset(), accept: bool = False,
             preserved: set[str] = frozenset()) -> SkillReport:
    """依規格逐檔判定一個 skill 複本。

    `ignored`：上游 .gitignore 命中的本地獨有檔（測試產物，對齊時不保留）。
    `preserved`：消費端 .gitignore 命中的本地獨有檔（不報告、對齊時保留）。
    `accept`：人已審過、確認本地修改只是上游歷史之前的舊版 → local-mod 改按 stale 對齊。
    """
    r = SkillReport(base=base, name=local.name)
    lv, uv = _version(local / "SKILL.md"), _version(up / "SKILL.md")
    r.local_version, r.upstream_version = _fmt(lv), _fmt(uv)
    lf, uf = _files(local), _files(up)
    for rel in sorted(lf.keys() & uf.keys()):
        if same_content(lf[rel], uf[rel]):
            continue
        if blob_hashes(lf[rel]) & history:
            r.stale.append(rel)
        elif _kept(rel, keep):
            r.keep.append(rel)
        elif accept:
            r.stale.append(rel)
        else:
            r.local_mod.append(rel)
    for rel in sorted(lf.keys() - uf.keys() - ignored):
        if rel in preserved:
            r.ignored_local.append(rel)
            continue
        (r.obsolete if blob_hashes(lf[rel]) & history else r.local_data).append(rel)
    r.missing = sorted(uf.keys() - lf.keys())

    if lv and uv and lv > uv:
        r.status = "NEWER"
    elif r.local_mod:
        r.status = "LOCAL"
    elif r.stale or r.missing or r.obsolete:
        r.status = "STALE"
    return r


def _force_writable(func, path, _exc) -> None:
    """rmtree 的錯誤處理：Windows 唯讀檔（WinError 5）先清唯讀屬性再重試；其他錯誤照拋。"""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _rmtree(path: Path) -> None:
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_force_writable)
    else:  # pragma: no cover
        shutil.rmtree(path, onerror=_force_writable)


def _sync_in_place(staging: Path, local: Path) -> None:
    """2.15.1：整份替換失敗（Windows 目錄被別的程序當工作目錄鎖住）時的退路 ——
    逐檔覆蓋、刪掉 staging 沒有的檔；鎖住的空目錄留著（不影響內容與雜湊）。"""
    want = {p.relative_to(staging) for p in staging.rglob("*") if p.is_file()}
    for rel in sorted(want):
        dst = local / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            os.chmod(dst, stat.S_IWRITE)
        shutil.copy2(staging / rel, dst)
    for p in sorted((p for p in local.rglob("*") if p.is_file()), reverse=True):
        if p.relative_to(local) not in want:
            os.chmod(p, stat.S_IWRITE)
            p.unlink()
    for d in sorted((d for d in local.rglob("*") if d.is_dir()), key=lambda d: len(d.parts), reverse=True):
        try:
            d.rmdir()          # 只刪空目錄；有內容或被鎖住就跳過
        except OSError:
            pass


def apply_one(local: Path, up: Path, r: SkillReport) -> None:
    """以上游內容重建複本，保留 keep 與 local-data 檔。

    2.15.1（Windows）：唯讀檔先清屬性再刪；整份替換失敗（目錄被鎖）就退回就地同步 ——
    不再「先刪本地、刪到一半失敗」留下半刪的 skill。"""
    staging = local.with_name(local.name + ".mirror-sync-tmp")
    if staging.exists():
        _rmtree(staging)
    shutil.copytree(up, staging)
    for rel in r.keep + r.local_data + r.ignored_local:
        dst = staging / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local / rel, dst)
    trash = local.with_name(local.name + ".mirror-sync-old")
    try:
        if trash.exists():
            _rmtree(trash)
        local.rename(trash)            # 先整個移開（原子）；被鎖住時這一步就失敗，本地完好
    except OSError:
        _sync_in_place(staging, local)
        _rmtree(staging)
        return
    staging.rename(local)
    try:
        _rmtree(trash)
    except OSError:
        pass                            # 舊目錄刪不掉不影響結果；下次 apply 會再清


LOCK_KEY = "mirror"   # `.ark/skills.lock` 與 align_sync 共用一份 JSON：align_sync 管 agents，本工具管 mirror


def _tree_hash(skill_dir: Path) -> str:
    """與 align_sync._tree_hash 同規則（執行期產物、頂層 release/ 不算內容）。"""
    h = hashlib.sha256()
    files = sorted((p for p in skill_dir.rglob("*")
                    if p.is_file() and not ({"__pycache__", ".pytest_cache", "node_modules"}
                                            & set(p.relative_to(skill_dir).parts))
                    and p.suffix != ".pyc" and p.relative_to(skill_dir).parts[0] != "release"),
                   key=lambda x: x.relative_to(skill_dir).as_posix())     # posix：與 Linux 產的 manifest 一致
    for p in files:
        h.update(p.relative_to(skill_dir).as_posix().encode("utf-8") + b"\0")
        h.update(p.read_bytes() + b"\0")
    return "sha256:" + h.hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_lock(d: Path, upstream: Path, up_root: Path) -> Path | None:
    """`.ark` 佈局的複本對齊後寫版本鎖（legacy 佈局不寫，行為不變）。

    只記上游也有的 skill（本地獨有的 domain／local_only 不鎖）；保留檔內其他 key（align_sync 的 agents）。
    """
    ws = d.parent.parent
    if find_ark_dirs(ws)[0] != ARK:
        return None
    commit = _git(["-C", str(upstream), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    origin = _git(["-C", str(upstream), "remote", "get-url", "origin"], capture_output=True, text=True)
    skills = {}
    for local in sorted(p for p in d.iterdir() if p.is_dir() and not p.is_symlink()):
        if (local / "SKILL.md").exists() and (up_root / local.name / "SKILL.md").exists():
            skills[local.name] = {"version": _fmt(_version(local / "SKILL.md")), "tree_hash": _tree_hash(local)}
    lk = lock_path(ws)
    data = _load_json(lk)
    data[LOCK_KEY] = {"upstream": {"repo": (origin.stdout.strip() if origin.returncode == 0 else str(upstream)),
                                   "commit": commit},
                      "skills": skills}
    lk.parent.mkdir(parents=True, exist_ok=True)
    lk.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return lk


def check_locks(target: Path, root_only: bool = False) -> list[str]:
    """比對 `.ark` 佈局複本與版本鎖；回傳問題清單（空＝一致）。legacy 佈局明說跳過。"""
    problems: list[str] = []
    for d in skill_dirs(target, root_only):
        ws = d.parent.parent
        rel = ws.relative_to(target).as_posix()
        if find_ark_dirs(ws)[0] != ARK:
            print(f"  ⏭ {rel}：legacy .kiro 佈局，無版本鎖（跳過）")
            continue
        locked = (_load_json(lock_path(ws)).get(LOCK_KEY) or {}).get("skills")
        if locked is None:
            problems.append(f"{rel}：沒有版本鎖 → 先跑 mirror_sync apply")
            continue
        for name, meta in sorted(locked.items()):
            sk = d / name
            if not sk.is_dir():
                problems.append(f"{rel}/{name}：鎖裡有、複本不見了 → mirror_sync apply 重建")
            elif _tree_hash(sk) != meta.get("tree_hash"):
                problems.append(f"{rel}/{name}：內容與鎖不符（被手改？）→ 改動提案回上游，或 mirror_sync apply 還原")
        print(f"  🔒 {rel}：檢查 {len(locked)} 個 skill")
    return problems


def run(upstream: Path, target: Path, keep: list[str], only: list[str] | None,
        do_apply: bool, accept: list[str] | None = None, root_only: bool = False) -> list[SkillReport]:
    """掃描 target 全部複本；do_apply 時對齊 STALE。`accept`：審過可用上游覆蓋的 skill 名。"""
    reports: list[SkillReport] = []
    with tempfile.TemporaryDirectory() as tmp:
        up_root = Path(tmp)
        history = export_upstream(upstream, up_root)
        for d in skill_dirs(target, root_only):
            base = d.parent.parent.relative_to(target).as_posix()
            for local in sorted(p for p in d.iterdir() if p.is_dir() and not p.is_symlink()):
                up = up_root / local.name
                if not (up / "SKILL.md").exists() or not (local / "SKILL.md").exists():
                    continue                       # 本地獨有 skill（domain／local_only）不碰
                if only and local.name not in only:
                    continue
                only_local = sorted(set(_files(local)) - set(_files(up)))
                ign = ignored_by_upstream(upstream, local.name, only_local)
                kept_ign = ignored_by_consumer(local, only_local) - ign
                r = classify(local, up, history, keep, base, ign, local.name in (accept or []),
                             kept_ign)
                if r.status == "SAME":
                    continue
                if do_apply and r.status == "STALE":
                    apply_one(local, up, r)
                reports.append(r)
            if do_apply:
                write_lock(d, upstream, up_root)
    return reports


def _print_human(reports: list[SkillReport], applied: bool) -> None:
    if not reports:
        print("✅ 全部與上游一致")
        return
    for r in reports:
        ver = f"{r.local_version or '?'}→{r.upstream_version or '?'}"
        print(f"[{r.status}] {r.base}/{r.name} ({ver}) stale={len(r.stale)} missing={len(r.missing)} "
              f"obsolete={len(r.obsolete)} 保留={len(r.keep) + len(r.local_data)}")
        for rel in r.local_mod:
            print(f"    ⚠️ 本地修改（上游從未有過）：{rel}")
    counts: dict[str, int] = {}
    for r in reports:
        counts[r.status] = counts.get(r.status, 0) + 1
    verb = "已對齊" if applied else "可對齊"
    print(f"\n{verb} STALE {counts.get('STALE', 0)}｜待審 LOCAL {counts.get('LOCAL', 0)}"
          f"｜本地較新 NEWER {counts.get('NEWER', 0)}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="消費端技能複本（.ark/skills 或 .kiro/skills）整份對齊上游")
    ap.add_argument("verb", choices=["plan", "apply", "check"],
                    help="check：比對 .ark 佈局複本與 .ark/skills.lock（不需 --upstream；不一致 exit 1）")
    ap.add_argument("--upstream", type=Path, help="ark-agent-skills 本機 clone（plan／apply 必填）")
    ap.add_argument("--target", required=True, type=Path, help="team repo 根")
    ap.add_argument("--keep", action="append", default=[], help="保留本地版本的 skill 內相對路徑（可重複）")
    ap.add_argument("--only", action="append", help="只處理指定 skill（可重複）")
    ap.add_argument("--accept-upstream", action="append", default=[], metavar="SKILL",
                    help="人工審過、確認本地修改只是舊版的 skill：本地修改改用上游覆蓋（可重複）")
    ap.add_argument("--root-only", action="store_true",
                    help="只處理 target 本身，不掃 target/projects/*（projects/ 底下是別的 repo 時必帶）")
    ap.add_argument("--yes", action="store_true", help="apply 必填")
    ap.add_argument("--json", action="store_true", help="輸出 JSON")
    a = ap.parse_args(argv)

    if a.verb == "check":
        problems = check_locks(a.target.resolve(), a.root_only)
        for msg in problems:
            print(f"❌ {msg}")
        print("✅ 版本鎖一致" if not problems else f"\n{len(problems)} 項不一致")
        return 1 if problems else 0
    if a.upstream is None:
        print("❌ plan／apply 需帶 --upstream", file=sys.stderr)
        return 2
    if a.verb == "apply" and not a.yes:
        print("❌ apply 需帶 --yes（先跑 plan 確認）", file=sys.stderr)
        return 2
    try:
        reports = run(a.upstream.resolve(), a.target.resolve(), a.keep, a.only, a.verb == "apply",
                      a.accept_upstream, a.root_only)
    except NotADirectoryError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 3
    if a.json:
        print(json.dumps([r.__dict__ for r in reports], ensure_ascii=False, indent=2))
    else:
        _print_human(reports, a.verb == "apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""check_consumers.py 的守門測試 —— 用合成的消費端樹，證明它會紅也不會亂紅。

## 為什麼測試用合成樹而不是真的 projects/

真實的 `~/kiro-cli/projects/` 不在版控裡、每台機器都不一樣、
而且它現在本來就有 95 個歷史懸空引用 —— 拿它當斷言對象等於永遠紅。
> 💡 判準：**守門的測試要有確定式輸入。** 對環境取樣的斷言遲早變成
> 「大家習慣性忽略的那條紅燈」（本 repo 記過多次）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
CHECKER = SCRIPTS / "check_consumers.py"


def _upstream(tmp: Path, names: list[str]) -> Path:
    repo = tmp / "skills"
    for n in names:
        (repo / n).mkdir(parents=True)
        (repo / n / "SKILL.md").write_text(f"---\nname: {n}\n---\n# {n}\n", encoding="utf-8")
    return repo


def _sync_script(matrix: dict, common: list[str], local: list[str] | None = None) -> str:
    """複製真實 sync_skills.py 的宣告形態 —— MATRIX 帶型別註記（AnnAssign）。"""
    return (
        f"COMMON = {common!r}\n"
        + (f"LOCAL_ONLY = {set(local)!r}\n" if local else "")
        + f"MATRIX: dict[str, list[str]] = {matrix!r}\n"
    )


def run(repo: Path, consumers: Path, *extra) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--repo", str(repo),
         "--consumers", str(consumers), *extra],
        capture_output=True, text=True)


@pytest.fixture()
def world(tmp_path):
    repo = _upstream(tmp_path, ["ark-alive", "ark-also-alive"])
    consumers = tmp_path / "projects"
    (consumers / "demo-team" / "scripts").mkdir(parents=True)
    return repo, consumers


# ── 乾淨時要綠 ─────────────────────────────────────────────────

def test_clean_consumers_pass(world):
    repo, consumers = world
    (consumers / "demo-team" / "scripts" / "sync_skills.py").write_text(
        _sync_script({"a-agent": ["ark-alive"]}, ["ark-also-alive"]), encoding="utf-8")
    r = run(repo, consumers)
    assert r.returncode == 0, r.stdout
    assert "懸空引用 0" in r.stdout


# ── 四個掃描面各自都要能紅 ──────────────────────────────────────

def test_matrix_reference_to_removed_skill_is_caught(world):
    repo, consumers = world
    (consumers / "demo-team" / "scripts" / "sync_skills.py").write_text(
        _sync_script({"a-agent": ["ark-alive", "ark-gone"]}, []), encoding="utf-8")
    r = run(repo, consumers)
    assert r.returncode == 1
    assert "ark-gone" in r.stdout and "[matrix" in r.stdout


def test_deployed_copy_of_removed_skill_is_caught(world):
    repo, consumers = world
    (consumers / "demo-team" / "agents" / "w" / ".kiro" / "skills" / "ark-gone").mkdir(parents=True)
    r = run(repo, consumers)
    assert r.returncode == 1
    assert "[deployed" in r.stdout


def test_soul_bullet_for_removed_skill_is_caught(world):
    repo, consumers = world
    soul = consumers / "demo-team" / "agents" / "w" / ".kiro" / "steering" / "SOUL.md"
    soul.parent.mkdir(parents=True)
    soul.write_text("## Skill\n\n- `ark-gone` — `.kiro/skills/ark-gone/SKILL.md`\n",
                    encoding="utf-8")
    r = run(repo, consumers)
    assert r.returncode == 1
    assert "[soul" in r.stdout


def test_distill_scan_path_for_removed_skill_is_caught(world):
    repo, consumers = world
    y = consumers / "demo-team" / "distill-sources.yaml"
    y.write_text("sources:\n  - scan_paths:\n      - ark-alive/\n      - ark-gone/  # 舊名\n",
                 encoding="utf-8")
    r = run(repo, consumers)
    assert r.returncode == 1
    assert "[yaml-path" in r.stdout


# ── 不該紅的三種情形 ────────────────────────────────────────────

def test_self_built_skill_is_not_dangling(world):
    """🔴 自建 skill（LOCAL_ONLY）上游本來就沒有 —— 報它就是假警報。

    實測過的代價：`ark-policy-translate` 一個名字就 39 處，
    足以讓人直接忽略整份輸出。而且它只在部分專案宣告 LOCAL_ONLY、
    卻部署到別的專案 → 排除清單必須是全庫一份，不能按專案切。
    """
    repo, consumers = world
    (consumers / "demo-team" / "scripts" / "sync_skills.py").write_text(
        _sync_script({"a-agent": ["ark-alive", "ark-mine"]}, [], local=["ark-mine"]),
        encoding="utf-8")
    # 另一個專案沒宣告，但部署了同一個自建 skill
    (consumers / "other-team" / "agents" / "x" / ".kiro" / "skills" / "ark-mine").mkdir(parents=True)
    r = run(repo, consumers)
    assert r.returncode == 0, r.stdout


def test_annotated_matrix_is_actually_parsed(world):
    """🔴 回歸：`MATRIX: dict[...] = {...}` 是 AnnAssign。

    只判 `ast.Assign` 會整個矩陣掃不到，然後回報「懸空 0 ✅」——
    一個什麼都沒驗的綠燈。2026-09-14 的第一版就是這樣。
    """
    repo, consumers = world
    (consumers / "demo-team" / "scripts" / "sync_skills.py").write_text(
        "MATRIX: dict[str, list[str]] = {'a-agent': ['ark-gone']}\n", encoding="utf-8")
    r = run(repo, consumers)
    assert r.returncode == 1, "帶型別註記的 MATRIX 沒被解析 → 守門是空轉的"


def test_missing_consumer_root_says_skipped_not_ok(tmp_path):
    """範圍是空的時候要**明說跳過** —— 不能讓它看起來像「檢查通過」"""
    repo = _upstream(tmp_path, ["ark-alive"])
    r = run(repo, tmp_path / "nope")
    assert r.returncode == 0
    assert "跳過" in r.stdout and "懸空引用 0" not in r.stdout


# ── 反向查詢：移除前先問「誰在用」──────────────────────────────

def test_name_query_lists_users(world):
    repo, consumers = world
    (consumers / "demo-team" / "scripts" / "sync_skills.py").write_text(
        _sync_script({"a-agent": ["ark-alive"]}, []), encoding="utf-8")
    (consumers / "demo-team" / "agents" / "w" / ".kiro" / "skills" / "ark-alive").mkdir(parents=True)
    r = run(repo, consumers, "--name", "ark-alive")
    assert r.returncode == 0
    assert "2 處" in r.stdout, r.stdout


# ── 專案自建 skill 沒有 LOCAL_ONLY 宣告時，靠上游 git 歷史判別 ──────

def test_never_upstream_name_is_treated_as_self_built(tmp_path):
    """🔴 沒有 sync_skills.py 的專案不會宣告 LOCAL_ONLY —— 它自己寫的 skill
    看起來全都像懸空。實測 95 個「懸空」名字裡 **74 個是自建的**
    （ark-slot-math／ark-pixi-slot／ark-go-game-server…），照著刪等於毀掉別人的東西。

    判準改成查上游 git 歷史：出現過 = 被移除的殘留（可清）；
    從沒出現過 = 專案自建（這裡是唯一一份，不可清）。
    """
    repo = _upstream(tmp_path, ["ark-alive"])
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "init"], cwd=repo, check=True)
    # 曾經存在、後來移除
    (repo / "ark-removed").mkdir()
    (repo / "ark-removed" / "SKILL.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "add"], cwd=repo, check=True)
    import shutil
    shutil.rmtree(repo / "ark-removed")

    consumers = tmp_path / "projects"
    for n in ("ark-removed", "ark-never-upstream"):
        (consumers / "demo" / ".kiro" / "skills" / n).mkdir(parents=True)

    r = run(repo, consumers)
    assert r.returncode == 1
    assert "ark-removed" in r.stdout, "被移除的殘留要報"
    assert "ark-never-upstream" not in r.stdout.split("🔴")[-1], \
        "從未上游過的自建 skill 不可列為懸空"
    assert "專案自建" in r.stdout


# ── 第②③段：接手者解析與「這個 agent 有沒有裝」 ──────────────────

def _git(repo, *args, msg=None):
    if args[0] == "commit":
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", msg], cwd=repo, check=True)
    else:
        subprocess.run(["git", *args], cwd=repo, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _repo_with_removal(tmp_path, removed: str, commit_msg: str, keep=("ark-alive",)):
    """建一個上游：先有 removed，再以 commit_msg 移除它。"""
    repo = _upstream(tmp_path, [*keep, removed])
    _git(repo, "init", "-q"); _git(repo, "add", "-A"); _git(repo, "commit", msg="init")
    import shutil
    shutil.rmtree(repo / removed)
    _git(repo, "add", "-A"); _git(repo, "commit", msg=commit_msg)
    return repo


def test_successor_read_from_arrow_in_removal_commit(tmp_path):
    repo = _repo_with_removal(tmp_path, "ark-old",
                              "chore: 移除 2 個 stub\n\n- ark-old → ark-alive\n")
    consumers = tmp_path / "projects"
    (consumers / "demo" / ".kiro" / "skills" / "ark-old").mkdir(parents=True)
    r = run(repo, consumers)
    assert r.returncode == 1
    assert "接手者 ark-alive" in r.stdout, r.stdout


def test_site_is_marked_by_whether_the_successor_is_installed_here(tmp_path):
    """第③段的材料：接手者在不在**同一個 agent**，決定刪掉會不會少一個能力"""
    repo = _repo_with_removal(tmp_path, "ark-old", "chore: 移除\n\n- ark-old → ark-alive\n")
    consumers = tmp_path / "projects"
    has = consumers / "demo" / "agents" / "a" / ".kiro" / "skills"
    lacks = consumers / "demo" / "agents" / "b" / ".kiro" / "skills"
    (has / "ark-old").mkdir(parents=True); (has / "ark-alive").mkdir()
    (lacks / "ark-old").mkdir(parents=True)

    r = run(repo, consumers)
    out = r.stdout
    assert "接手者已在同一個 agent" in out and "接手者未安裝" in out, out
    assert "1 處的接手者不在同一個 agent" in out, out


def test_batch_removal_does_not_invent_a_successor(tmp_path):
    """🔴 批次移除的 commit 會同行並列好幾個名字 —— 不可據此推斷接手關係。

    實測代價：`ark-executive-assistant` 被推成 `ark-community-ops`，
    而兩者只是同一批被刪。**猜錯的接手者比「不知道」更糟** ——
    照著它補裝會裝進一個同樣不存在的東西。
    """
    repo = _repo_with_removal(
        tmp_path, "ark-old",
        "chore: 移除冷門 skill\n\n- ark-old\n- ark-alive 保留\n")
    consumers = tmp_path / "projects"
    (consumers / "demo" / ".kiro" / "skills" / "ark-old").mkdir(parents=True)
    r = run(repo, consumers)
    assert "接手者 ark-alive" not in r.stdout, "同行並列被誤判成接手關係"
    assert "不確定" in r.stdout and "見移除 commit" in r.stdout, r.stdout


def test_output_states_all_three_stages(tmp_path):
    """輸出要把三段講出來 —— 只做第①段（該不該刪）就會靜默掉能力"""
    repo = _repo_with_removal(tmp_path, "ark-old", "chore: 移除\n\n- ark-old → ark-alive\n")
    consumers = tmp_path / "projects"
    (consumers / "demo" / ".kiro" / "skills" / "ark-old").mkdir(parents=True)
    out = run(repo, consumers).stdout
    for stage in ("① 該不該刪", "② 接手者是誰", "③ 這個 agent 該不該有接手者"):
        assert stage in out, f"缺 {stage}"

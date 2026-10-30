"""ark-agent-team-design 行為測試 —— team-spec.yaml → gen_team.py 產出的骨架。

## 驗什麼

- 正常路徑：拿內建編制樣板 dev-standard 生成 → team.yaml 結構符合 team-builder 慣例
  （entry 在根、worker 有 group、profile 只以註解存在）、skills-matrix 的 manifest_url
  指向上游正確位置、每個 instance 都有 role-profile stub。
- 反例：lint 不過（沒有 admin）→ exit 1，且一個 team.yaml 都不能產。
- 邊界：既有檔案不覆蓋（--force 才覆蓋）；custom base_role 的 stub 帶 TODO 並列進 NEXT.md；
  hybrid target 多產 bot／agents／scheduler，且 bot port = health_port + 5000。

一律以子進程跑 CLI（就是使用者實際的呼叫方式），輸出落 tmp_path。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
SKILL_ROOT = SCRIPTS.parent
PATTERN = SKILL_ROOT / "assets" / "patterns" / "dev-standard.yaml"
GEN = SCRIPTS / "gen_team.py"
MANIFEST_URL = ("https://raw.githubusercontent.com/igs-paddyyang-tw/ark-agent-skills/"
                "main/ark-skills-align/release/manifest.json")


def _gen(spec: Path, out: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GEN), str(spec), "--out", str(out), *extra],
                          capture_output=True, text=True, encoding="utf-8")


def _spec() -> dict:
    return yaml.safe_load(PATTERN.read_text(encoding="utf-8"))


def _write_spec(tmp_path: Path, spec: dict) -> Path:
    p = tmp_path / "team-spec.yaml"
    p.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


# ── 正常路徑 ─────────────────────────────────────────────────

def test_dev_standard_generates_consistent_team(tmp_path):
    """dev-standard 樣板 → team.yaml／skills-matrix／stub 三者彼此一致。"""
    out = tmp_path / "proj"
    r = _gen(PATTERN, out)
    assert r.returncode == 0, r.stdout + r.stderr

    text = (out / "team.yaml").read_text(encoding="utf-8")
    team = yaml.safe_load(text)
    insts = team["instances"]
    assert set(insts) == {"dev-admin-agent", "pm-agent", "coder-agent", "qa-agent", "devops-agent"}
    # entry 落專案根，其他在 agents/<name>
    assert insts["dev-admin-agent"]["working_directory"] == "."
    assert insts["coder-agent"]["working_directory"] == "agents/coder-agent"
    # worker 用 group 歸屬 leader；非 worker 沒有 group
    assert all(insts[w]["group"] == "pm-agent" for w in ("coder-agent", "qa-agent", "devops-agent"))
    assert "group" not in insts["pm-agent"]
    # profile 不得是裸欄位（套件會 WARNING），只能是註解
    assert all("profile" not in row for row in insts.values())
    assert "    # profile: role-profile.yaml" in text
    assert "    # profile: agents/qa-agent/role-profile.yaml" in text
    assert team["health_port"] == 24050

    mx = yaml.safe_load((out / "skills-matrix.yaml").read_text(encoding="utf-8"))
    assert mx["upstream"]["manifest_url"] == MANIFEST_URL
    assert mx["agents"]["pm-agent"] == {"role": "leader", "wave": 2}
    assert mx["agents"]["coder-agent"]["wave"] == 3

    # 每個 instance 都有 stub；relationships 由 spec 推導
    qa = yaml.safe_load((out / "agents/qa-agent/role-profile.yaml").read_text(encoding="utf-8"))
    assert qa["role_id"] == "qa" and qa["relationships"]["reports_to"] == "pm-agent"
    pm = yaml.safe_load((out / "agents/pm-agent/role-profile.yaml").read_text(encoding="utf-8"))
    assert set(pm["relationships"]["delegates_to"]) == {"coder-agent", "qa-agent", "devops-agent"}
    assert "_hint_locks" not in pm, "內部暫存欄位不得 dump 進 stub"
    assert (out / "role-profile.yaml").exists()

    auth = yaml.safe_load((out / "config/authority-matrix.yml").read_text(encoding="utf-8"))
    deploy = next(d for d in auth["decisions"] if d["decision"] == "部署 production")
    assert deploy["approver"] == "human" and deploy["allowed"] == ["devops-agent"]


# ── 反例 ─────────────────────────────────────────────────────

def test_spec_without_admin_is_rejected(tmp_path):
    """拿掉 admin → lint P0「沒有 admin」→ exit 1，且不可產出 team.yaml（半套骨架比沒有更糟）。"""
    spec = _spec()
    spec["instances"] = [i for i in spec["instances"] if i["tier"] != "admin"]
    spec["entry"] = "pm"
    spec["escalation"] = [e for e in spec["escalation"] if e["to"] != "dev-admin"]
    out = tmp_path / "proj"
    r = _gen(_write_spec(tmp_path, spec), out)
    assert r.returncode == 1
    assert "admin" in r.stdout
    assert not (out / "team.yaml").exists()


def test_worker_group_must_point_to_leader(tmp_path):
    """worker 的 group 指向非 leader（這裡指向 admin）→ lint 擋下，exit 1。"""
    spec = _spec()
    for i in spec["instances"]:
        if i["id"] == "coder":
            i["group"] = "dev-admin"
    r = _gen(_write_spec(tmp_path, spec), tmp_path / "proj")
    assert r.returncode == 1 and "不是 leader" in r.stdout


# ── 邊界 ─────────────────────────────────────────────────────

def test_existing_files_not_overwritten_without_force(tmp_path):
    """第二次生成不得覆蓋使用者已改過的 team.yaml；加 --force 才覆蓋。"""
    out = tmp_path / "proj"
    assert _gen(PATTERN, out).returncode == 0
    (out / "team.yaml").write_text("# 使用者手改\n", encoding="utf-8")
    r = _gen(PATTERN, out)
    assert r.returncode == 0 and "已存在，略過" in r.stdout
    assert (out / "team.yaml").read_text(encoding="utf-8") == "# 使用者手改\n"
    assert _gen(PATTERN, out, "--force").returncode == 0
    assert "instances:" in (out / "team.yaml").read_text(encoding="utf-8")


def test_custom_role_stub_has_todo_and_next_lists_it(tmp_path):
    """base_role: custom（角色庫沒有）→ stub 欄位留 TODO、檔頭警告，NEXT.md 第 3 步點名它。"""
    spec = _spec()
    for i in spec["instances"]:
        if i["id"] == "devops":
            i["base_role"] = "custom"
    out = tmp_path / "proj"
    r = _gen(_write_spec(tmp_path, spec), out)
    assert r.returncode == 0, r.stdout
    stub_text = (out / "agents/devops-agent/role-profile.yaml").read_text(encoding="utf-8")
    assert "⚠️ 含 TODO" in stub_text
    stub = yaml.safe_load(stub_text)
    assert stub["stance"] == ["TODO"] * 3
    assert stub["identity"]["one_liner"] == "容器化、部署、監控、環境診斷"
    nxt = (out / "NEXT.md").read_text(encoding="utf-8")
    assert "補 TODO stub（1 個：devops）" in nxt


def test_hybrid_target_emits_bot_files(tmp_path):
    """--target hybrid：team.yaml 之外再產 agents.yaml／bot.yaml／scheduler.yaml；
    bot 關掉 team 派工（team_leader 空）、port = health_port + 5000。"""
    spec = _spec()
    spec["scheduled_jobs"] = [{"id": "nightly", "schedule": "0 2 * * *", "task": "回歸", "target": "qa"}]
    out = tmp_path / "proj"
    r = _gen(_write_spec(tmp_path, spec), out, "--target", "hybrid")
    assert r.returncode == 0, r.stdout + r.stderr
    for f in ("team.yaml", "agents.yaml", "bot.yaml", "scheduler.yaml"):
        assert (out / f).exists(), f
    bot = yaml.safe_load((out / "bot.yaml").read_text(encoding="utf-8"))
    assert bot["server"]["port"] == 24050 + 5000
    assert bot["modes"]["team_leader"] == ""
    agents = yaml.safe_load((out / "agents.yaml").read_text(encoding="utf-8"))
    assert set(agents) == {"default"} and agents["default"]["name"] == "dev-admin-agent"
    sched = yaml.safe_load((out / "scheduler.yaml").read_text(encoding="utf-8"))
    assert sched["jobs"][0]["target"] == "qa-agent"

#!/usr/bin/env python3
"""排程閘門：有變化才叫 LLM（ark-agent-team-builder 3.3.0）。

用在 scheduler.yaml 的 `type: command` 排程：腳本先判斷「有沒有事」，有事才經 daemon `/api/send`
把提詞送給 agent；沒事就結束（零 LLM）。源自 game-team-agent `scripts/sched_gate.sh`（2026-11-17），
本版通用化：port／token 自動偵測、多兩種規則、可只喚醒「有新 daily 的 agent」取代 broadcast_all。

用法（在團隊專案根目錄）：
    python3 sched_gate.py <job>            # 判斷＋觸發
    python3 sched_gate.py <job> --dry      # 只印判斷，不送出、不記狀態（環境變數 DRY=1 同義）
    python3 sched_gate.py --check          # 檢查 config/gated_jobs.json（target 存在、提詞存在、規則參數齊）
    python3 sched_gate.py --list           # 所有 job 乾跑一次，看現在各自會不會觸發

設定 `config/gated_jobs.json`：{ "<job>": { "target": "ceo-agent", "rule": "...", ...規則參數, "max_skip_days": 7 } }
提詞：`config/gated_prompts/<job>.md`（`{date}` 會換成今天），或 job 裡直接給 "prompt"。

規則：
    fingerprint  任務板（id／status／note）＋ origin 各分支 head 沒變 → 跳過（game 原規則）
    git_paths    since_days 內指定路徑有 commit 才觸發
    metric       CSV 欄位近 since_days 合計 ≥ min_total 才觸發
    new_files    globs 內有檔案在「上次觸發後」改過才觸發（例：knowledge/raw/**、memory/daily/*.md）
    tasks_open   任務板有 open_statuses 狀態的任務才觸發（預設 todo／in_progress／blocked／review）
所有規則都可加 max_skip_days：超過這麼多天沒觸發就保底觸發一次。

target 特例 `@new_daily`：逐一檢查 team.yaml 每個 instance 的 `<working_directory>/memory/daily/`，
只把提詞送給上次觸發後有新 daily 的 agent（取代 memory-distill 的 broadcast_all —— 一次喚醒全隊）。

exit：0＝判斷完成（觸發或跳過）；1＝設定或 API 錯誤（daemon 會通知）；2＝參數錯誤。
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

RULES = ("fingerprint", "git_paths", "metric", "new_files", "tasks_open")
OPEN_DEFAULT = ("todo", "pending", "in_progress", "blocked", "review")
REQUIRED = {"git_paths": ("since_days", "paths"), "metric": ("since_days", "csv", "column", "min_total"),
            "new_files": ("globs",)}


class GateError(Exception):
    """設定或環境錯誤（exit 1）。"""


# ── 環境 ─────────────────────────────────────────────────────────────────────

def _yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as e:  # pragma: no cover - 部署環境都有 pyyaml
        raise GateError("需要 pyyaml（team daemon 的 venv 都有；用該專案的 python 執行）") from e
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def daemon_port(home: Path) -> int:
    """.env 的 TEAM_AGENT_PORT 優先，其次 team.yaml 的 health_port。"""
    env = home / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("TEAM_AGENT_PORT="):
                v = line.split("=", 1)[1].strip().strip('"\'')
                if v.isdigit():
                    return int(v)
    port = _yaml(home / "team.yaml").get("health_port")
    if not port:
        raise GateError("找不到 daemon port：.env 沒有 TEAM_AGENT_PORT、team.yaml 沒有 health_port")
    return int(port)


def instances(home: Path) -> dict[str, Path]:
    inst = _yaml(home / "team.yaml").get("instances") or {}
    items = inst.items() if isinstance(inst, dict) else ((i.get("name"), i) for i in inst)
    return {n: (home / ((c or {}).get("working_directory") or f"agents/{n}")).resolve() for n, c in items if n}


def _git(home: Path, *a: str) -> str:
    return subprocess.run(["git", *a], cwd=home, capture_output=True, text=True).stdout


def _board(home: Path) -> list[dict]:
    p = home / "tasks" / "board.json"
    if not p.exists():
        return []
    tasks = json.loads(p.read_text(encoding="utf-8")).get("tasks", [])
    return list(tasks.values()) if isinstance(tasks, dict) else list(tasks)


# ── 規則 ─────────────────────────────────────────────────────────────────────

def evaluate(home: Path, cfg: dict, state: dict, now: float | None = None) -> tuple[bool, str, dict]:
    """回傳 (觸發？, 理由, 要寫回 state 的額外欄位)。"""
    now = now or time.time()
    rule, last = cfg["rule"], state.get("last_trigger", 0)
    extra: dict = {}
    if rule == "fingerprint":
        _git(home, "fetch", "-q", "--prune", "origin")
        h = hashlib.sha256()
        h.update(json.dumps(sorted((t.get("id"), t.get("status"), t.get("note")) for t in _board(home)),
                            ensure_ascii=False, default=str).encode())
        h.update(_git(home, "for-each-ref", "--format=%(refname) %(objectname)", "refs/remotes/origin").encode())
        fp = h.hexdigest()[:16]
        extra["fingerprint"] = fp
        fire = fp != state.get("fingerprint")
        why = f"任務板或分支有變化（{state.get('fingerprint', '首次')} → {fp}）" if fire else "任務板與分支自上次觸發後沒有變化"
    elif rule == "git_paths":
        _git(home, "fetch", "-q", "--prune", "origin")
        out = _git(home, "log", "--all", "--oneline", f"--since={cfg['since_days']} days ago", "--", *cfg["paths"])
        n = len([ln for ln in out.splitlines() if ln.strip()])
        fire, why = n > 0, f"近 {cfg['since_days']} 天相關 commit {n} 筆"
    elif rule == "metric":
        since, total, p = (date.today() - timedelta(days=cfg["since_days"])).isoformat(), 0, home / cfg["csv"]
        if p.exists():
            for r in csv.DictReader(p.open(encoding="utf-8")):
                if r.get("date", "") >= since:
                    total += int(r.get(cfg["column"]) or 0)
        fire, why = total >= cfg["min_total"], f"近 {cfg['since_days']} 天 {cfg['column']} 合計 {total}（門檻 {cfg['min_total']}）"
    elif rule == "new_files":
        newer = [f for g in cfg["globs"] for f in glob.glob(str(home / g), recursive=True)
                 if Path(f).is_file() and Path(f).stat().st_mtime > last]
        fire, why = bool(newer), f"上次觸發後有 {len(newer)} 個檔案更新" if newer else "上次觸發後沒有檔案更新"
    elif rule == "tasks_open":
        open_s = set(cfg.get("open_statuses") or OPEN_DEFAULT)
        n = sum(1 for t in _board(home) if str(t.get("status", "")).lower() in open_s)
        fire, why = n > 0, f"任務板有 {n} 個未完成任務" if n else "任務板沒有未完成任務"
    else:
        raise GateError(f"未知 rule {rule!r} → 可用：{'、'.join(RULES)}")
    if not fire and cfg.get("max_skip_days") and last and (now - last) / 86400 >= cfg["max_skip_days"]:
        fire, why = True, f"已 {(now - last) / 86400:.0f} 天未觸發（保底 {cfg['max_skip_days']} 天）"
    return fire, why, extra


def new_daily_targets(home: Path, last: float) -> list[str]:
    """上次觸發後，自己的 memory/daily 有新檔的 instance。"""
    out = []
    for name, wd in instances(home).items():
        d = wd / "memory" / "daily"
        if d.is_dir() and any(f.stat().st_mtime > last for f in d.glob("*.md")):
            out.append(name)
    return out


# ── 送出 ─────────────────────────────────────────────────────────────────────

def send(home: Path, instance: str, message: str, job: str, port: int | None = None) -> None:
    tok_p = home / "state" / "api_token"
    if not tok_p.exists():
        raise GateError("找不到 state/api_token（daemon 啟動後才會產生）")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port or daemon_port(home)}/api/send", method="POST",
        data=json.dumps({"instance": instance, "message": message, "source": f"system:schedule-gate:{job}",
                         "expect_reply": False}).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + tok_p.read_text().strip()})
    try:
        urllib.request.urlopen(req, timeout=20)
    except Exception as e:  # noqa: BLE001
        raise GateError(f"送出失敗（{instance}）：{e}") from e


def prompt_for(home: Path, job: str, cfg: dict) -> str:
    if cfg.get("prompt"):
        text = cfg["prompt"]
    else:
        p = home / "config" / "gated_prompts" / f"{job}.md"
        if not p.exists():
            raise GateError(f"沒有提詞：job 加 \"prompt\"，或建立 config/gated_prompts/{job}.md")
        text = p.read_text(encoding="utf-8")
    return text.replace("{date}", date.today().isoformat())


def load_jobs(home: Path) -> dict:
    p = home / "config" / "gated_jobs.json"
    if not p.exists():
        raise GateError("找不到 config/gated_jobs.json")
    return json.loads(p.read_text(encoding="utf-8"))


def check(home: Path) -> list[str]:
    """設定檢查 → 問題清單（空＝通過）。"""
    probs, jobs = [], load_jobs(home)
    names = set(instances(home))
    if not jobs:
        probs.append("gated_jobs.json 是空的 —— 範圍是空的，不是通過")
    for job, cfg in jobs.items():
        if cfg.get("rule") not in RULES:
            probs.append(f"{job}：rule {cfg.get('rule')!r} 不認得 → 可用：{'、'.join(RULES)}")
        for k in REQUIRED.get(cfg.get("rule"), ()):
            if k not in cfg:
                probs.append(f"{job}：rule {cfg['rule']} 缺參數 {k}")
        t = cfg.get("target", "")
        if t != "@new_daily" and t not in names:
            probs.append(f"{job}：target {t!r} 不在 team.yaml instances → 可用：{'、'.join(sorted(names))} 或 @new_daily")
        try:
            prompt_for(home, job, cfg)
        except GateError as e:
            probs.append(f"{job}：{e}")
    return probs


def run(home: Path, job: str, dry: bool = False, now: float | None = None, port: int | None = None) -> str:
    jobs = load_jobs(home)
    if job not in jobs:
        raise GateError(f"config/gated_jobs.json 沒有 {job!r} → 有：{'、'.join(jobs) or '（空）'}")
    cfg = jobs[job]
    state_f = home / "state" / "gate" / f"{job}.json"
    state = json.loads(state_f.read_text()) if state_f.exists() else {}
    fire, why, extra = evaluate(home, cfg, state, now)
    if not fire:
        return f"⏭️ {job} 跳過：{why}"
    targets = new_daily_targets(home, state.get("last_trigger", 0)) if cfg["target"] == "@new_daily" else [cfg["target"]]
    if not targets:
        return f"⏭️ {job} 跳過：沒有 agent 有新 daily"
    if dry:
        return f"[DRY] ▶️ {job} 會觸發 → {'、'.join(targets)}：{why}"
    msg = prompt_for(home, job, cfg)
    for t in targets:
        send(home, t, msg, job, port)
    state_f.parent.mkdir(parents=True, exist_ok=True)
    state_f.write_text(json.dumps({"last_trigger": now or time.time(), "targets": targets, "why": why, **extra}, ensure_ascii=False))
    return f"▶️ {job} 已觸發 → {'、'.join(targets)}：{why}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="排程閘門：有變化才叫 LLM")
    ap.add_argument("job", nargs="?")
    ap.add_argument("--home", default=".")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    home = Path(a.home).resolve()
    try:
        if a.check:
            probs = check(home)
            for p in probs:
                print("❌", p)
            print("✅ gated_jobs.json 通過" if not probs else f"❌ {len(probs)} 個問題")
            return 1 if probs else 0
        if a.list:
            for job in load_jobs(home):
                print(run(home, job, dry=True))
            return 0
        if not a.job:
            ap.print_usage()
            return 2
        print(run(home, a.job, dry=a.dry or os.environ.get("DRY") == "1"))
        return 0
    except GateError as e:
        print(f"❌ {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

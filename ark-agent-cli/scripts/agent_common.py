"""agent_common — ark-agent-cli 共用：envelope / exit code、路徑、JSON 工具、backend 指令模板、輸出清理。"""
from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import re
import shlex
import sys
import uuid

CONTRACT = "1"
SKILL_VERSION = "2.1.0"
PROTOCOL_VERSION = "subagent-protocol/1"
EXIT = {"BAD_INPUT": 2, "GATE_BLOCKED": 3, "BUDGET_EXCEEDED": 4, "CONN_FAILED": 5, "QUERY_FAILED": 6, "TIMEOUT": 7, "DRIVER_MISSING": 8}
HERE = pathlib.Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
JOBS_ROOT = pathlib.Path(os.getenv("ARK_AGENT_JOBS_DIR", str(pathlib.Path.home() / ".ark" / "agent-jobs")))
DEFAULT_BACKEND = os.getenv("ARK_CLI_DEFAULT_BACKEND", "kiro")
DEFAULT_TIMEOUT = int(os.getenv("ARK_CLI_TIMEOUT", "300"))


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass


def emit(data, meta=None):
    _utf8()
    print(json.dumps({"success": True, "contract": CONTRACT, "data": data, "meta": {"skill_version": SKILL_VERSION, **(meta or {})}}, ensure_ascii=False, default=str))
    sys.exit(0)


def fail(code: str, message: str, hint: str = "", data=None):
    _utf8()
    body = {"success": False, "contract": CONTRACT, "error": {"code": code, "message": message, "hint": hint}}
    if data is not None:
        body["data"] = data
    print(json.dumps(body, ensure_ascii=False, default=str))
    sys.exit(EXIT.get(code, 1))


def now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def new_job_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")[:24] or "job"
    return f"{_dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{slug}-{uuid.uuid4().hex[:6]}"


def atomic_write(path: pathlib.Path, text: str):
    import time as _t
    path = pathlib.Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    # Windows：目標檔正被別的進程（status/wait）開著讀時 os.replace 會 WinError 5，短暫重試。
    # POSIX 的 rename 不受讀取者影響，第一次就成功。
    for i in range(10):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == 9:
                raise
            _t.sleep(0.02 * (i + 1))


def read_json(path: pathlib.Path, default=None):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def write_json(path: pathlib.Path, obj):
    atomic_write(path, json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def append_jsonl(path: pathlib.Path, obj):
    path = pathlib.Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"t": now(), **obj}, ensure_ascii=False, default=str) + "\n")


# ---------------------------------------------------------------- backend 指令模板
# 每個 backend：cmd（env 覆蓋）、one-shot 參數、prompt 怎麼給（argv | stdin）、模型 / json / 續接 / agent 旗標
BACKENDS = {
    "kiro":   {"env": ["ARK_CLI_KIRO_CMD", "KIRO_CLI_PATH"], "default": "kiro-cli", "args": ["chat", "--no-interactive", "--trust-all-tools"],
               "prompt": "argv", "model": ["--model", "{model}"], "json": [], "resume": ["--resume-id", "{session}"], "agent": ["--agent", "{agent}"]},
    "claude": {"env": ["ARK_CLI_CLAUDE_CMD", "CLAUDE_CLI_CMD"], "default": "claude", "args": ["-p"],
               "prompt": "argv", "model": ["--model", "{model}"], "json": ["--output-format", "json"], "resume": ["--resume", "{session}"], "agent": []},
    "gemini": {"env": ["ARK_CLI_GEMINI_CMD", "GEMINI_CLI_CMD"], "default": "gemini", "args": ["--approval-mode", "yolo", "--prompt"],
               "prompt": "argv", "model": ["-m", "{model}"], "json": ["--output-format", "json"], "resume": [], "agent": []},
    "codex":  {"env": ["ARK_CLI_CODEX_CMD", "CODEX_CLI_CMD"], "default": "codex", "args": ["exec", "--sandbox", "workspace-write"],
               "prompt": "argv", "model": ["-m", "{model}"], "json": [], "resume": [], "agent": []},
    "fake":   {"env": ["ARK_CLI_FAKE_CMD"], "default": f"{sys.executable} {HERE / 'fake_backend.py'}", "args": [],
               "prompt": "stdin", "model": [], "json": [], "resume": [], "agent": []},
}


def backend_cmd(backend: str) -> list[str]:
    spec = BACKENDS.get(backend)
    if not spec:
        raise ValueError(f"未知 backend {backend}（可用 {list(BACKENDS)}）")
    for e in spec["env"]:
        if os.getenv(e):
            return shlex.split(os.getenv(e), posix=(os.name != "nt"))
    return shlex.split(spec["default"], posix=(os.name != "nt"))


def build_argv(backend: str, prompt: str, model: str | None = None, json_output: bool = False, session: str | None = None,
               agent: str | None = None, lean: bool = False) -> tuple[list[str], str | None]:
    """→ (argv, stdin_text)。prompt 走 argv 或 stdin 依 backend。"""
    spec = BACKENDS[backend]
    argv = backend_cmd(backend) + list(spec["args"])
    if model and spec["model"]:
        argv += [a.replace("{model}", model) for a in spec["model"]]
    if json_output:
        argv += spec["json"]
    if session and spec["resume"]:
        argv += [a.replace("{session}", session) for a in spec["resume"]]
    if agent and spec["agent"]:
        argv += [a.replace("{agent}", agent) for a in spec["agent"]]
    if lean and backend == "claude":
        argv += ["--tools", ""]
    if spec["prompt"] == "argv":
        return argv + [prompt], None
    return argv, prompt


_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")
_NOISE = re.compile(r"^(▸ Time:|All tools are now trusted|> ?$)")


def clean_output(text: str) -> str:
    lines = []
    for l in _ANSI.sub("", text or "").splitlines():
        if _NOISE.match(l.strip()):
            continue
        lines.append(l[2:] if l.startswith("> ") else l)
    return "\n".join(lines).strip()


def extract_json(text: str):
    t = re.sub(r"```(?:json)?", "", text or "").strip()
    try:
        return json.loads(t)
    except Exception:  # noqa: BLE001
        pass
    for m in re.finditer(r"\{", t):
        depth = 0; start = m.start()
        for i in range(start, len(t)):
            if t[i] == "{":
                depth += 1
            elif t[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[start:i + 1])
                    except Exception:  # noqa: BLE001
                        break
    return None


def parse_model_spec(spec: str) -> tuple[str, str]:
    if "/" in spec:
        b, m = spec.split("/", 1); return b, m
    return DEFAULT_BACKEND, spec


def find_agents_yaml(start: pathlib.Path | None = None) -> pathlib.Path | None:
    """找 agents.yaml（agent 編制的唯一來源）：
    優先 env ARK_AGENTS_YAML；否則從 start（預設當前工作目錄）逐層往上找第一個 agents.yaml。
    找不到回 None（呼叫端決定是否報錯）。
    """
    env = os.getenv("ARK_AGENTS_YAML")
    if env:
        p = pathlib.Path(env)
        return p if p.exists() else None
    cur = (start or pathlib.Path.cwd()).resolve()
    for d in (cur, *cur.parents):
        cand = d / "agents.yaml"
        if cand.exists():
            return cand
    return None

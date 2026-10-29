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
SKILL_VERSION = "2.2.0"
PROTOCOL_VERSION = "subagent-protocol/1.1"
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
# 每個 backend：cmd（env 覆蓋）、one-shot 參數、prompt 餵法（stdin | file | argv）、模型 / json / 續接 / agent 旗標、access 映射。
# prompt 一律優先 stdin（Windows argv 上限 ~32K，長 prompt 會 WinError 206）；不吃 stdin 的 backend 走 file：
#   prompt 寫到檔，argv 只放一行「讀 <path> 並依其執行」。argv 只在測試 / 極短 prompt 用。
ACCESS_LEVELS = ("read-only", "workspace", "full")
BACKENDS = {
    "kiro":   {"env": ["ARK_CLI_KIRO_CMD", "KIRO_CLI_PATH"], "default": "kiro-cli", "args": ["chat", "--no-interactive"],
               "prompt": os.getenv("ARK_CLI_KIRO_PROMPT", "file"), "model": ["--model", "{model}"], "json": [], "resume": ["--resume-id", "{session}"], "agent": ["--agent", "{agent}"],
               "access": {"read-only": ["--trust-tools=fs_read"], "workspace": ["--trust-tools=fs_read,fs_write,execute_bash"], "full": ["--trust-all-tools"]}},
    "claude": {"env": ["ARK_CLI_CLAUDE_CMD", "CLAUDE_CLI_CMD"], "default": "claude", "args": ["-p"],
               "prompt": "stdin", "model": ["--model", "{model}"], "json": ["--output-format", "json"], "resume": ["--resume", "{session}"], "agent": [],
               "access": {"read-only": ["--allowedTools", "Read,Grep,Glob,LS"], "workspace": ["--allowedTools", "Read,Grep,Glob,LS,Write,Edit,Bash"], "full": ["--dangerously-skip-permissions"]}},
    "codex":  {"env": ["ARK_CLI_CODEX_CMD", "CODEX_CLI_CMD"], "default": "codex", "args": ["exec", "--skip-git-repo-check"],
               "prompt": "stdin", "stdin_marker": "-", "model": ["-m", "{model}"], "json": ["--json"], "resume": [], "agent": [],
               "access": {"read-only": ["-s", "read-only"], "workspace": ["-s", "workspace-write"], "full": ["-s", "danger-full-access"]}},
    "gemini": {"env": ["ARK_CLI_GEMINI_CMD", "GEMINI_CLI_CMD"], "default": "gemini", "args": [],
               "prompt": "stdin", "model": ["-m", "{model}"], "json": ["--output-format", "json"], "resume": [], "agent": [],
               "access": {"read-only": ["--approval-mode", "default"], "workspace": ["--approval-mode", "auto_edit"], "full": ["--approval-mode", "yolo"]}},
    "fake":   {"env": ["ARK_CLI_FAKE_CMD"], "default": f"{sys.executable} {HERE / 'fake_backend.py'}", "args": [],
               "prompt": "stdin", "model": [], "json": [], "resume": [], "agent": [], "access": {"read-only": [], "workspace": [], "full": []}},
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
               agent: str | None = None, lean: bool = False, access: str = "read-only", allow_tools: list[str] | None = None,
               prompt_file: pathlib.Path | None = None, force_argv: bool = False) -> tuple[list[str], str | None, pathlib.Path | None]:
    """→ (argv, stdin_text, prompt_file)。餵法：spec.prompt ∈ stdin | file | argv；file 模式需 prompt_file（呼叫端給路徑）。"""
    spec = BACKENDS[backend]
    if access not in ACCESS_LEVELS:
        raise ValueError(f"access 需 {ACCESS_LEVELS}")
    argv = backend_cmd(backend) + list(spec["args"])
    if model and spec["model"]:
        argv += [a.replace("{model}", model) for a in spec["model"]]
    if json_output:
        argv += spec["json"]
    if session and spec["resume"]:
        argv += [a.replace("{session}", session) for a in spec["resume"]]
    if agent and spec["agent"]:
        argv += [a.replace("{agent}", agent) for a in spec["agent"]]
    acc = list(spec.get("access", {}).get(access, []))
    if allow_tools and backend in ("kiro", "claude") and access != "full":
        acc = ["--trust-tools=" + ",".join(allow_tools)] if backend == "kiro" else ["--allowedTools", ",".join(allow_tools)]
    argv += acc
    if lean and backend == "claude":
        argv += ["--tools", ""]
    mode = "argv" if force_argv else spec["prompt"]
    if mode == "stdin":
        if spec.get("stdin_marker"):
            argv.append(spec["stdin_marker"])
        return argv, prompt, None
    if mode == "file":
        if prompt_file is None:
            import tempfile
            fd, name = tempfile.mkstemp(prefix="ark-prompt-", suffix=".md"); os.close(fd); prompt_file = pathlib.Path(name)
        pathlib.Path(prompt_file).write_text(prompt, encoding="utf-8")
        return argv + [f"請先完整讀取檔案 {prompt_file}，它是你這一段的全部指令與資料；讀完後依其執行，不要回頭問。"], None, pathlib.Path(prompt_file)
    return argv + [prompt], None, None


def extract_usage(text: str, json_data=None) -> dict | None:
    """從 CLI 輸出抽 usage（有就記，沒有回 None）：claude json.usage / codex --json turn.completed.usage / gemini stats。"""
    cands = []
    if isinstance(json_data, dict):
        cands.append(json_data.get("usage")); cands.append((json_data.get("stats") or {}).get("usage") if isinstance(json_data.get("stats"), dict) else None)
    for line in (text or "").splitlines():
        line = line.strip()
        if line.startswith("{") and '"usage"' in line:
            try:
                o = json.loads(line); cands.append((o.get("usage") or (o.get("turn") or {}).get("usage")))
            except Exception:  # noqa: BLE001
                pass
    for u in cands:
        if isinstance(u, dict):
            it = u.get("input_tokens") or u.get("prompt_tokens") or u.get("promptTokenCount") or 0
            ot = u.get("output_tokens") or u.get("completion_tokens") or u.get("candidatesTokenCount") or 0
            return {"input_tokens": int(it or 0), "output_tokens": int(ot or 0), "cost_usd": u.get("cost_usd") or json_data.get("total_cost_usd") if isinstance(json_data, dict) else u.get("cost_usd")}
    return None


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

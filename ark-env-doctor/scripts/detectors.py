"""環境偵測模組"""
import os
import platform
import subprocess
import sys
from pathlib import Path


def _run(cmd: str) -> str | None:
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return None


def detect_system() -> dict:
    return {
        "os": platform.system(),
        "arch": platform.machine(),
        "version": platform.version(),
        "shell": os.environ.get("SHELL") or os.environ.get("ComSpec", "unknown"),
    }


def detect_python() -> dict:
    venv = os.environ.get("VIRTUAL_ENV")
    return {
        "exists": True,
        "version": platform.python_version(),
        "path": sys.executable,
        "venv_active": venv is not None,
        "venv_path": venv,
        "pip": _run(f"{sys.executable} -m pip --version"),
    }


def detect_go() -> dict:
    version = _run("go version")
    gopath = _run("go env GOPATH")
    return {
        "exists": version is not None,
        "version": version,
        "gopath": gopath,
    }


def detect_node() -> dict:
    version = _run("node --version")
    npm = _run("npm --version")
    pnpm = _run("pnpm --version")
    return {
        "exists": version is not None,
        "version": version,
        "npm": npm,
        "pnpm": pnpm,
    }


def detect_git() -> dict:
    """偵測 Git 安裝狀態。"""
    version = _run("git --version")
    fix = None
    if not version:
        os_name = platform.system()
        if os_name == "Windows":
            fix = "winget install Git.Git"
        elif os_name == "Darwin":
            fix = "brew install git"
        else:
            fix = "sudo apt install git"
    return {"exists": version is not None, "version": version, "fix": fix}


def detect_gemini() -> dict:
    """偵測 Gemini CLI 安裝狀態。"""
    version = _run("gemini --version")
    return {
        "exists": version is not None,
        "version": version,
        "fix": "npm install -g @google/gemini-cli" if not version else None,
    }


def detect_kiro() -> dict:
    """偵測 Kiro CLI 安裝狀態。"""
    version = _run("kiro-cli --version")
    fix = None
    if not version:
        os_name = platform.system()
        if os_name == "Windows":
            fix = "irm 'https://cli.kiro.dev/install.ps1' | iex"
        elif os_name == "Darwin":
            fix = "curl -fsSL https://cli.kiro.dev/install | bash"
        else:
            fix = "curl -fsSL https://cli.kiro.dev/install | bash"
    return {"exists": version is not None, "version": version, "fix": fix}


def detect_packages(req_path: Path, pkg_type: str = "python") -> dict:
    """比對需求檔案，找出缺失套件"""
    missing = []
    req_path = Path(req_path)

    if not req_path.exists():
        return {"file": str(req_path), "exists": False, "missing": []}

    if pkg_type == "python":
        import importlib.metadata
        for line in req_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            pkg = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].split("[")[0].strip()
            try:
                importlib.metadata.distribution(pkg)
            except importlib.metadata.PackageNotFoundError:
                missing.append(line)

    elif pkg_type == "node":
        import json
        try:
            pkg_json = json.loads(req_path.read_text(encoding="utf-8"))
            deps = {**pkg_json.get("dependencies", {}), **pkg_json.get("devDependencies", {})}
            node_modules = req_path.parent / "node_modules"
            for pkg_name in deps:
                if not (node_modules / pkg_name).exists():
                    missing.append(pkg_name)
        except Exception:
            pass

    return {"file": str(req_path), "exists": True, "missing": missing}

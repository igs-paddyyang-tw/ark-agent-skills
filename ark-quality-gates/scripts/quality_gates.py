#!/usr/bin/env python3
"""quality_gates.py — 一支指令跑三道品質關：tests、lint、security。

規格：kiro-cli `docs/specs/ark-quality-gates-spec.md`（2026-10-29，由 ark-code-review／
ark-security-audit／ark-test-runner 三份產碼食譜合併成可執行的守門）。

每道關「一定會跑」的部分只用標準庫；外部工具（pytest-cov、ruff、bandit、pip-audit）有裝才加強。
🔴 缺工具不能假裝通過：狀態記 skip 並附安裝指令；`--strict` 時 skip 也算失敗。

用法：
    python quality_gates.py [--path .] [--only tests,lint,security] [--fail-under 80]
                            [--python <venv python>] [--strict] [--json r.json] [--md r.md]

Exit：0 全過（skip 不算失敗，除非 --strict）；1 有關失敗；2 參數錯誤。
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

GATES = ("tests", "lint", "security")
EXCLUDE_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist", ".tox",
                ".mypy_cache", ".pytest_cache", ".ruff_cache"}

#: 硬編碼密鑰：變數名像密鑰、值是夠長的字串常值（排除空字串與明顯的佔位符）
SECRET_RE = re.compile(
    r"""(?i)\b(password|passwd|pwd|api_?key|secret(?:_key)?|access_token|auth_token|token)\s*[:=]\s*['"]([^'"]{8,})['"]""")
PLACEHOLDER_RE = re.compile(r"(?i)^(\$\{|<|your|xxx|changeme|example|dummy|test|placeholder|\*+$)")
#: SQL 字串拼接：f-string／% 格式化／+ 串接出現 SQL 關鍵字
NOSEC_RE = re.compile(r"#\s*nosec\b")
SQL_RE = re.compile(r"""(?i)(f['"][^'"]*\b(select|insert|update|delete)\b[^'"]*\{|['"][^'"]*\b(select|insert|update|delete)\b[^'"]*['"]\s*(%|\+))""")


@dataclass
class Finding:
    file: str
    line: int
    rule: str
    severity: str  # high | medium | low
    message: str


@dataclass
class Gate:
    name: str
    status: str = "pass"  # pass | fail | skip
    summary: str = ""
    findings: list[Finding] = field(default_factory=list)
    hint: str = ""
    suppressed: int = 0  # 以 `# nosec` 標記略過的筆數（要讓人看得到，不靜默）


def py_files(root: Path) -> list[Path]:
    """root 底下的 .py（排除虛擬環境、建置產物等目錄）。"""
    if root.is_file():
        return [root] if root.suffix == ".py" else []
    return sorted(p for p in root.rglob("*.py") if not (EXCLUDE_DIRS & set(p.relative_to(root).parts)))


def _rel(p: Path, root: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


# ── tests ──────────────────────────────────────────────────────────

_COUNT_RE = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)")


def _has_module(python: str, mod: str) -> bool:
    r = subprocess.run([python, "-c", f"import {mod}"], capture_output=True)
    return r.returncode == 0


def gate_tests(root: Path, python: str, fail_under: float | None, timeout: int) -> Gate:
    g = Gate("tests")
    if not _has_module(python, "pytest"):
        g.status, g.summary = "skip", f"{python} 沒有 pytest"
        g.hint = f"{python} -m pip install pytest pytest-cov"
        return g
    cov = _has_module(python, "pytest_cov")
    with tempfile.TemporaryDirectory() as td:
        cov_json = Path(td) / "cov.json"
        cmd = [python, "-m", "pytest", "-q", "--tb=line", "-p", "no:cacheprovider", str(root)]
        if cov:
            cmd += [f"--cov={root}", f"--cov-report=json:{cov_json}", "--cov-report="]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=root if root.is_dir() else root.parent,
                               timeout=timeout)
        except subprocess.TimeoutExpired:
            g.status, g.summary = "fail", f"pytest 超過 {timeout} 秒未結束"
            g.hint = "用 --timeout 放寬，或先找出卡住的測試（pytest --timeout 需 pytest-timeout）"
            return g
        tail = (r.stdout.strip().splitlines() or [""])[-1]
        counts = {k.rstrip("s") if k.startswith("error") else k: int(n) for n, k in _COUNT_RE.findall(tail)}
        if r.returncode == 5:   # pytest：沒有收集到任何測試
            g.status, g.summary = "skip", "沒有收集到任何測試（0 個）"
            g.hint = "新增 tests/test_*.py；確認不是路徑或命名規則讓 pytest 找不到"
            return g
        for line in r.stdout.splitlines():
            if line.startswith(("FAILED ", "ERROR ")):
                g.findings.append(Finding(line.split(" ", 1)[1].split("::")[0], 0, "test-failed", "high", line))
        coverage = None
        if cov and cov_json.is_file():
            coverage = json.loads(cov_json.read_text(encoding="utf-8"))["totals"]["percent_covered"]
    parts = [f"{counts.get(k, 0)} {k}" for k in ("passed", "failed", "error", "skipped") if counts.get(k)]
    g.summary = "、".join(parts) or tail
    if coverage is not None:
        g.summary += f"；覆蓋率 {coverage:.1f}%"
    elif fail_under is not None:
        g.hint = f"沒有 pytest-cov，無法判定 --fail-under：{python} -m pip install pytest-cov"
    elif not cov:
        g.hint = f"覆蓋率未量（沒有 pytest-cov）：{python} -m pip install pytest-cov"
    if r.returncode not in (0, 5) or counts.get("failed") or counts.get("error"):
        g.status = "fail"
    if coverage is not None and fail_under is not None and coverage < fail_under:
        g.status = "fail"
        g.findings.append(Finding("", 0, "coverage-below", "high",
                                  f"覆蓋率 {coverage:.1f}% < --fail-under {fail_under}"))
    if g.status == "fail" and not g.findings and r.returncode not in (0, 1):
        g.findings.append(Finding("", 0, "pytest-error", "high", f"pytest exit {r.returncode}：{tail}"))
    return g


# ── lint ───────────────────────────────────────────────────────────

def gate_lint(root: Path, which=shutil.which) -> Gate:
    g = Gate("lint")
    files = py_files(root)
    for f in files:
        try:
            compile(f.read_text(encoding="utf-8", errors="replace"), str(f), "exec", dont_inherit=True)
        except SyntaxError as e:
            g.findings.append(Finding(_rel(f, root), e.lineno or 0, "syntax-error", "high", e.msg or "語法錯誤"))
    syntax_bad = len(g.findings)
    ruff = which("ruff")
    if ruff:
        r = subprocess.run([ruff, "check", "--output-format", "json", "--exit-zero", str(root)],
                           capture_output=True, text=True)
        try:
            for it in json.loads(r.stdout or "[]"):
                g.findings.append(Finding(_rel(Path(it["filename"]), root), it["location"]["row"],
                                          it.get("code") or "ruff", "medium", it["message"]))
        except (json.JSONDecodeError, KeyError):
            g.hint = f"ruff 輸出無法解析（exit {r.returncode}）"
    else:
        g.hint = "ruff 未安裝，只做了語法檢查：pip install ruff"
    if not files:
        g.status, g.summary = "skip", "沒有 .py 檔可檢查"
        return g
    g.summary = f"{len(files)} 個檔；語法錯誤 {syntax_bad}" + (f"；ruff {len(g.findings) - syntax_bad}" if ruff else "（ruff 未跑）")
    if g.findings:
        g.status = "fail"
    return g


# ── security ───────────────────────────────────────────────────────

def _call_name(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        base = f.value.id if isinstance(f.value, ast.Name) else ""
        return f"{base}.{f.attr}" if base else f".{f.attr}"
    return ""


def scan_ast(tree: ast.AST) -> list[tuple[int, str, str, str]]:
    """(行, 規則, 嚴重度, 說明)：用 AST 判函式呼叫，避免 regex 把 model.eval() 當成 eval。"""
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        kw = {k.arg: k.value for k in node.keywords if k.arg}
        if name in ("eval", "exec"):
            out.append((node.lineno, "dangerous-eval", "high", f"{name}() 可執行任意程式碼；改用 ast.literal_eval 或明確解析"))
        elif name in ("pickle.loads", "pickle.load"):
            out.append((node.lineno, "unsafe-pickle", "medium", "pickle 反序列化不可信資料可執行任意程式碼"))
        elif name == "yaml.load" and "Loader" not in kw:
            out.append((node.lineno, "unsafe-yaml", "medium", "yaml.load 未指定 Loader；改用 yaml.safe_load"))
        if isinstance(kw.get("shell"), ast.Constant) and kw["shell"].value is True:
            out.append((node.lineno, "shell-true", "high", "subprocess shell=True 有指令注入風險；改傳 list 參數"))
        if isinstance(kw.get("verify"), ast.Constant) and kw["verify"].value is False:
            out.append((node.lineno, "tls-verify-off", "medium", "verify=False 關閉 TLS 憑證驗證"))
    return out


def scan_text(text: str) -> list[tuple[int, str, str, str]]:
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        m = SECRET_RE.search(line)
        if m and not PLACEHOLDER_RE.match(m.group(2)) and "os.environ" not in line and "getenv" not in line:
            out.append((i, "hardcoded-secret", "high", f"疑似硬編碼密鑰（{m.group(1)}）；改從環境變數讀"))
        if SQL_RE.search(line):
            out.append((i, "sql-concat", "high", "SQL 以字串組合；改用參數化查詢（cursor.execute(sql, params)）"))
    return out


def gate_security(root: Path, which=shutil.which) -> Gate:
    g = Gate("security")
    files = py_files(root)
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        hits = scan_text(text)
        try:
            hits += scan_ast(ast.parse(text))
        except SyntaxError:
            pass   # 語法錯誤由 lint 關回報
        src = text.splitlines()
        for line, rule, sev, msg in sorted(hits):
            # `# nosec`：刻意的用法（例：執行使用者設定的指令）—— 與 bandit 同一個慣例
            if 0 < line <= len(src) and NOSEC_RE.search(src[line - 1]):
                g.suppressed += 1
                continue
            g.findings.append(Finding(_rel(f, root), line, rule, sev, msg))
    extra, missing = [], []
    bandit = which("bandit")
    if bandit:
        r = subprocess.run([bandit, "-r", "-q", "-f", "json", str(root), "-x",
                            ",".join(str(root / d) for d in sorted(EXCLUDE_DIRS))], capture_output=True, text=True)
        try:
            for it in json.loads(r.stdout or "{}").get("results", []):
                g.findings.append(Finding(_rel(Path(it["filename"]), root), it["line_number"],
                                          f"bandit:{it['test_id']}", it["issue_severity"].lower(), it["issue_text"]))
            extra.append("bandit")
        except (json.JSONDecodeError, KeyError):
            g.hint = f"bandit 輸出無法解析（exit {r.returncode}）"
    else:
        missing.append("bandit")
    req = root / "requirements.txt" if root.is_dir() else None
    audit = which("pip-audit")
    if audit and req and req.is_file():
        r = subprocess.run([audit, "-r", str(req), "-f", "json"], capture_output=True, text=True)
        try:
            for dep in json.loads(r.stdout or "{}").get("dependencies", []):
                for v in dep.get("vulns", []):
                    g.findings.append(Finding("requirements.txt", 0, f"vuln:{v['id']}", "high",
                                              f"{dep['name']} {dep.get('version', '')}：{v['id']}"))
            extra.append("pip-audit")
        except (json.JSONDecodeError, KeyError):
            g.hint = f"pip-audit 輸出無法解析（exit {r.returncode}）"
    elif not audit:
        missing.append("pip-audit")
    if not files:
        g.status, g.summary = "skip", "沒有 .py 檔可掃描"
        return g
    high = sum(f.severity == "high" for f in g.findings)
    g.summary = f"{len(files)} 個檔；high {high}、其他 {len(g.findings) - high}" + (
        f"；# nosec 略過 {g.suppressed}" if g.suppressed else "") + (
        f"（加跑 {'、'.join(extra)}）" if extra else "（只跑內建規則）")
    if missing and not g.hint:
        g.hint = f"未安裝 {'、'.join(missing)}（只跑內建規則）：pip install {' '.join(missing)}"
    if high:
        g.status = "fail"
    return g


# ── 報告 ───────────────────────────────────────────────────────────

ICON = {"pass": "✅", "fail": "❌", "skip": "⏭️"}


def verdict(gates: list[Gate], strict: bool) -> str:
    bad = {"fail", "skip"} if strict else {"fail"}
    return "fail" if any(g.status in bad for g in gates) else "pass"


def render_md(gates: list[Gate], v: str, root: Path) -> str:
    lines = [f"# 品質守門：{ICON['pass'] if v == 'pass' else ICON['fail']} {v.upper()}", "",
             f"> 路徑：`{root}`", "", "| 關 | 狀態 | 摘要 | 提示 |", "|---|---|---|---|"]
    for g in gates:
        lines.append(f"| {g.name} | {ICON[g.status]} {g.status} | {g.summary} | {g.hint} |")
    for g in gates:
        if not g.findings:
            continue
        lines += ["", f"## {g.name}（{len(g.findings)}）", ""]
        for f in g.findings[:50]:
            loc = f"{f.file}:{f.line}" if f.line else (f.file or "—")
            lines.append(f"- [{f.severity}] `{loc}` {f.rule} — {f.message}")
        if len(g.findings) > 50:
            lines.append(f"- …另 {len(g.findings) - 50} 筆（見 JSON）")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="一支指令跑 tests／lint／security 三道品質關")
    ap.add_argument("--path", type=Path, default=Path("."), help="要檢查的專案目錄（預設目前目錄）")
    ap.add_argument("--only", default=",".join(GATES), help=f"只跑這幾關，逗號分隔（{','.join(GATES)}）")
    ap.add_argument("--python", default=sys.executable, help="跑 pytest 用的 python（通常是專案 venv）")
    ap.add_argument("--fail-under", type=float, help="行覆蓋率低於此值 → tests 關失敗（需 pytest-cov）")
    ap.add_argument("--timeout", type=int, default=600, help="pytest 逾時秒數")
    ap.add_argument("--strict", action="store_true", help="skip 也算失敗（CI 用：缺工具不放行）")
    ap.add_argument("--json", type=Path, help="JSON 結果輸出路徑（給 AI／程式讀）")
    ap.add_argument("--md", type=Path, help="Markdown 報告輸出路徑（給人看）")
    args = ap.parse_args(argv)

    only = [x.strip() for x in args.only.split(",") if x.strip()]
    bad = [x for x in only if x not in GATES]
    if bad:
        ap.error(f"--only 不認得 {bad}；可用 {','.join(GATES)}")
    root = args.path.resolve()
    if not root.exists():
        ap.error(f"--path 不存在：{root}")

    gates = []
    if "tests" in only:
        gates.append(gate_tests(root, args.python, args.fail_under, args.timeout))
    if "lint" in only:
        gates.append(gate_lint(root))
    if "security" in only:
        gates.append(gate_security(root))
    v = verdict(gates, args.strict)
    md = render_md(gates, v, root)
    print(md)
    if args.json:
        args.json.write_text(json.dumps({"verdict": v, "path": str(root), "strict": args.strict,
                                         "gates": [asdict(g) for g in gates]}, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    if args.md:
        args.md.write_text(md, encoding="utf-8")
    return 0 if v == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())

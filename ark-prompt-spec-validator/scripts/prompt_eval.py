#!/usr/bin/env python3
"""prompt_eval.py — L2 behavioral eval for a prompt file (SKILL.md / system prompt).

Usage:
  python prompt_eval.py evals/<slug>.eval.yaml [--runs N] [--json out.json] [--only E-1,E-3] [--dry-run]

Runners:
  anthropic : POST /v1/messages with the target file as system prompt (needs ANTHROPIC_API_KEY)
  cmd       : run an arbitrary CLI; placeholders {target} {input} {input_file}; stdout = response

Deterministic assertions (expect.*) decide pass/fail and feed the score.
`judge` (LLM-as-judge) is recorded as trust=llm-distilled and never enters the score.
Exit code: 0 all deterministic cases ok, 1 otherwise.
Schema: references/eval-schema.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("需要 PyYAML：pip install pyyaml", file=sys.stderr)
    sys.exit(3)

FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.M)


# ---------------------------------------------------------------- runners
def run_anthropic(system: str, user: str, runner: dict, timeout: int) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY 未設定")
    body = {
        "model": runner.get("model", "claude-sonnet-4-6"),
        "max_tokens": int(runner.get("max_tokens", 800)),
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def run_cmd(target: Path, user: str, runner: dict, timeout: int) -> str:
    tpl = runner.get("command")
    if not tpl:
        raise RuntimeError("runner.kind=cmd 需要 command 列表")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tf:
        tf.write(user)
        input_file = tf.name
    cmd = [str(c).replace("{target}", str(target)).replace("{input}", user).replace("{input_file}", input_file) for c in tpl]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0 and not p.stdout:
        raise RuntimeError(f"cmd 非零退出 {p.returncode}: {p.stderr[-300:]}")
    return p.stdout


# ---------------------------------------------------------------- assertions
def check(expect: dict, resp: str) -> list[str]:
    fails = []
    low = resp.lower()
    for s in expect.get("must_contain", []) or []:
        if str(s).lower() not in low:
            fails.append(f"must_contain 缺 '{s}'")
    for s in expect.get("must_not_contain", []) or []:
        if str(s).lower() in low:
            fails.append(f"must_not_contain 出現 '{s}'")
    if rx := expect.get("regex"):
        if not re.search(rx, resp, re.M):
            fails.append(f"regex 未匹配 /{rx}/")
    if expect.get("starts_with") and not resp.lstrip().startswith(str(expect["starts_with"])):
        fails.append(f"starts_with 不符 '{expect['starts_with']}'")
    if (mx := expect.get("max_chars")) and len(resp) > int(mx):
        fails.append(f"長度 {len(resp)} > max_chars {mx}")
    if (mn := expect.get("min_chars")) and len(resp) < int(mn):
        fails.append(f"長度 {len(resp)} < min_chars {mn}")
    if expect.get("json") or expect.get("json_keys"):
        try:
            obj = json.loads(FENCE_RE.sub("", resp.strip()))
        except json.JSONDecodeError as e:
            fails.append(f"非合法 JSON：{e.msg}")
        else:
            for k in expect.get("json_keys", []) or []:
                if not isinstance(obj, dict) or k not in obj:
                    fails.append(f"json 缺鍵 '{k}'")
    return fails


def judge(question: str, resp: str, runner: dict, timeout: int) -> bool | None:
    if runner.get("kind") != "anthropic":
        return None
    q = f"{question}\n\n=== 待評回應 ===\n{resp}\n=== 結束 ===\n只輸出 PASS 或 FAIL 開頭。"
    try:
        out = run_anthropic("你是嚴格的評審，只依據給定判準回答。", q, runner, timeout)
    except Exception:
        return None
    return out.strip().upper().startswith("PASS")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("eval_yaml")
    ap.add_argument("--runs", type=int)
    ap.add_argument("--json")
    ap.add_argument("--only", help="逗號分隔案例 ID")
    ap.add_argument("--dry-run", action="store_true", help="只驗 yaml 結構，不呼叫 runner")
    a = ap.parse_args()

    yp = Path(a.eval_yaml)
    spec = yaml.safe_load(yp.read_text(encoding="utf-8")) or {}
    target = (yp.parent / spec["target"]).resolve()
    if not target.exists():
        print(f"❌ target 不存在：{target}", file=sys.stderr)
        sys.exit(2)
    runner = spec.get("runner") or {"kind": "anthropic"}
    runs = a.runs or int(spec.get("runs", 3))
    threshold = float(spec.get("threshold", 0.8))
    timeout = int(spec.get("timeout_sec", 90))
    cases = spec.get("cases") or []
    if a.only:
        keep = set(a.only.split(","))
        cases = [c for c in cases if c.get("id") in keep]

    # structural checks on the yaml itself
    ids = [c.get("id", "") for c in cases]
    nums = sorted(int(i[2:]) for i in ids if re.fullmatch(r"E-\d+", i))
    if nums != list(range(1, len(nums) + 1)) or len(set(ids)) != len(ids):
        print(f"⚠️ 案例 ID 需為 E-1..E-n 連續且不重複：{ids}", file=sys.stderr)
    for c in cases:
        if not c.get("expect") and not c.get("judge"):
            print(f"⚠️ {c.get('id')} 沒有 expect 也沒有 judge，無法評估", file=sys.stderr)
    if a.dry_run:
        print(f"yaml OK · target={target} · cases={len(cases)} · runs={runs}")
        sys.exit(0)

    system = target.read_text(encoding="utf-8")
    results = []
    for c in cases:
        cid, expect, jq = c.get("id"), c.get("expect") or {}, c.get("judge")
        trust = "deterministic" if expect else "llm-distilled"
        passed, jpass, jtotal, failures = 0, 0, 0, []
        for r in range(runs):
            try:
                resp = run_anthropic(system, c["input"], runner, timeout) if runner.get("kind", "anthropic") == "anthropic" \
                    else run_cmd(target, c["input"], runner, timeout)
            except Exception as e:
                failures.append({"run": r + 1, "error": str(e)[:200]})
                continue
            fails = check(expect, resp) if expect else []
            if not fails:
                passed += 1
            else:
                failures.append({"run": r + 1, "fails": fails, "response_head": resp[:240]})
            if jq:
                v = judge(jq, resp, runner, timeout)
                if v is not None:
                    jtotal += 1
                    jpass += int(v)
        rate = passed / runs if runs else 0
        ok = rate >= threshold if trust == "deterministic" else None
        results.append({
            "id": cid, "intent": c.get("intent", "behavior"), "trust": trust,
            "passed": passed, "total": runs, "pass_rate": round(rate, 3), "ok": ok,
            "failures": failures, "judge": {"passed": jpass, "total": jtotal} if jq else None,
        })
        mark = "✅" if ok else ("❌" if ok is False else "ℹ️")
        jtxt = f" · judge {jpass}/{jtotal}" if jq else ""
        print(f"{mark} {cid} [{c.get('intent','behavior')}] {passed}/{runs}{jtxt}")

    det = [r for r in results if r["trust"] == "deterministic"]
    llm = [r for r in results if r["trust"] == "llm-distilled"]
    det_ok = sum(1 for r in det if r["ok"])
    llm_ok = sum(1 for r in llm if r["judge"] and r["judge"]["total"] and r["judge"]["passed"] / r["judge"]["total"] >= threshold)
    summary = {
        "deterministic": {"ok": det_ok, "total": len(det), "score": round(det_ok / len(det) * 100, 1) if det else None},
        "llm_distilled": {"ok": llm_ok, "total": len(llm)},
    }
    out = {"tool": "prompt_eval", "target": str(target), "runs": runs, "threshold": threshold,
           "runner": runner.get("kind", "anthropic"), "cases": results, "summary": summary}
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    s = summary["deterministic"]
    print(f"\nL2 deterministic {s['ok']}/{s['total']} → {s['score']} · llm-distilled {llm_ok}/{len(llm)}（不計分）")
    sys.exit(0 if det_ok == len(det) else 1)


if __name__ == "__main__":
    main()

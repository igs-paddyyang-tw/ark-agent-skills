#!/usr/bin/env python3
"""aiqa_run — 依 checklist 在 BlueStacks（adb）或合成裝置（fake）執行測試項，留證據、判定、寫 run 目錄。

用法:
  python aiqa_run.py --checklist checklist.json --backend fake [--items ID,ID] [--tiers T1,T3,T5] [--out artifacts/aiqa]
  python aiqa_run.py --checklist checklist.json --backend adb --device 127.0.0.1:5555 --reader tesseract --visual llm
gating：NA tier → NA；block_if / 未綁定步驟 / 需 harness 而 pack 無 → BLOCK（不假裝跑）；T4 → BLOCK（v1 不支援多實例）。
判定：aiqa_oracle（腳本）；AI 只提供讀數與是非題。重複結果不一致 → FLAKY。
run 目錄：artifacts/aiqa/<run_id>/{manifest.json, results.json, items/<id>/rep-k/{step-*.png, roi-*.png, observations.json, verdict.json}, trace.jsonl}
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aiqa_common as C  # noqa: E402
import aiqa_device as D  # noqa: E402
import aiqa_oracle as O  # noqa: E402

DEFAULT_TIERS = ("T1", "T2", "T3", "T5")


class Blocked(Exception):
    pass


class Executor:
    def __init__(self, dev, pack: dict, rep_dir: pathlib.Path, reader: str, visual: str, llm, timeout_s: float):
        self.dev, self.pack, self.dir, self.reader, self.visual_engine, self.llm = dev, pack, rep_dir, reader, visual, llm
        self.obs: dict = {}
        self.marks: dict = {}
        self.evidence: list[dict] = []
        self.step = 0
        self.t0 = dev.now()
        self.timeout_s = timeout_s
        self.dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ helpers
    def _shot(self, tag: str) -> pathlib.Path:
        self.step += 1
        p = self.dir / f"step-{self.step:02d}-{re.sub(r'[^A-Za-z0-9_-]+', '_', tag)[:30]}.png"
        self.dev.screenshot(p)
        return p

    def _record(self, name, value):
        self.obs.setdefault(name, []).append(value)

    def _check_timeout(self):
        if self.dev.now() - self.t0 > self.timeout_s:
            raise TimeoutError(f"item 超過 {self.timeout_s}s")

    def screen(self, img: pathlib.Path | None = None) -> str:
        img = img or self._shot("detect")
        r = D.detect_screen(self.pack, img)
        if r["screen"] == "unknown" and self.dev.truth is not None:  # fake 後端：模板未命中時仍以模板為準，不偷看 truth
            pass
        return r["screen"]

    # ------------------------------------------------------------ actions
    def run_actions(self, actions: list[dict]):
        for a in actions:
            self._check_timeout()
            fn = getattr(self, "a_" + a.get("do", ""), None)
            if fn is None:
                raise Blocked(f"未知動作 {a.get('do')}")
            fn(a)

    def a_manual_step(self, a):
        raise Blocked(f"NEEDS_BINDING: 步驟未綁定「{a.get('text')}」")

    def a_harness(self, a):
        cap = {"trigger1": "trigger", "trigger2": "trigger", "gm": "gm", "locale": "gm"}.get(a.get("name"), a.get("name"))
        if (self.pack.get("harness") or {}).get(cap, "none") in (None, "none"):
            raise Blocked(f"需 harness:{a.get('name')}，pack 未提供（harness.{cap}=none）")
        raise Blocked(f"harness:{a.get('name')} adapter 尚未實作（v1）")

    def a_navigate(self, a):
        to = a["to"]
        cur = self.screen()
        if cur == to:
            return
        nav = self.pack.get("navigation") or {}
        path = nav.get(f"{cur}->{to}") or nav.get(f"*->{to}")
        if not path and cur != "lobby" and nav.get(f"{cur}->lobby") and nav.get(f"lobby->{to}"):
            path = nav[f"{cur}->lobby"] + nav[f"lobby->{to}"]
        if not path:
            raise Blocked(f"pack.navigation 無 {cur}->{to} 路徑")
        for st in path:
            if "tap" in st:
                self.a_tap({"target": st["tap"]})
            elif "key" in st:
                self.a_key({"name": st["key"]})
            elif "wait_screen" in st:
                self.a_wait({"screen": st["wait_screen"], "timeout_s": st.get("timeout_s", 10)})
        if self.screen() != to:
            raise Blocked(f"navigate 後畫面不是 {to}")

    def a_tap(self, a):
        img = self._shot("before_tap")
        loc = D.locate(self.pack, a["target"], img)
        self.dev.tap(loc["x"], loc["y"])
        self.dev.tick(0.5)
        if a.get("wait"):
            k, _, v = a["wait"].partition(":")
            self.a_wait({k: v, "timeout_s": a.get("timeout_s", 12)})

    def a_key(self, a):
        self.dev.key(a["name"]); self.dev.tick(0.5)

    def a_swipe(self, a):
        self.dev.swipe(*a.get("from", [0, 0]), *a.get("to", [0, 0]))

    def a_wait(self, a):
        timeout = float(a.get("timeout_s", 12))
        if "seconds" in a:
            self.dev.sleep(float(a["seconds"])); return
        if "screen" in a:
            t0 = self.dev.now()
            while self.dev.now() - t0 <= timeout:
                if self.screen() == a["screen"]:
                    return
                self.dev.tick(0.5)
            raise Blocked(f"等待 screen:{a['screen']} 超時 {timeout}s（現在 {self.screen()}）")
        if "state" in a:
            st = (self.pack.get("states") or {}).get(a["state"], {"method": "stable"})
            r = self.dev.wait_stable(self.dir / "_stable", float(st.get("timeout_s", timeout)))
            if not r["stable"]:
                self._record("unstable_timeouts", a["state"])
            return
        if "until_popup" in a:
            t0 = self.dev.now(); target = f"error_{a['until_popup']}"
            since = self.marks.get(a.get("since"), t0) if a.get("since") else t0
            while self.dev.now() - t0 <= timeout:
                if self.screen() == target:
                    self._record(a.get("record", "t_popup"), round(self.dev.now() - since, 2)); return
                self.dev.tick(0.5)
            self._record(a.get("record", "t_popup"), None); return
        raise Blocked(f"wait 參數不明 {a}")

    def a_read(self, a):
        img = self._shot(f"read_{a['roi']}")
        r = D.read_roi(self.dev, self.pack, a["roi"], img, self.dir, self.reader, a.get("oracle", "ocr_number"), self.llm)
        self._record(a["name"], r["value"])
        self.evidence.append({"kind": "read", "name": a["name"], "value": r["value"], "engine": r["engine"], "confidence": r["confidence"], "crop": r["crop"], "screen": str(img)})

    def a_capture(self, a):
        img = self._shot(f"capture_{a.get('name', 'shot')}")
        ev = {"kind": "capture", "name": a.get("name"), "screen": str(img)}
        if a.get("roi"):
            import ark_mobile_adb as M
            rect = C.pack_target(self.pack, f"roi:{a['roi']}")["rect"]
            ev["crop"] = M.crop_zoom(img, rect, float(a.get("zoom", 3)), self.dir / f"cap-{a.get('name')}-{self.step:02d}.png")["path"]
        self.evidence.append(ev)

    def a_ask(self, a):
        img = self._shot(f"ask_{a['name']}")
        r = D.visual(self.dev, a["question"], img, self.visual_engine, self.llm)
        self._record(a["name"], r)
        self.evidence.append({"kind": "visual", "name": a["name"], "question": a["question"], **r, "screen": str(img)})

    def a_repeat(self, a):
        for _ in range(int(a.get("times", 1))):
            self.run_actions(a.get("actions", []))

    def a_restart_app(self, a):
        self.dev.restart_app(); self.dev.tick(2.0)

    def a_net(self, a):
        if (self.pack.get("harness") or {}).get("network") not in ("adb", "clumsy"):
            raise Blocked("pack.harness.network=none，無法操作網路")
        self.dev.net(a.get("state") == "restore")
        self.marks["net_off" if a.get("state") != "restore" else "net_on"] = self.dev.now()

    def a_crash_check(self, a):
        r = self.dev.logcat_crash()
        self._record("crash", bool(r.get("crash"))); self._record("foreground", self.dev.foreground_ok())
        if r.get("fatal"):
            self.evidence.append({"kind": "logcat", "fatal": r["fatal"][:10]})

    def a_loop_spin(self, a):
        minutes = float(a.get("minutes", 1)); interval = float(a.get("interval_s", 10))
        end = self.dev.now() + minutes * 60
        last_hash, same_since, stuck = None, self.dev.now(), 0
        n = 0
        while self.dev.now() < end:
            self._check_timeout()
            img = self._shot("before_tap")
            loc = D.locate(self.pack, "btn:spin", img)
            self.dev.tap(loc["x"], loc["y"]); self.dev.tick(0.5)
            self.dev.wait_stable(self.dir / "_stable", 12)
            n += 1
            h = C.sha_file(img)[:16]
            if h == last_hash:
                if self.dev.now() - same_since > 120:
                    stuck += 1
            else:
                last_hash, same_since = h, self.dev.now()
            if n % max(1, int(interval / 2)) == 0:
                r = self.dev.logcat_crash()
                if r.get("crash"):
                    self._record("crash", True); break
            # 保留少量截圖：每 interval 一張，其餘刪除
            if n % max(1, int(interval / 2)) != 0:
                img.unlink(missing_ok=True)
        self._record("spins", n); self._record("stuck_frames", stuck)
        if "crash" not in self.obs:
            self._record("crash", False)
        self._record("foreground", self.dev.foreground_ok())


# ---------------------------------------------------------------- item
def gate(item: dict, pack: dict, tiers: tuple) -> tuple[str | None, str | None]:
    """→ (blocked_reason, na_reason)"""
    if item.get("tier") == "NA":
        return None, item.get("tier_reason") or "N/A"
    if item.get("tier") not in tiers:
        return f"tier {item['tier']} 不在本 run 範圍 {tiers}", None
    if item.get("tier") == "T4":
        return "T4 多實例 v1 不支援", None
    if item.get("block_if"):
        return "block_if: " + ", ".join(item["block_if"]), None
    if item.get("unbound_steps"):
        return f"NEEDS_BINDING: {len(item['unbound_steps'])} 個步驟未綁定 → bindings.yaml", None
    if any(a.get("needs_binding") for a in item.get("assertions", [])):
        return "NEEDS_BINDING: 斷言缺 expr / roi（需把預期結果寫成 expr）", None
    return None, None


def run_item(item: dict, pack: dict, dev_factory, run_dir: pathlib.Path, reader: str, visual: str, llm, timeout_s: float) -> dict:
    item_dir = run_dir / "items" / item["id"]
    item_dir.mkdir(parents=True, exist_ok=True)
    rep_results, reps = [], []
    for k in range(1, int(item.get("repeat", 1)) + 1):
        rep_dir = item_dir / f"rep-{k}"
        trace = D.Trace(rep_dir / "trace.jsonl")
        dev = dev_factory(trace)
        ex = Executor(dev, pack, rep_dir, reader, visual, llm, timeout_s)
        status, err = "ok", None
        try:
            ex.run_actions(item.get("actions", []))
            # 視覺斷言若沒有對應 ask，用最後畫面問一次
            for a in item.get("assertions", []):
                if a.get("oracle") == "visual" and (a.get("obs") or a["id"]) not in ex.obs and a.get("question"):
                    ex.a_ask({"name": a.get("obs") or a["id"], "question": a["question"]})
            ex._record("screen", ex.screen())
        except Blocked as e:
            status, err = "blocked", str(e)
        except TimeoutError as e:
            status, err = "timeout", str(e)
        except (C.PackError, Exception) as e:  # noqa: BLE001
            status, err = "error", f"{type(e).__name__}: {e}"
        # visual 斷言的 obs 名稱對齊
        obs = dict(ex.obs)
        for a in item.get("assertions", []):
            if a.get("oracle") == "visual":
                src = a.get("obs") or a["id"]
                if src in obs and a["id"] not in obs:
                    obs[a["id"]] = obs[src]
        results = O.evaluate(item.get("assertions", []), obs)  # 中斷也判：已收集的觀察若已 FAIL，FAIL 優先於 BLOCK
        C.atomic_write(rep_dir / "observations.json", json.dumps({k2: v for k2, v in obs.items()}, ensure_ascii=False, default=str, indent=1))
        C.atomic_write(rep_dir / "verdict.json", json.dumps({"status": status, "error": err, "assertions": results, "evidence": ex.evidence}, ensure_ascii=False, default=str, indent=1))
        reps.append({"rep": k, "status": status, "error": err, "assertions": results, "evidence_count": len(ex.evidence), "elapsed_s": round(dev.now() - ex.t0, 2)})
        if status != "ok":
            break
        rep_results.append(results)
    blocked = next((r["error"] for r in reps if r["status"] in ("blocked",)), None)
    errored = next((r["error"] for r in reps if r["status"] in ("error", "timeout")), None)
    hard_fail = any(a["result"] == "FAIL" for r in reps for a in r["assertions"])
    if hard_fail and (blocked or errored):
        v = {"verdict": "FAIL", "reason": f"斷言 FAIL（流程隨後中斷：{blocked or errored}）"}
    else:
        v = O.item_verdict(rep_results, blocked=blocked)
        if errored and not blocked:
            v = {"verdict": "NEEDS_HUMAN", "reason": f"執行錯誤：{errored}"}
    out = {"id": item["id"], "title": item["title"], "category": item.get("category"), "folder": item.get("folder"), "tier": item["tier"],
           **v, "reps": reps, "baseline": item.get("baseline"), "dir": str(item_dir)}
    C.atomic_write(item_dir / "verdict.json", json.dumps(out, ensure_ascii=False, default=str, indent=1))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="aiqa runner")
    ap.add_argument("--checklist", required=True)
    ap.add_argument("--backend", default=None, choices=["adb", "fake"])
    ap.add_argument("--device")
    ap.add_argument("--reader", default=None, choices=["fake", "tesseract", "llm", "dual"], help="dual = tesseract+llm 雙讀，不一致 → NEEDS_HUMAN")
    ap.add_argument("--visual", default=None, choices=["fake", "llm"])
    ap.add_argument("--out", default="artifacts/aiqa")
    ap.add_argument("--items", help="逗號分隔 id")
    ap.add_argument("--tiers", default=",".join(DEFAULT_TIERS))
    ap.add_argument("--max-items", type=int)
    ap.add_argument("--timeout-s", type=float, default=300)
    ap.add_argument("--allow-uncalibrated", action="store_true")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--bugs", help="fake 後端注入 bug 的 JSON，例 '{\"payout_off_by\": 10}'")
    ap.add_argument("--max-llm-calls", type=int, default=300)
    a = ap.parse_args()
    doc = json.loads(pathlib.Path(a.checklist).read_text(encoding="utf-8"))
    try:
        pack = C.load_pack(doc["game"], doc.get("machine"))
    except C.PackError as e:
        C.fail("BAD_INPUT", str(e), "")
    backend = a.backend or pack.get("backend_default", "adb")
    if backend == "adb" and not pack.get("calibrated") and not a.allow_uncalibrated:
        C.fail("GATE_BLOCKED", "gamepack 未校準（calibrated: false）", "先校準 screens/buttons/rois；或 --backend fake 做 dry-run；或 --allow-uncalibrated（結果只供除錯）")
    reader = a.reader or ("fake" if backend == "fake" else "tesseract")
    visual = a.visual or ("fake" if backend == "fake" else "llm")
    if backend == "adb" and (reader == "fake" or visual == "fake"):
        C.fail("BAD_INPUT", "adb 後端不可用 fake reader/visual", "--reader tesseract|llm --visual llm")
    llm = None
    if reader in ("llm", "dual") or visual == "llm":
        from aiqa_llm import LLM
        llm = LLM(max_calls=a.max_llm_calls)
    bugs = json.loads(a.bugs) if a.bugs else None
    run_dir = C.new_run_dir(pathlib.Path(a.out), doc["game"], doc.get("machine"))
    if backend == "adb":
        probe = D.make_device("adb", D.Trace(run_dir / "trace.jsonl"), a.device, pack.get("package"))
        w, h = probe.wm_size()
        res = pack.get("resolution") or {}
        if (w, h) != (res.get("width"), res.get("height")):
            C.fail("BAD_INPUT", f"裝置 wm size {w}x{h} ≠ pack {res}", "BlueStacks 顯示設定改成 pack 解析度，或重新校準 pack")
        serial = probe.serial
        dev_factory = lambda trace: D.make_device("adb", trace, serial, pack.get("package"))  # noqa: E731
    else:
        serial = "fake"
        shared = {"dev": None}
        def dev_factory(trace, _s=shared):  # fake 裝置跨 item 共用同一個遊戲狀態（像真機一樣連續）
            if _s["dev"] is None:
                _s["dev"] = D.make_device("fake", trace, seed=a.seed, bugs=bugs)
            else:
                _s["dev"].trace = trace
            return _s["dev"]
    items = doc["items"]
    if a.items:
        want = set(a.items.split(",")); items = [i for i in items if i["id"] in want]
    if a.max_items:
        items = items[: a.max_items]
    tiers = tuple(a.tiers.split(","))
    manifest = {"run_id": run_dir.name, "contract": C.CONTRACT, "created_at": C.now(), "checklist": str(a.checklist), "checklist_sha256": C.sha_file(a.checklist),
                "game": doc["game"], "machine": doc.get("machine"), "pack_sha256": pack["_sha256"], "backend": backend, "device": serial,
                "reader": reader, "visual": visual, "tiers": list(tiers), "protocol": C.PROTOCOL_VERSION, "skill_version": C.SKILL_VERSION,
                "llm": llm.meta() if llm else None, "bugs": bugs}
    C.atomic_write(run_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
    results, t0 = [], time.time()
    for it in items:
        blocked, na = gate(it, pack, tiers)
        if blocked or na:
            v = O.item_verdict([], blocked=blocked, na=na)
            results.append({"id": it["id"], "title": it["title"], "category": it.get("category"), "folder": it.get("folder"), "tier": it["tier"], **v,
                            "reps": [], "baseline": it.get("baseline"), "dir": None})
            continue
        results.append(run_item(it, pack, dev_factory, run_dir, reader, visual, llm, a.timeout_s))
        C.atomic_write(run_dir / "results.json", json.dumps({"results": results}, ensure_ascii=False, default=str, indent=1))
    counts = {v: sum(1 for r in results if r["verdict"] == v) for v in C.VERDICTS}
    manifest.update(finished_at=C.now(), elapsed_s=round(time.time() - t0, 1), counts=counts, items=len(results), llm=llm.meta() if llm else None)
    C.atomic_write(run_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
    C.atomic_write(run_dir / "results.json", json.dumps({"results": results}, ensure_ascii=False, default=str, indent=1))
    C.emit({"run": str(run_dir), "items": len(results), "counts": counts, "elapsed_s": manifest["elapsed_s"],
            "next": f"python aiqa_report.py --run {run_dir}"}, {"stage": "run", **(llm.meta() if llm else {})})


if __name__ == "__main__":
    main()

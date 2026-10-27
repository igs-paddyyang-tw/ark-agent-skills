#!/usr/bin/env python3
"""engine_trace — 把 FastTest 系 Go 快測引擎（金猴爺／slot_math_squad 範本）原樣跑 N 局，逐局錄下 主遊戲盤面＋MG／總贏分＋是否進特色，
轉成 Stage 的回放軌跡（proto-stage-result/1）→ 「引擎回放試玩版」（⑦-lite）。

為什麼：⑦ 正式試玩版要先有規格書、⑥ 玩法模型（每款數小時）；在那之前，引擎回放讓每款 Go 世代遊戲都有一個
「數學 = 該款快測引擎原樣」的單機試玩，可先看節奏、盤面、贏分分布。演出是泛用的（特色遊戲只顯示摘要）。

做法（不改原引擎，全在暫存複本）：
  1. check/check.go 的 GameCheck（主遊戲判獎入口）開頭記下本局盤面（只記每局第一次，= 主遊戲盤面）。
  2. main.go：GameProcess 呼叫後插入 __trialHook(主結果, 本局總贏分, 機率設定)；main 開頭 __trialInit()（固定 seed、stdout 導 DevNull）。
     `testcredit += GameProcess(...)` 會拆成 `__trialWin := GameProcess(...); testcredit += __trialWin`。（output 產圖套件保留；鉤子在迴圈內就結束程式，不會跑到產圖。）
  3. go run → JSONL（每局 {i, win, mg, sg, grid}）→ trace.json（SpinResult 陣列，整數 credit）。
用法：python engine_trace.py --engine <引擎目錄（含 go.mod、main.go）> --n 3000 --seed 7 --out <dir> [--name 遊戲名]
輸出：<out>/trace.json、<out>/engine-trace.jsonl、<out>/engine-trace.meta.json；exit 0 成功 / 2 改寫失敗 / 3 編譯或執行失敗
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HOOK = r'''%(godebug)spackage main

import (
	"bufio"
	"encoding/json"
	"math/rand"
	"os"
	"reflect"
	"strconv"
	"strings"

	__tc "%(mod)s/check"
)

var __tw *bufio.Writer
var __tout *os.File
var __tn, __tmax, __tkeep, __tfeat int
var __tsum, __tmg float64
var __tuned = map[string]interface{}{}

// __trialTune：試玩用一般模式——道具卡／Buy Bonus／保底／強制觸發類開關一律關掉（反射，欄位不存在就略過）
func __trialTune(ps interface{}) {
	if os.Getenv("TRIAL_NOTUNE") == "1" {
		return
	}
	p := reflect.ValueOf(ps)
	if p.Kind() == reflect.Ptr {
		p = p.Elem()
	}
	if !p.IsValid() || p.Kind() != reflect.Struct {
		return
	}
	for i := 0; i < p.NumField(); i++ {
		f := p.Field(i)
		n := p.Type().Field(i).Name
		ln := strings.ToLower(n)
		if !(strings.Contains(ln, "itemcard") || strings.Contains(ln, "buybonus") || strings.Contains(ln, "guarentee") && strings.Contains(ln, "enable") ||
			strings.Contains(ln, "guarantee") && strings.Contains(ln, "enable") || strings.HasPrefix(ln, "force") || strings.HasPrefix(ln, "istest") || ln == "trigger") {
			continue
		}
		if !f.CanSet() || strings.Contains(","+os.Getenv("TRIAL_TUNE_KEEP")+",", ","+n+",") {
			continue
		}
		switch f.Kind() {
		case reflect.Bool:
			if f.Bool() {
				__tuned[n] = true
				f.SetBool(false)
			}
		case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
			if f.Int() != 0 {
				__tuned[n] = f.Int()
				f.SetInt(0)
			}
		}
	}
}

func __trialInit() {
	seed, _ := strconv.ParseInt(os.Getenv("TRIAL_SEED"), 10, 64)
	rand.Seed(seed)
	__tmax, _ = strconv.Atoi(os.Getenv("TRIAL_N"))
	__tkeep, _ = strconv.Atoi(os.Getenv("TRIAL_KEEP"))
	if __tkeep <= 0 || __tkeep > __tmax {
		__tkeep = __tmax
	}
	f, err := os.Create(os.Getenv("TRIAL_OUT"))
	if err != nil {
		panic(err)
	}
	__tout = f
	__tw = bufio.NewWriterSize(f, 1<<20)
	if dn, err := os.OpenFile(os.DevNull, os.O_WRONLY, 0); err == nil {
		os.Stdout = dn
	}
}

func __num(v reflect.Value) (float64, bool) {
	switch v.Kind() {
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		return float64(v.Int()), true
	case reflect.Float32, reflect.Float64:
		return v.Float(), true
	}
	return 0, false
}

func __trialHook(mr interface{}, win int64, ps interface{}) {
	rec := map[string]interface{}{"i": __tn, "win": win}
	v := reflect.ValueOf(mr)
	if v.Kind() == reflect.Ptr {
		v = v.Elem()
	}
	if f := v.FieldByName("TotalWin"); f.IsValid() {
		if x, ok := __num(f); ok {
			rec["mg"] = x
		}
	}
	if f := v.FieldByName("SpecialGame"); f.IsValid() && f.Kind() == reflect.Slice {
		rec["sg"] = f.Len()
	}
	if __tn == 0 {
		meta := map[string]interface{}{}
		p := reflect.ValueOf(ps)
		if p.Kind() == reflect.Ptr {
			p = p.Elem()
		}
		for _, k := range []string{"Bet_Cost", "Line_bet", "Bet_Line", "BetCost", "LineBet", "MaxWin"} {
			if p.IsValid() {
				if f := p.FieldByName(k); f.IsValid() {
					if x, ok := __num(f); ok {
						meta[k] = x
					}
				}
			}
		}
		rec["meta"] = meta
	}
	if __tn == 0 {
		rec["tuned"] = __tuned
	}
	rec["grid"] = __tc.TrialGrid
	__tc.TrialGrid = nil
	__tsum += float64(win)
	if x, ok := rec["mg"].(float64); ok {
		__tmg += x
	}
	if sg, ok := rec["sg"].(int); ok && sg > 0 {
		__tfeat++
	}
	if __tn < __tkeep {
		b, _ := json.Marshal(rec)
		__tw.Write(b)
		__tw.WriteByte('\n')
	}
	__tn++
	if __tn >= __tmax {
		b, _ := json.Marshal(map[string]interface{}{"summary": true, "spins": __tn, "win": __tsum, "mg": __tmg, "feat": __tfeat})
		__tw.Write(b)
		__tw.WriteByte('\n')
		__tw.Flush()
		__tout.Close()
		os.Exit(0)
	}
}
'''


def balanced_end(s: str, i: int) -> int:
    """s[i] == '(' → 對應的 ')' 位置。"""
    d = 0
    for j in range(i, len(s)):
        if s[j] == "(":
            d += 1
        elif s[j] == ")":
            d -= 1
            if d == 0:
                return j
    raise ValueError("括號不平衡")


def patch(eng: pathlib.Path) -> dict:
    mod = re.search(r"^module\s+(\S+)", (eng / "go.mod").read_text(encoding="utf-8"), re.M).group(1)
    # check.go：GameCheck 記盤面
    ck = eng / "check" / "check.go"
    s = ck.read_text(encoding="utf-8")
    ms = list(re.finditer(r"^func GameCheck\w*\(", s, re.M))  # GameCheck、GameCheckV2…（主遊戲版本分支都要記）
    if not ms:
        raise ValueError("check/check.go 沒有 GameCheck")
    for m in reversed(ms):
        close = balanced_end(s, m.end() - 1)
        sig = s[m.start():close + 1]
        pm = re.search(r"(\w+)\s+\[\]\[\]int", sig)
        if not pm:
            if m is ms[0] and len(ms) == 1:
                raise ValueError("GameCheck 沒有 [][]int 盤面參數")
            continue
        body = s.index("{", close)
        grid = pm.group(1)
        ins = (f"\n\tif TrialGrid == nil {{\n\t\tTrialGrid = make([][]int, len({grid}))\n\t\tfor __i := range {grid} {{\n"
               f"\t\t\tTrialGrid[__i] = append([]int(nil), {grid}[__i]...)\n\t\t}}\n\t}}\n")
        s = s[:body + 1] + ins + s[body + 1:]
    s += "\n// TrialGrid：engine_trace 注入（本局主遊戲盤面）\nvar TrialGrid [][]int\n"
    ck.write_text(s, encoding="utf-8")
    # main.go
    mp = eng / "main.go"
    s = mp.read_text(encoding="utf-8")
    hint = bet_hint(s)
    ps = re.search(r"(\w+)\s*(?:,\s*\w+\s*)?:?=\s*odds\.(?:NewProbSetting\w*|LoadProbSetting\w*)\(", s)
    psv = ps.group(1) if ps else "nil"
    if ps:
        e = balanced_end(s, ps.end() - 1)
        s = s[:e + 1] + f"\n\t__trialTune({psv})" + s[e + 1:]
    gm = None
    for m in re.finditer(r"^[ \t]*([\w \t,]+?)\s*(\+=|:=|=)\s*(\w+)\.GameProcess\(", s, re.M):
        gm = m
        break
    if not gm:
        raise ValueError("main.go 找不到 GameProcess 呼叫")
    close = balanced_end(s, gm.end() - 1)
    lhs, op, call = gm.group(1).strip(), gm.group(2), s[gm.start(3):close + 1]
    lhs_vars = [x.strip() for x in lhs.split(",")]
    start = gm.start(1) + (len(gm.group(1)) - len(gm.group(1).lstrip()))
    if op == "+=":
        new = f"__trialWin := {call}\n\t\t{lhs} += __trialWin"
        winv = "__trialWin"
    else:
        new = s[start:close + 1]
        named = [v for v in lhs_vars if re.search(r"earn|win|credit", v, re.I)]  # 多回傳值：取贏分那個（例 guaranteeCount, earnCredit／earn, pigStatus, pigNum）
        winv = lhs_vars[0] if len(lhs_vars) == 1 else (named[0] if named else lhs_vars[1])
    after = s[close + 1:]
    cm = re.search(r"(\w+)\.Clear\(\)", after)
    if not cm:
        raise ValueError("找不到主結果的 .Clear()")
    mr = cm.group(1)
    s = s[:start] + new + f"\n\t\t__trialHook({mr}, int64({winv}), {psv})" + after
    s = re.sub(r"(func main\(\)\s*\{)", r"\1\n\t__trialInit()", s, count=1)
    mp.write_text(s, encoding="utf-8")
    gd = "" if "randseednop" in s else "//go:debug randseednop=0\n\n"  # Go 1.24 起 rand.Seed 預設無效
    (eng / "zz_trial_hook.go").write_text(HOOK % {"mod": mod, "godebug": gd}, encoding="utf-8")
    return {"bet_hint": hint, "module": mod, "prob_setting_var": psv, "main_result_var": mr, "win_var": winv, "call_op": op}


def local_go_toolchain(eng: pathlib.Path) -> None:
    """go.mod 要求比本機新的 go（例 1.25）且無法下載 toolchain 時：降成本機版本、去掉 toolchain 行（GOTOOLCHAIN=local）。"""
    v = re.search(r"go(\d+\.\d+)", subprocess.run(["go", "version"], capture_output=True, text=True).stdout)
    gm = eng / "go.mod"
    s = gm.read_text(encoding="utf-8")
    m = re.search(r"^go (\d+)\.(\d+)", s, re.M)
    if v and m and tuple(map(int, m.groups())) > tuple(map(int, v.group(1).split("."))):
        s = re.sub(r"^go .*$", f"go {v.group(1)}", s, count=1, flags=re.M)
        s = re.sub(r"^toolchain .*$\n?", "", s, flags=re.M)
        gm.write_text(s, encoding="utf-8")


def bet_hint(src: str) -> dict:
    """ProbSetting 沒有押注欄位時，從 main.go 常數讀（例 LINE_BET = 10、BET_COST = 50）。只收未註解的行。"""
    h = {}
    for line in src.splitlines():
        t = line.split("//", 1)[0]
        m = re.search(r"\b(LINE_BET|LineBet|Line_bet|BET_LINE|BetLine)\b\s*(?:int\w*\s*)?=\s*(\d+)", t)
        if m and "Line_bet" not in h:
            h["Line_bet"] = int(m.group(2))
        m = re.search(r"\b(BET_COST|BetCost|Bet_Cost|COST)\b\s*(?:int\w*\s*)?=\s*(\d+)", t)
        if m and "Bet_Cost" not in h:
            h["Bet_Cost"] = int(m.group(2))
    return h


def bet_of(meta: dict, hint: dict) -> int:
    lb = meta.get("Line_bet") or meta.get("LineBet") or meta.get("Bet_Line") or hint.get("Line_bet") or 1
    cost = meta.get("Bet_Cost") or meta.get("BetCost") or hint.get("Bet_Cost") or 1
    return int(lb * cost)


def stub_unfetchable(eng: pathlib.Path, err: str) -> bool:
    """模組下載失敗（例 golang.org/x/image 被擋）且只被非 main 套件的輔助檔用到（產圖）→ 該檔換成 stub：
    保留簽名不含外部型別的匯出函式、函式體 panic（鉤子在迴圈內就結束程式，不會跑到）。"""
    files = sorted({m for m in re.findall(r"^(\S+?\.go):\d+:\d+: \S+@v[\w.\-]+: ", err, re.M)})
    done = False
    for f in files:
        fp = eng / f
        if not fp.is_file():
            continue
        src = fp.read_text(encoding="utf-8")
        pkg = re.search(r"^package\s+(\w+)", src, re.M).group(1)
        if pkg == "main":
            continue
        out = [f"package {pkg}\n\n// engine_trace stub：原檔依賴的模組無法下載（試玩不會呼叫）\n"]
        for m in re.finditer(r"^func ([A-Z]\w*)\(([^)]*)\)\s*([^{]*)\{", src, re.M):
            if "." in m.group(2) + m.group(3):
                continue
            out.append(f"func {m.group(1)}({m.group(2)}) {m.group(3).strip()} {{ panic(\"trial stub\") }}\n")
        fp.write_text("\n".join(out), encoding="utf-8")
        done = True
    if done:
        gm = eng / "go.mod"
        mods = set(re.findall(r"(\S+)@v[\w.\-]+: ", err))
        g = gm.read_text(encoding="utf-8")
        for mo in mods:
            g = re.sub(r"^(require\s+)?\s*" + re.escape(mo) + r"\s+v\S+.*$", "", g, flags=re.M)
        gm.write_text(g, encoding="utf-8")
    return done


def unused_imports(eng: pathlib.Path, err: str) -> bool:
    """go 編譯錯誤 "xxx" imported and not used → 從 main.go 移除該 import（移除 output 後常見）。"""
    hit = re.findall(r'"([^"]+)" imported and not used', err)
    if not hit:
        return False
    mp = eng / "main.go"
    s = mp.read_text(encoding="utf-8")
    for h in hit:
        s = re.sub(r'^\s*(\w+\s+)?"' + re.escape(h) + r'"\s*$', "", s, flags=re.M)
    mp.write_text(s, encoding="utf-8")
    return True


def to_results(lines: list[dict], name: str, start_balance: int, bet: int) -> dict:
    bal = start_balance
    out = []
    # 盤面陣列比實際軸數寬（例 3 軸遊戲用 5 欄陣列、空格填 0）→ 所有局都是 0 的欄去掉
    ncol = max((len(x.get("grid") or []) for x in lines), default=0)
    grids = [x.get("grid") or [] for x in lines]
    keep = [c for c in range(ncol) if any(len(g) > c and any(v != 0 for v in g[c]) for g in grids)]
    for x in lines:
        if x.get("grid"):
            x["grid"] = [x["grid"][c] for c in keep if c < len(x["grid"])]
        win = int(x.get("win", 0))
        mg = int(x.get("mg", win))
        mg = min(mg, win)
        fg = win - mg
        grid = x.get("grid") or []
        r = {"schema": "proto-stage-result/1", "roundId": f"T{x['i'] + 1}", "requestId": None, "round": x["i"] + 1, "seed": None, "bet": bet,
             "betIndex": 0, "mode": "base", "reel": {"combo": 0, "stops": [0] * len(grid), "grid": [[f"S{v}" for v in col] for col in grid], "view": None},
             "base": {"winX": mg / bet, "win": mg, "ways": [], "scatter": None, "trigger": bool(x.get("sg")), "extra": {}},
             "feature": ({"type": "特色遊戲", "draw": {}, "group": None, "winX": fg / bet, "win": fg, "capped": False, "spinsPlayed": None,
                          "script": {"engine": "summary"}, "awaitAction": None} if (x.get("sg") or fg > 0) else None),
             "totalX": win / bet, "totalWin": win, "capped": False, "winType": "NO_WIN", "balanceBefore": bal, "balanceAfter": bal - bet + win, "fx": x["i"]}
        tiers = [[100, "GOLDEN"], [50, "SUPER"], [25, "MEGA"], [10, "BIG"], [5, "SMALL"], [1, "LIGHT"], [0, "NORMAL"]]
        r["winType"] = "NO_WIN" if not win else next(n for t, n in tiers if win / bet >= t)
        bal = r["balanceAfter"]
        out.append(r)
    return {"schema": "proto-stage-trace/1", "info": {"service": "replay", "balance": start_balance, "bets": [bet], "defaultBet": bet, "betBase": bet,
                                                       "name": name}, "results": out}


def to_lite(tr: dict) -> dict:
    """完整軌跡 → 精簡格式 proto-stage-trace-lite/1（data/ 體積 < 1 MB）：每局 [總贏分, 主遊戲贏分, 有無特色, 盤面]，回放包載入時展開。"""
    rounds = [[r["totalWin"], r["base"]["win"], 1 if r["feature"] else 0, [[int(v[1:]) for v in col] for col in r["reel"]["grid"]]] for r in tr["results"]]
    return {"schema": "proto-stage-trace-lite/1", "info": tr["info"], "meta": tr.get("meta"), "loop": tr.get("loop", True), "rounds": rounds}


def expand_lite(lt: dict) -> dict:
    """to_lite 的反函式（回放包 JS 的 expand 與此同邏輯；測試用）。"""
    lines = [{"i": i, "win": w, "mg": mg, "sg": sg, "grid": g} for i, (w, mg, sg, g) in enumerate(lt["rounds"])]
    tr = to_results(lines, lt["info"].get("name", ""), lt["info"]["balance"], lt["info"]["defaultBet"])
    tr["meta"], tr["loop"] = lt.get("meta"), lt.get("loop", True)
    return tr


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--engine", required=True)
    ap.add_argument("--n", type=int, default=3000, help="錄進回放軌跡的局數")
    ap.add_argument("--sim", type=int, default=200000, help="總共跑幾局（算 RTP 樣本；≥ n）")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default="")
    ap.add_argument("--engine-label", default="", help="寫進軌跡 meta 的引擎來源（例 slot_math_squad 相對路徑）")
    ap.add_argument("--balance", type=int, default=0, help="起始餘額（0 = 押注 × 2000）")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--keep", default="", help="不要被 __trialTune 關掉的 ProbSetting 欄位（逗號分隔；例 天井是線上基本規則：GuarenteeSpinEnable）")
    ap.add_argument("--config", help="引擎的 config json（ark-game-quicktest A 軌：以環境變數 QT_CONFIG 傳給引擎；例 quicktest/config/live.json）")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        eng = pathlib.Path(td) / "engine"
        shutil.copytree(a.engine, eng, ignore=shutil.ignore_patterns("*.exe", "*.txt", "*.png", "*.csv", "__debug_bin*", ".git"))
        local_go_toolchain(eng)
        try:
            info = patch(eng)
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"success": False, "stage": "patch", "error": str(e)}, ensure_ascii=False)); sys.exit(2)
        env = {**os.environ, "GOFLAGS": "-mod=mod", "GOSUMDB": "off", "TRIAL_SEED": str(a.seed), "TRIAL_N": str(a.sim), "TRIAL_KEEP": str(a.n), "TRIAL_OUT": str(out / "engine-trace.jsonl"), "CGO_ENABLED": "0", "GOTOOLCHAIN": "local",
               **({"QT_CONFIG": str(pathlib.Path(a.config).resolve())} if a.config else {}), "QT_SEED": str(a.seed), "TRIAL_TUNE_KEEP": a.keep}
        err = ""
        for _ in range(4):
            b = subprocess.run(["go", "build", "-o", "trial.bin", "."], cwd=eng, env=env, capture_output=True, text=True)
            if b.returncode == 0:
                break
            err = b.stderr
            if not (unused_imports(eng, err) or stub_unfetchable(eng, err)):
                break
        else:
            pass
        if b.returncode:
            print(json.dumps({"success": False, "stage": "build", "error": err[-900:], **info}, ensure_ascii=False)); sys.exit(3)
        info["notune"] = False
        for notune in (False, True):  # 關掉道具卡等開關後若引擎崩（例：只剩道具卡設定檔，一般權重全 0），改用原設定重跑並標記
            env["TRIAL_NOTUNE"] = "1" if notune else "0"
            try:
                r = subprocess.run([str(eng / "trial.bin")], cwd=eng, env=env, capture_output=True, text=True, timeout=a.timeout)
            except subprocess.TimeoutExpired:
                print(json.dumps({"success": False, "stage": "run", "error": f"逾時 {a.timeout}s", **info}, ensure_ascii=False)); sys.exit(3)
            if r.returncode == 0 or "panic" not in r.stderr:
                break
            info["notune"] = True
    p = out / "engine-trace.jsonl"
    lines = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []
    summ = next((x for x in lines if x.get("summary")), None)
    lines = [x for x in lines if not x.get("summary")]
    if len(lines) < a.n or not summ:
        print(json.dumps({"success": False, "stage": "run", "error": f"只錄到 {len(lines)} 局（rc {r.returncode}）{r.stderr[-400:]}", **info}, ensure_ascii=False)); sys.exit(3)
    meta = lines[0].get("meta", {})
    bet = bet_of(meta, info.get("bet_hint") or {})
    tr = to_results(lines, a.name, a.balance or bet * 2000, bet)
    wins = [x["totalWin"] for x in tr["results"]]
    sim0 = {"spins": summ["spins"], "rtp": round(100 * summ["win"] / summ["spins"] / bet, 3), "rtp_main": round(100 * summ["mg"] / summ["spins"] / bet, 3),
            "feature_rate": round(100 * summ["feat"] / summ["spins"], 4)}
    tr["meta"] = {**sim0, "engine": a.engine_label or pathlib.Path(a.engine).name, "seed": a.seed, "tuned": lines[0].get("tuned")}
    tr["loop"] = True
    (out / "trace.json").write_text(json.dumps(to_lite(tr), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    syms = sorted({s for x in tr["results"] for col in x["reel"]["grid"] for s in col}, key=lambda s: int(s[1:]))
    sim = {"spins": summ["spins"], "rtp": round(100 * summ["win"] / summ["spins"] / bet, 3), "rtp_main": round(100 * summ["mg"] / summ["spins"] / bet, 3),
           "feature_rate": round(100 * summ["feat"] / summ["spins"], 4)} if summ else None
    rep = {"success": True, "spins": len(wins), "bet": bet, "sim": sim, "tuned": lines[0].get("tuned") if lines else None,
           "rtp_trace": round(100 * sum(wins) / len(wins) / bet, 2), "features": sum(1 for x in tr["results"] if x["feature"]),
           "grid_ok": sum(1 for x in tr["results"] if x["reel"]["grid"]), "symbols": syms, "meta": meta, **info}
    (out / "engine-trace.meta.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    main()

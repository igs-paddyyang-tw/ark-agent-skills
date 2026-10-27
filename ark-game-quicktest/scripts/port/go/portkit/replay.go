package portkit

// replay 子命令（⑦ 引擎回放試玩）：同一個 seed 連跑 -sim 局（⑥-lite 的 RTP 樣本），前 -n 局錄成
// proto-stage-trace-lite/1 trace.json（rounds[i] = [總贏分, 主遊戲贏分, 有無特色, Grid]）＋ engine-trace.meta.json（欄位同 ark-game-proto engine_trace.py）。
//   go run . replay -config ../config/live.json -n 2000 -sim 200000 -seed 7 -out <data/slot/<slug>/game/replay> -name <中文名> -engine-label "…"

import (
	"encoding/json"
	"flag"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
)

func replay(spec Spec, newGame func(cfg []byte) (Game, error), args []string) {
	fs := flag.NewFlagSet("replay", flag.ExitOnError)
	cfgPath := fs.String("config", "../config/live.json", "config json")
	n := fs.Int("n", 2000, "錄進 trace.json 的局數")
	sim := fs.Int("sim", 200000, "總局數（RTP 樣本，≥ n）")
	seed := fs.Uint("seed", 7, "亂數種子")
	out := fs.String("out", ".", "輸出目錄")
	name := fs.String("name", spec.Name, "遊戲名")
	label := fs.String("engine-label", "quicktest/engine（config live.json）", "寫進 meta 的引擎來源")
	fs.Parse(args)
	raw, err := os.ReadFile(*cfgPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	g, err := newGame(raw)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	if *sim < *n {
		*sim = *n
	}
	r := NewRNG(uint32(*seed))
	var win, mainW, bet, traceWin float64
	var feat, featTrace, gridOK int
	var betUnit uint64
	rounds := make([][]any, 0, *n)
	syms := map[int]bool{}
	for i := 0; i < *sim; i++ {
		x := g.Play(r)
		betUnit = x.Bet
		win += float64(x.Win)
		mainW += float64(x.Main)
		bet += float64(x.Bet)
		f := 0
		for _, t := range x.Trig {
			if t {
				f = 1
			}
		}
		feat += f
		if i < *n {
			grid := x.Grid
			if grid == nil {
				grid = [][]int{}
			} else {
				gridOK++
			}
			for _, col := range grid {
				for _, v := range col {
					syms[v] = true
				}
			}
			featTrace += f
			traceWin += float64(x.Win)
			rounds = append(rounds, []any{x.Win, x.Main, f, grid})
		}
	}
	r3 := func(v float64) float64 { return math.Round(v*1000) / 1000 }
	r4 := func(v float64) float64 { return math.Round(v*10000) / 10000 }
	simM := map[string]any{"spins": *sim, "rtp": r3(100 * win / bet), "rtp_main": r3(100 * mainW / bet), "feature_rate": r4(100 * float64(feat) / float64(*sim))}
	b := int(betUnit)
	meta := map[string]any{"spins": *sim, "rtp": simM["rtp"], "rtp_main": simM["rtp_main"], "feature_rate": simM["feature_rate"], "engine": *label, "seed": *seed, "tuned": map[string]any{}}
	tr := map[string]any{"schema": "proto-stage-trace-lite/1",
		"info": map[string]any{"service": "replay", "balance": b * 2000, "bets": []int{b}, "defaultBet": b, "betBase": b, "name": *name},
		"meta": meta, "loop": true, "rounds": rounds}
	keys := make([]int, 0, len(syms))
	for k := range syms {
		keys = append(keys, k)
	}
	sort.Ints(keys)
	symList := make([]string, len(keys))
	for i, k := range keys {
		symList[i] = fmt.Sprintf("S%d", k)
	}
	rep := map[string]any{"success": true, "spins": *n, "bet": b, "sim": simM, "tuned": map[string]any{},
		"rtp_trace": math.Round(100*100*traceWin/float64(*n)/float64(b)) / 100, "features": featTrace, "grid_ok": gridOK, "symbols": symList,
		"module": "portkit replay 子命令", "config": filepath.Base(*cfgPath), "feature_flag": spec.Features}
	os.MkdirAll(*out, 0o755)
	tj, _ := json.Marshal(tr)
	os.WriteFile(filepath.Join(*out, "trace.json"), tj, 0o644)
	mj, _ := json.MarshalIndent(rep, "", " ")
	os.WriteFile(filepath.Join(*out, "engine-trace.meta.json"), mj, 0o644)
	fmt.Println(string(mj))
}

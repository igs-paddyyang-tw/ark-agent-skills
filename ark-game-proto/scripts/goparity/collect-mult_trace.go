// slotproto-trace — 逐局輸出 Go 快測引擎結果，給 slot-proto 的 go_parity.js 對照（不改引擎任何檔案）。
// 用法：把本檔放到 <engine>/cmd/slotproto-trace/main.go，於 engine 目錄執行：
//   go run ./cmd/slotproto-trace --config ../config/a-standard.json --seed 42 --n 100000 > trace.txt
// 輸出每行：i setIndex mgWin fgWin total group(-1=無FG) scCount+ssCount
package main

import (
	game_process "FastTest/game"
	"FastTest/odds"
	"FastTest/play_data"
	"FastTest/recorder"
	"bufio"
	"flag"
	"fmt"
	"os"
)

func main() {
	cfg := flag.String("config", "", "設定檔 JSON")
	seed := flag.Int64("seed", 42, "亂數種子（同 Go 快測 --seed 單一 worker 語意）")
	n := flag.Int("n", 10000, "手數")
	fgOnly := flag.Bool("fg-only", false, "只輸出進 FG 的局（大量手數找封頂用；JS 端仍逐局跑、未列出的局必須無 FG）")
	flag.Parse()
	ps, err := odds.LoadProbSettingFromJSON(*cfg)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	pi := play_data.NewPlayInfo(ps.Line_bet, ps.Bet_Line, ps.Bet_Cost, ps.Extra_Cost, ps.ExtraSetting)
	rec := recorder.NewDataRecorder(pi, 1, "1.0.0")
	w := game_process.NewGameWorker(ps, pi, rec, *seed)
	mr := play_data.NewMainResult()
	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()
	fmt.Fprintf(out, "# seed=%d n=%d line_bet=%d bet_cost=%d max_win=%d fg_only=%t\n", *seed, *n, ps.Line_bet, ps.Bet_Cost, ps.MaxWin, *fgOnly)
	for i := 0; i < *n; i++ {
		pm, pf := w.PartMainWin, w.PartFreeWin
		rs := w.ReelSetSpins
		gd := w.Stats.GroupDist
		var trig [16]int64
		copy(trig[:], w.Stats.TriggerSCDist[:])
		_, total := w.GameProcess(mr, 0)
		mr.Clear()
		set := -1
		for k := range rs {
			if w.ReelSetSpins[k] != rs[k] {
				set = k
			}
		}
		grp := -1
		for k := range gd {
			if w.Stats.GroupDist[k] != gd[k] {
				grp = k
			}
		}
		sp := 0
		for k := range trig {
			if w.Stats.TriggerSCDist[k] != trig[k] {
				sp = k
			}
		}
		if *fgOnly && grp < 0 {
			continue
		}
		fmt.Fprintf(out, "%d %d %d %d %d %d %d\n", i, set, w.PartMainWin-pm, w.PartFreeWin-pf, total, grp, sp)
	}
}

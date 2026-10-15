// slotproto-trace（coin-lock / Tiger and Dragon 引擎）— 逐局輸出 Go 快測引擎結果，給 tests/go_parity.js 對照（不改引擎任何檔案）。
// 用法：放到 <engine>/cmd/slotproto-trace/main.go，於 engine 目錄執行：
//   go run ./cmd/slotproto-trace --config ../odds/odds_1.0.0.json --seed 42 --n 100000 > trace.txt
// 輸出每行：i setIndex(-1=不提供) mgWin fgWin total group(-1=無FG) 0
package main

import (
	gameProcess "fast-test/game"
	"fast-test/odds"
	"fast-test/playdata"
	"fast-test/recorder"
	"bufio"
	"flag"
	"fmt"
	"os"
)

func main() {
	cfg := flag.String("config", "odds/odds_1.0.0.json", "odds JSON")
	seed := flag.Int64("seed", 42, "亂數種子")
	n := flag.Int("n", 10000, "手數")
	fgOnly := flag.Bool("fg-only", false, "只輸出進 Bonus 的局")
	flag.Parse()
	ps := odds.LoadProbSetting(*cfg)
	pi := playdata.NewPlayInfo(ps.LineBet, ps.BetLine, ps.BetCost, ps.ExtraCost, ps.ExtraSetting)
	rec := recorder.NewDataRecorder(pi, "1.0.0")
	w := gameProcess.NewGameWorker(ps, rec, nil, *seed)
	mr := playdata.NewMainResult()
	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()
	fmt.Fprintf(out, "# seed=%d n=%d line_bet=%d bet_cost=%d max_win=%d fg_only=%t\n", *seed, *n, ps.LineBet, ps.BetCost, ps.MaxWin, *fgOnly)
	for i := 0; i < *n; i++ {
		total := w.GameProcess(mr)
		grp := -1
		if len(mr.SpecialGame) > 0 {
			grp = mr.SpecialGame[0]
		}
		if !(*fgOnly && grp < 0) {
			fmt.Fprintf(out, "%d %d %d %d %d %d %d\n", i, -1, mr.TotalWin, total-mr.TotalWin, total, grp, 0)
		}
		mr.Clear()
	}
}

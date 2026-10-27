// slotproto-trace（frame-chest／神燈寶藏）— 逐局輸出 Go 快測引擎（v6 架構大變，全域 math/rand）結果，給 tests/go_parity.js 對照（不改引擎任何檔案）。
// 用法：放到 <engine>/cmd/slotproto-trace/main.go，於 engine 目錄執行：
//   go run ./cmd/slotproto-trace --config ../config/live-b.json --seed 42 --n 100000 > trace.txt
// --config：ProbSetting 的 JSON（cmd/dump 產的格式，鍵 = 欄位名）；空白 = odds.NewProbSetting()。
// 引擎用全域 rand（rand.Intn）：rand.Seed(seed) 後與 rand.New(rand.NewSource(seed)) 同一條流（go.mod go < 1.24 時 Seed 有效；
// 1.24+ 模組需 GODEBUG=randseednop=0，本檔啟動時自檢）。
// 引擎在 FG 會 fmt.Println 線獎最大倍率 → 本檔把 os.Stdout 導到 DevNull，trace 寫原本的 stdout。
// 輸出每行：i setIndex mgWin fgWin total group(-1=無FG) scCount
package main

import (
	game_process "FastTest/game"
	"FastTest/jackpot"
	"FastTest/odds"
	"FastTest/play_data"
	"FastTest/recorder"
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"math/rand"
	"os"
)

func main() {
	cfg := flag.String("config", "", "ProbSetting JSON（空白 = odds.NewProbSetting()）")
	seed := flag.Int64("seed", 42, "亂數種子")
	n := flag.Int("n", 10000, "手數")
	fgOnly := flag.Bool("fg-only", false, "只輸出進 FG 的局")
	flag.Parse()
	ps := odds.NewProbSetting()
	if *cfg != "" {
		raw, err := os.ReadFile(*cfg)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		ps = &odds.ProbSetting{}
		if err := json.Unmarshal(raw, ps); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
	}
	// 自檢：全域 Seed 必須生效（與 rand.New(rand.NewSource(seed)) 同流）
	rand.Seed(*seed)
	a := rand.Int63()
	if b := rand.New(rand.NewSource(*seed)).Int63(); a != b {
		fmt.Fprintln(os.Stderr, "rand.Seed 無效（Go 1.24+ 模組）：請設 GODEBUG=randseednop=0")
		os.Exit(2)
	}
	rand.Seed(*seed)

	pi := play_data.NewPlayInfo(ps.Line_bet, ps.Bet_Line, ps.Bet_Cost, ps.Extra_Cost, ps.ExtraSetting)
	rec := recorder.NewDataRecorder(pi, 1<<30, "slotproto-trace")
	jm := jackpot.NewJackpotManager(ps.Line_bet, ps.JackpotAccRate, ps.JackpotMultiple)
	game_process.InitGameProcess(ps, rec, jm)

	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()
	if devnull, err := os.OpenFile(os.DevNull, os.O_WRONLY, 0); err == nil {
		os.Stdout = devnull
	}
	fmt.Fprintf(out, "# seed=%d n=%d line_bet=%d bet_cost=%d max_win=%d fg_only=%t\n", *seed, *n, ps.Line_bet, ps.Bet_Cost, ps.MaxWin, *fgOnly)
	mr := play_data.NewMainResult()
	guarantee := 0
	for i := 0; i < *n; i++ {
		rs := rec.ReelSetBetTimes
		types := rec.FreeGameTypeCount
		if ps.GuarenteeSpinEnable {
			guarantee++
		}
		var total int64
		guarantee, total = game_process.GameProcess(mr, pi, guarantee)
		mg := mr.TotalWin
		sc := len(mr.SCPositions)
		mr.Clear()
		set := -1
		for k := range rs {
			if rec.ReelSetBetTimes[k] != rs[k] {
				set = k
			}
		}
		grp := -1
		for k := range types {
			if rec.FreeGameTypeCount[k] != types[k] {
				grp = k
			}
		}
		if *fgOnly && grp < 0 {
			continue
		}
		fmt.Fprintf(out, "%d %d %d %d %d %d %d\n", i, set, mg, total-mg, total, grp, sc)
	}
}

// Package portkit：C++ 快測 → Go 移植的共用執行框架（ark-game-quicktest 路線 C）。
//   - RNG：SFMT19937（與 C++ SFMTRand 逐位元相同）＋ MSVC rand()（LCG），各自計數，供逐局對照。
//   - Run：-n 局數、-seed、-workers 平行（每個 worker 自己的遊戲狀態與 seed+w）、-trace 逐局追蹤（強制 1 worker）。
//   - 報表：Go 快測範本格式 report_<ver>.txt（ark-game-quicktest qt_report 可直接解析）＋ summary JSON。
package portkit

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"math"
	"os"
	"strings"
	"sync"
	"time"
)

// RNG：對應 C++ getRandom()/RANDOM()（SFMT gen_rand32 % n）與 rand()（MSVC LCG，RAND_MAX 0x7fff）。
type RNG struct {
	S       *SFMT
	Calls   uint64
	ms      uint32
	MSCalls uint64
}

func NewRNG(seed uint32) *RNG { return &RNG{S: New(seed), ms: seed} }

// Intn = TwisterRandomizer::randomInt(n)：n = 0 回 0 且不耗亂數。
func (r *RNG) Intn(n uint32) uint32 {
	if n == 0 {
		return 0
	}
	r.Calls++
	return r.S.Uint32() % n
}

// MSRand = MSVC rand()（0..32767）。
func (r *RNG) MSRand() uint32 {
	r.MSCalls++
	r.ms = r.ms*214013 + 2531011
	return (r.ms >> 16) & 0x7fff
}

// Result：一手（含其特色遊戲）的結果；金額單位與 C++ 相同（整數分）。
type Result struct {
	Bet   uint64
	Win   uint64  // 本手總贏分
	Main  uint64  // 主遊戲連線贏分
	Parts []int64 // 依 Spec.Features 順序：各特色贏分（可為負：C++ 有時以差額拆分）
	Trig  []bool  // 依 Spec.Features 順序：本手是否觸發
	Spins []int   // 依 Spec.Features 順序：特色局數（無則 0）
	// Grid：主遊戲第一轉盤面 [軸][列]，已轉成回放遊戲包的顯示碼（1 WILD、2 SCATTER、3 BONUS、11～19 M1～M9、21～30 A K Q J 10 9 8 7 6 5；其他照原碼）。
	// 只有 replay 子命令會用；quicktest 可不填。
	Grid [][]int
}

type Spec struct {
	Name     string
	Version  string
	Features []string // 報表列名（例 FreeGame、BonusGame、Jackpot、CashGame）；SpecialGameTotal = 加總
	Source   string   // 報表 Source 段：移植自哪個 C++ 目錄
}

// Game：一個 worker 的遊戲實例（含跨手狀態，例收集條、彩金池）。
type Game interface {
	Play(r *RNG) Result
}

type acc struct {
	n, hit          uint64
	win, main, bet  float64
	sq              float64
	maxX            float64
	parts, maxParts []float64
	cnt, spins      []uint64
}

func newAcc(k int) *acc {
	return &acc{parts: make([]float64, k), maxParts: make([]float64, k), cnt: make([]uint64, k), spins: make([]uint64, k)}
}

func (a *acc) add(x Result) {
	a.n++
	a.bet += float64(x.Bet)
	a.win += float64(x.Win)
	a.main += float64(x.Main)
	if x.Main > 0 {
		a.hit++
	}
	wx := float64(x.Win) / float64(x.Bet)
	a.sq += wx * wx
	if wx > a.maxX {
		a.maxX = wx
	}
	for i := range a.parts {
		if i < len(x.Parts) {
			a.parts[i] += float64(x.Parts[i])
			if px := float64(x.Parts[i]) / float64(x.Bet); px > a.maxParts[i] {
				a.maxParts[i] = px
			}
		}
		if i < len(x.Trig) && x.Trig[i] {
			a.cnt[i]++
			if i < len(x.Spins) {
				a.spins[i] += uint64(x.Spins[i])
			}
		}
	}
}

func (a *acc) merge(b *acc) {
	a.n += b.n
	a.hit += b.hit
	a.win += b.win
	a.main += b.main
	a.bet += b.bet
	a.sq += b.sq
	a.maxX = math.Max(a.maxX, b.maxX)
	for i := range a.parts {
		a.parts[i] += b.parts[i]
		a.maxParts[i] = math.Max(a.maxParts[i], b.maxParts[i])
		a.cnt[i] += b.cnt[i]
		a.spins[i] += b.spins[i]
	}
}

// Run：解析旗標 → 讀設定 → 跑 → 寫報表。newGame 收 config JSON 原文。
func Run(spec Spec, newGame func(cfg []byte) (Game, error)) {
	if len(os.Args) > 1 && os.Args[1] == "replay" {
		replay(spec, newGame, os.Args[2:])
		return
	}
	cfgPath := flag.String("config", "config/config.json", "設定檔（odds json）")
	n := flag.Uint64("n", 1000000, "局數")
	seed := flag.Uint("seed", 42, "亂數種子（worker w 用 seed+w）")
	workers := flag.Int("workers", 1, "平行 worker 數（-trace 時強制 1）")
	trace := flag.String("trace", "", "逐局追蹤輸出（局號 總贏分 主遊戲贏分 SFMT累計 rand累計），與 cpp_trace.py 同格式")
	report := flag.String("report", "", "報表輸出（預設 report_<version>.txt）")
	version := flag.String("version", spec.Version, "版本字串（報表標頭）")
	flag.Parse()
	raw, err := os.ReadFile(*cfgPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "讀設定失敗:", err)
		os.Exit(2)
	}
	if *trace != "" {
		*workers = 1
	}
	k := len(spec.Features)
	accs := make([]*acc, *workers)
	var wg sync.WaitGroup
	var mu sync.Mutex
	errs := []string{}
	t0 := time.Now()
	for w := 0; w < *workers; w++ {
		accs[w] = newAcc(k)
		per := *n / uint64(*workers)
		if w == *workers-1 {
			per = *n - per*uint64(*workers-1)
		}
		wg.Add(1)
		go func(w int, per uint64) {
			defer wg.Done()
			g, err := newGame(raw)
			if err != nil {
				mu.Lock()
				errs = append(errs, err.Error())
				mu.Unlock()
				return
			}
			r := NewRNG(uint32(*seed) + uint32(w))
			var tw *bufio.Writer
			if *trace != "" {
				f, _ := os.Create(*trace)
				defer f.Close()
				tw = bufio.NewWriterSize(f, 1<<20)
				defer tw.Flush()
			}
			for i := uint64(0); i < per; i++ {
				x := g.Play(r)
				accs[w].add(x)
				if tw != nil {
					fmt.Fprintf(tw, "%d %d %d %d %d\n", i+1, x.Win, x.Main, r.Calls, r.MSCalls)
				}
			}
		}(w, per)
	}
	wg.Wait()
	if len(errs) > 0 {
		fmt.Fprintln(os.Stderr, strings.Join(errs, "\n"))
		os.Exit(2)
	}
	a := accs[0]
	for _, b := range accs[1:] {
		a.merge(b)
	}
	out := *report
	if out == "" {
		out = "report_" + *version + ".txt"
	}
	writeReport(out, spec, *version, a, *seed, *workers, *cfgPath)
	sum := map[string]any{"spins": a.n, "total_win": a.win, "total_bet": a.bet, "rtp": a.win / a.bet, "rtp_main": a.main / a.bet,
		"seconds": time.Since(t0).Seconds(), "seed": *seed, "workers": *workers, "config": *cfgPath, "features": map[string]any{}}
	for i, name := range spec.Features {
		sum["features"].(map[string]any)[name] = map[string]any{"rtp": a.parts[i] / a.bet, "count": a.cnt[i], "freq": safeDiv(float64(a.n), float64(a.cnt[i]))}
	}
	j, _ := json.Marshal(sum)
	fmt.Println(string(j))
}

func safeDiv(a, b float64) float64 {
	if b == 0 {
		return 0
	}
	return a / b
}

func writeReport(path string, spec Spec, version string, a *acc, seed uint, workers int, cfg string) {
	n := float64(a.n)
	rtp := a.win / a.bet
	mean := a.win / a.bet
	varX := (a.sq - n*mean*mean) / math.Max(1, n-1)
	sd := math.Sqrt(math.Max(0, varX))
	ci := 1.96 * sd / math.Sqrt(n)
	var featRTP float64
	var featCnt, featSpins uint64
	var featMax float64
	for i := range spec.Features {
		featRTP += a.parts[i] / a.bet
		featCnt += a.cnt[i]
		featSpins += a.spins[i]
		featMax = math.Max(featMax, a.maxParts[i])
	}
	avgBet := a.bet / n
	L := []string{
		fmt.Sprintf("====================== 版本: %s ====================== %s.0000", version, time.Now().Format("2006-01-02 15:04:05")),
		fmt.Sprintf("Times:%d TotalWin:%.0f TotalBet:%.0f", a.n, a.win, a.bet),
		"********** BASE INFO **********",
		fmt.Sprintf("%20s - %10s %9s %10s %9s %10s %10s %9s", "Game", "RTP", "HitRate", "Freq.", "Multi", "PlayTimes", "RetriRate", "MaxMulti"),
		fmt.Sprintf("%20s - %9.4f%% %8.2f%% %10s %9s %10s %10s %9s", "MainGame", 100*a.main/a.bet, 100*float64(a.hit)/n, "-", "-", "-", "-", "-"),
		fmt.Sprintf("%20s - %9.4f%% %9s %10.2f %9.2f %10.2f %10s %9.2f", "SpecialGameTotal", 100*featRTP, "-", safeDiv(n, float64(featCnt)),
			safeDiv(featRTP*a.bet/avgBet, float64(featCnt)), safeDiv(float64(featSpins), float64(featCnt)), "0.00%", featMax),
	}
	for i, name := range spec.Features {
		L = append(L, fmt.Sprintf("%20s - %9.4f%% %9s %10.2f %9.2f %10.2f %10s %9.2f", name, 100*a.parts[i]/a.bet, "-", safeDiv(n, float64(a.cnt[i])),
			safeDiv(a.parts[i]/avgBet, float64(a.cnt[i])), safeDiv(float64(a.spins[i]), float64(a.cnt[i])), "0.00%", a.maxParts[i]))
	}
	L = append(L, fmt.Sprintf("%20s - %9.4f%% %61s %9.2f", "Total", 100*rtp, "", a.maxX),
		"********** Game Detail Information **********",
		fmt.Sprintf("SD: %.2f", sd),
		fmt.Sprintf("95%% confidence level: %.2f%% ~ %.2f%%", 100*(rtp-ci), 100*(rtp+ci)),
		"********** Source **********",
		fmt.Sprintf("  engine: %s（portkit Go 移植）｜config: %s｜seed: %d｜workers: %d", spec.Source, cfg, seed, workers))
	os.WriteFile(path, []byte(strings.Join(L, "\n")+"\n"), 0o644)
}

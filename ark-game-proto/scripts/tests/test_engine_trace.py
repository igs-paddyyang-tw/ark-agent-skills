"""engine_trace 純函式測試（不需 Go）：押注常數、GameProcess 改寫、空欄裁切、go.mod 降版。"""
import pathlib, sys, tempfile, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import engine_trace as et  # noqa: E402

MAIN = """package main

const (
	LINE_BET   = 10
	// BET_COST = 99
	BET_COST   = 50
)

func main() {
	probSetting = odds.NewProbSetting()
	for {
		testcredit -= LINE_BET * BET_COST
		testcredit += game_process.GameProcess(probSetting, main_result)
		main_result.Clear()
	}
}
"""
CHECK = """package check

func GameCheck(result *R, reelData [][]int, n int) *R {
	return result
}

func GameCheckV2(result *R, reelData [][]int, n int) *R {
	return result
}
"""


class EngineTrace(unittest.TestCase):
    def test_bet_hint_skips_comments(self):
        self.assertEqual(et.bet_hint(MAIN), {"Line_bet": 10, "Bet_Cost": 50})
        self.assertEqual(et.bet_of({}, {"Line_bet": 10, "Bet_Cost": 50}), 500)
        self.assertEqual(et.bet_of({"BetCost": 40, "LineBet": 1}, {"Line_bet": 10}), 40)

    def test_patch_line_anchored_and_all_gamechecks(self):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            (d / "check").mkdir()
            (d / "go.mod").write_text("module FastTest\n\ngo 1.21\n")
            (d / "main.go").write_text(MAIN)
            (d / "check" / "check.go").write_text(CHECK)
            info = et.patch(d)
            m = (d / "main.go").read_text()
            self.assertIn("__trialWin := game_process.GameProcess(", m)
            self.assertIn("testcredit += __trialWin", m)
            self.assertIn("__trialHook(main_result, int64(__trialWin), probSetting)", m)
            self.assertEqual(info["bet_hint"], {"Line_bet": 10, "Bet_Cost": 50})
            self.assertEqual((d / "check" / "check.go").read_text().count("TrialGrid = make"), 2)

    def test_to_results_trims_empty_columns(self):
        lines = [{"i": i, "win": 0, "mg": 0, "grid": [[1, 2, 3], [4, 5, 6], [7, 8, 9], [0, 0, 0], [0, 0, 0]]} for i in range(3)]
        tr = et.to_results(lines, "t", 1000, 10)
        self.assertEqual(len(tr["results"][0]["reel"]["grid"]), 3)
        self.assertEqual(tr["results"][-1]["balanceAfter"], 1000 - 30)

    def test_lite_roundtrip(self):
        lines = [{"i": i, "win": [0, 50, 900][i], "mg": [0, 50, 100][i], "sg": i == 2, "grid": [[1, 2], [11, 21]]} for i in range(3)]
        tr = et.to_results(lines, "t", 1000, 10)
        tr["meta"], tr["loop"] = {"rtp": 96}, True
        self.assertEqual(et.expand_lite(et.to_lite(tr)), tr)

    def test_go_mod_downgrade(self):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            (d / "go.mod").write_text("module X\n\ngo 9.99.0\n\ntoolchain go9.99.1\n")
            try:
                et.local_go_toolchain(d)
            except FileNotFoundError:
                self.skipTest("no go")
            s = (d / "go.mod").read_text()
            self.assertNotIn("9.99", s)


if __name__ == "__main__":
    unittest.main()

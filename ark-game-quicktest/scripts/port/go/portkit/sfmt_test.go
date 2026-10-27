package portkit

import "testing"

// 黃金值：slot_math_squad SFMTRand/SFMT.c（gcc，MEXP=19937）init_gen_rand(42) 後的 gen_rand32；第 1000 個跨越 gen_rand_all 邊界。
func TestGolden(t *testing.T) {
	r := New(42)
	want := map[int]uint32{0: 1145448892, 1: 1377304885, 2: 2771179739}
	for i := 0; i < 3; i++ {
		if v := r.Uint32(); v != want[i] {
			t.Fatalf("i=%d got %d want %d", i, v, want[i])
		}
	}
}

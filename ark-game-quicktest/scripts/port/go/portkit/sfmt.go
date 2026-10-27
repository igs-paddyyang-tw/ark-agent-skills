// Package sfmt：SFMT19937（SIMD-oriented Fast Mersenne Twister）純 Go 移植，與 slot_math_squad 各 C++ 快測的
// SFMTRand/SFMT.c（非 SIMD 路徑、MEXP 19937）逐位元相同；用於 C++ → Go 移植的逐局對照（engine port kit）。
package portkit

const (
	n       = 19937/128 + 1
	n32     = n * 4
	pos1    = 122
	sl1     = 18
	sl2     = 1
	sr1     = 11
	sr2     = 1
	msk1    = 0xdfffffef
	msk2    = 0xddfecb7f
	msk3    = 0xbffaffff
	msk4    = 0xbffffff6
	parity1 = 0x00000001
	parity4 = 0x13c9e684
)

// SFMT 狀態；零值不可用，請用 New(seed)。
type SFMT struct {
	s   [n32]uint32
	idx int
}

func New(seed uint32) *SFMT {
	r := &SFMT{}
	r.Seed(seed)
	return r
}

// Seed 對應 init_gen_rand。
func (r *SFMT) Seed(seed uint32) {
	r.s[0] = seed
	for i := 1; i < n32; i++ {
		p := r.s[i-1]
		r.s[i] = 1812433253*(p^(p>>30)) + uint32(i)
	}
	r.idx = n32
	r.periodCert()
}

func (r *SFMT) periodCert() {
	parity := [4]uint32{parity1, 0, 0, parity4}
	var inner uint32
	for i := 0; i < 4; i++ {
		inner ^= r.s[i] & parity[i]
	}
	for i := 16; i > 0; i >>= 1 {
		inner ^= inner >> uint(i)
	}
	if inner&1 == 1 {
		return
	}
	for i := 0; i < 4; i++ {
		work := uint32(1)
		for j := 0; j < 32; j++ {
			if work&parity[i] != 0 {
				r.s[i] ^= work
				return
			}
			work <<= 1
		}
	}
}

func (r *SFMT) recursion(ri, ai, bi, ci, di int) {
	s := &r.s
	// x = a << (SL2*8)（128-bit 左移 8 bit）
	ah := uint64(s[ai+3])<<32 | uint64(s[ai+2])
	al := uint64(s[ai+1])<<32 | uint64(s[ai])
	xh := ah<<(sl2*8) | al>>(64-sl2*8)
	xl := al << (sl2 * 8)
	// y = c >> (SR2*8)
	ch := uint64(s[ci+3])<<32 | uint64(s[ci+2])
	cl := uint64(s[ci+1])<<32 | uint64(s[ci])
	yh := ch >> (sr2 * 8)
	yl := cl>>(sr2*8) | ch<<(64-sr2*8)
	x := [4]uint32{uint32(xl), uint32(xl >> 32), uint32(xh), uint32(xh >> 32)}
	y := [4]uint32{uint32(yl), uint32(yl >> 32), uint32(yh), uint32(yh >> 32)}
	m := [4]uint32{msk1, msk2, msk3, msk4}
	for k := 0; k < 4; k++ {
		s[ri+k] = s[ai+k] ^ x[k] ^ ((s[bi+k] >> sr1) & m[k]) ^ y[k] ^ (s[di+k] << sl1)
	}
}

func (r *SFMT) genAll() {
	r1, r2 := (n-2)*4, (n-1)*4
	i := 0
	for ; i < n-pos1; i++ {
		r.recursion(i*4, i*4, (i+pos1)*4, r1, r2)
		r1, r2 = r2, i*4
	}
	for ; i < n; i++ {
		r.recursion(i*4, i*4, (i+pos1-n)*4, r1, r2)
		r1, r2 = r2, i*4
	}
}

// Uint32 對應 gen_rand32。
func (r *SFMT) Uint32() uint32 {
	if r.idx >= n32 {
		r.genAll()
		r.idx = 0
	}
	v := r.s[r.idx]
	r.idx++
	return v
}

// Intn 對應 TwisterRandomizer::randomInt(range) = gen_rand32() % range（range = 0 回 0 且不耗亂數）。
func (r *SFMT) Intn(rng uint32) uint32 {
	if rng == 0 {
		return 0
	}
	return r.Uint32() % rng
}

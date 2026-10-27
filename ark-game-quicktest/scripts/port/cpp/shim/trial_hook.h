#pragma once
// engine port kit：C++ 快測逐局追蹤鉤子（由 cpp_trace.py 以 -include 強制載入每個編譯單元）
// - 亂數：SFMT 用固定 seed（TRIAL_SEED）；rand()/srand() 換成 MSVC 的 LCG（Windows 原行為，Go 端 portkit.MSRand 同算法）
// - 每局：__trial_hand(總贏分, 主遊戲贏分) 寫一行到 TRIAL_OUT：「局號 總贏分 主遊戲贏分 SFMT 次數 rand 次數」，滿 TRIAL_N 局 exit(0)
#ifdef __cplusplus
extern "C" {
#endif
unsigned int __trial_seed(void);
unsigned long long __trial_sfmt_calls(void);
void __trial_count_sfmt(void);
void __trial_hand(unsigned long long win, unsigned long long mainwin);
double __trial_n(void);
#ifdef __cplusplus
}
#endif
// MSVC 的 RAND_MAX（glibc 是 2^31-1）；rand()/srand() 在 trial_hook.c 直接覆寫（連結時優先於 libc）
#include <stdlib.h>
#undef RAND_MAX
#define RAND_MAX 0x7fff

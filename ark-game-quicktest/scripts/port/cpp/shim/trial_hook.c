#include <stdio.h>
#include <stdlib.h>
static unsigned long long sf_calls = 0, ms_calls = 0, hands = 0;
static unsigned int ms_state = 1;
static FILE *out = 0;
unsigned int __trial_seed(void){ const char *s = getenv("TRIAL_SEED"); return s ? (unsigned int)strtoul(s,0,10) : 42u; }
unsigned long long __trial_sfmt_calls(void){ return sf_calls; }
void __trial_count_sfmt(void){ sf_calls++; }
int rand(void){ ms_calls++; ms_state = ms_state * 214013u + 2531011u; return (int)((ms_state >> 16) & 0x7fff); }
void srand(unsigned int x){ (void)x; ms_state = __trial_seed(); }
double __trial_n(void){ const char *s = getenv("TRIAL_N"); return s ? atof(s) : 1000.0; }
void __trial_hand(unsigned long long win, unsigned long long mainwin){
  if(!out){ const char *p = getenv("TRIAL_OUT"); out = fopen(p ? p : "trace.txt", "w"); }
  hands++;
  fprintf(out, "%llu %llu %llu %llu %llu\n", hands, win, mainwin, sf_calls, ms_calls);
  if((double)hands >= __trial_n()){ fclose(out); _Exit(0); }
}
int system(const char *cmd){ (void)cmd; return 0; } /* system("pause"／"cls") 不執行 */

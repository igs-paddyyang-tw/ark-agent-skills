#pragma once
// shim：windows.h 必要子集
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
typedef uint32_t DWORD; typedef int BOOL; typedef uint16_t WORD; typedef uint8_t BYTE;
#ifndef TRUE
#define TRUE 1
#define FALSE 0
#endif
static inline DWORD GetTickCount(void){ struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return (DWORD)(t.tv_sec*1000+t.tv_nsec/1000000); }
static inline void Sleep(DWORD ms){ usleep(ms*1000); }
#define sprintf_s snprintf

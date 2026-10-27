#pragma once
// shim：conio.h（Windows 主控台）——批次跑不等鍵盤
static inline int _getch(void){ return 0; }
static inline int getch(void){ return 0; }
static inline int _kbhit(void){ return 0; }
static inline int kbhit(void){ return 0; }

#pragma once
// engine port shim (Linux)：MSVC tchar.h 最小替身
typedef char _TCHAR;
typedef char TCHAR;
#define _tmain main
#define _T(x) x
#define _tprintf printf

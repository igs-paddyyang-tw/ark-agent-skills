#!/usr/bin/env python3
"""cpp_trace — 把 slot_math_squad 的 C++ 快測（Visual Studio 專案）在 Linux 用 g++ 編起來，固定 seed 逐局輸出追蹤，當 Go 移植的對照組。

做法（不改原檔，複製到暫存目錄再 patch）：
  1. 編譯清單：讀 *.vcxproj／*.vcproj 的 ClCompile／File；沒有專案檔就用目錄下全部 .cpp／.c（排除 Backup）。
  2. 編譯：g++ -m32 -msse2 -mfpmath=sse（long = 32 bit、SSE 浮點，對齊 MSVC；需 g++-multilib）。shim：-I kit/cpp/shim（tchar.h、conio.h、windows.h 最小替身）；-include trial_hook.h（RAND_MAX = 0x7fff）；
     連結 trial_hook.c（rand／srand 換成 MSVC LCG、固定 seed）。
  3. Randomizer.cpp：init_gen_rand(time(0)) → init_gen_rand(__trial_seed())；randomInt() 每次計數。
  4. 主程式：`cin >> 局數` → `局數 = __trial_n()`；「本手贏分 = …;」之後插 __trial_hand(本手贏分, 主遊戲贏分)。
輸出：每局一行「局號 總贏分 主遊戲贏分 SFMT累計次數 rand累計次數」。
用法：python cpp_trace.py --src <C++ 專案目錄> --n 100000 --seed 42 --out trace.txt [--define DEF_VERSION=0] [--keep <dir>]
"""
from __future__ import annotations
import argparse, json, os, pathlib, re, shutil, subprocess, sys, tempfile

KIT = pathlib.Path(__file__).resolve().parent
SHIM = KIT / "shim"


def sources(src: pathlib.Path) -> list[pathlib.Path]:
    files = []
    for proj in list(src.glob("*.vcxproj")) + list(src.glob("*.vcproj")):
        t = proj.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'(?:ClCompile Include|RelativePath)="([^"]+\.(?:cpp|c))"', t, re.I):
            p = (src / m.group(1).replace("\\", "/").lstrip("./")).resolve()
            if p.is_file() and p not in files:
                files.append(p)
        if files:
            return files
    return [p for p in src.rglob("*") if p.suffix.lower() in (".cpp", ".c") and "Backup" not in p.parts]


def patch(work: pathlib.Path) -> dict:
    info = {"seed_patch": 0, "count_patch": 0, "n_patch": 0, "hand_patch": None, "main_var": None}
    for p in work.rglob("*"):
        if p.suffix.lower() not in (".cpp", ".c", ".h"):
            continue
        b = p.read_bytes()
        # Big5 註解的第 2 位元組可能是 0x5C（例「珮」），落在行尾會被 g++ 當成續行、吃掉下一行 → 去掉 // 註解行尾的反斜線
        b = re.sub(rb"(//[^\n]*?)\\+[ \t]*(\r?\n)", rb"\1\2", b)  # 反斜線後面可能還有空白／tab（g++ 照樣當續行）
        s = b.decode("latin-1")
        o = s
        s, k = re.subn(r"init_gen_rand\s*\(\s*\(\s*uint32_t\s*\)\s*time\s*\(\s*(?:0|NULL)\s*\)\s*\)", "init_gen_rand(__trial_seed())", s)
        info["seed_patch"] += k
        s, k = re.subn(r"(uint32_t\s+random\s*=\s*gen_rand32\s*\(\s*\)\s*;)", r"\1 __trial_count_sfmt();", s)
        info["count_patch"] += k
        s, k = re.subn(r"cin\s*>>\s*(\w+)\s*;", r"\1 = __trial_n() ;", s)
        # ASSERT 巨集只印訊息＋getchar，不影響結果；換成空（MSVC 容忍的指標 > 0 等寫法 g++ 編不過）
        s = re.sub(r"(#define\s+\w*ASSERT\s*\(\s*a\s*\))[^\n]*", r"\1 {}", s)
        info["n_patch"] += k
        # 逐局寫檔的統計輸出（GHY 系 DEF_OUTPUT_GAMEDATA）：只影響統計，關掉
        s, k = re.subn(r"^([ \t]*)#define[ \t]+DEF_OUTPUT_GAMEDATA\b", r"\1// trial: #define DEF_OUTPUT_GAMEDATA", s, flags=re.M)
        info["output_gamedata_off"] = info.get("output_gamedata_off", 0) + k
        # 週期報表輸出（printf 格式錯在 glibc 會崩、也拖慢）：主迴圈裡的 Print*Process( … ) 呼叫拿掉
        s, k = re.subn(r"(\n[ \t]*)(v\w*_Print\w*Process\s*\([^;]*\)\s*;)", r"\1/* trial: \2 */", s)
        info["print_patch"] = info.get("print_patch", 0) + k
        if info["hand_patch"] is None:
            m = re.search(r"\n([ \t]*)(\w*ThisHandWin\w*)\s*=\s*\(?[^;]*?Result\.[^;]*;", s)
            if m:
                end = s.index(";", m.start(2)) + 1
                mv = re.search(r"(\w+)\.([us]l\w*MainGameWin|[us]l\w*MainWin|\w*MainGameWin)\b", s[m.start():end])
                main = f"{mv.group(1)}.{mv.group(2)}" if mv else "0"
                s = s[:end] + f" __trial_hand((unsigned long long){m.group(2)}, (unsigned long long){main});" + s[end:]
                info["hand_patch"] = f"{p.name}:{m.group(2)}"
                info["main_var"] = main
        if s != o:
            p.write_bytes(s.encode("latin-1"))
    return info


def build(src: pathlib.Path, work: pathlib.Path, defines: list[str], patch_sh: str | None = None) -> tuple[pathlib.Path, dict]:
    shutil.copytree(src, work, ignore=shutil.ignore_patterns("*.exe", "*.obj", "*.pdb", "*.xls*", "Backup", "Debug", "Release", "*.txt"))
    info = patch(work)
    if patch_sh:  # 遊戲專屬修正（放在該款 quicktest/port/cpp_patch.sh；在副本目錄執行）
        r = subprocess.run(["bash", str(pathlib.Path(patch_sh).resolve())], cwd=work, capture_output=True, text=True)
        info["patch_sh"] = {"script": patch_sh, "rc": r.returncode}
        if r.returncode:
            info["error"] = f"patch 腳本失敗 rc={r.returncode}：{(r.stderr or r.stdout)[-600:]}"
            return work / "trial.bin", info  # patch 失敗就不編譯，保留 patch 的錯誤訊息
    srcs = [work / p.relative_to(src) for p in sources(src)]
    incs = sorted({str(p.parent) for p in work.rglob("*.h")})
    exe = work / "trial.bin"
    hook_o = work / "trial_hook.o"
    subprocess.run(["gcc", "-m32", "-O2", "-c", str(SHIM / "trial_hook.c"), "-o", str(hook_o)], check=True)
    cmd = ["g++", "-m32", "-msse2", "-mfpmath=sse", "-O2", "-w", "-fpermissive", "-std=gnu++11", "-I", str(SHIM), "-include", str(SHIM / "trial_hook.h"), "-DMEXP=19937"]
    cmd += [f"-D{d}" for d in defines] + [x for i in incs for x in ("-I", i)] + [str(s) for s in srcs] + [str(hook_o), "-o", str(exe), "-lpthread"]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    info["sources"] = [s.name for s in srcs]
    if r.returncode:
        info["error"] = r.stderr[-3000:]
    return exe, info


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", required=True); ap.add_argument("--n", type=int, default=100000); ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", required=True); ap.add_argument("--define", action="append", default=[]); ap.add_argument("--keep"); ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--patch", help="遊戲專屬修正腳本（bash，cwd = 副本目錄）")
    a = ap.parse_args()
    src = pathlib.Path(a.src).resolve()
    td = pathlib.Path(a.keep).resolve() if a.keep else pathlib.Path(tempfile.mkdtemp(prefix="cpptrace-"))
    if td.exists() and a.keep:
        shutil.rmtree(td)
    exe, info = build(src, td / "src", a.define, a.patch)
    if "error" in info or not exe.exists():
        print(json.dumps({"success": False, "stage": "build", **info}, ensure_ascii=False)); sys.exit(3)
    if not info["hand_patch"]:
        print(json.dumps({"success": False, "stage": "patch", "error": "找不到「本手贏分 = …Result…;」可插追蹤；請手動在每局結束處呼叫 __trial_hand(win, mainwin)", **info}, ensure_ascii=False)); sys.exit(3)
    out = pathlib.Path(a.out).resolve()
    env = {**os.environ, "TRIAL_SEED": str(a.seed), "TRIAL_N": str(a.n), "TRIAL_OUT": str(out)}
    r = subprocess.run([str(exe)], cwd=exe.parent, env=env, input="\n" * 20, capture_output=True, text=True, errors="replace", timeout=a.timeout)
    lines = out.read_text().splitlines() if out.exists() else []
    ok = len(lines) == a.n
    print(json.dumps({"success": ok, "hands": len(lines), "rc": r.returncode, **info, **({} if ok else {"stderr": r.stderr[-800:]})}, ensure_ascii=False))
    sys.exit(0 if ok else 3)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import shutil
import sys

def check(name):
    path = shutil.which(name)
    return path

def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print("preflight 檢查 ffmpeg/ffprobe/yt-dlp 是否安裝 + Whisper API key 是否設定。")
        print("用法: python3 setup.py   （無參數;缺工具回 rc=1，齊全回 0）")
        return 0
    print("Ark Video Understanding preflight")
    print("-" * 40)
    ok = True
    for tool in ("ffmpeg", "ffprobe", "yt-dlp"):
        path = check(tool)
        if path:
            print(f"[OK] {tool}: {path}")
        else:
            ok = False
            print(f"[MISSING] {tool}")

    if not ok:
        print("\nInstall prerequisites:")
        print("  macOS:  brew install ffmpeg yt-dlp")
        print("  Ubuntu: sudo apt-get install ffmpeg && python3 -m pip install -U yt-dlp")
        print("  Windows: winget install Gyan.FFmpeg && py -m pip install -U yt-dlp")

    from config import whisper_provider
    provider = whisper_provider()
    if provider:
        print(f"[OK] Whisper fallback: {provider}")
    else:
        print("[INFO] No Whisper API key configured; native captions and frames still work.")

    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())

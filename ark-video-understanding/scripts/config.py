#!/usr/bin/env python3
import os
from pathlib import Path

CONFIG_DIR = Path(os.getenv("ARK_VIDEO_CONFIG_DIR", Path.home() / ".config" / "ark-video-understanding"))
ENV_FILE = CONFIG_DIR / ".env"

def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def whisper_provider():
    load_env()
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return None

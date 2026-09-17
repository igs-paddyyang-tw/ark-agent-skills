# ark-video-understanding

ArkAgent's domain-agnostic Video Understanding Skill.

Inspired by the architecture of `bradautomates/claude-video`: captions first,
`yt-dlp` for acquisition, `ffmpeg` for frame extraction, scene-aware sampling,
near-duplicate removal, timestamp grounding, and a structured evidence package.

Reference:
https://github.com/bradautomates/claude-video

## Quick start

```bash
python3 scripts/setup.py --check

python3 scripts/watch.py "https://www.youtube.com/watch?v=..." \
  --detail balanced \
  --out-dir ./artifacts/video/demo
```

For a local file:

```bash
python3 scripts/watch.py ./demo.mp4 \
  --detail balanced \
  --out-dir ./artifacts/video/demo
```

The output is designed to be consumed by another Agent Skill rather than being
the final game analysis itself.

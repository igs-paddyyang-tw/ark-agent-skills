---
name: ark-video-understanding
description: >
  Analyze local or remote videos for ArkAgent by downloading media, extracting
  timestamped captions/transcripts, detecting visually distinct frames,
  deduplicating frames, and producing a structured evidence package for
  downstream Game Analysis / Knowledge / Spec Skills. Designed for competitor
  game videos, especially slot-game POCs, but domain-agnostic.
metadata:
  author: paddyyang
  schema_version: 1
  version: 0.1.0
  updated: 2026-09-17
  category: pipeline
  outputs:
    - { format: data, audience: ai }
    - { format: md, audience: ai }
  render: none
  depends_on: []
---

# Ark Video Understanding

## Purpose

Turn a video into an evidence package that an Agent can inspect and use as the
grounded input for downstream analysis.

Core pipeline:

Video URL / local file
→ media acquisition
→ captions / speech-to-text
→ scene-aware frame extraction
→ near-duplicate removal
→ timestamp alignment
→ `manifest.json`
→ `evidence.md`

This Skill is intentionally **domain-agnostic**. Do not put slot, pachinko, fish,
or other game rules into this Skill. Domain interpretation belongs to a separate
Game Analysis Skill.

## What this Skill must do

1. Accept a supported remote URL or local video path.
2. Prefer native captions when available.
3. Fall back to Whisper when captions are unavailable and transcription is enabled.
4. Extract visually useful frames.
5. Preserve timestamps for every frame.
6. Deduplicate near-identical frames.
7. Produce machine-readable and human-readable evidence.
8. Never invent observations that are not present in the video.
9. Mark missing information as `NOT_OBSERVED` rather than guessing.
10. Keep raw evidence separate from interpretation.

## Invocation contract

Recommended:

```bash
python3 scripts/watch.py "<VIDEO_OR_URL>" \
  --detail balanced \
  --out-dir ./artifacts/video/<run-id>
```

Focused section:

```bash
python3 scripts/watch.py "<VIDEO_OR_URL>" \
  --start 00:02:10 \
  --end 00:02:45 \
  --detail balanced \
  --out-dir ./artifacts/video/<run-id>
```

Useful modes:

- `transcript`: captions/transcript only; no default frames.
- `efficient`: fast keyframe scan.
- `balanced`: scene-aware frames, default for POC.
- `token-burner`: uncapped scene candidates; use only when detailed coverage is needed.

Useful options:

- `--timestamps 00:01:23,00:02:10`
- `--max-frames 100`
- `--resolution 512`
- `--fps 1`
- `--whisper groq|openai`
- `--no-whisper`
- `--no-dedup`

## Output contract

Each run creates:

```text
<out-dir>/
├── manifest.json
├── evidence.md
├── transcript.vtt              # when available
├── transcript.txt
├── frames/
│   ├── E001_00-00-12.jpg
│   ├── E002_00-00-18.jpg
│   └── ...
└── meta/
    └── run.json
```

### `manifest.json`

Every frame is an evidence object:

```json
{
  "schema_version": "ark-video-evidence/v1",
  "source": {
    "input": "...",
    "type": "url"
  },
  "transcript": {
    "source": "native_caption",
    "language": "en"
  },
  "frames": [
    {
      "evidence_id": "E001",
      "timestamp": "00:00:12.400",
      "path": "frames/E001_00-00-12.jpg",
      "kind": "scene",
      "confidence": "high"
    }
  ]
}
```

## Evidence semantics

Downstream Skills must preserve these distinctions:

- `OBSERVED`: directly visible/audible in the evidence.
- `INFERRED`: an interpretation derived from evidence.
- `FROM_KB`: information retrieved from a knowledge base.
- `PROPOSED`: a new design suggestion.

This Skill produces **OBSERVED evidence only**.

## Agent reading procedure

After the script completes:

1. Read `manifest.json`.
2. Read `evidence.md`.
3. Read the transcript.
4. Inspect the frame images relevant to the user's question.
5. Cite timestamps/evidence IDs in downstream analysis.
6. If evidence is insufficient, say `NOT_OBSERVED`.
7. Do not turn visual guesses into confirmed game rules.

## Competitor-game POC guidance

For slot-game videos, prioritize frames around:

- game entry / title
- base game
- reel layout
- spin start / stop
- winning combinations
- Wild / Scatter appearance
- Bonus trigger
- Free Spin entry
- Free Spin behavior
- multiplier
- respin / hold-and-win
- jackpot
- UI state changes
- feature transitions
- result / settlement

This is only a **capture priority list**. The Skill must not claim that a feature exists
until an Agent verifies it from the evidence.

## Long-video strategy

For videos longer than roughly 10 minutes, start with `balanced`. If the output is
too sparse, rerun a focused interval with `--start/--end`, or use `token-burner`.

Do not spend a large frame budget on an entire long video when the user asks about
one specific moment.

## Failure behavior

- Missing `ffmpeg`: fail with an actionable installation message.
- Missing `yt-dlp` for URL input: fail with an actionable installation message.
- Missing captions + no Whisper key: still produce frames and mark transcript
  as unavailable.
- Invalid URL/path: fail clearly.
- Extraction failure: preserve any successfully generated artifacts and report
  the failing stage.

## Separation of responsibilities

```text
ark-video-understanding
    ↓
Evidence

slot-game-analysis
    ↓
Game mechanics

game-knowledge
    ↓
Domain knowledge

game-spec
    ↓
Specification
```

Do not merge these responsibilities into this Skill.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pi5 Offline Bilingual Speech Interaction System — 树莓派5上的全离线中英双语语音交互系统。

**Core Pipeline**: ASR (Vosk) → MT (Argos Translate) → TTS (Piper)

**Key Constraints**:
- 全离线运行，不依赖网络
- 模型内存总占用 < 2GB
- 单句处理延迟 < 5秒
- 历史记录最多5条，录音最多5个文件
- 音频标准: 16kHz, 16-bit, Mono WAV

## Development Environment

### Install Profiles

**Windows dev/test** (no ALSA):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

**Linux / Raspberry Pi runtime** (with ALSA):
```bash
sudo apt install -y build-essential python3-dev libasound2-dev espeak-ng ffmpeg
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-pi.txt
```

### Running

```bash
# Web API mode (default: http://127.0.0.1:5000)
python main.py --server

# CLI mode
python main.py --cli

# Run tests (excludes Pi5 hardware tests by default)
pytest -q

# Run with coverage
pytest --cov

# Run specific test file
pytest tests/test_pipeline.py -v

# Run Pi5 hardware tests (requires real device)
pytest -m pi5
```

## Architecture

### Pipeline Chain

Modes are defined in `app/mode_registry.py` and processed by pipeline chains:

| Mode | Chain | Input | Output |
|------|-------|-------|--------|
| tts_zh_zh | (tts) | text | audio |
| asr_zh_zh | (asr) | audio | text |
| mt_tts_zh_en | (mt, tts) | text | audio |
| asr_mt_zh_en | (asr, mt) | audio | text |
| asr_mt_tts_zh_en | (asr, mt, tts) | audio | audio |

**Pipeline execution**: `pipeline/composite.py:run_composite_mode()` → `pipeline/operations.py`

### Web UI Architecture

The web UI is a **Pi5 control plane** — browser does not process audio locally:
- Recording: `POST /api/pi5/recordings/start` → `stop` (saves to recordings folder)
- Playback: Pi5-local ALSA via `POST /api/pi5/media/stop` to stop active playback
- UI polls `GET /api/pi5/media/state` for recording/playback status
- Artifact links provided for download only

### Key Modules

- `models/asr.py` — Vosk wrapper; **critical**: must call `Result()` when `AcceptWaveform()` returns True to collect intermediate results
- `models/mt.py` — Argos Translate wrapper with lazy loading
- `models/tts.py` — Piper wrapper
- `audio/` — ALSA capture/playback (Linux only)
- `storage/` — History (max 5) and recordings (max 5) with FIFO eviction
- `api/` — Flask routes; health check at `/api/health`, bootstrap at `/api/bootstrap`

## Configuration

Main config: `config/default.yaml`
- `audio.device` — ALSA device (e.g., "plughw:3,0")
- `audio.max_record_duration` — 180s limit
- `models.*.model_path` — Model file paths
- `storage.max_history/max_recordings` — 5 each

## Development Rules

### Python Coding (from `.claude/rules/python-coding-rules.md`)

- Import order: stdlib → third-party → local (blank lines between groups)
- Public functions MUST have type annotations
- Use `logging.getLogger(__name__)` — NEVER use `print()`
- No silent exception handling (`except: pass`)
- Context managers for file handles and audio devices
- Subprocess calls MUST have timeout

### Commit Format (from `.claude/rules/commit-rules.md`)

```
<type>(<scope>): <subject>

[optional body]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
Scopes: `audio`, `asr`, `mt`, `tts`, `pipeline`, `storage`, `api`, `hardware`, `config`

### Code Review Checklist (Blocking Issues)

- Type annotations on public functions
- No `except: pass`
- No `print()` statements
- Context managers for resources
- Subprocess timeout
- Storage limits enforced

## Testing

Test markers (from `pytest.ini`):
- Default: `pytest -m "not pi5"` (excludes hardware tests)
- `-m pi5`: Tests requiring real Pi5 hardware/models

Test structure:
- `tests/test_storage.py` — Storage module
- `tests/test_pipeline.py` — Pipeline integration (uses stubs for vosk/argos)
- `tests/test_api.py` — API endpoints
- `tests/test_system.py` — End-to-end

## Common Tasks

```bash
# Check health endpoint
curl http://localhost:5000/api/health

# Export recordings
curl http://localhost:5000/api/recordings/export -o recordings.zip

# Export history
curl http://localhost:5000/api/history/export -o history.zip
```

## Notes

- If `/api/health` returns 503, check `app.config["PIPELINE_FN"]` — pipeline module failed to import
- Windows dev environment intentionally excludes `pyalsaaudio`; real audio requires Linux/Pi5
- Model files must be downloaded separately via `scripts/download_models.sh`

# Pi5 Offline Bilingual Speech Interaction System

Offline Chinese/English speech-text processing project targeting Raspberry Pi 5.
The repo now supports two installation profiles:

- **Windows dev/test profile**: installable without `pyalsaaudio`, suitable for API/UI development and automated tests.
- **Linux / Raspberry Pi runtime profile**: includes ALSA audio bindings for real device recording/playback.

## Install Profiles

### 1. Windows dev/test

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
pytest -q
python main.py
```

Or use the helper script:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_env.ps1
```

Notes:
- This profile intentionally does **not** install `pyalsaaudio`.
- Suitable for Web/API development, contract tests, and most local debugging.
- Real ALSA capture/playback still needs Linux / Raspberry Pi.

### 2. Linux / Raspberry Pi runtime

```bash
sudo apt update
sudo apt install -y build-essential python3-dev python3-venv python3-pip libasound2-dev espeak-ng ffmpeg
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-pi.txt
pytest -q
python main.py
```

Or use the helper script:

```bash
bash scripts/setup_env.sh
```

## Dependency Files

- `requirements.txt`
  - default local/dev entrypoint
  - currently points to `requirements-dev.txt`
- `requirements-dev.txt`
  - cross-platform development/test dependencies
  - excludes Linux-only ALSA binding
- `requirements-pi.txt`
  - Raspberry Pi / Linux runtime dependencies
  - includes `pyalsaaudio`

## Start Commands

### Web server

```bash
python main.py
```

or:

```bash
python main.py --server
```

Default address:
- `http://127.0.0.1:5000`

### CLI mode

```bash
python main.py --cli
```

## Verification

```bash
pytest -q
```

## Notes

- If `pyalsaaudio` fails on Windows, that is expected; use `requirements-dev.txt` instead of the Pi profile.
- Real ASR/TTS/recording validation should still be executed on Raspberry Pi hardware with the required models installed.
- Web audio-output modes now target **Pi5-local ALSA playback**; use `GET /api/pi5/media/state` to inspect playback state and `POST /api/pi5/media/stop` to stop the active Pi5 playback session.
- Pi5-local recording now uses `POST /api/pi5/recordings/start`, `GET /api/pi5/recordings/state`, and `POST /api/pi5/recordings/stop`; the stop route persists a standard recording item that can be reused via `recording_id` in `/api/conversions/speech`.
- The web UI is now a Pi5 control plane: it polls Pi5 media state while recording/playback is active, exposes a browser-side “Stop Pi5 playback” control, and keeps artifact links for download/archive rather than in-browser audio playback.

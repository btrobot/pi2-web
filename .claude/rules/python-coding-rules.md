---
paths:
  - "**/*.py"
---

# Python Coding Rules

适用于项目中所有 Python 代码。

## Import Organization

- imports MUST follow this order: stdlib → third-party → local
- imports MUST be grouped with blank lines between groups

**Correct**:

```python
# 1. Standard library
import os
import logging
from pathlib import Path
from typing import Optional

# 2. Third-party
from flask import Flask, jsonify, request
import vosk

# 3. Local application
from models.asr import ASREngine
from audio.capture import AudioCapture
```

## Type Annotations

- public functions MUST have type annotations for all parameters and return values
- private functions SHOULD have type annotations

**Correct**:

```python
def recognize_audio(audio_path: str, lang: str = "zh") -> str:
    ...

def save_recording(frames: bytes, output_path: str, duration: float) -> str:
    ...
```

## Logging

- MUST use `logging` module (not print)
- MUST configure logger per module: `logger = logging.getLogger(__name__)`

**Correct**:

```python
import logging

logger = logging.getLogger(__name__)

logger.info("ASR 识别完成: lang=%s, duration=%.1fs", lang, duration)
logger.error("模型加载失败: model=%s, error=%s", model_path, str(e))
```

**Incorrect**:

```python
# VIOLATION: using print
print("识别完成")

# VIOLATION: f-string in logging
logger.info(f"result={result}")
```

## Error Handling

- MUST NOT silently catch exceptions (except: pass)
- MUST handle specific exceptions before generic ones
- MUST log errors with context before raising

**Correct**:

```python
try:
    model = vosk.Model(model_path)
except FileNotFoundError:
    logger.error("模型文件不存在: path=%s", model_path)
    raise
except Exception as e:
    logger.error("模型加载失败: path=%s, error=%s", model_path, str(e))
    raise RuntimeError(f"无法加载模型: {model_path}") from e
```

**Incorrect**:

```python
# VIOLATION: silent exception handling
try:
    model = vosk.Model(model_path)
except Exception:
    pass
```

## Flask Routes

- routes SHOULD have docstring descriptions
- routes MUST return appropriate HTTP status codes
- routes MUST validate input parameters

**Correct**:

```python
from flask import Flask, jsonify, send_file, abort

app = Flask(__name__)

@app.route("/api/history", methods=["GET"])
def list_history():
    """获取最近 5 条交互记录"""
    records = storage.get_history()
    return jsonify(records)

@app.route("/api/recordings/<int:rec_id>", methods=["GET"])
def download_recording(rec_id: int):
    """下载录音文件"""
    path = storage.get_recording_path(rec_id)
    if not path or not path.exists():
        abort(404, description="录音文件不存在")
    return send_file(path, mimetype="audio/wav")
```

## Resource Management

- file handles and audio devices MUST use context managers
- subprocess calls MUST have timeout
- audio recording MUST enforce 3-minute limit

**Correct**:

```python
import subprocess

# File I/O
with open(output_path, "wb") as f:
    f.write(audio_data)

# Subprocess with timeout
result = subprocess.run(
    ["espeak", "-v", "zh", text],
    capture_output=True,
    timeout=30,
)

# Audio device
with AudioCapture(device="plughw:2,0", rate=16000) as mic:
    frames = mic.record(max_duration=180)  # 3 min limit
```

## Prohibited Patterns

- MUST NOT use `print()` — use `logging`
- MUST NOT use `except Exception: pass`
- MUST NOT hardcode file paths (use config)
- MUST NOT leave audio devices or file handles open without context managers
- MUST NOT use blocking I/O without timeout

## Related Rules

- `code-review-rules.md` — Code review checklist
- `commit-rules.md` — Commit message format

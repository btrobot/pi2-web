"""Browser-facing audio upload staging and validation helpers."""

from __future__ import annotations

import os
import tempfile
import wave
from pathlib import Path

from werkzeug.datastructures import FileStorage

_MISSING_FILENAME_ERROR = "input_audio filename is required"
_INVALID_WAV_ERROR = "input_audio must be a valid WAV file"
_DURATION_LIMIT_ERROR = "input_audio duration must not exceed {max_duration_seconds} seconds"


class AudioIngressError(ValueError):
    """Raised when a browser-provided audio upload is invalid."""


def _duration_limit_error(max_duration_seconds: int) -> str:
    return _DURATION_LIMIT_ERROR.format(max_duration_seconds=max_duration_seconds)


def stage_browser_wav_upload(upload: FileStorage, *, max_duration_seconds: int | None = None) -> str:
    """Persist one uploaded browser audio file as a validated temp WAV file."""

    filename = (upload.filename or "").strip()
    if not filename:
        raise AudioIngressError(_MISSING_FILENAME_ERROR)

    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            temp_path = handle.name

        upload.save(temp_path)
        _validate_wav_file(Path(temp_path), max_duration_seconds=max_duration_seconds)
        return temp_path
    except AudioIngressError:
        _cleanup_temp_file(temp_path)
        raise
    except Exception as exc:  # noqa: BLE001 - convert parser/runtime failures into stable API errors
        _cleanup_temp_file(temp_path)
        raise AudioIngressError(_INVALID_WAV_ERROR) from exc


def _validate_wav_file(path: Path, *, max_duration_seconds: int | None = None) -> None:
    if not path.exists() or path.stat().st_size == 0:
        raise AudioIngressError(_INVALID_WAV_ERROR)

    try:
        with wave.open(str(path), "rb") as handle:
            if handle.getnchannels() <= 0 or handle.getsampwidth() <= 0:
                raise AudioIngressError(_INVALID_WAV_ERROR)

            frame_rate = handle.getframerate()
            if frame_rate <= 0:
                raise AudioIngressError(_INVALID_WAV_ERROR)

            frame_count = handle.getnframes()
            if frame_count <= 0:
                raise AudioIngressError(_INVALID_WAV_ERROR)

            if max_duration_seconds is not None and (frame_count / frame_rate) > max_duration_seconds:
                raise AudioIngressError(_duration_limit_error(max_duration_seconds))
    except AudioIngressError:
        raise
    except Exception as exc:  # noqa: BLE001 - stdlib parser raises multiple exception types
        raise AudioIngressError(_INVALID_WAV_ERROR) from exc


def _cleanup_temp_file(path: str | None) -> None:
    if path and os.path.exists(path):
        os.unlink(path)

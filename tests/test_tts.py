"""TTS command resolution regression tests."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from models.tts import TTSEngine


def test_tts_engine_finds_local_piper_next_to_active_python(tmp_path: Path) -> None:
    scripts_dir = tmp_path / "venv" / "Scripts"
    scripts_dir.mkdir(parents=True)
    python_path = scripts_dir / "python.exe"
    python_path.write_text("", encoding="utf-8")
    piper_path = scripts_dir / "piper.exe"
    piper_path.write_text("", encoding="utf-8")

    engine = TTSEngine("zh.onnx", "en.onnx")

    with (
        patch.object(sys, "executable", str(python_path)),
        patch("models.tts.shutil.which", return_value=None),
    ):
        assert engine._resolve_piper_command() == str(piper_path)
        assert engine._is_piper_available() is True


def test_run_piper_uses_local_venv_command_even_when_not_on_path(tmp_path: Path) -> None:
    scripts_dir = tmp_path / "venv" / "Scripts"
    scripts_dir.mkdir(parents=True)
    python_path = scripts_dir / "python.exe"
    python_path.write_text("", encoding="utf-8")
    piper_path = scripts_dir / "piper.exe"
    piper_path.write_text("", encoding="utf-8")

    model_path = tmp_path / "voice.onnx"
    model_path.write_text("", encoding="utf-8")
    output_path = tmp_path / "out.wav"

    engine = TTSEngine(str(model_path), str(model_path))

    with (
        patch.object(sys, "executable", str(python_path)),
        patch("models.tts.shutil.which", return_value=None),
        patch("models.tts.subprocess.run", return_value=SimpleNamespace(returncode=0, stderr="")) as mock_run,
    ):
        engine._run_piper("hello", str(model_path), str(output_path))

    assert mock_run.call_args.args[0][0] == str(piper_path)

"""Pi5-local media coordination for playback and recording flows."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from audio.playback import AudioPlaybackError, play as play_wav
from pipeline.operations import capture_audio
from storage.recordings import RecordingManager

logger = logging.getLogger(__name__)

_STOP_TIMEOUT_SECONDS = 2
_RECORD_JOIN_TIMEOUT_SECONDS = 5
_PLAYBACK_SETTLE_SECONDS = 0.35
_RECORD_START_RESPONSE_GRACE_SECONDS = 0.05


class MediaCoordinatorError(Exception):
    """Raised when Pi5 media coordination fails."""


class MediaBusyError(MediaCoordinatorError):
    """Raised when Pi5 media is already occupied."""


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class Pi5MediaCoordinator:
    """Serialize Pi5-local playback and recording on one ALSA device."""

    def __init__(self, *, config: dict[str, Any]) -> None:
        storage_cfg = config["storage"]
        audio_cfg = config["audio"]
        self._config = config
        # 支持独立的录音和播放设备配置
        self._device = audio_cfg.get("device", audio_cfg.get("record_device", "default"))
        self._playback_device = audio_cfg.get("playback_device", self._device)
        self._record_device = audio_cfg.get("record_device", self._device)
        self._recordings_dir = Path(storage_cfg["recordings_dir"])
        self._recordings_dir.mkdir(parents=True, exist_ok=True)
        self._recording_manager = RecordingManager(
            recordings_dir=storage_cfg["recordings_dir"],
            max_recordings=storage_cfg["max_recordings"],
        )
        self._lock = threading.Lock()
        self._playback_proc: subprocess.Popen[Any] | None = None
        self._playback_info: dict[str, Any] | None = None
        self._playback_token = 0
        self._playback_error: str | None = None
        self._recording_thread: threading.Thread | None = None
        self._recording_stop_event: threading.Event | None = None
        self._recording_info: dict[str, Any] | None = None
        self._recording_result_path: str | None = None
        self._recording_error: str | None = None
        self._recording_token = 0
        self._playback_settle_until = 0.0

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            self._refresh_playback_locked()
            return self._snapshot_locked()

    def get_busy_state(self, *, requested_action: str) -> dict[str, Any]:
        payload = self.get_state()
        payload["status"] = "busy"
        payload["requested_action"] = requested_action
        return payload

    def start_playback(
        self,
        wav_path: str,
        *,
        mode_key: str,
        history_id: int,
        audio_url: str | None,
    ) -> dict[str, Any]:
        with self._lock:
            self._refresh_playback_locked()
            busy_message = self._busy_reason_locked(requested_action="playback")
            if busy_message is not None:
                raise MediaBusyError(busy_message)

            try:
                proc = play_wav(wav_path=wav_path, device=self._playback_device, blocking=False)
            except AudioPlaybackError as exc:
                self._playback_error = str(exc)
                raise MediaCoordinatorError(str(exc)) from exc

            if proc is None:  # pragma: no cover - defensive; blocking=False should return Popen
                self._playback_error = "Pi5 playback did not start"
                raise MediaCoordinatorError(self._playback_error)

            self._playback_token += 1
            token = self._playback_token
            self._playback_proc = proc
            self._playback_info = {
                "mode_key": mode_key,
                "history_id": history_id,
                "audio_url": audio_url,
                "wav_path": wav_path,
                "device": self._playback_device,
                "started_at": _utc_now_iso(),
                "pid": proc.pid,
            }
            self._playback_error = None
            self._playback_settle_until = 0.0

        watcher = threading.Thread(
            target=self._watch_playback,
            args=(proc, token),
            daemon=True,
            name=f"pi5-playback-{token}",
        )
        watcher.start()
        return self.get_state()

    def stop_playback(self) -> dict[str, Any]:
        with self._lock:
            self._refresh_playback_locked()
            proc = self._playback_proc
            if proc is None:
                self._playback_error = None
                return self._snapshot_locked()

            self._playback_token += 1
            self._playback_proc = None
            self._playback_info = None
            self._playback_error = None
            self._arm_playback_settle_locked()

        self._terminate_process(proc)
        return self.get_state()

    def start_recording(self) -> dict[str, Any]:
        temp_path = self._create_temp_recording_path()
        stop_event = threading.Event()

        with self._lock:
            self._refresh_playback_locked()
            busy_message = self._busy_reason_locked(requested_action="recording")
            if busy_message is not None:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                raise MediaBusyError(busy_message)

            self._recording_token += 1
            token = self._recording_token
            self._recording_thread = threading.Thread(
                target=self._record_audio_worker_bootstrap,
                args=(temp_path, stop_event, token),
                daemon=True,
                name=f"pi5-recording-{token}",
            )
            self._recording_stop_event = stop_event
            self._recording_info = {
                "started_at": _utc_now_iso(),
                "device": self._record_device,
                "max_duration_seconds": int(self._config["audio"]["max_record_duration"]),
                "temp_wav_path": temp_path,
            }
            self._recording_result_path = None
            self._recording_error = None
            thread = self._recording_thread
            start_state = self._snapshot_locked()

        try:
            thread.start()
        except RuntimeError as exc:
            with self._lock:
                self._reset_recording_locked(clear_error=True)
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
            raise MediaCoordinatorError(f"Pi5 recording failed to start: {exc}") from exc
        return start_state

    def _record_audio_worker_bootstrap(self, output_path: str, stop_event: threading.Event, token: int) -> None:
        time.sleep(_RECORD_START_RESPONSE_GRACE_SECONDS)
        self._record_audio_worker(output_path, stop_event, token)

    def stop_recording(self) -> dict[str, Any]:
        with self._lock:
            thread = self._recording_thread
            stop_event = self._recording_stop_event
            pending_path = self._recording_result_path
            if thread is None and pending_path is None:
                raise MediaCoordinatorError("Pi5 recording is not active")

        if thread is not None and stop_event is not None:
            stop_event.set()
            thread.join(timeout=_RECORD_JOIN_TIMEOUT_SECONDS)
            if thread.is_alive():
                raise MediaCoordinatorError("Pi5 recording did not finish cleanly")

        with self._lock:
            if self._recording_error:
                error = self._recording_error
                self._reset_recording_locked(clear_error=False)
                raise MediaCoordinatorError(error)

            result_path = self._recording_result_path
            if result_path is None:
                raise MediaCoordinatorError("Pi5 recording did not produce audio")

        try:
            recording = self._recording_manager.save_recording(result_path)
        except Exception as exc:  # noqa: BLE001 - surface save failure via coordinator
            raise MediaCoordinatorError(f"failed to save Pi5 recording: {exc}") from exc
        finally:
            if os.path.exists(result_path):
                try:
                    os.unlink(result_path)
                except OSError as exc:  # pragma: no cover - defensive cleanup
                    logger.warning("failed to delete temp Pi5 recording: path=%s, error=%s", result_path, str(exc))

        with self._lock:
            self._reset_recording_locked(clear_error=True)

        return recording

    def _record_audio_worker(self, output_path: str, stop_event: threading.Event, token: int) -> None:
        try:
            captured_path = capture_audio(
                config=self._config,
                prefix="pi5_recording",
                stop_flag=stop_event,
                output_path=output_path,
                max_duration=int(self._config["audio"]["max_record_duration"]),
            )
        except Exception as exc:  # noqa: BLE001 - background worker must persist error
            with self._lock:
                if token != self._recording_token:
                    return
                self._recording_thread = None
                self._recording_stop_event = None
                self._recording_result_path = None
                self._recording_error = str(exc)
            logger.error("Pi5 recording failed: error=%s", str(exc))
            return

        with self._lock:
            if token != self._recording_token:
                if os.path.exists(captured_path):
                    try:
                        os.unlink(captured_path)
                    except OSError:
                        pass
                return
            self._recording_thread = None
            self._recording_stop_event = None
            self._recording_result_path = captured_path
            self._recording_error = None

    def _watch_playback(self, proc: subprocess.Popen[Any], token: int) -> None:
        return_code = proc.wait()
        with self._lock:
            if token != self._playback_token or self._playback_proc is not proc:
                return

            self._playback_proc = None
            self._playback_info = None
            self._arm_playback_settle_locked()
            if return_code != 0:
                self._playback_error = f"Pi5 playback exited with code {return_code}"
                logger.error("Pi5 playback failed: returncode=%s", return_code)
            else:
                self._playback_error = None

    def _refresh_playback_locked(self) -> None:
        proc = self._playback_proc
        if proc is None:
            return

        return_code = proc.poll()
        if return_code is None:
            return

        self._playback_proc = None
        self._playback_info = None
        self._arm_playback_settle_locked()
        if return_code != 0:
            self._playback_error = f"Pi5 playback exited with code {return_code}"
        else:
            self._playback_error = None

    def _snapshot_locked(self) -> dict[str, Any]:
        recording_thread_alive = self._recording_thread is not None and self._recording_thread.is_alive()
        recording_starting = (
            self._recording_thread is not None
            and self._recording_info is not None
            and self._recording_result_path is None
            and self._recording_error is None
        )
        playback_settling = self._is_playback_settling_locked()
        recording_info = None
        if self._recording_info is not None:
            recording_info = {
                key: value
                for key, value in self._recording_info.items()
                if key != "temp_wav_path"
            }
            recording_info["pending_save"] = self._recording_result_path is not None

        if recording_thread_alive or recording_starting:
            status = "recording"
            active_kind = "recording"
        elif self._playback_proc is not None:
            status = "playing"
            active_kind = "playback"
        elif playback_settling:
            status = "busy"
            active_kind = None
        elif self._recording_error or self._playback_error:
            status = "error"
            active_kind = None
        else:
            status = "idle"
            active_kind = None

        playback = dict(self._playback_info) if self._playback_info else None
        # Keep the top-level Pi5 state payload stable for API consumers.
        # Device-specific details stay nested inside playback / recording entries.
        return {
            "status": status,
            "device": self._device,
            "active_kind": active_kind,
            "playback": playback,
            "recording": recording_info,
            "error": self._recording_error or self._playback_error,
        }

    def _reset_recording_locked(self, *, clear_error: bool) -> None:
        self._recording_thread = None
        self._recording_stop_event = None
        self._recording_info = None
        self._recording_result_path = None
        if clear_error:
            self._recording_error = None

    def _busy_reason_locked(self, *, requested_action: str) -> str | None:
        recording_thread_alive = self._recording_thread is not None and self._recording_thread.is_alive()
        if recording_thread_alive or self._recording_result_path is not None:
            if requested_action == "playback":
                return "Pi5 media is busy with recording"
            return "Pi5 recording is already in progress"
        if self._playback_proc is not None:
            if requested_action == "recording":
                return "Pi5 media is busy with playback"
            return "Pi5 media is busy with playback"
        if self._is_playback_settling_locked():
            return "Pi5 media is busy with playback"
        return None

    def _is_playback_settling_locked(self) -> bool:
        if self._playback_settle_until <= 0:
            return False
        if time.monotonic() < self._playback_settle_until:
            return True
        self._playback_settle_until = 0.0
        return False

    def _arm_playback_settle_locked(self) -> None:
        self._playback_settle_until = max(
            self._playback_settle_until,
            time.monotonic() + _PLAYBACK_SETTLE_SECONDS,
        )

    def _create_temp_recording_path(self) -> str:
        with tempfile.NamedTemporaryFile(
            prefix="pi5_recording_",
            suffix=".wav",
            dir=self._recordings_dir,
            delete=False,
        ) as handle:
            return handle.name

    def _terminate_process(self, proc: subprocess.Popen[Any]) -> None:
        if proc.poll() is not None:
            return

        try:
            proc.terminate()
            proc.wait(timeout=_STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=_STOP_TIMEOUT_SECONDS)
        except OSError as exc:  # pragma: no cover - defensive cleanup
            logger.warning("failed to stop Pi5 playback process: error=%s", str(exc))

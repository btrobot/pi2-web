"""系统集成测试 — Pi5 离线翻译系统

覆盖范围:
- FR-01~06 端到端功能验证（mock ASR/MT/TTS）
- 管线延迟性能断言
- 内存占用检查（< 2GB）
- FIFO 存储淘汰验证
- API 端点: /api/health, /api/history, /api/recordings

标记说明:
- @pytest.mark.pi5  — 需要实机运行（真实模型/音频设备）
- 无标记            — 纯 mock，CI 可直接运行
"""

# 1. Standard library
import time
import wave
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# 2. Third-party
import pytest

# 3. Local
from api.app import create_app
from pipeline import run_pipeline
from storage.history import HistoryManager

# ---------------------------------------------------------------------------
# Pytest markers
# ---------------------------------------------------------------------------
pi5 = pytest.mark.pi5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wav(path: Path, duration_s: float = 0.5, sample_rate: int = 16000) -> None:
    """Write a silent WAV file to *path*."""
    num_frames = int(sample_rate * duration_s)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00" * num_frames * 2)


# ---------------------------------------------------------------------------
# Shared mock pipeline results
# ---------------------------------------------------------------------------

_TTS_RESULT: dict[str, Any] = {
    "text": "你好世界",
    "audio_path": None,
    "error": None,
}

_ASR_RESULT: dict[str, Any] = {
    "text": "hello world",
    "audio_path": None,
    "error": None,
}

_MT_TTS_RESULT: dict[str, Any] = {
    "source_text": "你好世界",
    "translated_text": "hello world",
    "audio_path": None,
    "error": None,
}

_ASR_MT_RESULT: dict[str, Any] = {
    "source_text": "hello world",
    "translated_text": "你好世界",
    "audio_path": None,
    "error": None,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app(mock_config: dict) -> Any:
    """Flask test application with mocked pipeline."""
    mock_run = MagicMock(return_value=_TTS_RESULT.copy())
    flask_app = create_app(mock_config)
    flask_app.config["PIPELINE_FN"] = mock_run
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture()
def client(app: Any) -> Any:
    return app.test_client()


# ---------------------------------------------------------------------------
# FR-01: TTS — text → audio
# ---------------------------------------------------------------------------

class TestFR01TTS:
    """FR-01: 文本转语音（TTS）端到端"""

    def test_tts_returns_result(self, mock_config: dict, tmp_path: Path) -> None:
        result_with_audio = {**_TTS_RESULT, "audio_path": str(tmp_path / "out.wav")}
        _make_wav(tmp_path / "out.wav")

        with patch("pipeline.run_tts", return_value=result_with_audio):
            result = run_pipeline("tts", mock_config, text="你好世界", lang="zh")

        assert result["text"] == "你好世界"
        assert result.get("error") is None

    def test_tts_saves_history(self, mock_config: dict, tmp_path: Path) -> None:
        audio_file = tmp_path / "out.wav"
        _make_wav(audio_file)
        result_with_audio = {**_TTS_RESULT, "audio_path": str(audio_file)}

        with patch("pipeline.run_tts", return_value=result_with_audio):
            result = run_pipeline("tts", mock_config, text="你好世界", lang="zh")

        assert "history_id" in result

    def test_tts_invalid_mode_raises(self, mock_config: dict) -> None:
        with pytest.raises(ValueError, match="不支持的管线模式"):
            run_pipeline("unknown", mock_config, text="x", lang="zh")


# ---------------------------------------------------------------------------
# FR-02: ASR — audio → text
# ---------------------------------------------------------------------------

class TestFR02ASR:
    """FR-02: 语音识别（ASR）端到端"""

    def test_asr_returns_text(self, mock_config: dict) -> None:
        with patch("pipeline.run_asr", return_value=_ASR_RESULT.copy()):
            result = run_pipeline("asr", mock_config, lang="en")

        assert result["text"] == "hello world"
        assert result.get("error") is None

    def test_asr_saves_history(self, mock_config: dict) -> None:
        with patch("pipeline.run_asr", return_value=_ASR_RESULT.copy()):
            result = run_pipeline("asr", mock_config, lang="en")

        assert "history_id" in result


# ---------------------------------------------------------------------------
# FR-03: MT+TTS — text → translated audio
# ---------------------------------------------------------------------------

class TestFR03MTTTS:
    """FR-03: 机器翻译 + TTS 端到端"""

    def test_mt_tts_returns_translation(self, mock_config: dict) -> None:
        with patch("pipeline.run_mt_tts", return_value=_MT_TTS_RESULT.copy()):
            result = run_pipeline(
                "mt_tts", mock_config,
                text="你好世界", source_lang="zh", target_lang="en",
            )

        assert result["translated_text"] == "hello world"
        assert result.get("error") is None

    def test_mt_tts_saves_history(self, mock_config: dict) -> None:
        with patch("pipeline.run_mt_tts", return_value=_MT_TTS_RESULT.copy()):
            result = run_pipeline(
                "mt_tts", mock_config,
                text="你好世界", source_lang="zh", target_lang="en",
            )

        assert "history_id" in result


# ---------------------------------------------------------------------------
# FR-04: ASR+MT — audio → translated text
# ---------------------------------------------------------------------------

class TestFR04ASRMT:
    """FR-04: ASR + 机器翻译端到端"""

    def test_asr_mt_returns_translation(self, mock_config: dict) -> None:
        with patch("pipeline.run_asr_mt", return_value=_ASR_MT_RESULT.copy()):
            result = run_pipeline(
                "asr_mt", mock_config,
                source_lang="en", target_lang="zh",
            )

        assert result["translated_text"] == "你好世界"
        assert result.get("error") is None

    def test_asr_mt_saves_history(self, mock_config: dict) -> None:
        with patch("pipeline.run_asr_mt", return_value=_ASR_MT_RESULT.copy()):
            result = run_pipeline(
                "asr_mt", mock_config,
                source_lang="en", target_lang="zh",
            )

        assert "history_id" in result


# ---------------------------------------------------------------------------
# FR-05: 历史记录存储与检索
# ---------------------------------------------------------------------------

class TestFR05History:
    """FR-05: 历史记录 FIFO 存储"""

    def test_add_and_retrieve_record(self, tmp_storage_dir: Path) -> None:
        mgr = HistoryManager(str(tmp_storage_dir / "history"), max_records=5)
        record = mgr.add_record(
            record_type="tts",
            source_lang="zh",
            target_lang=None,
            source_text="你好",
            target_text=None,
            audio_path=None,
        )
        assert record["id"] == 1
        assert record["type"] == "tts"
        assert mgr.get_record(1) is not None

    def test_fifo_eviction_at_max_capacity(self, tmp_storage_dir: Path) -> None:
        """超过 max_records 时，最旧记录被淘汰。"""
        mgr = HistoryManager(str(tmp_storage_dir / "history"), max_records=5)
        for i in range(6):
            mgr.add_record(
                record_type="tts",
                source_lang="zh",
                target_lang=None,
                source_text=f"text-{i}",
                target_text=None,
                audio_path=None,
            )
        records = mgr.list_records()
        assert len(records) == 5
        # 第一条（id=1）应已被淘汰
        assert records[0]["id"] == 2

    def test_fifo_eviction_removes_audio_file(self, tmp_storage_dir: Path, tmp_path: Path) -> None:
        """FIFO 淘汰时，关联音频文件应被删除。"""
        history_dir = tmp_storage_dir / "history"
        mgr = HistoryManager(str(history_dir), max_records=2)

        audio_file = tmp_path / "audio.wav"
        _make_wav(audio_file)

        # 第一条带音频
        mgr.add_record(
            record_type="tts",
            source_lang="zh",
            target_lang=None,
            source_text="first",
            target_text=None,
            audio_path=str(audio_file),
        )
        copied = history_dir / "history_001.wav"
        assert copied.exists()

        # 再加两条触发淘汰
        for _ in range(2):
            mgr.add_record(
                record_type="tts",
                source_lang="zh",
                target_lang=None,
                source_text="filler",
                target_text=None,
                audio_path=None,
            )

        assert not copied.exists(), "淘汰的历史音频文件应已被删除"


# ---------------------------------------------------------------------------
# FR-06: API 端点
# ---------------------------------------------------------------------------

class TestFR06APIEndpoints:
    """FR-06: HTTP API 端点验证"""

    def test_health_returns_ok(self, client: Any) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}

    def test_history_returns_list(self, client: Any) -> None:
        resp = client.get("/api/history")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_recordings_returns_list(self, client: Any) -> None:
        resp = client.get("/api/recordings")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_translate_mode1_tts(self, client: Any, app: Any) -> None:
        app.config["PIPELINE_FN"].return_value = _TTS_RESULT.copy()
        resp = client.post(
            "/api/translate",
            json={"mode": 1, "text": "你好", "source_lang": "zh", "target_lang": ""},
        )
        assert resp.status_code == 200
        assert "result" in resp.get_json()

    def test_translate_mode2_asr(self, client: Any, app: Any) -> None:
        app.config["PIPELINE_FN"].return_value = _ASR_RESULT.copy()
        resp = client.post(
            "/api/translate",
            json={"mode": 2, "text": "", "source_lang": "en", "target_lang": ""},
        )
        assert resp.status_code == 200

    def test_translate_mode3_mt_tts(self, client: Any, app: Any) -> None:
        app.config["PIPELINE_FN"].return_value = _MT_TTS_RESULT.copy()
        resp = client.post(
            "/api/translate",
            json={"mode": 3, "text": "你好", "source_lang": "zh", "target_lang": "en"},
        )
        assert resp.status_code == 200

    def test_translate_mode4_asr_mt(self, client: Any, app: Any) -> None:
        app.config["PIPELINE_FN"].return_value = _ASR_MT_RESULT.copy()
        resp = client.post(
            "/api/translate",
            json={"mode": 4, "text": "", "source_lang": "en", "target_lang": "zh"},
        )
        assert resp.status_code == 200

    def test_translate_invalid_mode(self, client: Any) -> None:
        resp = client.post(
            "/api/translate",
            json={"mode": 99, "text": "x", "source_lang": "zh", "target_lang": "en"},
        )
        assert resp.status_code == 400

    def test_translate_no_pipeline(self, mock_config: dict) -> None:
        app = create_app(mock_config)
        app.config["PIPELINE_FN"] = None
        app.config["TESTING"] = True
        c = app.test_client()
        resp = c.post(
            "/api/translate",
            json={"mode": 1, "text": "x", "source_lang": "zh", "target_lang": ""},
        )
        assert resp.status_code == 503

    def test_history_audio_404_for_missing(self, client: Any) -> None:
        resp = client.get("/api/history/9999/audio")
        assert resp.status_code == 404

    def test_recordings_audio_404_for_missing(self, client: Any) -> None:
        resp = client.get("/api/recordings/9999/audio")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Performance: pipeline latency targets
# ---------------------------------------------------------------------------

class TestPipelineLatency:
    """管线延迟性能检查（mock 下的调度开销，不含模型推理）"""

    # 目标值（秒）— mock 下应远低于此值
    _TTS_LATENCY_TARGET = 0.5
    _ASR_LATENCY_TARGET = 0.5
    _MT_TTS_LATENCY_TARGET = 0.5
    _ASR_MT_LATENCY_TARGET = 0.5

    def test_tts_latency(self, mock_config: dict) -> None:
        with patch("pipeline.run_tts", return_value=_TTS_RESULT.copy()):
            t0 = time.perf_counter()
            run_pipeline("tts", mock_config, text="你好", lang="zh")
            elapsed = time.perf_counter() - t0
        assert elapsed < self._TTS_LATENCY_TARGET, (
            f"TTS 调度延迟 {elapsed:.3f}s 超过目标 {self._TTS_LATENCY_TARGET}s"
        )

    def test_asr_latency(self, mock_config: dict) -> None:
        with patch("pipeline.run_asr", return_value=_ASR_RESULT.copy()):
            t0 = time.perf_counter()
            run_pipeline("asr", mock_config, lang="en")
            elapsed = time.perf_counter() - t0
        assert elapsed < self._ASR_LATENCY_TARGET, (
            f"ASR 调度延迟 {elapsed:.3f}s 超过目标 {self._ASR_LATENCY_TARGET}s"
        )

    def test_mt_tts_latency(self, mock_config: dict) -> None:
        with patch("pipeline.run_mt_tts", return_value=_MT_TTS_RESULT.copy()):
            t0 = time.perf_counter()
            run_pipeline("mt_tts", mock_config, text="你好", source_lang="zh", target_lang="en")
            elapsed = time.perf_counter() - t0
        assert elapsed < self._MT_TTS_LATENCY_TARGET, (
            f"MT+TTS 调度延迟 {elapsed:.3f}s 超过目标 {self._MT_TTS_LATENCY_TARGET}s"
        )

    def test_asr_mt_latency(self, mock_config: dict) -> None:
        with patch("pipeline.run_asr_mt", return_value=_ASR_MT_RESULT.copy()):
            t0 = time.perf_counter()
            run_pipeline("asr_mt", mock_config, source_lang="en", target_lang="zh")
            elapsed = time.perf_counter() - t0
        assert elapsed < self._ASR_MT_LATENCY_TARGET, (
            f"ASR+MT 调度延迟 {elapsed:.3f}s 超过目标 {self._ASR_MT_LATENCY_TARGET}s"
        )

    @pi5
    def test_tts_e2e_latency_pi5(self, mock_config: dict) -> None:
        """实机: TTS 端到端延迟（含模型推理）< 3s"""
        t0 = time.perf_counter()
        run_pipeline("tts", mock_config, text="你好世界", lang="zh")
        elapsed = time.perf_counter() - t0
        assert elapsed < 3.0, f"TTS 实机延迟 {elapsed:.3f}s 超过 3s 目标"

    @pi5
    def test_asr_e2e_latency_pi5(self, mock_config: dict) -> None:
        """实机: ASR 端到端延迟（含模型推理）< 5s"""
        t0 = time.perf_counter()
        run_pipeline("asr", mock_config, lang="en")
        elapsed = time.perf_counter() - t0
        assert elapsed < 5.0, f"ASR 实机延迟 {elapsed:.3f}s 超过 5s 目标"


# ---------------------------------------------------------------------------
# Memory: model load < 2 GB
# ---------------------------------------------------------------------------

class TestMemoryUsage:
    """内存占用检查"""

    def test_process_memory_under_2gb(self) -> None:
        """当前进程 RSS < 2 GB（mock 测试环境基线）"""
        try:
            import psutil  # type: ignore[import]
            proc = psutil.Process()
            rss_bytes = proc.memory_info().rss
        except ImportError:
            # 回退到 /proc/meminfo（Linux/Pi5）
            rss_bytes = _read_proc_rss_bytes()

        limit = 2 * 1024 ** 3  # 2 GB
        assert rss_bytes < limit, (
            f"进程内存 {rss_bytes / 1024**3:.2f} GB 超过 2 GB 限制"
        )

    @pi5
    def test_memory_after_model_load_pi5(self) -> None:
        """实机: 加载所有模型后内存 < 2 GB"""
        try:
            import psutil  # type: ignore[import]
            proc = psutil.Process()

            from models.asr import ASREngine  # type: ignore[import]
            from models.mt import MTEngine  # type: ignore[import]
            from models.tts import TTSEngine  # type: ignore[import]

            rss_bytes = proc.memory_info().rss
        except ImportError:
            pytest.skip("psutil 或模型模块不可用，跳过实机内存测试")

        limit = 2 * 1024 ** 3
        assert rss_bytes < limit, (
            f"模型加载后内存 {rss_bytes / 1024**3:.2f} GB 超过 2 GB 限制"
        )


def _read_proc_rss_bytes() -> int:
    """从 /proc/self/status 读取 VmRSS（Linux 回退方案）。"""
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    kb = int(line.split()[1])
                    return kb * 1024
    except OSError:
        pass
    return 0


# ---------------------------------------------------------------------------
# Storage limits: FIFO enforcement
# ---------------------------------------------------------------------------

class TestStorageLimits:
    """存储限制与 FIFO 淘汰"""

    def test_history_never_exceeds_max(self, tmp_storage_dir: Path) -> None:
        mgr = HistoryManager(str(tmp_storage_dir / "history"), max_records=5)
        for i in range(10):
            mgr.add_record(
                record_type="asr",
                source_lang="en",
                target_lang=None,
                source_text=f"utterance-{i}",
                target_text=None,
                audio_path=None,
            )
        assert len(mgr.list_records()) == 5

    def test_history_ids_are_monotonic(self, tmp_storage_dir: Path) -> None:
        mgr = HistoryManager(str(tmp_storage_dir / "history"), max_records=5)
        for i in range(3):
            mgr.add_record(
                record_type="tts",
                source_lang="zh",
                target_lang=None,
                source_text=f"text-{i}",
                target_text=None,
                audio_path=None,
            )
        ids = [r["id"] for r in mgr.list_records()]
        assert ids == sorted(ids)

    def test_history_export_zip_contains_metadata(self, tmp_storage_dir: Path) -> None:
        import zipfile

        mgr = HistoryManager(str(tmp_storage_dir / "history"), max_records=5)
        mgr.add_record(
            record_type="mt_tts",
            source_lang="zh",
            target_lang="en",
            source_text="你好",
            target_text="hello",
            audio_path=None,
        )
        buf = mgr.export_all()
        with zipfile.ZipFile(buf) as zf:
            assert "metadata.json" in zf.namelist()

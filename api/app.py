"""Flask 应用工厂 — Pi5 离线翻译系统 HTTP 服务"""

import logging
import os
import tempfile
from typing import Any

from flask import Flask, Response, jsonify, render_template, request

from storage.recordings import RecordingManager

logger = logging.getLogger(__name__)

_MODE_MAP = {
    1: ("tts", True),
    2: ("asr", False),
    3: ("asr_mt", False),
    4: ("asr_mt", False),
    5: ("asr_mt", False),
}


def create_app(config: dict[str, Any]) -> Flask:
    app = Flask(__name__)
    app.config["APP_CONFIG"] = config

    from api.history_routes import history_bp
    from api.recording_routes import recording_bp
    app.register_blueprint(history_bp)
    app.register_blueprint(recording_bp)

    # Pipeline runner 单例，避免每次请求重建
    app.config["PIPELINE_RUNNER"] = None
    try:
        from pipeline import run_pipeline
        app.config["PIPELINE_FN"] = run_pipeline
    except ImportError:
        app.config["PIPELINE_FN"] = None
        logger.warning("pipeline 模块未找到，翻译/录音功能不可用")

    @app.route("/", methods=["GET"])
    def index() -> str | Response:
        return render_template("index.html")

    @app.route("/api/health", methods=["GET"])
    def health() -> tuple[Response, int]:
        return jsonify({"status": "ok"}), 200

    @app.route("/api/translate", methods=["POST"])
    def translate() -> tuple[Response, int]:
        body = request.get_json(silent=True) or {}
        mode = body.get("mode")
        text = body.get("text", "")
        source_lang = body.get("source_lang", "")
        target_lang = body.get("target_lang", "")

        # 输入校验
        if mode not in (1, 2, 3, 4, 5):
            return jsonify({"error": "mode 必须为 1~5"}), 400
        if not isinstance(text, str):
            return jsonify({"error": "text 必须为字符串"}), 400
        if not isinstance(source_lang, str) or not isinstance(target_lang, str):
            return jsonify({"error": "source_lang/target_lang 必须为字符串"}), 400

        run_fn = app.config.get("PIPELINE_FN")
        if run_fn is None:
            return jsonify({"error": "翻译服务未初始化"}), 503

        try:
            cfg = app.config["APP_CONFIG"]
            pipeline_mode, needs_text = _MODE_MAP[mode]

            kwargs: dict[str, Any] = {}
            if pipeline_mode == "tts":
                kwargs = {"text": text, "lang": source_lang or "zh"}
            elif pipeline_mode == "asr":
                kwargs = {"lang": source_lang or "en"}
            else:  # mt_tts, asr_mt
                # 从请求体获取语言对，默认识别中文
                kwargs = {
                    "source_lang": source_lang or "zh",
                    "target_lang": target_lang or "en",
                }
                if pipeline_mode == "mt_tts":
                    kwargs["text"] = text

            result = run_fn(pipeline_mode, cfg, **kwargs)
            return jsonify({"result": result}), 200
        except Exception as e:
            logger.error("翻译失败: mode=%s, error=%s", mode, str(e))
            return jsonify({"error": "翻译失败: " + str(e)}), 500

    @app.route("/api/record", methods=["POST"])
    def record() -> tuple[Response, int]:
        cfg = app.config["APP_CONFIG"]
        from audio import record as audio_record

        storage_cfg = cfg["storage"]
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            audio_record(output_path=tmp_path, device=cfg["audio"]["device"])
            mgr = RecordingManager(storage_cfg["recordings_dir"], storage_cfg["max_recordings"])
            rec = mgr.save_recording(tmp_path)
            return jsonify({"message": "录音完成", "recording": rec}), 200
        except Exception as e:
            logger.error("录音失败: error=%s", str(e))
            return jsonify({"error": "录音失败: " + str(e)}), 500
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError as e:
                    logger.warning("临时文件删除失败: path=%s, error=%s", tmp_path, str(e))

    logger.info("Flask 应用初始化完成")
    return app


def run_server(config: dict[str, Any]) -> None:
    app = create_app(config)
    api_cfg = config.get("api", {})
    host = api_cfg.get("host", "0.0.0.0")
    port = api_cfg.get("port", 5000)
    logger.info("启动 API 服务器: host=%s, port=%d", host, port)
    app.run(host=host, port=port)

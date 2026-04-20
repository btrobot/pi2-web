"""Flask 应用工厂 — Pi5 离线翻译系统 HTTP 服务"""

import logging
from typing import Any

from flask import Flask, Response, jsonify, render_template

from audio.media_coordinator import Pi5MediaCoordinator
from app.i18n_registry import DEFAULT_LOCALE, SUPPORTED_LOCALES, get_bootstrap_i18n
from app.mode_registry import list_mode_definitions

logger = logging.getLogger(__name__)



def _build_bootstrap_payload(config: dict[str, Any]) -> dict[str, Any]:
    audio_cfg = config["audio"]
    storage_cfg = config["storage"]

    return {
        "app": {
            "default_locale": DEFAULT_LOCALE,
            "supported_locales": list(SUPPORTED_LOCALES),
        },
        "constraints": {
            "max_record_seconds": audio_cfg["max_record_duration"],
            "max_history": storage_cfg["max_history"],
            "max_recordings": storage_cfg["max_recordings"],
        },
        "modes": [
            {
                "mode_key": mode.mode_key,
                "group_key": mode.group_key,
                "input_type": mode.input_type,
                "output_type": mode.output_type,
                "source_lang": mode.source_lang,
                "target_lang": mode.target_lang,
            }
            for mode in list_mode_definitions()
        ],
        "i18n": get_bootstrap_i18n(),
    }


def create_app(config: dict[str, Any]) -> Flask:
    app = Flask(__name__)
    app.config["APP_CONFIG"] = config
    app.extensions["pi5_media_coordinator"] = Pi5MediaCoordinator(config=config)

    from api.conversion_routes import conversion_bp
    from api.history_routes import history_bp
    from api.pi5_media_routes import pi5_media_bp
    from api.recording_routes import recording_bp
    app.register_blueprint(conversion_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(pi5_media_bp)
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

    @app.route("/api/bootstrap", methods=["GET"])
    def bootstrap() -> tuple[Response, int]:
        return jsonify(_build_bootstrap_payload(app.config["APP_CONFIG"])), 200

    logger.info("Flask 应用初始化完成")
    return app


def run_server(config: dict[str, Any]) -> None:
    app = create_app(config)
    api_cfg = config.get("api", {})
    host = api_cfg.get("host", "0.0.0.0")
    port = api_cfg.get("port", 5000)
    logger.info("启动 API 服务器: host=%s, port=%d", host, port)
    app.run(host=host, port=port)

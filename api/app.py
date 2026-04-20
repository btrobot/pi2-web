"""Flask application factory for the Pi5 offline bilingual speech system."""

import logging
from typing import Any

from flask import Flask, Response, jsonify, render_template

from audio.media_coordinator import Pi5MediaCoordinator
from app.i18n_registry import DEFAULT_LOCALE, SUPPORTED_LOCALES, get_bootstrap_i18n
from app.mode_registry import list_mode_definitions
from models.mt import configure_argos_environment, validate_mt_runtime

logger = logging.getLogger(__name__)


def _run_startup_checks(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mt_cfg = config.get("models", {}).get("mt", {})
    package_dir = configure_argos_environment(mt_cfg.get("package_path"))
    mt_issues = validate_mt_runtime(package_dir=package_dir, allow_network=False)

    if mt_issues:
        logger.warning("startup MT self-check failed: %s", " | ".join(mt_issues))
    else:
        logger.info("startup MT self-check passed: package_dir=%s", package_dir)

    return {
        "mt": {
            "ok": not mt_issues,
            "issues": mt_issues,
            "package_dir": str(package_dir) if package_dir is not None else None,
        }
    }


def _build_health_payload(app: Flask) -> tuple[dict[str, Any], int]:
    startup_checks = app.extensions.get("startup_checks", {})
    pipeline_ok = app.config.get("PIPELINE_FN") is not None
    checks = {
        "pipeline": {
            "ok": pipeline_ok,
            "issues": [] if pipeline_ok else ["pipeline service unavailable"],
        },
        **startup_checks,
    }
    overall_ok = all(check.get("ok", False) for check in checks.values())
    return {"status": "ok" if overall_ok else "error", "checks": checks}, 200 if overall_ok else 503


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
    app.extensions["startup_checks"] = _run_startup_checks(config)

    from api.conversion_routes import conversion_bp
    from api.history_routes import history_bp
    from api.pi5_media_routes import pi5_media_bp
    from api.recording_routes import recording_bp

    app.register_blueprint(conversion_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(pi5_media_bp)
    app.register_blueprint(recording_bp)

    app.config["PIPELINE_RUNNER"] = None
    try:
        from pipeline import run_pipeline

        app.config["PIPELINE_FN"] = run_pipeline
    except ImportError:
        app.config["PIPELINE_FN"] = None
        logger.warning("pipeline module not found; conversion and recording features are unavailable")

    @app.route("/", methods=["GET"])
    def index() -> str | Response:
        return render_template("index.html")

    @app.route("/api/health", methods=["GET"])
    def health() -> tuple[Response, int]:
        payload, status_code = _build_health_payload(app)
        return jsonify(payload), status_code

    @app.route("/api/bootstrap", methods=["GET"])
    def bootstrap() -> tuple[Response, int]:
        return jsonify(_build_bootstrap_payload(app.config["APP_CONFIG"])), 200

    logger.info("Flask application initialized")
    return app


def run_server(config: dict[str, Any]) -> None:
    app = create_app(config)
    api_cfg = config.get("api", {})
    host = api_cfg.get("host", "0.0.0.0")
    port = api_cfg.get("port", 5000)
    logger.info("starting API server: host=%s, port=%d", host, port)
    app.run(host=host, port=port)

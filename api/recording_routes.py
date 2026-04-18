"""录音路由 — GET /api/recordings"""

# 1. Standard library
import logging

# 2. Third-party
from flask import Blueprint, current_app, jsonify, send_file, abort

# 3. Local
from storage.recordings import RecordingManager

logger = logging.getLogger(__name__)

recording_bp = Blueprint("recordings", __name__)


def _get_manager() -> RecordingManager:
    config = current_app.config["APP_CONFIG"]
    storage_cfg = config["storage"]
    return RecordingManager(
        recordings_dir=storage_cfg["recordings_dir"],
        max_recordings=storage_cfg["max_recordings"],
    )


@recording_bp.route("/api/recordings", methods=["GET"])
def list_recordings() -> tuple:
    """获取最近 5 条录音列表"""
    try:
        recordings = _get_manager().list_recordings()
        return jsonify(recordings), 200
    except Exception as e:
        logger.error("获取录音列表失败: error=%s", str(e))
        return jsonify({"error": "获取录音列表失败"}), 500


@recording_bp.route("/api/recordings/<int:recording_id>/audio", methods=["GET"])
def get_recording_audio(recording_id: int) -> object:
    """下载指定录音文件"""
    try:
        path = _get_manager().get_audio_path(recording_id)
    except Exception as e:
        logger.error("获取录音音频失败: id=%d, error=%s", recording_id, str(e))
        return jsonify({"error": "获取音频失败"}), 500

    if path is None:
        abort(404, description="录音文件不存在")
    return send_file(path, mimetype="audio/wav")


@recording_bp.route("/api/recordings/export", methods=["GET"])
def export_recordings() -> object:
    """导出全部录音为 ZIP 包"""
    try:
        buf = _get_manager().export_all()
    except Exception as e:
        logger.error("导出录音失败: error=%s", str(e))
        return jsonify({"error": "导出失败"}), 500

    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="recordings_export.zip",
    )

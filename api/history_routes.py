"""历史记录路由 — GET /api/history"""

# 1. Standard library
import logging

# 2. Third-party
from flask import Blueprint, current_app, jsonify, send_file, abort

# 3. Local
from storage.history import HistoryManager

logger = logging.getLogger(__name__)

history_bp = Blueprint("history", __name__)


def _get_manager() -> HistoryManager:
    config = current_app.config["APP_CONFIG"]
    storage_cfg = config["storage"]
    return HistoryManager(
        history_dir=storage_cfg["history_dir"],
        max_records=storage_cfg["max_history"],
    )


@history_bp.route("/api/history", methods=["GET"])
def list_history() -> tuple:
    """获取最近 5 条历史记录列表"""
    try:
        records = _get_manager().list_records()
        return jsonify(records), 200
    except Exception as e:
        logger.error("获取历史记录失败: error=%s", str(e))
        return jsonify({"error": "获取历史记录失败"}), 500


@history_bp.route("/api/history/<int:record_id>/audio", methods=["GET"])
def get_history_audio(record_id: int) -> object:
    """下载指定历史记录的音频文件"""
    try:
        path = _get_manager().get_audio_path(record_id)
    except Exception as e:
        logger.error("获取历史音频失败: id=%d, error=%s", record_id, str(e))
        return jsonify({"error": "获取音频失败"}), 500

    if path is None:
        abort(404, description="音频文件不存在")
    return send_file(path, mimetype="audio/wav")


@history_bp.route("/api/history/export", methods=["GET"])
def export_history() -> object:
    """导出全部历史记录为 ZIP 包"""
    try:
        buf = _get_manager().export_all()
    except Exception as e:
        logger.error("导出历史记录失败: error=%s", str(e))
        return jsonify({"error": "导出失败"}), 500

    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="history_export.zip",
    )

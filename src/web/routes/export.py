"""
导出相关 API 路由
"""
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, send_file, jsonify

from ..services.session_manager import SessionManager
from ..middleware.error_handler import (
    api_response, ValidationError, SessionNotFoundError, ExportError
)
from ..middleware.validator import sanitize_filename

# 创建蓝图
export_bp = Blueprint('export', __name__)

# 获取服务实例
session_manager = SessionManager()

# 输出目录
OUTPUT_DIR = Path("output")


@export_bp.route('/export', methods=['POST'])
def export_messages():
    """
    导出消息为Markdown文件

    Request:
        {
            "session_id": "xxx",  // 必需
            "filename": "xxx",    // 可选，自定义文件名（不含扩展名）
            "custom_messages": [] // 可选，自定义消息列表（用于方案选择）
        }

    Returns:
        {
            "success": true,
            "data": {
                "filename": "对话标题_20240101_120000.md",
                "path": "output/对话标题_20240101_120000.md"
            }
        }
    """
    data = request.get_json()
    if not data:
        raise ValidationError("请求体不能为空")

    session_id = data.get('session_id')
    if not session_id:
        raise ValidationError("缺少 session_id")

    session = session_manager.get_session(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)

    # 获取消息：优先使用自定义消息，否则使用选中的消息
    custom_messages = data.get('custom_messages')
    if custom_messages:
        selected_messages = custom_messages
    else:
        selected_messages = session_manager.get_selected_messages(session_id)

    if not selected_messages:
        raise ValidationError("没有选中任何消息")

    # 生成Markdown内容
    markdown = _generate_markdown(
        title=session.title,
        url=session.url,
        messages=selected_messages
    )

    # 生成文件名
    custom_filename = data.get('filename')
    if custom_filename:
        safe_filename = sanitize_filename(custom_filename)
    else:
        safe_filename = _generate_filename(session.title)

    # 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 写入文件
    file_path = OUTPUT_DIR / f"{safe_filename}.md"
    file_path.write_text(markdown, encoding='utf-8')

    return api_response({
        "filename": f"{safe_filename}.md",
        "path": str(file_path)
    })


@export_bp.route('/export/<path:filename>', methods=['GET'])
def download_export(filename: str):
    """
    下载导出的文件

    Args:
        filename: 文件名

    Returns:
        文件内容
    """
    # 安全检查：防止路径遍历
    safe_filename = sanitize_filename(filename)
    if safe_filename != filename:
        raise ValidationError("无效的文件名")

    # 构建文件路径
    file_path = OUTPUT_DIR / safe_filename

    # 检查文件是否存在
    if not file_path.exists():
        raise ValidationError("文件不存在")

    # 检查是否在输出目录内（防止路径遍历）
    try:
        file_path.resolve().relative_to(OUTPUT_DIR.resolve())
    except ValueError:
        raise ValidationError("无效的文件路径")

    return send_file(
        file_path,
        as_attachment=True,
        download_name=safe_filename
    )


@export_bp.route('/export/preview', methods=['POST'])
def preview_export():
    """
    预览导出内容（不保存文件）

    Request:
        {
            "session_id": "xxx"
        }

    Returns:
        {
            "success": true,
            "data": {
                "markdown": "...",
                "message_count": 5
            }
        }
    """
    data = request.get_json()
    if not data:
        raise ValidationError("请求体不能为空")

    session_id = data.get('session_id')
    if not session_id:
        raise ValidationError("缺少 session_id")

    session = session_manager.get_session(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)

    # 获取选中的消息
    selected_messages = session_manager.get_selected_messages(session_id)
    if not selected_messages:
        raise ValidationError("没有选中任何消息")

    # 生成Markdown内容
    markdown = _generate_markdown(
        title=session.title,
        url=session.url,
        messages=selected_messages
    )

    return api_response({
        "markdown": markdown,
        "message_count": len(selected_messages)
    })


@export_bp.route('/export/list', methods=['GET'])
def list_exports():
    """
    列出已导出的文件

    Query params:
        limit: 最大返回数量（默认20）

    Returns:
        {
            "success": true,
            "data": {
                "files": [
                    {"name": "xxx.md", "size": 1234, "modified": "..."},
                    ...
                ]
            }
        }
    """
    if not OUTPUT_DIR.exists():
        return api_response({"files": []})

    try:
        limit = int(request.args.get('limit', 20))
        limit = min(limit, 100)  # 限制最大值
    except ValueError:
        limit = 20

    files = []
    for file_path in OUTPUT_DIR.glob("*.md"):
        stat = file_path.stat()
        files.append({
            "name": file_path.name,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })

    # 按修改时间排序（最新的在前）
    files.sort(key=lambda x: x['modified'], reverse=True)

    return api_response({
        "files": files[:limit]
    })


def _generate_filename(title: str) -> str:
    """生成文件名"""
    safe_title = sanitize_filename(title or "未命名对话")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{safe_title}_{timestamp}"


def _generate_markdown(title: str, url: str, messages: list) -> str:
    """
    生成Markdown内容

    Args:
        title: 对话标题
        url: 来源URL
        messages: 消息列表

    Returns:
        Markdown内容
    """
    parts = []

    # 标题
    parts.append(f"# {title}")
    parts.append("")

    # 元数据
    parts.append(f"> 来源: {url}")
    parts.append(f"> 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    parts.append("")
    parts.append("---")
    parts.append("")

    # 消息
    for msg in messages:
        if msg.get("isThinking"):
            role_label = "DeepSeek思考过程"
        elif msg.get("role") == "user":
            role_label = "用户"
        else:
            role_label = "DeepSeek回答"

        parts.append(f"## {role_label}")
        parts.append("")
        parts.append(msg.get("content", ""))
        parts.append("")
        parts.append("---")
        parts.append("")

    return "\n".join(parts)

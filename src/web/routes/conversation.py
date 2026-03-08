"""
对话相关 API 路由
会话管理和获取功能
"""
from flask import Blueprint, request, jsonify

from ..services.session_manager import SessionManager, SessionStatus
from ..services.fetch_service import FetchService, TaskStatus
from ..middleware.error_handler import (
    api_response, ValidationError, SessionNotFoundError, with_session
)
from ..middleware.validator import validate_url, validate_indices, IndexValidator

# 创建蓝图
conversation_bp = Blueprint('conversation', __name__)

# 获取服务实例
session_manager = SessionManager()
fetch_service = FetchService()


@conversation_bp.route('/session', methods=['POST'])
def create_session():
    """
    创建新会话

    Returns:
        {
            "success": true,
            "data": {"id": "xxx", "status": "idle", ...}
        }
    """
    session = session_manager.create_session()
    return api_response(session.to_dict())


@conversation_bp.route('/session/<session_id>', methods=['GET'])
def get_session(session_id: str):
    """
    获取会话状态

    Args:
        session_id: 会话ID

    Returns:
        {
            "success": true,
            "data": {"id": "xxx", "status": "ready", ...}
        }
    """
    session = session_manager.get_session(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)

    return api_response(session.to_dict())


@conversation_bp.route('/session/<session_id>', methods=['DELETE'])
def delete_session(session_id: str):
    """
    删除会话

    Args:
        session_id: 会话ID

    Returns:
        {
            "success": true,
            "message": "会话已删除"
        }
    """
    if not session_manager.delete_session(session_id):
        raise SessionNotFoundError(session_id)

    return api_response(message="会话已删除")


@conversation_bp.route('/fetch', methods=['POST'])
def start_fetch():
    """
    启动获取任务

    Request:
        {
            "url": "https://chat.deepseek.com/...",
            "session_id": "xxx"  // 可选，不提供则创建新会话
        }

    Returns:
        {
            "success": true,
            "data": {
                "task_id": "xxx",
                "session_id": "xxx"
            }
        }
    """
    data = request.get_json()
    if not data:
        raise ValidationError("请求体不能为空")

    # 验证URL
    url = validate_url(data.get('url', ''))

    # 获取或创建会话
    session_id = data.get('session_id')
    if session_id:
        session = session_manager.get_session(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
    else:
        session = session_manager.create_session()
        session_id = session.id

    # 启动获取任务
    task = fetch_service.start_fetch(session_id, url)

    return api_response({
        "task_id": task.id,
        "session_id": session_id
    })


@conversation_bp.route('/fetch/<task_id>/status', methods=['GET'])
def get_fetch_status(task_id: str):
    """
    获取任务状态

    Args:
        task_id: 任务ID

    Returns:
        {
            "success": true,
            "data": {
                "id": "xxx",
                "status": "completed",
                "progress": 100,
                ...
            }
        }
    """
    task = fetch_service.get_task(task_id)
    if task is None:
        raise ValidationError("任务不存在")

    response_data = task.to_dict()

    # 如果任务完成，包含会话数据
    if task.status == TaskStatus.COMPLETED:
        session = session_manager.get_session(task.session_id)
        if session:
            response_data["session"] = session.to_dict()

    return api_response(response_data)


@conversation_bp.route('/session/<session_id>/selection', methods=['PUT'])
def update_selection(session_id: str):
    """
    更新消息选择

    Args:
        session_id: 会话ID

    Request:
        {
            "indices": [0, 1, 2]  // 选中的消息索引列表
        }
        或
        {
            "toggle": 0  // 切换单个索引的选择状态
        }

    Returns:
        {
            "success": true,
            "data": {"selected_count": 3}
        }
    """
    session = session_manager.get_session(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)

    data = request.get_json()
    if not data:
        raise ValidationError("请求体不能为空")

    if 'toggle' in data:
        # 切换单个索引
            index = data['toggle']
            index = IndexValidator.validate(index, len(session.messages))
            session = session_manager.toggle_selection(session_id, index)
    elif 'indices' in data:
        # 设置选中列表
        indices = validate_indices(data['indices'], len(session.messages))
        session = session_manager.set_selection(session_id, indices)
    elif 'clear' in data and data['clear']:
        # 清除选择
        session = session_manager.clear_selection(session_id)
    else:
        raise ValidationError("无效的请求参数")

    return api_response({
        "selected_count": len(session.selected_indices) if session else 0
    })


@conversation_bp.route('/session/<session_id>/messages', methods=['GET'])
def get_messages(session_id: str):
    """
    获取会话消息

    Args:
        session_id: 会话ID

    Query params:
        selected_only: 是否只返回选中的消息（默认false）

    Returns:
        {
            "success": true,
            "data": {
                "title": "...",
                "messages": [...]
            }
        }
    """
    session = session_manager.get_session(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)

    selected_only = request.args.get('selected_only', 'false').lower() == 'true'

    if selected_only:
        messages = session_manager.get_selected_messages(session_id)
    else:
        messages = session.messages

    return api_response({
        "title": session.title,
        "url": session.url,
        "messages": messages,
        "total_count": len(session.messages),
        "selected_count": len(session.selected_indices)
    })


# 注意： validate_index 已移至 middleware/validator.py 的 IndexValidator.validate
# 这里保留此函数是为了向后兼容，实际应使用 validate_indices 从 validator 模块导入

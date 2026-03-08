"""
统一错误处理中间件
"""
from functools import wraps
from typing import Callable, Any


def _get_flask():
    """延迟导入Flask"""
    try:
        from flask import jsonify, current_app
        return jsonify, current_app
    except ImportError:
        raise ImportError(
            "Flask 未安装。请运行: pip install flask"
        )


class AppError(Exception):
    """应用错误基类"""

    def __init__(self, message: str, status_code: int = 400, error_code: str = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "UNKNOWN_ERROR"

    def to_dict(self):
        """转换为字典"""
        return {
            "success": False,
            "error": {
                "code": self.error_code,
                "message": self.message
            }
        }


class ValidationError(AppError):
    """验证错误"""

    def __init__(self, message: str):
        super().__init__(message, status_code=400, error_code="VALIDATION_ERROR")


class NotFoundError(AppError):
    """资源未找到错误"""

    def __init__(self, message: str = "资源未找到"):
        super().__init__(message, status_code=404, error_code="NOT_FOUND")


class SessionNotFoundError(NotFoundError):
    """会话未找到错误"""

    def __init__(self, session_id: str = None):
        message = f"会话 {session_id} 未找到" if session_id else "会话未找到"
        super().__init__(message)
        self.error_code = "SESSION_NOT_FOUND"


class FetchError(AppError):
    """获取错误"""

    def __init__(self, message: str):
        super().__init__(message, status_code=500, error_code="FETCH_ERROR")


class ExportError(AppError):
    """导出错误"""

    def __init__(self, message: str):
        super().__init__(message, status_code=500, error_code="EXPORT_ERROR")


class RequestTooLargeError(AppError):
    """请求体过大错误"""

    def __init__(self, max_size: int):
        message = f"请求体过大，最大允许 {max_size} 字节"
        super().__init__(message, status_code=413, error_code="REQUEST_TOO_LARGE")


def init_error_handlers(app):
    """
    初始化错误处理器

    Args:
        app: Flask应用实例
    """
    jsonify, current_app = _get_flask()

    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        """处理应用错误"""
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response

    @app.errorhandler(404)
    def handle_404(error):
        """处理404错误"""
        return jsonify({
            "success": False,
            "error": {
                "code": "NOT_FOUND",
                "message": "请求的资源不存在"
            }
        }), 404

    @app.errorhandler(405)
    def handle_405(error):
        """处理405错误"""
        return jsonify({
            "success": False,
            "error": {
                "code": "METHOD_NOT_ALLOWED",
                "message": "不支持的HTTP方法"
            }
        }), 405

    @app.errorhandler(413)
    def handle_413(error):
        """处理413错误（请求体过大）"""
        return jsonify({
            "success": False,
            "error": {
                "code": "REQUEST_TOO_LARGE",
                "message": "请求体过大"
            }
        }), 413

    @app.errorhandler(500)
    def handle_500(error):
        """处理500错误"""
        current_app.logger.error(f"Internal server error: {error}")
        return jsonify({
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误"
            }
        }), 500

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """处理未预期的错误"""
        current_app.logger.exception(f"Unexpected error: {error}")
        return jsonify({
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误"
            }
        }), 500


def api_response(data: Any = None, message: str = "success"):
    """
    生成标准API响应

    Args:
        data: 响应数据
        message: 响应消息

    Returns:
        Flask响应
    """
    jsonify, _ = _get_flask()
    return jsonify({
        "success": True,
        "message": message,
        "data": data
    })


def with_session(f: Callable) -> Callable:
    """
    装饰器：自动获取会话

    用法:
        @with_session
        def my_route(session, **kwargs):
            # session 已自动注入
            pass
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from ..services.session_manager import SessionManager

        session_id = kwargs.get('session_id')
        if not session_id:
            raise ValidationError("缺少会话ID")

        session_manager = SessionManager()
        session = session_manager.get_session(session_id)

        if session is None:
            raise SessionNotFoundError(session_id)

        # 注入session到kwargs
        kwargs['session'] = session
        return f(*args, **kwargs)

    return decorated

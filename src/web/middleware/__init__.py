"""
中间件层
"""
# 错误类（不需要Flask）
from .error_handler import (
    AppError, ValidationError, NotFoundError,
    SessionNotFoundError, FetchError, ExportError,
    RequestTooLargeError, with_session
)

# 验证器（不需要Flask）
from .validator import (
    URLValidator, IndexValidator, RequestValidator, FilenameValidator,
    validate_url, validate_index, validate_indices, sanitize_filename,
    MAX_CONTENT_LENGTH
)

# Flask相关函数（延迟导入）
def init_error_handlers(app):
    """初始化错误处理器"""
    from .error_handler import init_error_handlers as _init
    return _init(app)


def api_response(data=None, message="success"):
    """生成标准API响应"""
    from .error_handler import api_response as _api_response
    return _api_response(data, message)


__all__ = [
    # 错误处理
    'AppError', 'ValidationError', 'NotFoundError',
    'SessionNotFoundError', 'FetchError', 'ExportError',
    'RequestTooLargeError', 'init_error_handlers',
    'api_response', 'with_session',
    # 验证器
    'URLValidator', 'IndexValidator', 'RequestValidator', 'FilenameValidator',
    'validate_url', 'validate_index', 'validate_indices', 'sanitize_filename',
    'MAX_CONTENT_LENGTH'
]

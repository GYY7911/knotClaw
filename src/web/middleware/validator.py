"""
请求验证中间件
URL验证、索引验证、请求大小限制
"""
import re
from typing import Optional, List
from urllib.parse import urlparse

from .error_handler import ValidationError, RequestTooLargeError


# 支持的URL模式
SUPPORTED_URL_PATTERNS = [
    # DeepSeek 分享链接
    r'^https?://chat\.deepseek\.com/share/.*',
    r'^https?://.*\.deepseek\.com/share/.*',
    # Gemini 分享链接
    r'^https?://gemini\.google\.com/share/.*',
    r'^https?://bard\.google\.com/share/.*',
]

# 平台名称映射（用于错误提示）
SUPPORTED_PLATFORMS = "DeepSeek、Gemini"

# 请求体大小限制（10MB）
MAX_CONTENT_LENGTH = 10 * 1024 * 1024


class URLValidator:
    """URL验证器"""

    @staticmethod
    def validate(url: str) -> str:
        """
        验证URL格式和支持性

        Args:
            url: 待验证的URL

        Returns:
            验证通过的URL

        Raises:
            ValidationError: URL无效或不支持
        """
        if not url:
            raise ValidationError("URL不能为空")

        url = url.strip()

        # 检查URL格式
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValidationError("URL格式无效")
        except Exception:
            raise ValidationError("URL格式无效")

        # 检查是否为支持的URL
        if not URLValidator.is_supported(url):
            raise ValidationError(f"不支持的URL类型，目前支持: {SUPPORTED_PLATFORMS}")

        return url

    @staticmethod
    def is_supported(url: str) -> bool:
        """
        检查URL是否支持

        Args:
            url: 待检查的URL

        Returns:
            是否支持
        """
        for pattern in SUPPORTED_URL_PATTERNS:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        return False


class IndexValidator:
    """索引验证器"""

    @staticmethod
    def validate(index: int, max_value: int) -> int:
        """
        验证索引范围

        Args:
            index: 待验证的索引
            max_value: 最大允许值（不含）

        Returns:
            验证通过的索引

        Raises:
            ValidationError: 索引超出范围
        """
        if not isinstance(index, int):
            try:
                index = int(index)
            except (ValueError, TypeError):
                raise ValidationError("索引必须是整数")

        if index < 0:
            raise ValidationError("索引不能为负数")

        if max_value > 0 and index >= max_value:
            raise ValidationError(f"索引 {index} 超出范围 [0, {max_value})")

        return index

    @staticmethod
    def validate_list(indices: List[int], max_value: int) -> List[int]:
        """
        验证索引列表

        Args:
            indices: 索引列表
            max_value: 最大允许值（不含）

        Returns:
            验证通过的索引列表

        Raises:
            ValidationError: 索引无效
        """
        if not isinstance(indices, list):
            raise ValidationError("索引列表格式无效")

        validated = []
        for idx in indices:
            validated.append(IndexValidator.validate(idx, max_value))

        return validated


class RequestValidator:
    """请求验证器"""

    @staticmethod
    def validate_content_length(content_length: Optional[int]) -> None:
        """
        验证请求体大小

        Args:
            content_length: 请求体长度

        Raises:
            RequestTooLargeError: 请求体过大
        """
        if content_length is None:
            return

        if content_length > MAX_CONTENT_LENGTH:
            raise RequestTooLargeError(MAX_CONTENT_LENGTH)

    @staticmethod
    def validate_json_request(request) -> dict:
        """
        验证JSON请求

        Args:
            request: Flask请求对象

        Returns:
            解析后的JSON数据

        Raises:
            ValidationError: JSON格式无效
        """
        # 检查Content-Type
        if not request.is_json:
            raise ValidationError("请求必须是JSON格式")

        # 检查请求体大小
        RequestValidator.validate_content_length(request.content_length)

        # 解析JSON
        try:
            data = request.get_json()
            if data is None:
                raise ValidationError("请求体不能为空")
            return data
        except Exception as e:
            raise ValidationError(f"JSON解析失败: {str(e)}")


class FilenameValidator:
    """文件名验证器"""

    # 不允许的字符
    FORBIDDEN_CHARS = r'[<>:"/\\|?*\x00-\x1f]'

    # 路径遍历模式
    PATH_TRAVERSAL_PATTERNS = [
        r'\.\.',           # ..
        r'[/\\]',          # 路径分隔符
        r'^\.',            # 以.开头
        r'\.$',            # 以.结尾
    ]

    @staticmethod
    def sanitize(filename: str) -> str:
        """
        清理文件名，防止路径遍历攻击

        Args:
            filename: 原始文件名

        Returns:
            安全的文件名
        """
        if not filename:
            return "unnamed"

        # 移除不允许的字符
        safe = re.sub(FilenameValidator.FORBIDDEN_CHARS, '_', filename)

        # 检查路径遍历
        for pattern in FilenameValidator.PATH_TRAVERSAL_PATTERNS:
            safe = re.sub(pattern, '', safe)

        # 限制长度
        if len(safe) > 200:
            safe = safe[:200]

        # 确保非空
        if not safe:
            safe = "unnamed"

        return safe

    @staticmethod
    def validate(filename: str) -> str:
        """
        验证文件名安全性

        Args:
            filename: 待验证的文件名

        Returns:
            验证通过的文件名

        Raises:
            ValidationError: 文件名不安全
        """
        if not filename:
            raise ValidationError("文件名不能为空")

        # 检查路径遍历
        if '..' in filename:
            raise ValidationError("文件名包含非法字符")

        if '/' in filename or '\\' in filename:
            raise ValidationError("文件名不能包含路径分隔符")

        # 检查不允许的字符
        if re.search(FilenameValidator.FORBIDDEN_CHARS, filename):
            raise ValidationError("文件名包含非法字符")

        return filename


def validate_url(url: str) -> str:
    """URL验证快捷函数"""
    return URLValidator.validate(url)


def validate_index(index: int, max_value: int) -> int:
    """索引验证快捷函数"""
    return IndexValidator.validate(index, max_value)


def validate_indices(indices: List[int], max_value: int) -> List[int]:
    """索引列表验证快捷函数"""
    return IndexValidator.validate_list(indices, max_value)


def sanitize_filename(filename: str) -> str:
    """文件名清理快捷函数"""
    return FilenameValidator.sanitize(filename)

"""
平台识别工具
从 URL 或对话源识别平台名称
"""
from typing import Tuple

# 平台名称映射（内部标识 -> 显示名称）
PLATFORM_DISPLAY_NAMES = {
    "deepseek": "DeepSeek",
    "gemini": "Gemini",
}


def _get_platform_info(url: str) -> Tuple[str, str]:
    """
    从 URL 获取平台信息

    Args:
        url: 对话分享链接

    Returns:
        (platform_key, display_name) 元组
        - platform_key: 平台内部标识（小写，如 "deepseek"）
        - display_name: 平台显示名称（如 "DeepSeek"）
    """
    # 延迟导入避免循环依赖
    from ..fetcher.fetcher_factory import FetcherFactory

    for fetcher_cls in FetcherFactory._registered_fetchers:
        if fetcher_cls.can_handle(url):
            platform_key = fetcher_cls.__name__.replace("Fetcher", "").lower()
            display_name = PLATFORM_DISPLAY_NAMES.get(platform_key, platform_key.title())
            return platform_key, display_name
    return "unknown", "Unknown"


def get_platform_from_url(url: str) -> str:
    """
    从 URL 识别平台显示名称

    Args:
        url: 对话分享链接

    Returns:
        平台显示名称（如 "DeepSeek", "Gemini"）
    """
    return _get_platform_info(url)[1]


def get_platform_from_source(source_url: str) -> str:
    """
    从来源 URL 提取平台名称（别名，语义更清晰）

    Args:
        source_url: 对话来源 URL

    Returns:
        平台显示名称
    """
    return get_platform_from_url(source_url)


def get_platform_key(url: str) -> str:
    """
    从 URL 获取平台内部标识（小写）

    Args:
        url: 对话分享链接

    Returns:
        平台内部标识（如 "deepseek", "gemini"）
    """
    return _get_platform_info(url)[0]

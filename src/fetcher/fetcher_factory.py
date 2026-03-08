"""
抓取器工厂
根据URL自动选择合适的抓取器
"""
from typing import Optional, List, Type

from .base_fetcher import BaseFetcher
from .deepseek_fetcher import DeepSeekFetcher
from .gemini_fetcher import GeminiFetcher


class FetcherFactory:
    """
    抓取器工厂类
    根据URL自动选择合适的抓取器
    """

    # 注册的抓取器列表
    _registered_fetchers: List[Type[BaseFetcher]] = [
        DeepSeekFetcher,
        GeminiFetcher,
    ]
    
    @classmethod
    def register(cls, fetcher_class: Type[BaseFetcher]) -> None:
        """
        注册新的抓取器
        
        Args:
            fetcher_class: 抓取器类
        """
        if fetcher_class not in cls._registered_fetchers:
            cls._registered_fetchers.append(fetcher_class)
    
    @classmethod
    def get_fetcher(cls, url: str, page_size: int = 10) -> Optional[BaseFetcher]:
        """
        根据URL获取合适的抓取器
        
        Args:
            url: 对话分享链接
            page_size: 分页大小
            
        Returns:
            抓取器实例，如果没有匹配的返回None
        """
        for fetcher_class in cls._registered_fetchers:
            if fetcher_class.can_handle(url):
                return fetcher_class(page_size=page_size)
        return None
    
    @classmethod
    def get_supported_domains(cls) -> List[str]:
        """获取所有支持的域名列表"""
        domains = []
        for fetcher_class in cls._registered_fetchers:
            domains.extend(fetcher_class.SUPPORTED_DOMAINS)
        return list(set(domains))
    
    @classmethod
    def is_supported(cls, url: str) -> bool:
        """
        检查URL是否支持
        
        Args:
            url: 对话分享链接
            
        Returns:
            是否支持该URL
        """
        return cls.get_fetcher(url) is not None
    
    @classmethod
    def list_fetchers(cls) -> List[str]:
        """列出所有注册的抓取器名称"""
        return [fetcher.__name__ for fetcher in cls._registered_fetchers]
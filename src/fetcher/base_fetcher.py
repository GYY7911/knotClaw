"""
基础抓取器抽象类
定义抓取器接口和通用功能
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Generator, Tuple
from dataclasses import dataclass
import hashlib
from datetime import datetime

from ..models import Conversation, Message, MessageRole


@dataclass
class FetchResult:
    """抓取结果"""
    success: bool
    conversation: Optional[Conversation] = None
    error_message: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


class BaseFetcher(ABC):
    """
    抓取器基类
    定义抓取对话数据的接口
    """
    
    # 支持的域名列表
    SUPPORTED_DOMAINS: List[str] = []
    
    def __init__(self, page_size: int = 10):
        """
        初始化抓取器
        
        Args:
            page_size: 分页大小，控制每次加载的消息数量
        """
        self.page_size = page_size
        self._raw_messages: List[Dict[str, Any]] = []
        self._conversation_meta: Dict[str, Any] = {}
    
    @classmethod
    @abstractmethod
    def can_handle(cls, url: str) -> bool:
        """
        检查是否能处理该URL
        
        Args:
            url: 对话分享链接
            
        Returns:
            是否支持该链接
        """
        pass
    
    @abstractmethod
    def fetch_page(self, url: str, page: int = 0) -> FetchResult:
        """
        抓取指定页的消息
        
        Args:
            url: 对话分享链接
            page: 页码（从0开始）
            
        Returns:
            抓取结果
        """
        pass
    
    @abstractmethod
    def fetch_all_metadata(self, url: str) -> FetchResult:
        """
        抓取所有消息的元数据（不含完整内容）
        用于构建导航索引
        
        Args:
            url: 对话分享链接
            
        Returns:
            包含元数据的抓取结果
        """
        pass
    
    @abstractmethod
    def load_message_content(self, message_id: str) -> Optional[str]:
        """
        加载指定消息的完整内容
        
        Args:
            message_id: 消息ID
            
        Returns:
            消息内容
        """
        pass
    
    def iter_messages(self, url: str, load_content: bool = False) -> Generator[Message, None, None]:
        """
        迭代器方式遍历消息（增量加载）
        
        Args:
            url: 对话分享链接
            load_content: 是否加载完整内容
            
        Yields:
            消息对象
        """
        page = 0
        while True:
            result = self.fetch_page(url, page)
            if not result.success or not result.conversation:
                break
            
            messages = result.conversation.messages
            if not messages:
                break
            
            for msg in messages:
                if load_content and not msg.is_loaded:
                    content = self.load_message_content(msg.id)
                    if content:
                        msg.load_content(content)
                yield msg
            
            page += 1
            
            # 检查是否还有更多消息
            if len(messages) < self.page_size:
                break
    
    def get_total_messages(self, url: str) -> int:
        """
        获取消息总数
        
        Args:
            url: 对话分享链接
            
        Returns:
            消息总数
        """
        result = self.fetch_all_metadata(url)
        if result.success and result.conversation:
            return result.conversation.total_messages
        return 0
    
    def _generate_message_id(self, role: str, content: str, index: int) -> str:
        """生成消息ID"""
        hash_input = f"{role}_{index}_{content[:50]}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]
    
    def _create_message_from_raw(self, raw_data: Dict[str, Any], index: int, load_content: bool = False) -> Message:
        """
        从原始数据创建消息对象
        
        Args:
            raw_data: 原始消息数据
            index: 消息索引
            load_content: 是否加载完整内容
        """
        role_str = raw_data.get("role", "user").lower()
        role = MessageRole.USER if role_str == "user" else (
            MessageRole.ASSISTANT if role_str == "assistant" else MessageRole.SYSTEM
        )
        
        content = raw_data.get("content", "")
        summary = raw_data.get("summary", "")
        
        msg = Message(
            id=raw_data.get("id") or self._generate_message_id(role_str, content, index),
            role=role,
            content=content if load_content else None,
            summary=summary or (content[:100] + "..." if len(content) > 100 else content),
            timestamp=self._parse_timestamp(raw_data.get("timestamp")),
            metadata=raw_data.get("metadata", {}),
            _raw_data_ref=raw_data if not load_content else None
        )
        
        return msg
    
    def _parse_timestamp(self, timestamp: Any) -> Optional[datetime]:
        """解析时间戳"""
        if not timestamp:
            return None
        
        if isinstance(timestamp, datetime):
            return timestamp
        
        if isinstance(timestamp, str):
            try:
                return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                pass
        
        if isinstance(timestamp, (int, float)):
            try:
                return datetime.fromtimestamp(timestamp)
            except (ValueError, OSError):
                pass
        
        return None
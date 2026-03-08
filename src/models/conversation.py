"""
对话数据模型
定义对话和消息的数据结构，支持增量加载和元数据压缩
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
import hashlib
import json


class MessageRole(Enum):
    """消息角色枚举"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """
    消息数据结构
    支持懒加载：content仅在需要时加载
    """
    id: str
    role: MessageRole
    # 内容可以是实际内容或None（未加载状态）
    content: Optional[str] = None
    # 内容摘要，用于导航和预览
    summary: Optional[str] = None
    # 时间戳
    timestamp: Optional[datetime] = None
    # Token数量估算
    token_count: int = 0
    # 是否已加载完整内容
    is_loaded: bool = False
    # 原始数据引用（用于懒加载）
    _raw_data_ref: Optional[Dict[str, Any]] = field(default=None, repr=False)
    # 额外元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if self.content and not self.summary:
            self.summary = self._generate_summary()
        if self.content and not self.is_loaded:
            self.is_loaded = True
        if self.content and self.token_count == 0:
            self.token_count = self._estimate_tokens()
    
    def _generate_summary(self, max_length: int = 100) -> str:
        """生成消息摘要"""
        if not self.content:
            return ""
        content = self.content.strip()
        if len(content) <= max_length:
            return content
        return content[:max_length - 3] + "..."
    
    def _estimate_tokens(self) -> int:
        """
        估算Token数量
        使用简单的启发式方法：中文约1.5字符/token，英文约4字符/token
        """
        if not self.content:
            return 0
        # 简化估算：平均3字符/token
        return len(self.content) // 3 + 1
    
    def load_content(self, content: str) -> None:
        """加载完整内容"""
        self.content = content
        self.summary = self._generate_summary()
        self.token_count = self._estimate_tokens()
        self.is_loaded = True
    
    def unload_content(self) -> None:
        """卸载内容以释放内存（保留摘要和元数据）"""
        if self.summary:
            self.content = None
            self.is_loaded = False
    
    def to_dict(self, include_content: bool = True) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "id": self.id,
            "role": self.role.value,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "token_count": self.token_count,
            "is_loaded": self.is_loaded,
            "metadata": self.metadata
        }
        if include_content and self.content:
            result["content"] = self.content
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """从字典创建消息"""
        timestamp = cls._safe_parse_timestamp(data.get("timestamp"))
        return cls(
            id=data["id"],
            role=MessageRole(data["role"]),
            content=data.get("content"),
            summary=data.get("summary"),
            timestamp=timestamp,
            token_count=data.get("token_count", 0),
            is_loaded=data.get("is_loaded", False),
            metadata=data.get("metadata", {})
        )

    @staticmethod
    def _safe_parse_timestamp(timestamp: Optional[Any]) -> Optional[datetime]:
        """安全解析时间戳"""
        if not timestamp:
            return None

        if isinstance(timestamp, datetime):
            return timestamp
        if isinstance(timestamp, str):
            if timestamp.endswith("Z"):
                try:
                    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
            else:
                try:
                    return datetime.fromisoformat(timestamp)
                except ValueError:
                    pass
        if isinstance(timestamp, (int, float)):
            try:
                return datetime.fromtimestamp(timestamp)
            except (ValueError, OSError):
                pass
        return None


@dataclass
class Conversation:
    """
    对话数据结构
    支持分页加载和增量处理
    """
    # 对话唯一标识
    id: str
    # 对话标题
    title: str
    # 来源URL
    source_url: str
    # 消息列表（可能未完全加载）
    messages: List[Message] = field(default_factory=list)
    # 总消息数（用于分页）
    total_messages: int = 0
    # 已加载的消息范围
    loaded_range: tuple = (0, 0)
    # 创建时间
    created_at: Optional[datetime] = None
    # 更新时间
    updated_at: Optional[datetime] = None
    # 对话元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    # 用户选择的方案索引列表
    selected_indices: List[int] = field(default_factory=list)
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.created_at:
            self.created_at = datetime.now()
        if not self.updated_at:
            self.updated_at = datetime.now()
        if not self.id:
            # 基于URL生成唯一ID
            self.id = hashlib.md5(self.source_url.encode()).hexdigest()[:12]
    
    @property
    def total_tokens(self) -> int:
        """计算已加载消息的总Token数"""
        return sum(msg.token_count for msg in self.messages if msg.is_loaded)
    
    @property
    def loaded_message_count(self) -> int:
        """已加载的消息数量"""
        return len([m for m in self.messages if m.is_loaded])
    
    def get_message_summaries(self) -> List[Dict[str, Any]]:
        """
        获取所有消息的摘要列表
        用于导航，不包含完整内容
        """
        return [
            {
                "index": i,
                "id": msg.id,
                "role": msg.role.value,
                "summary": msg.summary,
                "token_count": msg.token_count,
                "is_loaded": msg.is_loaded
            }
            for i, msg in enumerate(self.messages)
        ]
    
    def get_message_page(self, start: int, end: int, load_content: bool = False) -> List[Message]:
        """
        获取指定范围的消息（分页）
        
        Args:
            start: 起始索引
            end: 结束索引（不包含）
            load_content: 是否加载完整内容
        """
        page = self.messages[start:end]
        if load_content:
            for msg in page:
                if not msg.is_loaded and msg._raw_data_ref:
                    # 从原始数据加载内容
                    msg.load_content(msg._raw_data_ref.get("content", ""))
        return page
    
    def add_message(self, message: Message) -> None:
        """添加消息"""
        self.messages.append(message)
        self.total_messages = len(self.messages)
        self.updated_at = datetime.now()
    
    def mark_selected(self, indices: List[int]) -> None:
        """标记选中的消息索引"""
        self.selected_indices = indices
        self.updated_at = datetime.now()
    
    def get_selected_messages(self) -> List[Message]:
        """获取选中的消息"""
        return [self.messages[i] for i in self.selected_indices if i < len(self.messages)]
    
    def unload_all_content(self) -> None:
        """卸载所有消息内容以释放内存"""
        for msg in self.messages:
            msg.unload_content()
        self.loaded_range = (0, 0)
    
    def to_dict(self, include_messages: bool = True, include_content: bool = False) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "id": self.id,
            "title": self.title,
            "source_url": self.source_url,
            "total_messages": self.total_messages,
            "loaded_range": self.loaded_range,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.metadata,
            "selected_indices": self.selected_indices
        }
        if include_messages:
            result["messages"] = [msg.to_dict(include_content) for msg in self.messages]
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Conversation":
        """从字典创建对话"""
        conv = cls(
            id=data["id"],
            title=data["title"],
            source_url=data["source_url"],
            total_messages=data.get("total_messages", 0),
            loaded_range=tuple(data.get("loaded_range", (0, 0))),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
            metadata=data.get("metadata", {}),
            selected_indices=data.get("selected_indices", [])
        )
        if "messages" in data:
            conv.messages = [Message.from_dict(msg) for msg in data["messages"]]
        return conv
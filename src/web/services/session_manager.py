"""
会话管理器
线程安全的会话存储，替代全局变量
"""
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Set, Optional, Any, List
from enum import Enum


class SessionStatus(Enum):
    """会话状态枚举"""
    IDLE = "idle"
    FETCHING = "fetching"
    READY = "ready"
    ERROR = "error"


@dataclass
class Session:
    """会话数据结构"""
    id: str
    status: SessionStatus = SessionStatus.IDLE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # 对话数据
    title: str = ""
    url: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)

    # 用户选择
    selected_indices: Set[int] = field(default_factory=set)

    # 错误信息
    error_message: str = ""

    # 后台任务
    task_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON响应）"""
        return {
            "id": self.id,
            "status": self.status.value,
            "title": self.title,
            "url": self.url,
            "messages": self.messages,
            "selected_indices": list(self.selected_indices),
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class SessionManager:
    """
    线程安全的会话管理器（单例模式）

    使用 RLock 实现并发安全：
    - 所有操作都受锁保护
    - 支持同一线程的重复获取（可重入）

    用法:
        manager = SessionManager()  # 获取单例实例
        session = manager.create_session()
    """

    # 类级别的单例状态
    _instance: Optional["SessionManager"] = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls) -> "SessionManager":
        """线程安全的单例模式"""
        # 双重检查锁定：先检查是否已初始化（无锁快速路径）
        if cls._instance is not None:
            return cls._instance

        # 获取锁后再次检查
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                cls._instance = instance
            return cls._instance

    def __init__(self):
        """初始化会话管理器（仅执行一次）"""
        # 使用类级别标志避免重复初始化
        if SessionManager._initialized:
            return

        with SessionManager._lock:
            if SessionManager._initialized:
                return

            self._sessions: Dict[str, Session] = {}
            self._data_lock = threading.RLock()
            SessionManager._initialized = True

    def create_session(self) -> Session:
        """
        创建新会话

        Returns:
            新创建的会话对象
        """
        session_id = str(uuid.uuid4())[:8]
        session = Session(id=session_id)

        with self._data_lock:
            self._sessions[session_id] = session

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        获取会话

        Args:
            session_id: 会话ID

        Returns:
            会话对象，不存在返回None
        """
        with self._data_lock:
            return self._sessions.get(session_id)

    def update_session(self, session_id: str, **kwargs) -> Optional[Session]:
        """
        更新会话

        Args:
            session_id: 会话ID
            **kwargs: 要更新的字段

        Returns:
            更新后的会话对象，不存在返回None
        """
        with self._data_lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None

            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)

            session.updated_at = datetime.now()
            return session

    def delete_session(self, session_id: str) -> bool:
        """
        删除会话

        Args:
            session_id: 会话ID

        Returns:
            是否删除成功
        """
        with self._data_lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def set_session_data(
        self,
        session_id: str,
        title: str,
        url: str,
        messages: List[Dict[str, Any]]
    ) -> Optional[Session]:
        """
        设置会话数据（获取完成后调用）

        Args:
            session_id: 会话ID
            title: 对话标题
            url: 来源URL
            messages: 消息列表

        Returns:
            更新后的会话对象
        """
        return self.update_session(
            session_id,
            status=SessionStatus.READY,
            title=title,
            url=url,
            messages=messages
        )

    def set_session_error(self, session_id: str, error_message: str) -> Optional[Session]:
        """
        设置会话错误状态

        Args:
            session_id: 会话ID
            error_message: 错误信息

        Returns:
            更新后的会话对象
        """
        return self.update_session(
            session_id,
            status=SessionStatus.ERROR,
            error_message=error_message
        )

    def toggle_selection(self, session_id: str, index: int) -> Optional[Session]:
        """
        切换消息选择状态

        Args:
            session_id: 会话ID
            index: 消息索引

        Returns:
            更新后的会话对象
        """
        with self._data_lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None

            if index in session.selected_indices:
                session.selected_indices.discard(index)
            else:
                session.selected_indices.add(index)

            session.updated_at = datetime.now()
            return session

    def set_selection(self, session_id: str, indices: List[int]) -> Optional[Session]:
        """
        设置选中的消息索引

        Args:
            session_id: 会话ID
            indices: 消息索引列表

        Returns:
            更新后的会话对象
        """
        return self.update_session(
            session_id,
            selected_indices=set(indices)
        )

    def clear_selection(self, session_id: str) -> Optional[Session]:
        """
        清除选择

        Args:
            session_id: 会话ID

        Returns:
            更新后的会话对象
        """
        return self.update_session(
            session_id,
            selected_indices=set()
        )

    def get_selected_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """
        获取选中的消息

        Args:
            session_id: 会话ID

        Returns:
            选中的消息列表
        """
        with self._data_lock:
            session = self._sessions.get(session_id)
            if session is None:
                return []

            return [
                session.messages[i]
                for i in sorted(session.selected_indices)
                if i < len(session.messages)
            ]

    def cleanup_expired_sessions(self, max_age_hours: int = 24) -> int:
        """
        清理过期会话

        Args:
            max_age_hours: 最大存活时间（小时）

        Returns:
            清理的会话数量
        """
        cutoff = datetime.now()
        expired_ids = []

        with self._data_lock:
            for session_id, session in self._sessions.items():
                age_hours = (cutoff - session.updated_at).total_seconds() / 3600
                if age_hours > max_age_hours:
                    expired_ids.append(session_id)

            for session_id in expired_ids:
                del self._sessions[session_id]

        return len(expired_ids)

    def session_count(self) -> int:
        """获取会话数量"""
        with self._data_lock:
            return len(self._sessions)

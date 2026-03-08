"""
获取服务
后台任务管理，与 FetcherFactory 集成
"""
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Any, Callable

from ..services.session_manager import SessionManager, SessionStatus
from ..middleware.error_handler import FetchError

# 配置日志
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class FetchTask:
    """获取任务数据结构"""
    id: str
    session_id: str
    url: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""
    progress: int = 0  # 0-100

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "url": self.url,
            "status": self.status.value,
            "progress": self.progress,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class FetchService:
    """
    获取服务（单例模式）

    管理后台获取任务，与 FetcherFactory 集成

    用法:
        service = FetchService()  # 获取单例实例
        task = service.start_fetch(session_id, url)
    """

    # 类级别的单例状态
    _instance: Optional["FetchService"] = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls) -> "FetchService":
        """线程安全的单例模式"""
        if cls._instance is not None:
            return cls._instance

        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                cls._instance = instance
            return cls._instance

    def __init__(self):
        """初始化获取服务（仅执行一次）"""
        if FetchService._initialized:
            return

        with FetchService._lock:
            if FetchService._initialized:
                return

            self._tasks: Dict[str, FetchTask] = {}
            self._tasks_lock = threading.Lock()
            self._session_manager = SessionManager()
            FetchService._initialized = True

    def start_fetch(self, session_id: str, url: str) -> FetchTask:
        """
        启动获取任务

        Args:
            session_id: 会话ID
            url: 分享链接

        Returns:
            任务对象
        """
        # 创建任务
        task_id = str(uuid.uuid4())[:8]
        task = FetchTask(
            id=task_id,
            session_id=session_id,
            url=url
        )

        with self._tasks_lock:
            self._tasks[task_id] = task

        # 更新会话状态
        self._session_manager.update_session(
            session_id,
            status=SessionStatus.FETCHING,
            task_id=task_id
        )

        # 启动后台线程
        thread = threading.Thread(
            target=self._fetch_task,
            args=(task_id,),
            daemon=True
        )
        thread.start()

        return task

    def get_task(self, task_id: str) -> Optional[FetchTask]:
        """
        获取任务

        Args:
            task_id: 任务ID

        Returns:
            任务对象，不存在返回None
        """
        with self._tasks_lock:
            return self._tasks.get(task_id)

    def get_task_by_session(self, session_id: str) -> Optional[FetchTask]:
        """
        根据会话ID获取任务

        Args:
            session_id: 会话ID

        Returns:
            任务对象，不存在返回None
        """
        with self._tasks_lock:
            for task in self._tasks.values():
                if task.session_id == session_id:
                    return task
            return None

    def _fetch_task(self, task_id: str):
        """
        执行获取任务（后台线程）

        Args:
            task_id: 任务ID
        """
        import logging
        import time
        logger = logging.getLogger(__name__)

        task = self.get_task(task_id)
        if task is None:
            return

        try:
            # 更新任务状态
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            task.progress = 5
            logger.info(f"[Task {task_id}] 开始获取: {task.url}")

            # 导入 FetcherFactory
            from ...fetcher import FetcherFactory

            # 获取合适的 fetcher
            task.progress = 10
            fetcher = FetcherFactory.get_fetcher(task.url)
            if fetcher is None:
                raise FetchError("不支持的URL类型")

            task.progress = 15
            logger.info(f"[Task {task_id}] Fetcher 已创建，开始获取页面...")

            # 启动一个后台线程来模拟进度更新
            # 在等待浏览器加载时增加进度
            import threading
            progress_stop = threading.Event()

            def progress_updater():
                current_progress = 15
                while not progress_stop.is_set() and current_progress < 75:
                    time.sleep(1)  # 每1秒更新一次（从2秒减少）
                    if not progress_stop.is_set():
                        current_progress = min(current_progress + 8, 75)  # 增加步进（从5改为8）
                        task.progress = current_progress

            progress_thread = threading.Thread(target=progress_updater, daemon=True)
            progress_thread.start()

            try:
                # 使用上下文管理器确保资源正确释放
                with fetcher:
                    # 执行获取
                    result = fetcher.fetch_all_metadata(task.url)
            finally:
                progress_stop.set()
                progress_thread.join(timeout=1)

            task.progress = 85

            if not result.success:
                raise FetchError(result.error_message or "获取失败")

            # 转换消息格式
            conv = result.conversation
            messages = []
            for msg in conv.messages:
                messages.append({
                    "role": msg.role.value,
                    "content": msg.content or msg.summary or "",
                    "isThinking": msg.metadata.get("isThinking", False) if msg.metadata else False
                })

            logger.info(f"[Task {task_id}] 成功获取 {len(messages)} 条消息")

            # 更新会话数据
            self._session_manager.set_session_data(
                task.session_id,
                title=conv.title,
                url=task.url,
                messages=messages
            )

            # 更新任务状态
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.progress = 100
            logger.info(f"[Task {task_id}] 任务完成")

        except Exception as e:
            # 更新错误状态
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.now()
            logger.error(f"[Task {task_id}] 任务失败: {e}")

            # 更新会话错误状态
            self._session_manager.set_session_error(
                task.session_id,
                str(e)
            )

    def cleanup_completed_tasks(self, max_age_hours: int = 1) -> int:
        """
        清理已完成的任务

        Args:
            max_age_hours: 最大存活时间（小时）

        Returns:
            清理的任务数量
        """
        cutoff = datetime.now()
        expired_ids = []

        with self._tasks_lock:
            for task_id, task in self._tasks.items():
                if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    if task.completed_at:
                        age_hours = (cutoff - task.completed_at).total_seconds() / 3600
                        if age_hours > max_age_hours:
                            expired_ids.append(task_id)

            for task_id in expired_ids:
                del self._tasks[task_id]

        return len(expired_ids)

    def task_count(self) -> int:
        """获取任务数量"""
        with self._tasks_lock:
            return len(self._tasks)

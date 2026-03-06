"""
断点续传数据模型
用于记录任务进度，支持异常恢复
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
from pathlib import Path


class CheckpointStatus(Enum):
    """断点状态枚举"""
    PENDING = "pending"           # 待处理
    IN_PROGRESS = "in_progress"   # 处理中
    PAUSED = "paused"             # 已暂停
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    RECOVERED = "recovered"       # 已恢复


@dataclass
class Checkpoint:
    """
    断点数据结构
    记录任务执行进度，支持中断恢复
    """
    # 任务唯一标识
    task_id: str
    # 来源URL
    source_url: str
    # 当前状态
    status: CheckpointStatus = CheckpointStatus.PENDING
    # 当前处理的消息索引
    current_message_index: int = 0
    # 总消息数
    total_messages: int = 0
    # 已处理的消息索引列表
    processed_indices: List[int] = field(default_factory=list)
    # 用户选择的消息索引
    selected_indices: List[int] = field(default_factory=list)
    # 已导出的消息索引
    exported_indices: List[int] = field(default_factory=list)
    # 临时文件路径
    temp_file_path: Optional[str] = None
    # 输出文件路径
    output_file_path: Optional[str] = None
    # 错误信息
    error_message: Optional[str] = None
    # Token使用统计
    token_usage: Dict[str, int] = field(default_factory=dict)
    # 创建时间
    created_at: Optional[datetime] = None
    # 更新时间
    updated_at: Optional[datetime] = None
    # 额外元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.created_at:
            self.created_at = datetime.now()
        if not self.updated_at:
            self.updated_at = datetime.now()
        if not self.task_id:
            import hashlib
            self.task_id = hashlib.md5(self.source_url.encode()).hexdigest()[:12]
    
    @property
    def progress_percentage(self) -> float:
        """计算进度百分比"""
        if self.total_messages == 0:
            return 0.0
        return (len(self.processed_indices) / self.total_messages) * 100
    
    @property
    def is_resumable(self) -> bool:
        """是否可恢复"""
        return self.status in [
            CheckpointStatus.PAUSED,
            CheckpointStatus.FAILED,
            CheckpointStatus.IN_PROGRESS
        ] and self.current_message_index < self.total_messages
    
    @property
    def is_completed(self) -> bool:
        """是否已完成"""
        return self.status == CheckpointStatus.COMPLETED
    
    def update_progress(self, message_index: int) -> None:
        """更新处理进度"""
        self.current_message_index = message_index
        if message_index not in self.processed_indices:
            self.processed_indices.append(message_index)
        self.updated_at = datetime.now()
    
    def mark_selected(self, indices: List[int]) -> None:
        """标记选中的消息"""
        self.selected_indices = indices
        self.updated_at = datetime.now()
    
    def mark_exported(self, indices: List[int]) -> None:
        """标记已导出的消息"""
        for idx in indices:
            if idx not in self.exported_indices:
                self.exported_indices.append(idx)
        self.updated_at = datetime.now()
    
    def set_status(self, status: CheckpointStatus) -> None:
        """设置状态"""
        self.status = status
        self.updated_at = datetime.now()
    
    def set_error(self, error_message: str) -> None:
        """设置错误信息"""
        self.error_message = error_message
        self.status = CheckpointStatus.FAILED
        self.updated_at = datetime.now()
    
    def update_token_usage(self, used: int, remaining: int = None) -> None:
        """更新Token使用统计"""
        self.token_usage["used"] = used
        if remaining is not None:
            self.token_usage["remaining"] = remaining
        self.token_usage["last_updated"] = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "source_url": self.source_url,
            "status": self.status.value,
            "current_message_index": self.current_message_index,
            "total_messages": self.total_messages,
            "processed_indices": self.processed_indices,
            "selected_indices": self.selected_indices,
            "exported_indices": self.exported_indices,
            "temp_file_path": self.temp_file_path,
            "output_file_path": self.output_file_path,
            "error_message": self.error_message,
            "token_usage": self.token_usage,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        """从字典创建断点"""
        return cls(
            task_id=data["task_id"],
            source_url=data["source_url"],
            status=CheckpointStatus(data["status"]),
            current_message_index=data.get("current_message_index", 0),
            total_messages=data.get("total_messages", 0),
            processed_indices=data.get("processed_indices", []),
            selected_indices=data.get("selected_indices", []),
            exported_indices=data.get("exported_indices", []),
            temp_file_path=data.get("temp_file_path"),
            output_file_path=data.get("output_file_path"),
            error_message=data.get("error_message"),
            token_usage=data.get("token_usage", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
            metadata=data.get("metadata", {})
        )
    
    def save(self, checkpoint_dir: Path) -> Path:
        """保存断点到文件"""
        checkpoint_dir = Path(checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = checkpoint_dir / f"{self.task_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        
        return file_path
    
    @classmethod
    def load(cls, file_path: Path) -> "Checkpoint":
        """从文件加载断点"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    @classmethod
    def find_pending_tasks(cls, checkpoint_dir: Path) -> List["Checkpoint"]:
        """查找所有待恢复的任务"""
        checkpoint_dir = Path(checkpoint_dir)
        if not checkpoint_dir.exists():
            return []
        
        pending = []
        for file_path in checkpoint_dir.glob("*.json"):
            try:
                checkpoint = cls.load(file_path)
                if checkpoint.is_resumable:
                    pending.append(checkpoint)
            except Exception:
                continue
        
        return pending
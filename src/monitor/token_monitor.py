"""
Token监控器
监控Token使用量，防止超出限制
"""
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime
import threading


class TokenLimitExceeded(Exception):
    """Token超限异常"""
    
    def __init__(self, used: int, limit: int, message: str = ""):
        self.used = used
        self.limit = limit
        self.message = message or f"Token使用量超限: 已使用 {used}, 限制 {limit}"
        super().__init__(self.message)


@dataclass
class TokenUsage:
    """Token使用记录"""
    timestamp: datetime
    used: int
    remaining: int
    operation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class TokenMonitor:
    """
    Token监控器
    
    监控Token使用量，在接近限制时发出警告，超限时抛出异常
    支持多线程安全操作
    """
    
    # 默认警告阈值（百分比）
    DEFAULT_WARNING_THRESHOLD = 0.8  # 80%
    DEFAULT_CRITICAL_THRESHOLD = 0.95  # 95%
    
    def __init__(
        self,
        token_limit: int = 100000,
        warning_threshold: float = DEFAULT_WARNING_THRESHOLD,
        critical_threshold: float = DEFAULT_CRITICAL_THRESHOLD,
        on_warning: Optional[Callable[[int, int], None]] = None,
        on_critical: Optional[Callable[[int, int], None]] = None,
        on_exceeded: Optional[Callable[[int, int], None]] = None
    ):
        """
        初始化Token监控器
        
        Args:
            token_limit: Token使用上限
            warning_threshold: 警告阈值（0-1之间的比例）
            critical_threshold: 临界阈值（0-1之间的比例）
            on_warning: 警告回调函数
            on_critical: 临界回调函数
            on_exceeded: 超限回调函数
        """
        self.token_limit = token_limit
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        
        # 回调函数
        self._on_warning = on_warning
        self._on_critical = on_critical
        self._on_exceeded = on_exceeded
        
        # 状态变量
        self._used_tokens = 0
        self._lock = threading.Lock()
        self._usage_history: List[TokenUsage] = []
        self._is_paused = False
        self._pause_reason = ""
        
        # 状态标记
        self._warning_triggered = False
        self._critical_triggered = False
    
    @property
    def used_tokens(self) -> int:
        """已使用的Token数量"""
        return self._used_tokens
    
    @property
    def remaining_tokens(self) -> int:
        """剩余Token数量"""
        return max(0, self.token_limit - self._used_tokens)
    
    @property
    def usage_percentage(self) -> float:
        """使用百分比"""
        return (self._used_tokens / self.token_limit) * 100 if self.token_limit > 0 else 0
    
    @property
    def is_paused(self) -> bool:
        """是否已暂停"""
        return self._is_paused
    
    @property
    def pause_reason(self) -> str:
        """暂停原因"""
        return self._pause_reason
    
    def use(self, tokens: int, operation: str = "", metadata: Dict[str, Any] = None) -> int:
        """
        使用Token
        
        Args:
            tokens: 要使用的Token数量
            operation: 操作描述
            metadata: 额外元数据
            
        Returns:
            实际使用的Token数量
            
        Raises:
            TokenLimitExceeded: 当Token超限时抛出
        """
        with self._lock:
            if self._is_paused:
                raise TokenLimitExceeded(
                    self._used_tokens,
                    self.token_limit,
                    f"监控器已暂停: {self._pause_reason}"
                )
            
            new_total = self._used_tokens + tokens
            
            # 检查是否超限
            if new_total > self.token_limit:
                # 触发超限回调
                if self._on_exceeded:
                    self._on_exceeded(new_total, self.token_limit)
                
                raise TokenLimitExceeded(new_total, self.token_limit)
            
            # 更新使用量
            self._used_tokens = new_total
            
            # 记录使用历史
            self._usage_history.append(TokenUsage(
                timestamp=datetime.now(),
                used=tokens,
                remaining=self.remaining_tokens,
                operation=operation,
                metadata=metadata or {}
            ))
            
            # 检查阈值
            self._check_thresholds()
            
            return tokens
    
    def _check_thresholds(self) -> None:
        """检查阈值并触发回调"""
        usage_ratio = self._used_tokens / self.token_limit
        
        # 检查临界阈值
        if usage_ratio >= self.critical_threshold and not self._critical_triggered:
            self._critical_triggered = True
            if self._on_critical:
                self._on_critical(self._used_tokens, self.token_limit)
        
        # 检查警告阈值
        elif usage_ratio >= self.warning_threshold and not self._warning_triggered:
            self._warning_triggered = True
            if self._on_warning:
                self._on_warning(self._used_tokens, self.token_limit)
    
    def can_use(self, tokens: int) -> bool:
        """
        检查是否可以使用指定数量的Token
        
        Args:
            tokens: 要检查的Token数量
            
        Returns:
            是否可以使用
        """
        with self._lock:
            if self._is_paused:
                return False
            return self._used_tokens + tokens <= self.token_limit
    
    def estimate_text_tokens(self, text: str) -> int:
        """
        估算文本的Token数量
        
        Args:
            text: 要估算的文本
            
        Returns:
            估算的Token数量
        """
        if not text:
            return 0
        # 简化估算：平均3字符/token
        return len(text) // 3 + 1
    
    def can_load_content(self, content: str) -> bool:
        """
        检查是否可以加载内容
        
        Args:
            content: 要加载的内容
            
        Returns:
            是否可以加载
        """
        estimated = self.estimate_text_tokens(content)
        return self.can_use(estimated)
    
    def pause(self, reason: str = "") -> None:
        """
        暂停监控器
        
        Args:
            reason: 暂停原因
        """
        with self._lock:
            self._is_paused = True
            self._pause_reason = reason
    
    def resume(self) -> None:
        """恢复监控器"""
        with self._lock:
            self._is_paused = False
            self._pause_reason = ""
    
    def reset(self) -> None:
        """重置监控器状态"""
        with self._lock:
            self._used_tokens = 0
            self._is_paused = False
            self._pause_reason = ""
            self._warning_triggered = False
            self._critical_triggered = False
            self._usage_history.clear()
    
    def get_usage_history(self, limit: int = 100) -> List[TokenUsage]:
        """
        获取使用历史
        
        Args:
            limit: 返回的最大记录数
            
        Returns:
            使用历史列表
        """
        with self._lock:
            return self._usage_history[-limit:]
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取监控器状态
        
        Returns:
            状态字典
        """
        with self._lock:
            return {
                "used_tokens": self._used_tokens,
                "remaining_tokens": self.remaining_tokens,
                "token_limit": self.token_limit,
                "usage_percentage": self.usage_percentage,
                "is_paused": self._is_paused,
                "pause_reason": self._pause_reason,
                "warning_triggered": self._warning_triggered,
                "critical_triggered": self._critical_triggered,
                "history_count": len(self._usage_history)
            }
    
    def set_limit(self, new_limit: int) -> None:
        """
        设置新的Token限制
        
        Args:
            new_limit: 新的限制值
        """
        with self._lock:
            self.token_limit = new_limit
            # 重置阈值标记
            self._warning_triggered = False
            self._critical_triggered = False
            self._check_thresholds()
"""
熔断器
实现异常场景熔断机制，支持紧急备份和自动恢复
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Any, Dict
from datetime import datetime, timedelta
import threading
import traceback


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"        # 正常状态（关闭）
    OPEN = "open"            # 熔断状态（打开）
    HALF_OPEN = "half_open"  # 半开状态（尝试恢复）


@dataclass
class FailureRecord:
    """失败记录"""
    timestamp: datetime
    exception: Exception
    operation: str
    traceback_str: str


class CircuitBreaker:
    """
    熔断器
    
    监控操作失败，在失败率达到阈值时触发熔断
    支持紧急备份和自动恢复
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
        on_open: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        on_half_open: Optional[Callable[[], None]] = None,
        on_failure: Optional[Callable[[Exception, str], None]] = None,
        emergency_backup: Optional[Callable[[Any], None]] = None
    ):
        """
        初始化熔断器
        
        Args:
            failure_threshold: 失败次数阈值
            recovery_timeout: 恢复超时时间（秒）
            half_open_max_calls: 半开状态最大尝试次数
            on_open: 熔断触发回调
            on_close: 熔断恢复回调
            on_half_open: 进入半开状态回调
            on_failure: 失败回调
            emergency_backup: 紧急备份回调
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        # 回调函数
        self._on_open = on_open
        self._on_close = on_close
        self._on_half_open = on_half_open
        self._on_failure = on_failure
        self._emergency_backup = emergency_backup
        
        # 状态变量
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0
        self._failure_history: list = []
        self._lock = threading.Lock()
        
        # 断点数据
        self._checkpoint_data: Any = None
    
    @property
    def state(self) -> CircuitState:
        """当前状态"""
        return self._state
    
    @property
    def is_open(self) -> bool:
        """是否处于熔断状态"""
        return self._state == CircuitState.OPEN
    
    @property
    def is_closed(self) -> bool:
        """是否处于正常状态"""
        return self._state == CircuitState.CLOSED
    
    @property
    def is_half_open(self) -> bool:
        """是否处于半开状态"""
        return self._state == CircuitState.HALF_OPEN
    
    @property
    def failure_count(self) -> int:
        """失败计数"""
        return self._failure_count
    
    def _transition_to(self, new_state: CircuitState) -> None:
        """状态转换"""
        old_state = self._state
        self._state = new_state
        
        if new_state == CircuitState.OPEN and old_state != CircuitState.OPEN:
            if self._on_open:
                self._on_open()
        elif new_state == CircuitState.CLOSED and old_state != CircuitState.CLOSED:
            if self._on_close:
                self._on_close()
        elif new_state == CircuitState.HALF_OPEN and old_state != CircuitState.HALF_OPEN:
            if self._on_half_open:
                self._on_half_open()
    
    def _should_attempt_recovery(self) -> bool:
        """检查是否应该尝试恢复"""
        if self._last_failure_time is None:
            return False
        
        elapsed = datetime.now() - self._last_failure_time
        return elapsed >= timedelta(seconds=self.recovery_timeout)
    
    def record_success(self) -> None:
        """记录成功操作"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                self._half_open_calls += 1
                
                # 半开状态下连续成功，恢复正常
                if self._success_count >= self.half_open_max_calls:
                    self._failure_count = 0
                    self._success_count = 0
                    self._half_open_calls = 0
                    self._transition_to(CircuitState.CLOSED)
            
            elif self._state == CircuitState.CLOSED:
                # 正常状态下成功，重置失败计数
                self._failure_count = 0
    
    def record_failure(self, exception: Exception, operation: str = "") -> None:
        """
        记录失败操作
        
        Args:
            exception: 异常对象
            operation: 操作描述
        """
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()
            
            # 记录失败历史
            self._failure_history.append(FailureRecord(
                timestamp=datetime.now(),
                exception=exception,
                operation=operation,
                traceback_str=traceback.format_exc()
            ))
            
            # 保留最近100条记录
            if len(self._failure_history) > 100:
                self._failure_history = self._failure_history[-100:]
            
            # 触发失败回调
            if self._on_failure:
                self._on_failure(exception, operation)
            
            if self._state == CircuitState.HALF_OPEN:
                # 半开状态下失败，立即熔断
                self._half_open_calls = 0
                self._success_count = 0
                self._transition_to(CircuitState.OPEN)
                
                # 执行紧急备份
                self._do_emergency_backup()
            
            elif self._state == CircuitState.CLOSED:
                # 正常状态下检查是否需要熔断
                if self._failure_count >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
                    
                    # 执行紧急备份
                    self._do_emergency_backup()
    
    def _do_emergency_backup(self) -> None:
        """执行紧急备份"""
        if self._emergency_backup and self._checkpoint_data is not None:
            try:
                self._emergency_backup(self._checkpoint_data)
            except Exception as e:
                # 备份失败，记录但不抛出
                if self._on_failure:
                    self._on_failure(e, "emergency_backup")
    
    def set_checkpoint(self, data: Any) -> None:
        """
        设置断点数据
        
        Args:
            data: 断点数据
        """
        with self._lock:
            self._checkpoint_data = data
    
    def get_checkpoint(self) -> Any:
        """获取断点数据"""
        return self._checkpoint_data
    
    def can_execute(self) -> bool:
        """
        检查是否可以执行操作
        
        Returns:
            是否可以执行
        """
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            
            if self._state == CircuitState.OPEN:
                # 检查是否可以尝试恢复
                if self._should_attempt_recovery():
                    self._transition_to(CircuitState.HALF_OPEN)
                    self._half_open_calls = 0
                    self._success_count = 0
                    return True
                return False
            
            if self._state == CircuitState.HALF_OPEN:
                # 半开状态下限制调用次数
                return self._half_open_calls < self.half_open_max_calls
            
            return False
    
    def execute(self, operation: Callable, *args, **kwargs) -> Any:
        """
        执行操作（带熔断保护）
        
        Args:
            operation: 要执行的操作
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            操作结果
            
        Raises:
            CircuitBreakerOpenError: 熔断器打开时抛出
        """
        if not self.can_execute():
            raise CircuitBreakerOpenError(
                "熔断器已打开，操作被拒绝",
                self._last_failure_time,
                self.recovery_timeout
            )
        
        try:
            result = operation(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e, getattr(operation, '__name__', 'unknown'))
            raise
    
    def reset(self) -> None:
        """重置熔断器"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0
            self._checkpoint_data = None
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取熔断器状态
        
        Returns:
            状态字典
        """
        with self._lock:
            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "failure_threshold": self.failure_threshold,
                "last_failure_time": self._last_failure_time.isoformat() if self._last_failure_time else None,
                "recovery_timeout": self.recovery_timeout,
                "half_open_calls": self._half_open_calls,
                "can_execute": self.can_execute(),
                "has_checkpoint": self._checkpoint_data is not None
            }
    
    def get_failure_history(self, limit: int = 10) -> list:
        """
        获取失败历史
        
        Args:
            limit: 返回的最大记录数
            
        Returns:
            失败记录列表
        """
        with self._lock:
            return self._failure_history[-limit:]


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""
    
    def __init__(self, message: str, last_failure_time: datetime, recovery_timeout: int):
        self.message = message
        self.last_failure_time = last_failure_time
        self.recovery_timeout = recovery_timeout
        super().__init__(self.message)
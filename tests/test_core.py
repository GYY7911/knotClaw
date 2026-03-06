"""
核心功能测试
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import Conversation, Message, MessageRole, Checkpoint, CheckpointStatus
from src.monitor import TokenMonitor, TokenLimitExceeded, CircuitBreaker, CircuitState
from src.exporter import MarkdownExporter, ExportOptions
from src.fetcher import FetcherFactory


def test_models():
    """测试数据模型"""
    print("测试数据模型...")
    
    # 创建消息
    msg = Message(
        id="msg_1",
        role=MessageRole.USER,
        content="这是一个测试消息",
        summary="测试消息摘要"
    )
    assert msg.role == MessageRole.USER
    assert msg.is_loaded == True
    assert msg.token_count > 0
    print("  ✓ Message 模型正常")
    
    # 创建对话
    conv = Conversation(
        id="conv_1",
        title="测试对话",
        source_url="https://example.com/share/test",
        messages=[msg],
        total_messages=1
    )
    assert conv.title == "测试对话"
    assert conv.total_messages == 1
    assert len(conv.messages) == 1
    print("  ✓ Conversation 模型正常")
    
    # 创建断点
    cp = Checkpoint(
        task_id="task_1",
        source_url="https://example.com/share/test",
        total_messages=10
    )
    assert cp.status == CheckpointStatus.PENDING
    assert cp.is_resumable == False  # PENDING状态不可恢复
    cp.set_status(CheckpointStatus.IN_PROGRESS)
    assert cp.is_resumable == True
    print("  ✓ Checkpoint 模型正常")


def test_token_monitor():
    """测试Token监控器"""
    print("\n测试Token监控器...")
    
    warning_called = []
    exceeded_called = []
    
    def on_warning(used, limit):
        warning_called.append((used, limit))
    
    def on_exceeded(used, limit):
        exceeded_called.append((used, limit))
    
    monitor = TokenMonitor(
        token_limit=100,
        warning_threshold=0.8,
        on_warning=on_warning,
        on_exceeded=on_exceeded
    )
    
    # 测试正常使用
    monitor.use(50)
    assert monitor.used_tokens == 50
    assert monitor.remaining_tokens == 50
    print("  ✓ Token使用正常")
    
    # 测试警告阈值
    monitor.use(30)  # 总共80，达到80%阈值
    assert len(warning_called) == 1
    print("  ✓ 警告阈值触发正常")
    
    # 测试超限
    try:
        monitor.use(50)  # 超过限制
        assert False, "应该抛出异常"
    except TokenLimitExceeded:
        pass
    print("  ✓ Token超限检测正常")


def test_circuit_breaker():
    """测试熔断器"""
    print("\n测试熔断器...")
    
    open_called = []
    backup_called = []
    
    def on_open():
        open_called.append(True)
    
    def emergency_backup(data):
        backup_called.append(data)
    
    breaker = CircuitBreaker(
        failure_threshold=3,
        on_open=on_open,
        emergency_backup=emergency_backup
    )
    
    # 测试正常状态
    assert breaker.is_closed
    assert breaker.can_execute()
    print("  ✓ 熔断器初始状态正常")
    
    # 测试失败记录
    for i in range(3):
        breaker.record_failure(Exception(f"Error {i}"), f"operation_{i}")
    
    assert breaker.is_open
    assert len(open_called) == 1
    print("  ✓ 熔断触发正常")
    
    # 测试熔断后无法执行
    assert not breaker.can_execute()
    print("  ✓ 熔断后拒绝执行正常")


def test_exporter():
    """测试导出器"""
    print("\n测试导出器...")
    
    # 创建测试对话
    messages = [
        Message(
            id="msg_1",
            role=MessageRole.USER,
            content="用户消息内容",
            summary="用户消息摘要"
        ),
        Message(
            id="msg_2",
            role=MessageRole.ASSISTANT,
            content="助手回复内容",
            summary="助手回复摘要"
        )
    ]
    
    conv = Conversation(
        id="conv_1",
        title="测试对话",
        source_url="https://example.com/share/test",
        messages=messages
    )
    
    # 测试导出
    exporter = MarkdownExporter(output_dir="./test_output")
    options = ExportOptions(
        include_metadata=True,
        include_timestamps=True,
        include_token_stats=True
    )
    
    output_path = exporter.export(conv, options, filename="test_export")
    assert output_path.exists()
    print(f"  ✓ 导出成功: {output_path}")
    
    # 验证内容
    content = output_path.read_text(encoding='utf-8')
    assert "测试对话" in content
    assert "用户消息内容" in content
    assert "助手回复内容" in content
    print("  ✓ 导出内容正确")
    
    # 清理
    output_path.unlink()
    output_path.parent.rmdir()


def test_fetcher_factory():
    """测试抓取器工厂"""
    print("\n测试抓取器工厂...")
    
    # 测试支持的URL
    assert FetcherFactory.is_supported("https://chat.deepseek.com/share/xxxxx")
    print("  ✓ DeepSeek URL识别正常")
    
    # 测试不支持的URL
    assert not FetcherFactory.is_supported("https://example.com/share/xxxxx")
    print("  ✓ 不支持的URL拒绝正常")
    
    # 测试获取抓取器
    fetcher = FetcherFactory.get_fetcher("https://chat.deepseek.com/share/xxxxx")
    assert fetcher is not None
    print("  ✓ 抓取器创建正常")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("  Knotclaw 核心功能测试")
    print("=" * 60)
    
    try:
        test_models()
        test_token_monitor()
        test_circuit_breaker()
        test_exporter()
        test_fetcher_factory()
        
        print("\n" + "=" * 60)
        print("  ✅ 所有测试通过！")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
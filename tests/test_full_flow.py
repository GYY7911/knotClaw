"""
完整流程测试
使用模拟数据测试整个归档流程
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.models import Conversation, Message, MessageRole, Checkpoint, CheckpointStatus
from src.exporter import MarkdownExporter, ExportOptions
from src.monitor import TokenMonitor


def create_mock_conversation():
    """创建模拟对话数据"""
    messages = [
        Message(
            id="msg_1",
            role=MessageRole.USER,
            content="请帮我写一个Python函数，计算斐波那契数列",
            summary="请求写斐波那契函数"
        ),
        Message(
            id="msg_2",
            role=MessageRole.ASSISTANT,
            content="""好的，这是一个计算斐波那契数列的Python函数：

```python
def fibonacci(n):
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    elif n == 2:
        return [0, 1]
    
    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[i-1] + fib[i-2])
    return fib

# 使用示例
print(fibonacci(10))  # 输出: [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
```

这个函数使用迭代方法，时间复杂度是O(n)，空间复杂度也是O(n)。""",
            summary="提供斐波那契函数实现"
        ),
        Message(
            id="msg_3",
            role=MessageRole.USER,
            content="能优化一下空间复杂度吗？",
            summary="请求优化空间复杂度"
        ),
        Message(
            id="msg_4",
            role=MessageRole.ASSISTANT,
            content="""当然可以！这是空间优化版本：

```python
def fibonacci_optimized(n):
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    elif n == 2:
        return [0, 1]
    
    result = [0, 1]
    a, b = 0, 1
    for _ in range(2, n):
        a, b = b, a + b
        result.append(b)
    return result
```

这个版本的空间复杂度降到了O(1)（不包括结果存储）。""",
            summary="提供优化版本"
        ),
        Message(
            id="msg_5",
            role=MessageRole.USER,
            content="谢谢！再帮我写一个递归版本",
            summary="请求递归版本"
        ),
        Message(
            id="msg_6",
            role=MessageRole.ASSISTANT,
            content="""好的，这是递归版本：

```python
def fibonacci_recursive(n):
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    return fibonacci_recursive(n-1) + fibonacci_recursive(n-2)

# 获取前n项
def fibonacci_seq_recursive(n):
    return [fibonacci_recursive(i) for i in range(n)]
```

注意：递归版本的时间复杂度是O(2^n)，效率较低，建议使用记忆化优化：

```python
from functools import lru_cache

@lru_cache(maxsize=None)
def fibonacci_memo(n):
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    return fibonacci_memo(n-1) + fibonacci_memo(n-2)
```""",
            summary="提供递归版本和记忆化优化"
        ),
    ]
    
    conversation = Conversation(
        id="test_conv_1",
        title="斐波那契数列讨论",
        source_url="https://chat.deepseek.com/share/test123",
        messages=messages,
        total_messages=len(messages)
    )
    
    return conversation


def test_full_flow():
    """测试完整流程"""
    print("=" * 60)
    print("  Knotclaw 完整流程测试")
    print("=" * 60)
    
    # 1. 创建模拟对话
    print("\n1. 创建模拟对话数据...")
    conversation = create_mock_conversation()
    print(f"   ✓ 对话标题: {conversation.title}")
    print(f"   ✓ 消息数量: {conversation.total_messages}")
    
    # 2. 测试Token监控
    print("\n2. 测试Token监控...")
    monitor = TokenMonitor(token_limit=10000)
    total_tokens = sum(msg.token_count for msg in conversation.messages)
    monitor.use(total_tokens, operation="load_conversation")
    print(f"   ✓ 已使用Token: {monitor.used_tokens}")
    print(f"   ✓ 剩余Token: {monitor.remaining_tokens}")
    
    # 3. 测试消息选择
    print("\n3. 模拟消息选择...")
    selected_indices = [0, 1, 2, 3, 4, 5]  # 选择所有消息
    conversation.mark_selected(selected_indices)
    print(f"   ✓ 已选择 {len(selected_indices)} 条消息")
    
    # 4. 测试导出
    print("\n4. 测试Markdown导出...")
    exporter = MarkdownExporter(output_dir="./test_output")
    options = ExportOptions(
        include_metadata=True,
        include_timestamps=True,
        include_token_stats=True,
        include_source_url=True
    )
    
    output_path = exporter.export(conversation, options, filename="test_full_flow")
    print(f"   ✓ 导出成功: {output_path}")
    
    # 5. 验证导出内容
    print("\n5. 验证导出内容...")
    content = output_path.read_text(encoding='utf-8')
    
    checks = [
        ("标题", "斐波那契数列讨论" in content),
        ("用户消息", "请帮我写一个Python函数" in content),
        ("助手回复", "def fibonacci" in content),
        ("优化版本", "fibonacci_optimized" in content),
        ("递归版本", "fibonacci_recursive" in content),
        ("Token统计", "Token数" in content),
    ]
    
    all_passed = True
    for name, passed in checks:
        status = "✓" if passed else "✗"
        print(f"   {status} {name}: {'通过' if passed else '失败'}")
        if not passed:
            all_passed = False
    
    # 6. 显示导出文件内容摘要
    print("\n6. 导出文件内容摘要:")
    print("-" * 40)
    lines = content.split('\n')
    for line in lines[:30]:
        print(line)
    if len(lines) > 30:
        print(f"... (共 {len(lines)} 行)")
    print("-" * 40)
    
    # 清理
    print("\n清理测试文件...")
    output_path.unlink()
    try:
        output_path.parent.rmdir()
    except:
        pass
    
    print("\n" + "=" * 60)
    if all_passed:
        print("  ✅ 所有测试通过！")
    else:
        print("  ❌ 部分测试失败")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = test_full_flow()
    sys.exit(0 if success else 1)
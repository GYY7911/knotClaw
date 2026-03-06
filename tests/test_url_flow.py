"""
完整URL流程测试
模拟从URL获取对话到导出的完整流程
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.fetcher import DeepSeekFetcher
from src.exporter import MarkdownExporter, ExportOptions
from src.models import MessageRole


def create_mock_deepseek_html():
    """创建模拟的DeepSeek HTML页面（包含__NEXT_DATA__）"""
    mock_data = {
        "props": {
            "pageProps": {
                "conversation": {
                    "id": "test_conv_001",
                    "title": "Python编程技巧讨论",
                    "createdAt": "2026-03-04T10:00:00.000Z",
                    "updatedAt": "2026-03-04T10:30:00.000Z",
                    "messages": [
                        {
                            "id": "msg_1",
                            "role": "user",
                            "content": "你好，请介绍一下Python的装饰器",
                            "createdAt": "2026-03-04T10:00:00.000Z"
                        },
                        {
                            "id": "msg_2",
                            "role": "assistant",
                            "content": """Python装饰器是一个非常强大的功能，它允许你在不修改原函数代码的情况下，扩展函数的功能。

## 什么是装饰器？

装饰器本质上是一个函数，它接受一个函数作为参数，并返回一个新的函数。

## 基本语法

```python
@decorator_name
def my_function():
    pass
```

## 简单示例

```python
def my_decorator(func):
    def wrapper():
        print("函数执行前")
        func()
        print("函数执行后")
    return wrapper

@my_decorator
def say_hello():
    print("Hello!")

# 调用
say_hello()
# 输出:
# 函数执行前
# Hello!
# 函数执行后
```

## 实用示例 - 计时装饰器

```python
import time

def timer(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} 执行时间: {end - start:.2f}秒")
        return result
    return wrapper

@timer
def slow_function():
    time.sleep(1)
    return "完成"
```

希望这个解释对你有帮助！""",
                            "createdAt": "2026-03-04T10:01:00.000Z"
                        },
                        {
                            "id": "msg_3",
                            "role": "user",
                            "content": "能再讲讲带参数的装饰器吗？",
                            "createdAt": "2026-03-04T10:15:00.000Z"
                        },
                        {
                            "id": "msg_4",
                            "role": "assistant",
                            "content": """当然可以！带参数的装饰器需要多一层嵌套。

## 带参数的装饰器

```python
def repeat(times):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for _ in range(times):
                result = func(*args, **kwargs)
            return result
        return wrapper
    return decorator

@repeat(times=3)
def say_hello(name):
    print(f"Hello, {name}!")

# 调用
say_hello("World")
# 输出:
# Hello, World!
# Hello, World!
# Hello, World!
```

## 类装饰器

也可以用类来实现装饰器：

```python
class CountCalls:
    def __init__(self, func):
        self.func = func
        self.count = 0
    
    def __call__(self, *args, **kwargs):
        self.count += 1
        print(f"第 {self.count} 次调用")
        return self.func(*args, **kwargs)

@CountCalls
def my_function():
    print("执行函数")

my_function()  # 第 1 次调用
my_function()  # 第 2 次调用
```

## functools.wraps

为了保留原函数的元信息，建议使用 `functools.wraps`：

```python
from functools import wraps

def my_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper
```

这样可以保留 `func.__name__`、`func.__doc__` 等属性。""",
                            "createdAt": "2026-03-04T10:16:00.000Z"
                        },
                        {
                            "id": "msg_5",
                            "role": "user",
                            "content": "太棒了，谢谢！最后能讲讲常见内置装饰器吗？",
                            "createdAt": "2026-03-04T10:25:00.000Z"
                        },
                        {
                            "id": "msg_6",
                            "role": "assistant",
                            "content": """当然！Python内置了几个非常实用的装饰器。

## @property

将方法变成属性访问：

```python
class Circle:
    def __init__(self, radius):
        self._radius = radius
    
    @property
    def radius(self):
        return self._radius
    
    @radius.setter
    def radius(self, value):
        if value > 0:
            self._radius = value
    
    @property
    def area(self):
        return 3.14159 * self._radius ** 2

c = Circle(5)
print(c.radius)  # 5
print(c.area)    # 78.54
```

## @staticmethod 和 @classmethod

```python
class MyClass:
    count = 0
    
    def __init__(self):
        MyClass.count += 1
    
    @staticmethod
    def static_method():
        print("静态方法，不需要self或cls")
    
    @classmethod
    def class_method(cls):
        print(f"类方法，访问类变量: {cls.count}")

MyClass.static_method()
MyClass.class_method()
```

## @functools.lru_cache

缓存函数结果，提高性能：

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# 第一次调用会计算
print(fibonacci(100))  # 很快！

# 第二次直接返回缓存
print(fibonacci(100))  # 瞬间返回
```

## @dataclass

简化类的定义（Python 3.7+）：

```python
from dataclasses import dataclass

@dataclass
class Person:
    name: str
    age: int
    city: str = "未知"

p = Person("张三", 25)
print(p)  # Person(name='张三', age=25, city='未知')
```

希望这些内容对你有帮助！有任何问题随时问我。""",
                            "createdAt": "2026-03-04T10:26:00.000Z"
                        }
                    ]
                }
            }
        }
    }
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Python编程技巧讨论 - DeepSeek</title>
</head>
<body>
    <script id="__NEXT_DATA__" type="application/json">
    {json.dumps(mock_data, ensure_ascii=False, indent=2)}
    </script>
</body>
</html>"""
    
    return html


def test_fetcher_with_mock_html():
    """测试抓取器解析模拟HTML"""
    print("=" * 60)
    print("  DeepSeek 抓取器测试")
    print("=" * 60)
    
    # 创建模拟HTML
    print("\n1. 创建模拟的DeepSeek HTML页面...")
    html = create_mock_deepseek_html()
    print(f"   HTML大小: {len(html)} 字符")
    
    # 创建抓取器实例
    fetcher = DeepSeekFetcher()
    
    # 检查是否能识别对话数据
    print("\n2. 检测对话数据...")
    has_data = fetcher._has_conversation_data(html)
    print(f"   包含对话数据: {'是' if has_data else '否'}")
    
    if not has_data:
        print("   ❌ 未检测到对话数据！")
        return False
    
    # 解析HTML
    print("\n3. 解析HTML提取对话...")
    data = fetcher._parse_html(html)
    
    print(f"   对话标题: {data.get('title')}")
    print(f"   消息数量: {len(data.get('messages', []))}")
    
    messages = data.get('messages', [])
    print("\n   消息预览:")
    for i, msg in enumerate(messages[:3]):
        role = "👤 用户" if msg['role'] == 'user' else "🤖 助手"
        content = msg['content'][:50] + "..." if len(msg['content']) > 50 else msg['content']
        print(f"   [{i+1}] {role}: {content}")
    
    if len(messages) > 3:
        print(f"   ... 还有 {len(messages) - 3} 条消息")
    
    # 测试 fetch_all_metadata
    print("\n4. 测试 fetch_all_metadata 方法...")
    fetcher._cached_html = html  # 设置缓存
    result = fetcher.fetch_all_metadata("https://chat.deepseek.com/share/test123")
    
    if not result.success:
        print(f"   ❌ 抓取失败: {result.error_message}")
        return False
    
    conversation = result.conversation
    print(f"   ✓ 对话标题: {conversation.title}")
    print(f"   ✓ 消息总数: {conversation.total_messages}")
    print(f"   ✓ 来源URL: {conversation.source_url}")
    
    # 加载消息内容（模拟交互式CLI中的导出流程）
    print("\n5. 加载消息内容...")
    for msg in conversation.messages:
        if not msg.is_loaded and msg._raw_data_ref:
            content = msg._raw_data_ref.get("content", "")
            if content:
                msg.load_content(content)
                print(f"   ✓ 加载消息 {msg.id}: {len(content)} 字符")
    
    # 导出为Markdown
    print("\n6. 导出为Markdown...")
    exporter = MarkdownExporter(output_dir="./test_output")
    options = ExportOptions(
        include_metadata=True,
        include_timestamps=True,
        include_token_stats=True,
        include_source_url=True
    )
    
    output_path = exporter.export(conversation, options, filename="url_flow_test")
    print(f"   ✓ 导出成功: {output_path}")
    
    # 验证导出内容
    print("\n6. 验证导出内容...")
    content = output_path.read_text(encoding='utf-8')
    
    checks = [
        ("标题", "Python编程技巧讨论" in content),
        ("用户消息", "装饰器" in content),
        ("代码块", "def" in content and "```python" in content),
        ("装饰器示例", "@decorator" in content),
        ("property", "@property" in content),
    ]
    
    all_passed = True
    for name, passed in checks:
        status = "✓" if passed else "✗"
        print(f"   {status} {name}: {'通过' if passed else '失败'}")
        if not passed:
            all_passed = False
    
    # 显示文件摘要
    print("\n7. 导出文件内容摘要:")
    print("-" * 40)
    lines = content.split('\n')
    for line in lines[:20]:
        print(line)
    if len(lines) > 20:
        print(f"... (共 {len(lines)} 行)")
    print("-" * 40)
    
    # 清理
    print("\n清理测试文件...")
    output_path.unlink()
    try:
        output_path.parent.rmdir()
    except:
        pass
    
    return all_passed


def main():
    print("\n" + "=" * 60)
    print("  Knotclaw 完整URL流程测试")
    print("=" * 60)
    
    success = test_fetcher_with_mock_html()
    
    print("\n" + "=" * 60)
    if success:
        print("  ✅ 所有测试通过！项目可正常工作")
        print()
        print("  使用说明:")
        print("  1. 运行: python main.py")
        print("  2. 输入 DeepSeek 分享链接")
        print("  3. 如果自动抓取失败，可以选择:")
        print("     - [1] 从文件读取HTML")
        print("     - [2] 直接粘贴HTML内容")
        print()
        print("  或者使用辅助工具获取HTML:")
        print("     python fetch_html_interactive.py")
    else:
        print("  ❌ 部分测试失败")
    print("=" * 60)
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
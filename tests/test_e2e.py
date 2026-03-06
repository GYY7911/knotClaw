"""
端到端测试 - 模拟完整的用户使用流程
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.fetcher import DeepSeekFetcher
from src.exporter import MarkdownExporter, ExportOptions


def test_with_sample_html():
    """使用 sample_conversation.html 测试完整流程"""
    print("=" * 60)
    print("  Knotclaw 端到端测试")
    print("=" * 60)
    
    # 1. 读取示例 HTML 文件
    sample_path = Path("sample_conversation.html")
    if not sample_path.exists():
        print(f"❌ 示例文件不存在: {sample_path}")
        return False
    
    print(f"\n1. 读取示例 HTML 文件: {sample_path}")
    html = sample_path.read_text(encoding='utf-8')
    print(f"   文件大小: {len(html)} 字符")
    
    # 2. 使用抓取器解析
    print("\n2. 解析 HTML 提取对话...")
    fetcher = DeepSeekFetcher()
    
    if not fetcher._has_conversation_data(html):
        print("   ❌ 未检测到对话数据")
        return False
    
    print("   ✓ 检测到对话数据")
    
    # 设置缓存并获取元数据
    fetcher._cached_html = html
    result = fetcher.fetch_all_metadata("https://chat.deepseek.com/share/sample")
    
    if not result.success:
        print(f"   ❌ 解析失败: {result.error_message}")
        return False
    
    conversation = result.conversation
    print(f"   ✓ 对话标题: {conversation.title}")
    print(f"   ✓ 消息数量: {conversation.total_messages}")
    
    # 3. 加载消息内容
    print("\n3. 加载消息内容...")
    for msg in conversation.messages:
        if not msg.is_loaded and msg._raw_data_ref:
            content = msg._raw_data_ref.get("content", "")
            if content:
                msg.load_content(content)
    print(f"   ✓ 已加载 {len(conversation.messages)} 条消息")
    
    # 4. 显示消息预览
    print("\n4. 消息预览:")
    for i, msg in enumerate(conversation.messages):
        role = "👤 用户" if msg.role.value == "user" else "🤖 助手"
        content = msg.content[:60] + "..." if msg.content and len(msg.content) > 60 else msg.content
        print(f"   [{i+1}] {role}: {content}")
    
    # 5. 导出为 Markdown
    print("\n5. 导出为 Markdown...")
    exporter = MarkdownExporter(output_dir="./output")
    options = ExportOptions(
        include_metadata=True,
        include_timestamps=True,
        include_token_stats=True,
        include_source_url=True
    )
    
    output_path = exporter.export(conversation, options, filename="e2e_test")
    print(f"   ✓ 导出成功: {output_path}")
    
    # 6. 验证导出内容
    print("\n6. 验证导出内容:")
    content = output_path.read_text(encoding='utf-8')
    
    checks = [
        ("标题存在", "Python编程技巧讨论" in content),
        ("用户消息存在", "装饰器" in content),
        ("代码块存在", "```python" in content),
        ("消息分隔符", "---" in content),
        ("导出统计", "导出时间" in content),
    ]
    
    all_passed = True
    for name, passed in checks:
        status = "✓" if passed else "✗"
        print(f"   {status} {name}")
        if not passed:
            all_passed = False
    
    # 7. 显示导出文件片段
    print("\n7. 导出文件内容片段:")
    print("-" * 50)
    lines = content.split('\n')[:25]
    for line in lines:
        print(line)
    print(f"... (共 {len(content.split(chr(10)))} 行)")
    print("-" * 50)
    
    return all_passed


def main():
    success = test_with_sample_html()
    
    print("\n" + "=" * 60)
    if success:
        print("  ✅ 端到端测试通过！")
        print()
        print("  项目使用方式:")
        print("  ----------------")
        print("  1. 运行主程序:")
        print("     python main.py")
        print()
        print("  2. 输入 DeepSeek 分享链接")
        print()
        print("  3. 如果自动抓取失败（WAF 保护），选择:")
        print("     [1] 从文件读取 HTML - 输入 sample_conversation.html 测试")
        print("     [2] 直接粘贴 HTML 内容")
        print()
        print("  4. 浏览消息，选择要导出的内容")
        print()
        print("  5. 按 'e' 导出为 Markdown 文件")
        print()
        print("  导出文件保存在: ./output/ 目录")
    else:
        print("  ❌ 测试失败")
    print("=" * 60)
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
"""
交互式浏览器测试 - 解决 AWS WAF 保护问题
打开真实浏览器让用户手动完成验证，然后自动获取 HTML
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def fetch_with_interactive_browser(url: str) -> str:
    """使用交互式浏览器获取 HTML"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    import time
    
    print("\n" + "=" * 60)
    print("🌐 启动交互式浏览器...")
    print("=" * 60)
    
    options = Options()
    
    # 不使用 headless 模式，显示真实浏览器窗口
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--start-maximized')
    
    # 更真实的 User-Agent
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
    except Exception:
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            print(f"❌ 无法启动浏览器: {e}")
            return None
    
    try:
        # 注入反检测脚本
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
        
        print(f"\n📂 正在访问: {url}")
        driver.get(url)
        
        print("\n" + "=" * 60)
        print("⚠️  重要提示:")
        print("=" * 60)
        print("1. 浏览器窗口已打开")
        print("2. 如果出现验证页面，请手动完成验证")
        print("3. 等待对话内容完全加载（能看到所有消息）")
        print("4. 确认页面完全加载后，回到这里按回车键继续")
        print("=" * 60)
        
        input("\n按回车键继续...")
        
        html = driver.page_source
        driver.quit()
        
        return html
        
    except Exception as e:
        if driver:
            driver.quit()
        print(f"❌ 获取失败: {e}")
        return None


def main():
    print("=" * 60)
    print("  Knotclaw - 交互式浏览器测试")
    print("=" * 60)
    
    url = "https://chat.deepseek.com/share/bz0etehaisvzmm1tlg"
    print(f"\n目标链接: {url}")
    
    # 获取 HTML
    html = fetch_with_interactive_browser(url)
    
    if not html:
        print("\n❌ 获取 HTML 失败")
        return False
    
    print(f"\n✓ 获取成功！HTML 大小: {len(html)} 字符")
    
    # 检查是否有对话数据
    if '__NEXT_DATA__' in html:
        print("✓ 检测到 __NEXT_DATA__")
    else:
        print("⚠️ 未检测到 __NEXT_DATA__，可能页面未完全加载")
    
    # 保存 HTML 到文件
    output_file = Path("fetched_conversation.html")
    output_file.write_text(html, encoding='utf-8')
    print(f"\n📄 HTML 已保存到: {output_file}")
    
    # 尝试解析并导出
    print("\n" + "-" * 40)
    print("正在解析对话内容...")
    
    from src.fetcher import DeepSeekFetcher
    from src.exporter import MarkdownExporter, ExportOptions
    
    fetcher = DeepSeekFetcher()
    
    if not fetcher._has_conversation_data(html):
        print("❌ 未检测到对话数据，无法解析")
        return False
    
    # 设置缓存并解析
    fetcher._cached_html = html
    result = fetcher.fetch_all_metadata(url)
    
    if not result.success:
        print(f"❌ 解析失败: {result.error_message}")
        return False
    
    conversation = result.conversation
    print(f"✓ 对话标题: {conversation.title}")
    print(f"✓ 消息数量: {conversation.total_messages}")
    
    # 加载消息内容
    for msg in conversation.messages:
        if not msg.is_loaded and msg._raw_data_ref:
            content = msg._raw_data_ref.get("content", "")
            if content:
                msg.load_content(content)
    
    # 导出为 Markdown
    exporter = MarkdownExporter(output_dir="./output")
    options = ExportOptions(
        include_metadata=True,
        include_timestamps=True,
        include_token_stats=True,
        include_source_url=True
    )
    
    output_path = exporter.export(conversation, options, filename="real_conversation")
    print(f"\n✅ 导出成功！文件: {output_path}")
    
    # 显示消息预览
    print("\n消息预览:")
    print("-" * 40)
    for i, msg in enumerate(conversation.messages[:5]):
        role = "👤 用户" if msg.role.value == "user" else "🤖 助手"
        content = msg.content[:60] + "..." if msg.content and len(msg.content) > 60 else msg.content
        print(f"[{i+1}] {role}: {content}")
    
    if conversation.total_messages > 5:
        print(f"... 还有 {conversation.total_messages - 5} 条消息")
    
    return True


if __name__ == "__main__":
    success = main()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 测试成功！项目可以正常工作")
    else:
        print("❌ 测试失败")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
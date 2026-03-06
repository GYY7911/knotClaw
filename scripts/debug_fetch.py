"""
调试抓取器
测试DeepSeek页面的实际抓取情况
"""
import sys
import re
import json
from pathlib import Path
from datetime import datetime

# 修复Windows终端编码问题
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 输出目录
OUTPUT_DIR = PROJECT_ROOT / "temp"
OUTPUT_DIR.mkdir(exist_ok=True)


def debug_fetch_with_browser(url: str):
    """使用浏览器抓取（解决WAF验证问题）"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    print(f"正在使用浏览器抓取: {url}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError as e:
        print(f"错误: 缺少依赖 - {e}")
        print("请运行: pip install selenium webdriver-manager")
        return None

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = None
    try:
        print("正在初始化浏览器...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        print(f"正在访问页面...")
        driver.get(url)

        import time
        max_wait = 45
        start_time = time.time()

        # 等待WAF验证通过
        print("等待页面加载...")
        while time.time() - start_time < max_wait:
            html = driver.page_source
            if "AwsWafIntegration" in html or "challenge-container" in html:
                print(f"  WAF验证中... ({int(time.time() - start_time)}s)")
                time.sleep(3)
                continue
            # 检查是否有对话内容出现
            try:
                # 查找对话消息元素
                messages = driver.find_elements(By.CSS_SELECTOR, "[class*='message'], [class*='chat'], [class*='conversation']")
                if messages:
                    print(f"  找到 {len(messages)} 个可能的对话元素 ({int(time.time() - start_time)}s)")
                    break
            except:
                pass
            print(f"  等待对话内容渲染... ({int(time.time() - start_time)}s)")
            time.sleep(3)

        # 额外等待确保内容完全加载
        print("等待内容完全渲染...")
        time.sleep(5)

        # 获取页面HTML
        html = driver.page_source
        print(f"HTML长度: {len(html)} 字符")

        # 尝试从localStorage获取数据
        print("\n尝试从浏览器获取数据...")
        try:
            local_storage = driver.execute_script("""
                var items = {};
                for (var i = 0; i < localStorage.length; i++) {
                    var key = localStorage.key(i);
                    items[key] = localStorage.getItem(key);
                }
                return items;
            """)
            print(f"localStorage中有 {len(local_storage)} 个项目")
            for key in local_storage:
                if 'chat' in key.lower() or 'message' in key.lower() or 'conversation' in key.lower():
                    print(f"  发现相关key: {key}")
        except Exception as e:
            print(f"获取localStorage失败: {e}")

        # 尝试获取React状态
        try:
            react_data = driver.execute_script("""
                // 尝试获取React内部状态
                var root = document.getElementById('__next') || document.body;
                var keys = Object.keys(root);
                for (var key of keys) {
                    if (key.startsWith('__reactInternalInstance') || key.startsWith('__reactFiber')) {
                        return 'Found React instance';
                    }
                }
                return 'No React instance found';
            """)
            print(f"React状态: {react_data}")
        except Exception as e:
            print(f"获取React状态失败: {e}")

        # 保存完整HTML
        debug_file = OUTPUT_DIR / f"deepseek_{timestamp}.html"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(html)

        # 提取并保存对话文本内容
        print("\n提取对话文本内容...")
        try:
            # 获取所有文本内容
            text_content = driver.execute_script("""
                var messages = [];
                // 尝试多种选择器
                var selectors = [
                    "[class*='message-content']",
                    "[class*='MessageContent']",
                    "[class*='chat-message']",
                    "[data-message]",
                    ".markdown-body",
                    "[class*='prose']"
                ];

                for (var sel of selectors) {
                    var els = document.querySelectorAll(sel);
                    if (els.length > 0) {
                        for (var el of els) {
                            var text = el.innerText.trim();
                            if (text.length > 10) {
                                messages.push(text);
                            }
                        }
                        break;
                    }
                }

                // 如果没找到，尝试获取body的所有直接文本
                if (messages.length === 0) {
                    var body = document.body;
                    var allText = body.innerText;
                    messages.push(allText);
                }

                return messages;
            """)

            if text_content:
                text_file = OUTPUT_DIR / f"deepseek_{timestamp}.txt"
                with open(text_file, 'w', encoding='utf-8') as f:
                    for i, text in enumerate(text_content):
                        f.write(f"=== 消息 {i+1} ===\n")
                        f.write(text)
                        f.write("\n\n")
                print(f"文本内容已保存到: {text_file}")
                print(f"共提取 {len(text_content)} 条消息")
            else:
                print("未能提取到文本内容")

        except Exception as e:
            print(f"提取文本失败: {e}")

        # 验证保存的文件
        print(f"\n" + "=" * 60)
        print("文件保存验证:")
        print(f"  HTML文件: {debug_file}")
        print(f"  文件大小: {debug_file.stat().st_size / 1024:.2f} KB")

        # 检查是否包含对话内容
        with open(debug_file, 'r', encoding='utf-8') as f:
            saved_content = f.read()

        # 查找对话内容标记
        content_markers = ['OpenClaw', 'pnpm', '镜像源', '解决方案']
        found_markers = [m for m in content_markers if m in saved_content]
        print(f"  包含的对话标记: {found_markers}")

        if found_markers:
            print(f"\n[OK] 成功获取到对话内容!")
        else:
            print(f"\n[WARNING] 可能未获取到完整对话内容")

        return html

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        if driver:
            driver.quit()
            print("\n浏览器已关闭")


def analyze_html_file(file_path: str = None):
    """分析保存的HTML文件"""
    if file_path is None:
        # 查找最新的HTML文件
        html_files = list(OUTPUT_DIR.glob("deepseek_*.html"))
        if html_files:
            file_path = max(html_files, key=lambda f: f.stat().st_mtime)
        else:
            print("未找到任何HTML文件")
            return
    else:
        file_path = Path(file_path)

    if not file_path.exists():
        print(f"文件不存在: {file_path}")
        return

    print(f"分析文件: {file_path}")
    print("=" * 60)

    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()

    print(f"文件大小: {len(html)} 字符")

    # 提取meta标签中的对话描述
    og_desc = re.search(r'<meta property="og:description" content="([^"]*)"', html)
    if og_desc:
        desc = og_desc.group(1)
        print(f"\n从og:description提取的内容预览:")
        print(f"  {desc[:500]}...")

    # 查找可能的JSON数据
    json_patterns = [
        (r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', 'window.__INITIAL_STATE__'),
        (r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', '__NEXT_DATA__'),
    ]

    for pattern, name in json_patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            print(f"\n找到 {name}")
            try:
                data = json.loads(match.group(1))
                print(f"  JSON顶层键: {list(data.keys())[:10]}")
            except:
                print(f"  JSON解析失败")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="调试抓取器")
    parser.add_argument("--browser", "-b", action="store_true", help="使用浏览器模式")
    parser.add_argument("--analyze", "-a", action="store_true", help="分析已保存的HTML文件")
    parser.add_argument("--url", "-u", default="https://chat.deepseek.com/share/bz0etehaisvzmm1tlg", help="要抓取的URL")
    args = parser.parse_args()

    if args.analyze:
        analyze_html_file()
    elif args.browser:
        print(f"使用测试URL: {args.url}")
        print()
        debug_fetch_with_browser(args.url)
    else:
        print("请使用 --browser 或 --analyze 参数")
        print("  python debug_fetch.py --browser  # 使用浏览器获取内容")
        print("  python debug_fetch.py --analyze  # 分析已保存的HTML")

    print("\n" + "=" * 60)
    print("提示: 输出文件保存在 temp/ 文件夹，文件名带时间戳")
    print("=" * 60)

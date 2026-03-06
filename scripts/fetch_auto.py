"""
获取 DeepSeek 对话并自动保存 - 自动等待版本
自动检测页面加载完成，无需手动操作
"""
import sys
import time
import re
import json
from pathlib import Path
from datetime import datetime


def fetch_and_save_automatically(url: str, wait_time: int = 30) -> dict:
    """自动获取并保存，带有超时等待"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    results = {
        'success': False,
        'html_length': 0,
        'has_next_data': False,
        'has_conversation': False,
        'files_saved': [],
        'error': None
    }
    
    print("\n" + "=" * 70)
    print("🌐 启动浏览器...")
    print("=" * 70)
    
    options = Options()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--start-maximized')
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
            results['error'] = f"无法启动浏览器: {e}"
            print(f"❌ {results['error']}")
            return results
    
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
        
        print(f"\n⏳ 等待页面加载 ({wait_time} 秒)...")
        print("   如果出现验证页面，请在浏览器中手动完成验证")
        print("   脚本会自动继续...")
        
        # 等待并检测页面加载
        start_time = time.time()
        last_html_len = 0
        stable_count = 0
        
        while time.time() - start_time < wait_time:
            time.sleep(2)
            current_html = driver.page_source
            current_len = len(current_html)
            
            elapsed = int(time.time() - start_time)
            print(f"   [{elapsed}s] HTML 大小: {current_len:,} 字符", end="")
            
            # 检查是否有 __NEXT_DATA__
            has_next = '__NEXT_DATA__' in current_html
            if has_next:
                print(" ✅ 检测到对话数据!")
            else:
                print("")
            
            # 如果页面大小稳定，提前结束
            if current_len == last_html_len and current_len > 1000:
                stable_count += 1
                if stable_count >= 3:
                    print(f"\n   页面已稳定，提前结束等待")
                    break
            else:
                stable_count = 0
            
            last_html_len = current_len
        
        # 获取最终HTML
        print("\n📥 正在获取页面内容...")
        html = driver.page_source
        current_url = driver.current_url
        print(f"   当前 URL: {current_url}")
        
        # 截图
        output_dir = Path("deepseek_output")
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        screenshot_file = output_dir / f"screenshot_{timestamp}.png"
        driver.save_screenshot(str(screenshot_file))
        print(f"📸 截图: {screenshot_file.name}")
        
        driver.quit()
        
        # 分析并保存
        results['html_length'] = len(html)
        results['has_next_data'] = '__NEXT_DATA__' in html
        
        # 保存原始HTML
        html_file = output_dir / f"raw_{timestamp}.html"
        html_file.write_text(html, encoding='utf-8')
        results['files_saved'].append(('原始HTML', html_file))
        print(f"\n✅ 原始HTML已保存: {html_file.name} ({len(html):,} 字符)")
        
        # 提取并保存 __NEXT_DATA__
        if results['has_next_data']:
            match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
            if match:
                try:
                    json_str = match.group(1)
                    data = json.loads(json_str)
                    
                    json_file = output_dir / f"next_data_{timestamp}.json"
                    json_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                    results['files_saved'].append(('Next.js数据', json_file))
                    print(f"✅ Next.js数据已保存: {json_file.name}")
                    
                    # 检查对话内容
                    props = data.get('props', {})
                    page_props = props.get('pageProps', {})
                    
                    if 'chat' in page_props or 'conversation' in page_props or 'messages' in str(page_props):
                        results['has_conversation'] = True
                        print("✅ 检测到对话内容!")
                        
                        # 尝试提取消息
                        chat_data = page_props.get('chat', {})
                        messages = chat_data.get('messages', [])
                        if messages:
                            print(f"✅ 发现 {len(messages)} 条消息")
                        
                except json.JSONDecodeError as e:
                    print(f"⚠️ JSON解析失败: {e}")
        
        # 提取可见文本
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            for element in soup(['script', 'style', 'head', 'title', 'meta', 'noscript']):
                element.decompose()
            
            visible_text = soup.get_text(separator='\n', strip=True)
            
            text_file = output_dir / f"visible_text_{timestamp}.txt"
            text_file.write_text(visible_text, encoding='utf-8')
            results['files_saved'].append(('可见文本', text_file))
            print(f"✅ 可见文本已保存: {text_file.name} ({len(visible_text):,} 字符)")
            
            # 显示预览
            print(f"\n📄 可见文本预览 (前 500 字符):")
            print("-" * 50)
            print(visible_text[:500])
            if len(visible_text) > 500:
                print("...")
            print("-" * 50)
            
            # 如果有较多可见文本，也算成功
            if len(visible_text) > 200:
                results['has_conversation'] = True
                
        except ImportError:
            print("⚠️ BeautifulSoup 未安装，跳过文本提取")
        
        results['success'] = True
        
    except Exception as e:
        results['error'] = str(e)
        print(f"❌ 错误: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    return results


def main():
    print("=" * 70)
    print("🚀 DeepSeek 对话获取工具 - 自动保存版")
    print("=" * 70)
    
    url = "https://chat.deepseek.com/share/bz0etehaisvzmm1tlg"
    print(f"\n📋 目标链接: {url}")
    
    # 设置等待时间
    wait_time = 45  # 默认45秒
    print(f"\n将等待 {wait_time} 秒让页面完全加载")
    print("如果页面加载快，会提前完成")
    
    # 执行获取
    results = fetch_and_save_automatically(url, wait_time)
    
    # 显示结果
    print("\n" + "=" * 70)
    print("📊 结果汇总")
    print("=" * 70)
    
    print(f"\n状态: {'✅ 成功' if results['success'] else '❌ 失败'}")
    print(f"HTML大小: {results['html_length']:,} 字符")
    print(f"包含__NEXT_DATA__: {'是' if results['has_next_data'] else '否'}")
    print(f"检测到对话: {'是 ✅' if results['has_conversation'] else '否 ⚠️'}")
    
    if results['error']:
        print(f"错误: {results['error']}")
    
    print(f"\n📁 保存的文件:")
    output_dir = Path("deepseek_output").absolute()
    print(f"   文件夹: {output_dir}")
    
    for file_type, file_path in results['files_saved']:
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"   - [{file_type}] {file_path.name} ({size:,} bytes)")
    
    if results['has_conversation']:
        print("\n✅ 成功获取对话内容!")
        print(f"请检查 {output_dir} 中的文件")
    else:
        print("\n⚠️ 可能未获取到有效内容")
        print("请检查保存的文件和截图")
    
    print("\n" + "=" * 70)
    return results['success']


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n已取消")
        sys.exit(1)
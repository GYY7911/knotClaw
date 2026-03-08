"""
调试脚本 - 手动验证后自动提取
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def debug_fetch(url):
    print("=" * 50)
    print("DeepSeek 调试脚本")
    print("=" * 50)

    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        print(f"\n[1] 打开URL...")
        driver.get(url)

        print("\n[2] 请在浏览器中完成验证（如需要）...")
        print("    等待页面加载（自动检测消息元素）...")
        time.sleep(8)  # Auto-wait for page to load

        print("\n[3] 执行JavaScript提取...")

        # 先检查页面元素
        check_js = """
        return {
            ds_message: document.querySelectorAll('.ds-message').length,
            ds_markdown: document.querySelectorAll('.ds-markdown').length,
            ds_think: document.querySelectorAll('.ds-think-content').length
        };
        """
        counts = driver.execute_script(check_js)
        print(f"    找到 ds-message: {counts['ds_message']}")
        print(f"    找到 ds-markdown: {counts['ds_markdown']}")
        print(f"    找到 ds-think-content: {counts['ds_think']}")

        # 提取消息 - 使用容器结构正确识别角色
        extract_js = """
        var result = [];
        var msgContainers = document.querySelectorAll('.ds-message');

        for (var i = 0; i < msgContainers.length; i++) {
            var container = msgContainers[i];
            var markdown = container.querySelector('.ds-markdown');
            var thinkContent = container.querySelector('.ds-think-content');

            if (!markdown) {
                // No markdown = user message
                var userText = (container.innerText || '').trim();
                if (userText.length >= 2 && userText.indexOf('One more step') < 0) {
                    result.push({
                        role: 'user',
                        content: userText,
                        isThinking: false
                    });
                }
            } else {
                // Has markdown = assistant message
                // Extract thinking first
                if (thinkContent) {
                    var thinkText = (thinkContent.innerText || '').trim();
                    if (thinkText.length >= 10) {
                        result.push({
                            role: 'assistant',
                            content: thinkText,
                            isThinking: true
                        });
                    }
                }

                // Extract answer (not in think-content)
                var answerText = '';
                var allMd = container.querySelectorAll('.ds-markdown');
                for (var j = 0; j < allMd.length; j++) {
                    var parent = allMd[j].parentElement;
                    var inThink = false;
                    while (parent && parent !== container) {
                        if (parent.classList && parent.classList.contains('ds-think-content')) {
                            inThink = true;
                            break;
                        }
                        parent = parent.parentElement;
                    }
                    if (!inThink) {
                        answerText = (allMd[j].innerText || '').trim();
                        break;
                    }
                }

                if (answerText.length >= 5 && answerText.indexOf('One more step') < 0) {
                    result.push({
                        role: 'assistant',
                        content: answerText,
                        isThinking: false
                    });
                }
            }
        }

        return result;
        """

        raw_messages = driver.execute_script(extract_js)

        # Clean up UI text
        messages = []
        if raw_messages:
            for i, msg_data in enumerate(raw_messages):
                content = msg_data.get('content', '')
                if content and len(content) >= 5:
                    # Remove "该对话来自分享..." prefix
                    if '该对话来自分享' in content:
                        lines = content.split('\n')
                        content = '\n'.join([l for l in lines if '该对话来自分享' not in l and not l.startswith('已思考') and not l.startswith('已阅读')])
                    content = content.strip()
                    if content and len(content) >= 5:
                        messages.append({
                            'role': msg_data.get('role', 'assistant'),
                            'content': content,
                            'isThinking': msg_data.get('isThinking', False)
                        })

        print(f"\n[4] 提取结果 ({len(messages) if messages else 0} 条):")
        print("-" * 50)

        if messages:
            for i, msg in enumerate(messages):
                content = msg.get('content', '')
                print(f"\n消息{i}:")
                print(f"  role: {msg.get('role')}")
                print(f"  isThinking: {msg.get('isThinking')}")
                preview = content[:150] + '...' if len(content) > 150 else content
                print(f"  content: {preview}")
        else:
            print("  未提取到消息!")

        # 保存HTML
        with open("temp/debug_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"\n[5] HTML已保存到 temp/debug_page.html")

        print("\n按回车关闭浏览器...")
        input()

    finally:
        driver.quit()

if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else input("请输入DeepSeek分享URL: ").strip()
    if url:
        debug_fetch(url)

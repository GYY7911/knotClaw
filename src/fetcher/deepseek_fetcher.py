"""
DeepSeek对话抓取器
支持从 chat.deepseek.com 抓取分享的对话
使用浏览器自动化获取渲染后的页面内容
"""
import re
import json
import urllib.request
import urllib.error
import sys
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from .base_fetcher import BaseFetcher, FetchResult
from ..models import Conversation, Message, MessageRole


from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


class DeepSeekFetcher(BaseFetcher):
    """
    DeepSeek对话抓取器
    使用浏览器自动化获取渲染后的页面内容
    """

    SUPPORTED_DOMAINS = ["chat.deepseek.com", "deepseek.com"]

    def __init__(self, page_size: int = 10, timeout: int = 30):
        super().__init__(page_size)
        self.timeout = timeout
        self._cached_html: str = ""
        self._parsed_data: Dict[str, Any] = {}
        self._driver = None

        self._current_url = ""

    @classmethod
    def can_handle(cls, url: str) -> bool:
        return any(domain in url for domain in cls.SUPPORTED_DOMAINS) and "/share/" in url

    def _init_driver(self):
        """初始化浏览器驱动"""
        if self._driver:
            return

        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager
        except ImportError as e:
            print(f"  缺少依赖: {e}")
            print("  请安装: pip install selenium webdriver-manager")
            return

        options = Options()
        # 不使用headless模式，让用户可以看到并操作浏览器完成验证
        # options.add_argument("--headless=new")  # 注释掉headless
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        service = Service(ChromeDriverManager().install())
        self._driver = webdriver.Chrome(service=service, options=options)
        print("  浏览器已打开，如需验证请在浏览器中完成")

    def _close_driver(self):
        """关闭浏览器"""
        if self._driver:
            self._driver.quit()
            self._driver = None

    def _fetch_html(self, url: str) -> str:
        """获取HTML内容"""
        if self._cached_html:
            return self._cached_html

        print(f"\n正在获取页面内容...")
        self._current_url = url

        # 使用浏览器获取
        html = self._fetch_with_browser(url)

        if not html:
            raise ConnectionError("无法获取页面内容")

        self._cached_html = html
        return html

    def _fetch_with_browser(self, url: str) -> Optional[str]:
        """使用浏览器获取页面"""
        try:
            self._init_driver()
            print("  启动浏览器...")
            self._driver.get(url)

            # 等待WAF验证和页面加载 - 增加等待时间
            max_wait = 120  # 增加到2分钟
            start_time = time.time()

            while time.time() - start_time < max_wait:
                html = self._driver.page_source

                # 检测各种验证页面
                if "AwsWafIntegration" in html or "challenge-container" in html:
                    elapsed = int(time.time() - start_time)
                    print(f"  WAF验证中... ({elapsed}s) 请在浏览器窗口中完成验证")
                    time.sleep(3)
                    continue

                # 检测CAPTCHA验证
                if "CAPTCHA" in html or "验证" in html or "拼图" in html or "JavaScript is disabled" in html:
                    elapsed = int(time.time() - start_time)
                    print(f"  需要真人验证! ({elapsed}s) 请在浏览器窗口中完成验证后等待...")
                    time.sleep(5)
                    continue

                # 检查是否有对话元素
                try:
                    elements = self._driver.find_elements("css selector", ".ds-message, .ds-markdown")
                    if elements:
                        print(f"  页面加载完成! 找到{len(elements)}个消息元素 ({int(time.time() - start_time)}s)")
                        break
                except:
                    pass

                time.sleep(2)

            html = self._driver.page_source
            print(f"  HTML长度: {len(html)} 字符")

            # 保存HTML供调试
            temp_file = Path("temp") / "deepseek_page.html"
            temp_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file.write_text(html, encoding='utf-8')
            print(f"  HTML已保存到: {temp_file}")

            return html

        except Exception as e:
            print(f"  浏览器获取失败: {e}")
            return None

    def _extract_messages_with_selenium(self) -> List[Dict]:
        """使用Selenium从渲染后的页面提取消息 - 简化版"""
        messages = []

        try:
            # 先保存HTML到本地
            html = self._driver.page_source
            temp_file = Path("temp") / "deepseek_page.html"
            temp_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file.write_text(html, encoding="utf-8")
            print(f"  HTML已保存: {len(html)} 字符")

            # 提取逻辑：从ds-message容器中识别用户和助手消息
            js_script = """
            var result = [];
            var msgContainers = document.querySelectorAll('.ds-message');

            for (var i = 0; i < msgContainers.length; i++) {
                var container = msgContainers[i];
                var markdown = container.querySelector('.ds-markdown');
                var thinkContent = container.querySelector('.ds-think-content');

                if (!markdown) {
                    // 没有ds-markdown -> 用户消息
                    var userText = (container.innerText || '').trim();
                    if (userText.length >= 2 && userText.indexOf('One more step') < 0) {
                        result.push({
                            role: 'user',
                            content: userText,
                            isThinking: false
                        });
                    }
                } else {
                    // 有ds-markdown -> 助手消息
                    // 先提取思考内容
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

                    // 再提取回答内容（排除思考部分）
                    var answerText = '';
                    var allMd = container.querySelectorAll('.ds-markdown');
                    for (var j = 0; j < allMd.length; j++) {
                        // 检查这个markdown是否在think-content内
                        var parent = allMd[j].parentElement;
                        var inThink = false;
                        while (parent && parent !== container) {
                            if (parent.classList.contains('ds-think-content')) {
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

                    if (answerText.length >= 5) {
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

            raw_messages = self._driver.execute_script(js_script)
            print(f"  JavaScript提取到 {len(raw_messages) if raw_messages else 0} 条消息")

            if raw_messages:
                for i, msg_data in enumerate(raw_messages):
                    content = msg_data.get("content", "")
                    if content and len(content) >= 5:
                        # Clean up UI text from content
                        # Remove "该对话来自分享..." prefix
                        if "该对话来自分享" in content:
                            lines = content.split("\n")
                            content = "\n".join([l for l in lines if "该对话来自分享" not in l and "AI 生成" not in l and "甄别" not in l])
                        # Remove "已思考" and "已阅读" prefixes from thinking
                        if msg_data.get("isThinking"):
                            lines = content.split("\n")
                            content = "\n".join([l for l in lines if not l.startswith("已思考") and not l.startswith("已阅读")])
                        content = content.strip()

                        if content and len(content) >= 5:
                            messages.append({
                                "id": f"msg_{i}",
                                "role": msg_data.get("role", "assistant"),
                                "content": content,
                                "timestamp": None,
                                "metadata": {"isThinking": msg_data.get("isThinking", False)}
                            })

            print(f"  最终提取到 {len(messages)} 条消息 (用户: {sum(1 for m in messages if m['role']=='user')}, 助手: {sum(1 for m in messages if m['role']=='assistant')})")

        except Exception as e:
            print(f"  Selenium提取失败: {e}")
            import traceback
            traceback.print_exc()

        return messages

    def _extract_with_beautifulsoup(self) -> List[Dict]:
        """使用BeautifulSoup的备选提取方法"""
        messages = []
        try:
            from bs4 import BeautifulSoup
            import re as regex

            html = self._driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            # 查找所有包含markdown的元素
            all_markdown = soup.find_all(class_='ds-markdown')

            # 查找所有可能的消息容器
            all_containers = soup.find_all('div', class_=regex.compile(r'.{6,}'))

            thinking_keywords = ['嗯，', '用户是', '我们被问到', '我计划', '看搜索结果']

            def is_thinking(text):
                if not text or len(text) < 30:
                    return False
                first_100 = text[:100]
                return any(kw in first_100 for kw in thinking_keywords)

            all_messages = []
            order = 0

            # 从markdown元素提取助手消息
            for md in all_markdown:
                text = md.get_text(strip=True)
                if len(text) >= 20 and not is_thinking(text):
                    all_messages.append({
                        "role": "assistant",
                        "content": text,
                        "order": order
                    })
                    order += 1

            # 尝试识别用户消息
            for container in all_containers:
                text = container.get_text(strip=True)
                # 用户消息通常较短且没有markdown
                if len(text) >= 10 and len(text) < 2000:
                    if not container.find(class_='ds-markdown'):
                        if '该对话来自分享' not in text:
                            all_messages.append({
                                "role": "user",
                                "content": text,
                                "order": order
                            })
                            order += 1

            # 按order排序并去重
            all_messages.sort(key=lambda x: x["order"])

            seen = set()
            for msg in all_messages:
                key = msg["role"] + ":" + msg["content"][:50]
                if key not in seen:
                    seen.add(key)
                    messages.append({
                        "id": f"msg_{len(messages)}",
                        "role": msg["role"],
                        "content": msg["content"],
                        "timestamp": None,
                        "metadata": {}
                    })

        except Exception as e:
            print(f"  BeautifulSoup提取失败: {e}")

        return messages

    def _parse_html(self, html: str) -> Dict[str, Any]:
        """解析HTML提取对话数据"""
        if self._parsed_data:
            return self._parsed_data

        result = {
            "title": "DeepSeek 对话",
            "messages": [],
            "metadata": {}
        }

        # 提取标题
        title_match = re.search(r'<title>([^<]+)</title>', html)
        if title_match:
            title = title_match.group(1).strip()
            if "DeepSeek" in title:
                # 从og:title获取更好的标题
                og_title = re.search(r'<meta property="og:title" content="([^"]*)"', html)
                if og_title:
                    result["title"] = og_title.group(1).strip()
            else:
                result["title"] = title

        # 使用Selenium提取消息（如果有driver）
        if self._driver:
            messages = self._extract_messages_with_selenium()
            if messages:
                result["messages"] = messages
                self._parsed_data = result
                return result

        # 备选：从HTML文本提取
        text = self._clean_html_content(html)
        if text and len(text) > 100:
            # 按段落分割
            paragraphs = re.split(r'\n\s*\n', text)
            current_role = "user"
            messages = []

            for para in paragraphs:
                para = para.strip()
                if not para or len(para) < 20:
                    continue

                # 跳过导航和无关内容
                if any(skip in para.lower() for skip in ['登录', '注册', 'deepseek', '探索', '设置', '帮助']):
                    continue

                messages.append({
                    "id": f"msg_{len(messages)}",
                    "role": current_role,
                    "content": para,
                    "timestamp": None,
                    "metadata": {}
                })
                current_role = "assistant" if current_role == "user" else "user"

                if len(messages) > 50:  # 限制数量
                    break

            result["messages"] = messages

        self._parsed_data = result
        return result

    def _clean_html_content(self, html: str) -> str:
        """清理HTML内容，提取纯文本"""
        # 移除script和style标签
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL)

        # 将br和p标签转换为换行
        html = re.sub(r'<br\s*/?>', '\n', html)
        html = re.sub(r'</p>', '\n', html)
        html = re.sub(r'</div>', '\n', html)

        # 移除所有其他HTML标签
        html = re.sub(r'<[^>]+>', '', html)

        # 解码HTML实体
        import html as html_module
        html = html_module.unescape(html)

        # 清理多余空白
        html = re.sub(r'\n\s*\n', '\n\n', html)
        html = html.strip()

        return html

    def fetch_page(self, url: str, page: int = 0) -> FetchResult:
        """抓取指定页的消息"""
        try:
            html = self._fetch_html(url)
            data = self._parse_html(html)

            all_messages = data.get("messages", [])
            start = page * self.page_size
            end = start + self.page_size

            if start >= len(all_messages):
                return FetchResult(
                    success=False,
                    error_message="已到达最后一页"
                )

            page_messages = all_messages[start:end]

            messages = []
            for i, msg_data in enumerate(page_messages):
                msg = self._create_message_from_raw(msg_data, start + i, load_content=True)
                messages.append(msg)

            conversation = Conversation(
                id="",
                title=data.get("title", "未命名对话"),
                source_url=url,
                messages=messages,
                total_messages=len(all_messages),
                loaded_range=(start, end),
                metadata=data.get("metadata", {})
            )

            return FetchResult(
                success=True,
                conversation=conversation,
                raw_data={"page": page, "total": len(all_messages)}
            )

        except Exception as e:
            return FetchResult(
                success=False,
                error_message=str(e)
            )

    def fetch_all_metadata(self, url: str) -> FetchResult:
        """抓取所有消息的元数据"""
        try:
            html = self._fetch_html(url)
            data = self._parse_html(html)

            all_messages = data.get("messages", [])

            messages = []
            for i, msg_data in enumerate(all_messages):
                content = msg_data.get("content", "")
                summary = content[:100] + "..." if len(content) > 100 else content

                msg = Message(
                    id=msg_data.get("id", f"msg_{i}"),
                    role=MessageRole.USER if msg_data.get("role") == "user" else MessageRole.ASSISTANT,
                    content=content,
                    summary=summary,
                    timestamp=self._parse_timestamp(msg_data.get("timestamp")),
                    metadata=msg_data.get("metadata", {}),
                    _raw_data_ref=msg_data
                )
                messages.append(msg)

            conversation = Conversation(
                id="",
                title=data.get("title", "未命名对话"),
                source_url=url,
                messages=messages,
                total_messages=len(all_messages),
                loaded_range=(0, len(all_messages)),
                metadata=data.get("metadata", {})
            )

            return FetchResult(
                success=True,
                conversation=conversation
            )

        except Exception as e:
            return FetchResult(
                success=False,
                error_message=str(e)
            )

    def load_message_content(self, message_id: str) -> Optional[str]:
        """加载指定消息的完整内容"""
        for msg_data in self._parsed_data.get("messages", []):
            if msg_data.get("id") == message_id:
                return msg_data.get("content", "")
        return None

    def clear_cache(self) -> None:
        """清除缓存"""
        self._cached_html = ""
        self._parsed_data = {}
        self._close_driver()

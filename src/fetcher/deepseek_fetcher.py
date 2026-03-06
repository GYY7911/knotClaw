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
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        service = Service(ChromeDriverManager().install())
        self._driver = webdriver.Chrome(service=service, options=options)

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

            # 等待WAF验证和页面加载
            max_wait = 45
            start_time = time.time()

            while time.time() - start_time < max_wait:
                html = self._driver.page_source

                if "AwsWafIntegration" in html or "challenge-container" in html:
                    print(f"  WAF验证中... ({int(time.time() - start_time)}s)")
                    time.sleep(3)
                    continue

                # 检查是否有对话元素
                try:
                    elements = self._driver.find_elements("css selector", "[class*='message'], [class*='chat']")
                    if elements:
                        print(f"  页面加载完成! ({int(time.time() - start_time)}s)")
                        break
                except:
                    pass

                time.sleep(2)

            html = self._driver.page_source
            print(f"  HTML长度: {len(html)} 字符")
            return html

        except Exception as e:
            print(f"  浏览器获取失败: {e}")
            return None

    def _extract_messages_with_selenium(self) -> List[Dict]:
        """使用Selenium从渲染后的页面提取消息"""
        messages = []

        try:
            # 使用BeautifulSoup解析HTML (比JavaScript更可靠)
            from bs4 import BeautifulSoup
            import re as regex

            html = self._driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            # 查找所有用户消息 (class包含fbb737a4)
            user_msgs = soup.find_all(class_=regex.compile('fbb737a4'))

            # 查找所有助手消息容器 (class包含_74c0879)
            asst_containers = soup.find_all(class_=regex.compile('_74c0879'))

            # 构建消息列表，交替排列
            all_messages = []

            # 思考过程的特征关键词
            thinking_keywords = [
                '嗯，用户', '我计划从', '看搜索结果', '用户是', '准备结合',
                '我们被问到', '我们被问到的是', '我们正在帮助', '我们需要',
                '这是一个典型的', '从技术角度来说', '根据上下文',
                '结合之前的对话', '先看看搜索', '看看搜索结果',
            ]

            def is_thinking_content(text):
                """检查是否是思考过程内容"""
                if not text:
                    return True
                text_lower = text.lower()
                for kw in thinking_keywords:
                    if kw in text[:150]:
                        return True
                # 额外检查：如果开头是第一人称分析，很可能是思考
                first_50 = text[:50]
                if any(word in first_50 for word in ['嗯，', '分析', '判断', '推断', '考虑']):
                    return True
                return False

            max_len = max(len(user_msgs), len(asst_containers))

            for i in range(max_len):
                # 添加用户消息
                if i < len(user_msgs):
                    text = user_msgs[i].get_text(strip=True)
                    # 跳过提示文字和代码块输出
                    if text and not text.startswith('该对话来自分享') and not text.startswith('由 AI 生成'):
                        # 检查是否是代码输出（通常是路径或命令结果）
                        if len(text) >= 10:
                            all_messages.append({
                                "role": "user",
                                "content": text,
                                "order": i * 2
                            })

                # 添加助手消息
                if i < len(asst_containers):
                    container = asst_containers[i]
                    # 获取ds-markdown元素
                    markdowns = container.find_all(class_='ds-markdown')

                    # 找到第一个非思考过程的markdown
                    for md in markdowns:
                        text = md.get_text(strip=True)
                        if len(text) >= 20 and not is_thinking_content(text):
                            all_messages.append({
                                "role": "assistant",
                                "content": text,
                                "order": i * 2 + 1
                            })
                            break

            # 按order排序
            all_messages.sort(key=lambda x: x["order"])

            # 转换为最终格式
            for i, msg in enumerate(all_messages):
                messages.append({
                    "id": f"msg_{i}",
                    "role": msg["role"],
                    "content": msg["content"],
                    "timestamp": None,
                    "metadata": {}
                })

            print(f"  提取到 {len(messages)} 条消息 (用户: {sum(1 for m in messages if m['role']=='user')}, 助手: {sum(1 for m in messages if m['role']=='assistant')})")

        except ImportError:
            print("  BeautifulSoup未安装，回退到JavaScript提取")
            messages = self._extract_with_javascript()
        except Exception as e:
            print(f"  提取消息失败: {e}")
            import traceback
            traceback.print_exc()

        return messages

    def _extract_with_javascript(self) -> List[Dict]:
        """使用JavaScript提取消息的备选方法"""
        messages = []

        try:
            js_script = """
            var result = [];
            var mainArea = document.querySelector('[class*="_9663006"]') || document.body;

            var userMsgs = mainArea.querySelectorAll('[class*="fbb737a4"]');
            var asstContainers = mainArea.querySelectorAll('[class*="_74c0879"]');

            var thinkingKeywords = ['嗯，用户', '我计划从', '看搜索结果', '用户是',
                '我们被问到', '我们正在帮助', '结合之前的对话'];

            function isThinking(text) {
                if (!text) return true;
                for (var i = 0; i < thinkingKeywords.length; i++) {
                    if (text.substring(0, 150).includes(thinkingKeywords[i])) {
                        return true;
                    }
                }
                return false;
            }

            var maxLen = Math.max(userMsgs.length, asstContainers.length);

            for (var i = 0; i < maxLen; i++) {
                if (i < userMsgs.length) {
                    var text = userMsgs[i].innerText.trim();
                    if (text.length >= 10 && !text.includes('该对话来自分享')) {
                        result.push({role: 'user', content: text, order: i * 2});
                    }
                }
                if (i < asstContainers.length) {
                    var mds = asstContainers[i].querySelectorAll('.ds-markdown');
                    for (var j = 0; j < mds.length; j++) {
                        var mdText = mds[j].innerText.trim();
                        if (mdText.length >= 20 && !isThinking(mdText)) {
                            result.push({role: 'assistant', content: mdText, order: i * 2 + 1});
                            break;
                        }
                    }
                }
            }

            result.sort(function(a, b) { return a.order - b.order; });
            return result;
            """

            raw_messages = self._driver.execute_script(js_script)

            for i, msg_data in enumerate(raw_messages):
                messages.append({
                    "id": f"msg_{i}",
                    "role": msg_data.get("role", "assistant"),
                    "content": msg_data.get("content", ""),
                    "timestamp": None,
                    "metadata": {}
                })

        except Exception as e:
            print(f"  JavaScript提取失败: {e}")

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

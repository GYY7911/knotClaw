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
import logging
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Generator
from datetime import datetime
from pathlib import Path

from .base_fetcher import BaseFetcher, FetchResult
from ..models import Conversation, Message, MessageRole


# 配置日志
logger = logging.getLogger(__name__)

# Selenium 相关导入（延迟导入以避免强制依赖）
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    webdriver = None
    Options = None
    Service = None
    ChromeDriverManager = None


# 配置常量
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_WAIT = 60  # WAF 验证最大等待时间（秒）- 从120减少
DEFAULT_PAGE_LOAD_WAIT = 0.5  # 页面加载轮询间隔（秒）- 从2秒减少
DEFAULT_WAF_CHECK_INTERVAL = 1  # WAF验证检查间隔（秒）
CACHE_HTML_PATH = Path(".cache") / "debug" / "deepseek" / "deepseek_page.html"


class DeepSeekFetcher(BaseFetcher):
    """
    DeepSeek对话抓取器
    使用浏览器自动化获取渲染后的页面内容

    支持上下文管理器协议，确保资源正确释放：
        with DeepSeekFetcher() as fetcher:
            result = fetcher.fetch_all_metadata(url)
    """

    SUPPORTED_DOMAINS = ["chat.deepseek.com", "deepseek.com"]

    def __init__(self, page_size: int = 10, timeout: int = DEFAULT_TIMEOUT):
        """
        初始化抓取器

        Args:
            page_size: 分页大小
            timeout: 超时时间（秒）
        """
        super().__init__(page_size)
        self.timeout = timeout
        self._cached_html: str = ""
        self._parsed_data: Dict[str, Any] = {}
        self._driver = None
        self._current_url = ""

        if not SELENIUM_AVAILABLE:
            logger.warning(
                "Selenium 未安装，浏览器自动化功能不可用。"
                "请运行: pip install selenium webdriver-manager"
            )

    def __enter__(self) -> "DeepSeekFetcher":
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器退出，确保资源释放"""
        self._close_driver()
        self.clear_cache()

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """检查是否能处理该URL"""
        return any(domain in url for domain in cls.SUPPORTED_DOMAINS) and "/share/" in url

    def _init_driver(self) -> None:
        """
        初始化浏览器驱动

        Raises:
            ImportError: Selenium 未安装
            RuntimeError: 驱动初始化失败
        """
        if self._driver:
            return

        if not SELENIUM_AVAILABLE:
            raise ImportError(
                "Selenium 未安装。请运行: pip install selenium webdriver-manager"
            )

        options = Options()
        # 不使用headless模式，让用户可以看到并操作浏览器完成验证
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        try:
            service = Service(ChromeDriverManager().install())
            self._driver = webdriver.Chrome(service=service, options=options)
            logger.info("浏览器已打开，如需验证请在浏览器中完成")
        except Exception as e:
            logger.error(f"浏览器驱动初始化失败: {e}")
            raise RuntimeError(f"无法初始化浏览器驱动: {e}") from e

    def _close_driver(self) -> None:
        """安全关闭浏览器驱动"""
        if self._driver is not None:
            try:
                self._driver.quit()
                logger.debug("浏览器驱动已关闭")
            except Exception as e:
                logger.warning(f"关闭浏览器驱动时出错: {e}")
            finally:
                self._driver = None

    @contextmanager
    def _get_driver_context(self) -> Generator[Any, None, None]:
        """
        获取浏览器驱动的上下文管理器

        Yields:
            WebDriver 实例
        """
        self._init_driver()
        try:
            yield self._driver
        finally:
            # 注意：这里不关闭 driver，由外层上下文管理器控制
            pass

    def _fetch_html(self, url: str) -> str:
        """
        获取HTML内容

        Args:
            url: 目标URL

        Returns:
            HTML内容字符串

        Raises:
            ConnectionError: 无法获取页面内容
        """
        if self._cached_html:
            return self._cached_html

        logger.info(f"正在获取页面内容...")
        self._current_url = url

        # 使用浏览器获取
        html = self._fetch_with_browser(url)

        if not html:
            raise ConnectionError("无法获取页面内容")

        self._cached_html = html
        return html

    def _fetch_with_browser(self, url: str) -> Optional[str]:
        """
        使用浏览器获取页面

        Args:
            url: 目标URL

        Returns:
            HTML内容，失败返回 None
        """
        try:
            self._init_driver()
            logger.info("  启动浏览器...")
            self._driver.get(url)

            # 等待WAF验证和页面加载
            start_time = time.time()
            last_check_time = 0
            found_elements = False
            waf_detected = False

            while time.time() - start_time < DEFAULT_MAX_WAIT:
                elapsed = time.time() - start_time

                # 每0.5秒检查一次页面状态
                html = self._driver.page_source
                html_len = len(html)

                # 检测各种验证页面（只在特定情况下输出日志）
                is_waf = "AwsWafIntegration" in html or "challenge-container" in html
                is_captcha = "CAPTCHA" in html or "验证" in html or "拼图" in html or "JavaScript is disabled" in html

                if is_waf:
                    if not waf_detected:
                        logger.info(f"  WAF验证中... 请在浏览器窗口中完成验证")
                        waf_detected = True
                    time.sleep(DEFAULT_WAF_CHECK_INTERVAL)
                    continue

                if is_captcha:
                    if not waf_detected:
                        logger.info(f"  需要真人验证! 请在浏览器窗口中完成验证")
                        waf_detected = True
                    time.sleep(DEFAULT_WAF_CHECK_INTERVAL)
                    continue

                waf_detected = False  # 重置WAF检测状态

                # 检查是否有对话元素（优化：减少检测频率）
                if elapsed - last_check_time >= 0.5:
                    last_check_time = elapsed
                    try:
                        # 使用更快的JavaScript检测
                        has_content = self._driver.execute_script(
                            "return document.querySelectorAll('.ds-message, .ds-markdown').length > 0;"
                        )
                        if has_content:
                            found_elements = True
                            element_count = self._driver.execute_script(
                                "return document.querySelectorAll('.ds-message, .ds-markdown').length;"
                            )
                            logger.info(f"  页面加载完成! 找到{element_count}个消息元素 ({elapsed:.1f}s)")
                            break
                    except Exception:
                        pass

                # 如果HTML长度稳定且足够大，可能已经加载完成
                if html_len > 50000 and elapsed > 3 and not found_elements:
                    # 尝试最后一次元素检测
                    try:
                        element_count = self._driver.execute_script(
                            "return document.querySelectorAll('.ds-message, .ds-markdown').length;"
                        )
                        if element_count > 0:
                            logger.info(f"  页面加载完成! 找到{element_count}个消息元素 ({elapsed:.1f}s)")
                            break
                    except Exception:
                        pass

                time.sleep(DEFAULT_PAGE_LOAD_WAIT)

            html = self._driver.page_source
            logger.info(f"  HTML长度: {len(html)} 字符, 耗时: {time.time() - start_time:.1f}s")

            # 保存HTML供调试
            self._save_html_for_debug(html)

            return html

        except Exception as e:
            logger.error(f"  浏览器获取失败: {e}")
            return None

    def _save_html_for_debug(self, html: str) -> None:
        """保存HTML到缓存文件供调试"""
        try:
            CACHE_HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
            CACHE_HTML_PATH.write_text(html, encoding='utf-8')
            logger.debug(f"  HTML已保存到: {CACHE_HTML_PATH}")
        except Exception as e:
            logger.warning(f"保存HTML缓存文件失败: {e}")

    def _extract_messages_with_selenium(self) -> List[Dict]:
        """
        使用Selenium从渲染后的页面提取消息

        Returns:
            消息列表，每条消息包含 id, role, content, timestamp, metadata
        """
        messages = []

        if self._driver is None:
            logger.warning("Driver 未初始化，无法提取消息")
            return messages

        try:
            # 先保存HTML到本地
            html = self._driver.page_source
            self._save_html_for_debug(html)
            logger.debug(f"  HTML已保存: {len(html)} 字符")

            # JavaScript 提取脚本
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
            logger.debug(f"  JavaScript提取到 {len(raw_messages) if raw_messages else 0} 条消息")

            if raw_messages:
                for i, msg_data in enumerate(raw_messages):
                    content = msg_data.get("content", "")
                    if content and len(content) >= 5:
                        # 清理UI文本
                        content = self._clean_message_content(content, msg_data.get("isThinking", False))

                        if content and len(content) >= 5:
                            messages.append({
                                "id": f"msg_{i}",
                                "role": msg_data.get("role", "assistant"),
                                "content": content,
                                "timestamp": None,
                                "metadata": {"isThinking": msg_data.get("isThinking", False)}
                            })

            user_count = sum(1 for m in messages if m['role'] == 'user')
            assistant_count = sum(1 for m in messages if m['role'] == 'assistant')
            logger.info(f"  最终提取到 {len(messages)} 条消息 (用户: {user_count}, 助手: {assistant_count})")

        except Exception as e:
            logger.error(f"  Selenium提取失败: {e}")
            logger.exception("详细错误信息")

        return messages

    def _clean_message_content(self, content: str, is_thinking: bool) -> str:
        """
        清理消息内容中的UI文本

        Args:
            content: 原始内容
            is_thinking: 是否为思考内容

        Returns:
            清理后的内容
        """
        # 移除 "该对话来自分享..." 前缀
        if "该对话来自分享" in content:
            lines = content.split("\n")
            content = "\n".join([
                l for l in lines
                if "该对话来自分享" not in l and "AI 生成" not in l and "甄别" not in l
            ])

        # 移除思考内容中的 "已思考" 和 "已阅读" 前缀
        if is_thinking:
            lines = content.split("\n")
            content = "\n".join([
                l for l in lines
                if not l.startswith("已思考") and not l.startswith("已阅读")
            ])

        # 修复引用标识换行问题
        # 模式1: 修复单独成行的引用数字（如 "1\n-\n4\n-\n8" -> "[1][4][8]"）
        content = self._fix_citation_linebreaks(content)

        # 模式2: 移除"复制"和"下载"按钮文本
        content = re.sub(r'\n复制\n|\n下载\n', ' ', content)
        content = re.sub(r'\n复制$|\n下载$', '', content)

        return content.strip()

    def _fix_citation_linebreaks(self, content: str) -> str:
        """
        修复引用标识被错误换行的问题

        DeepSeek 页面中的引用标识（如 [1]、[2]）在 innerText 提取时
        可能被处理成单独成行的数字。此函数尝试修复这种格式问题。

        Args:
            content: 原始内容

        Returns:
            修复后的内容
        """
        lines = content.split('\n')
        result_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]

            # 检测是否是引用标识模式：单独的数字行，后跟 "-" 行
            # 例如: "1" -> "-" -> "4" -> "-" -> "8"
            if re.match(r'^\d+$', line.strip()):
                citation_nums = [line.strip()]
                j = i + 1

                # 收集连续的 数字-横线 模式
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line == '-':
                        j += 1
                        if j < len(lines) and re.match(r'^\d+$', lines[j].strip()):
                            citation_nums.append(lines[j].strip())
                            j += 1
                        else:
                            break
                    else:
                        break

                # 如果收集到多个数字，合并为引用标识
                if len(citation_nums) > 1:
                    citation_str = ''.join(f'[{n}]' for n in citation_nums)
                    # 追加到前一行的末尾
                    if result_lines:
                        result_lines[-1] = result_lines[-1].rstrip() + citation_str
                    else:
                        result_lines.append(citation_str)
                    i = j
                    continue
                elif len(citation_nums) == 1:
                    # 单个数字，检查前一行是否以 "-" 或特定字符结尾
                    if result_lines and result_lines[-1].rstrip().endswith('-'):
                        # 合并到前一行
                        result_lines[-1] = result_lines[-1].rstrip()[:-1] + f'[{citation_nums[0]}]'
                        i += 1
                        continue

            # 检测行尾的 "-数字" 模式（可能是引用的一部分）
            if result_lines and re.search(r'-\s*$', result_lines[-1]):
                if re.match(r'^\d+$', line.strip()):
                    # 合并
                    result_lines[-1] = re.sub(r'-\s*$', f'[{line.strip()}]', result_lines[-1])
                    i += 1
                    continue

            result_lines.append(line)
            i += 1

        # 清理多余的空行
        cleaned = '\n'.join(result_lines)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        return cleaned

    def _extract_with_beautifulsoup(self) -> List[Dict]:
        """
        使用BeautifulSoup的备选提取方法

        Returns:
            消息列表
        """
        messages = []
        try:
            from bs4 import BeautifulSoup

            html = self._driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            # 查找所有包含markdown的元素
            all_markdown = soup.find_all(class_='ds-markdown')

            # 查找所有可能的消息容器
            all_containers = soup.find_all('div', class_=re.compile(r'.{6,}'))

            thinking_keywords = ['嗯，', '用户是', '我们被问到', '我计划', '看搜索结果']

            def is_thinking(text: str) -> bool:
                """判断是否为思考内容"""
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

        except ImportError:
            logger.warning("BeautifulSoup 未安装，备选提取方法不可用")
        except Exception as e:
            logger.error(f"BeautifulSoup提取失败: {e}")

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
        """清除缓存数据"""
        self._cached_html = ""
        self._parsed_data = {}
        # 注意：不在这里关闭 driver，由上下文管理器控制

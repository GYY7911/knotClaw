"""
Gemini 对话抓取器
支持从 gemini.google.com 抓取分享的对话
使用浏览器自动化获取渲染后的页面内容
"""
import re
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
DEFAULT_MAX_WAIT = 90  # Gemini 可能需要更长等待时间（登录）
DEFAULT_PAGE_LOAD_WAIT = 0.5
DEFAULT_LOGIN_CHECK_INTERVAL = 2
CACHE_HTML_PATH = Path(".cache") / "debug" / "gemini" / "gemini_page.html"


class GeminiFetcher(BaseFetcher):
    """
    Gemini 对话抓取器
    使用浏览器自动化获取渲染后的页面内容

    注意：Gemini 分享页面需要登录才能查看完整内容

    支持上下文管理器协议，确保资源正确释放：
        with GeminiFetcher() as fetcher:
            result = fetcher.fetch_all_metadata(url)
    """

    SUPPORTED_DOMAINS = ["gemini.google.com", "bard.google.com"]

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

    def __enter__(self) -> "GeminiFetcher":
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
        # 不使用 headless 模式，让用户可以登录
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # 尝试使用用户已有的 Chrome 配置文件（保持登录状态）
        # options.add_argument("--user-data-dir=~/.config/google-chrome")

        try:
            service = Service(ChromeDriverManager().install())
            self._driver = webdriver.Chrome(service=service, options=options)
            logger.info("浏览器已打开，如需登录请在浏览器中完成")
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

            # 等待登录和页面加载
            start_time = time.time()
            last_check_time = 0
            found_elements = False
            login_detected = False

            while time.time() - start_time < DEFAULT_MAX_WAIT:
                elapsed = time.time() - start_time

                html = self._driver.page_source
                html_len = len(html)

                # 检测是否需要登录
                is_login_page = (
                    "Sign in" in html or
                    "登录" in html or
                    "accounts.google.com" in self._driver.current_url or
                    "myaccount.google.com" in self._driver.current_url
                )

                if is_login_page:
                    if not login_detected:
                        logger.info(f"  需要登录! 请在浏览器窗口中完成登录")
                        login_detected = True
                    time.sleep(DEFAULT_LOGIN_CHECK_INTERVAL)
                    continue

                login_detected = False  # 重置登录检测状态

                # 检查是否有对话元素
                if elapsed - last_check_time >= 0.5:
                    last_check_time = elapsed
                    try:
                        # Gemini 使用 Angular，检测关键元素
                        has_content = self._driver.execute_script(
                            "return document.querySelectorAll('.message-content, .user-query-container, .response-container').length > 0;"
                        )
                        if has_content:
                            found_elements = True
                            element_count = self._driver.execute_script(
                                "return document.querySelectorAll('.message-content, .user-query-container, .response-container').length;"
                            )
                            logger.info(f"  页面加载完成! 找到{element_count}个消息元素 ({elapsed:.1f}s)")
                            break
                    except Exception:
                        pass

                # 如果 HTML 长度稳定且足够大
                if html_len > 50000 and elapsed > 5 and not found_elements:
                    try:
                        element_count = self._driver.execute_script(
                            "return document.querySelectorAll('.message-content, .user-query-container, .response-container').length;"
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

            # Gemini 页面结构：
            # - .user-query-container: 用户消息（可能有多个嵌套层级）
            # - .response-container: AI 响应
            # - .message-content: 消息内容

            js_script = """
            var result = [];
            var order = 0;

            // 1. 提取用户消息
            var userQueries = document.querySelectorAll('.user-query-container');
            var seenUserText = new Set();

            for (var i = 0; i < userQueries.length; i++) {
                var query = userQueries[i];
                var text = (query.innerText || query.textContent || '').trim();

                // 过滤条件
                if (text.length >= 2 &&
                    text.indexOf('Sign in') < 0 &&
                    !seenUserText.has(text.substring(0, 30))) {

                    seenUserText.add(text.substring(0, 30));
                    result.push({
                        role: 'user',
                        content: text,
                        order: order++
                    });
                }
            }

            // 2. 提取 AI 响应
            var responses = document.querySelectorAll('.response-container');
            var seenResponseText = new Set();

            for (var j = 0; j < responses.length; j++) {
                var resp = responses[j];

                // 跳过 processing 状态
                if (resp.querySelector('.response-container-header-processing-state')) {
                    continue;
                }

                var text = (resp.innerText || resp.textContent || '').trim();

                if (text.length >= 20 &&
                    !seenResponseText.has(text.substring(0, 50))) {

                    seenResponseText.add(text.substring(0, 50));
                    result.push({
                        role: 'assistant',
                        content: text,
                        order: order++
                    });
                }
            }

            // 3. 如果没找到响应，尝试从 message-content 获取
            if (result.filter(function(r) { return r.role === 'assistant'; }).length === 0) {
                var msgContents = document.querySelectorAll('.message-content');
                for (var k = 0; k < msgContents.length; k++) {
                    var mc = msgContents[k];
                    var text = (mc.innerText || mc.textContent || '').trim();
                    if (text.length >= 10) {
                        result.push({
                            role: 'assistant',
                            content: text,
                            order: order++
                        });
                    }
                }
            }

            // 按 order 排序
            result.sort(function(a, b) { return a.order - b.order; });

            return result;
            """

            raw_messages = self._driver.execute_script(js_script)
            logger.debug(f"  JavaScript提取到 {len(raw_messages) if raw_messages else 0} 条消息")

            if raw_messages:
                for i, msg_data in enumerate(raw_messages):
                    content = msg_data.get("content", "")
                    role = msg_data.get("role", "assistant")

                    # 最小长度要求
                    min_len = 2 if role == "user" else 10
                    if content and len(content) >= min_len:
                        # 清理UI文本
                        content = self._clean_message_content(content)

                        if content and len(content) >= min_len:
                            messages.append({
                                "id": f"msg_{i}",
                                "role": role,
                                "content": content,
                                "timestamp": None,
                                "metadata": {}
                            })

            user_count = sum(1 for m in messages if m['role'] == 'user')
            assistant_count = sum(1 for m in messages if m['role'] == 'assistant')
            logger.info(f"  最终提取到 {len(messages)} 条消息 (用户: {user_count}, 助手: {assistant_count})")

        except Exception as e:
            logger.error(f"  Selenium提取失败: {e}")
            logger.exception("详细错误信息")

        return messages

    def _clean_message_content(self, content: str) -> str:
        """
        清理消息内容中的UI文本

        Args:
            content: 原始内容

        Returns:
            清理后的内容
        """
        # 移除可能的 UI 元素文本
        ui_patterns = [
            r'\n复制\n',
            r'\n分享\n',
            r'\n点赞\n',
            r'\n下载\n',
            r'复制的代码',
            r'检查其他回答',
        ]

        for pattern in ui_patterns:
            content = re.sub(pattern, ' ', content)

        # 清理多余空白
        content = re.sub(r'\n{3,}', '\n\n', content)

        return content.strip()

    def _parse_html(self, html: str) -> Dict[str, Any]:
        """解析HTML提取对话数据"""
        if self._parsed_data:
            return self._parsed_data

        result = {
            "title": "Gemini 对话",
            "messages": [],
            "metadata": {}
        }

        # 提取标题
        title_match = re.search(r'<title>([^<]+)</title>', html)
        if title_match:
            title = title_match.group(1).strip()
            if "Gemini" in title:
                # 尝试从 og:title 获取更好的标题
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

        self._parsed_data = result
        return result

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

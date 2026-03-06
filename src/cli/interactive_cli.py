"""
交互式命令行界面
提供用户友好的交互体验，支持分页浏览和选择
"""
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path
from datetime import datetime
import sys
import signal

# 修复Windows终端编码问题
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from ..models import Conversation, Message, MessageRole, Checkpoint, CheckpointStatus
from ..fetcher import FetcherFactory
from ..exporter import MarkdownExporter, ExportOptions
from ..monitor import TokenMonitor, TokenLimitExceeded, CircuitBreaker, CircuitState


class InteractiveCLI:
    """
    交互式命令行界面
    
    提供完整的对话归档工作流：
    1. 输入URL
    2. 抓取并展示对话概要
    3. 分页浏览消息
    4. 选择要保留的消息
    5. 导出为Markdown
    """
    
    # 分页大小
    PAGE_SIZE = 5
    
    # 颜色代码
    COLORS = {
        'reset': '\033[0m',
        'bold': '\033[1m',
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m',
        'white': '\033[97m',
    }
    
    def __init__(
        self,
        output_dir: str = "./output",
        checkpoint_dir: str = "./checkpoints",
        token_limit: int = 100000
    ):
        """
        初始化CLI
        
        Args:
            output_dir: 输出目录
            checkpoint_dir: 断点目录
            token_limit: Token限制
        """
        self.output_dir = Path(output_dir)
        self.checkpoint_dir = Path(checkpoint_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # 组件
        self.exporter = MarkdownExporter(output_dir)
        self.token_monitor = TokenMonitor(
            token_limit=token_limit,
            on_warning=self._on_token_warning,
            on_critical=self._on_token_critical,
            on_exceeded=self._on_token_exceeded
        )
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30,
            on_open=self._on_circuit_open,
            on_close=self._on_circuit_close,
            emergency_backup=self._emergency_backup
        )
        
        # 状态
        self.current_conversation: Optional[Conversation] = None
        self.current_checkpoint: Optional[Checkpoint] = None
        self.selected_indices: List[int] = []
        self.current_page = 0
        self.is_running = True
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._handle_interrupt)
    
    def _color(self, text: str, color: str) -> str:
        """添加颜色"""
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"
    
    def _print(self, text: str = "", color: str = None) -> None:
        """打印文本"""
        if color:
            print(self._color(text, color))
        else:
            print(text)
    
    def _print_header(self) -> None:
        """打印头部"""
        self._print()
        self._print("=" * 60, "cyan")
        self._print("  🐱 Knotclaw - 大模型对话归档客户端", "bold")
        self._print("=" * 60, "cyan")
        self._print()
    
    def _print_separator(self) -> None:
        """打印分隔线"""
        self._print("-" * 60, "cyan")
    
    def _on_token_warning(self, used: int, limit: int) -> None:
        """Token警告回调"""
        percentage = (used / limit) * 100
        self._print(f"\n⚠️  Token使用量已达 {percentage:.1f}% ({used}/{limit})", "yellow")
    
    def _on_token_critical(self, used: int, limit: int) -> None:
        """Token临界回调"""
        percentage = (used / limit) * 100
        self._print(f"\n🔴 Token使用量已达 {percentage:.1f}%，即将触发熔断！", "red")
    
    def _on_token_exceeded(self, used: int, limit: int) -> None:
        """Token超限回调"""
        self._print(f"\n❌ Token超限！已使用 {used}，限制 {limit}", "red")
    
    def _on_circuit_open(self) -> None:
        """熔断器打开回调"""
        self._print("\n⚡ 熔断器已触发，正在执行紧急备份...", "red")
    
    def _on_circuit_close(self) -> None:
        """熔断器关闭回调"""
        self._print("\n✅ 熔断器已恢复", "green")
    
    def _emergency_backup(self, data: Any) -> None:
        """紧急备份"""
        if self.current_checkpoint:
            self.current_checkpoint.set_status(CheckpointStatus.PAUSED)
            self.current_checkpoint.save(self.checkpoint_dir)
            self._print(f"✅ 已保存断点到: {self.checkpoint_dir}", "green")
    
    def _handle_interrupt(self, signum, frame) -> None:
        """处理中断信号"""
        self._print("\n\n收到中断信号，正在保存进度...", "yellow")
        
        if self.current_conversation and self.current_checkpoint:
            self.current_checkpoint.set_status(CheckpointStatus.PAUSED)
            self.current_checkpoint.selected_indices = self.selected_indices
            self.current_checkpoint.save(self.checkpoint_dir)
            self._print("✅ 进度已保存，下次启动可继续", "green")
        
        self._print("\n再见！👋")
        sys.exit(0)
    
    def check_pending_tasks(self) -> Optional[Checkpoint]:
        """检查未完成的任务"""
        pending = Checkpoint.find_pending_tasks(self.checkpoint_dir)
        
        if not pending:
            return None
        
        self._print("\n📋 发现未完成的任务：", "yellow")
        for i, cp in enumerate(pending):
            progress = cp.progress_percentage
            self._print(f"  [{i + 1}] {cp.source_url}")
            self._print(f"      进度: {progress:.1f}% | 状态: {cp.status.value}")
        
        self._print(f"  [0] 开始新任务")
        self._print()
        
        choice = self._input("请选择 (输入编号): ")
        
        try:
            index = int(choice)
            if index == 0:
                return None
            if 1 <= index <= len(pending):
                return pending[index - 1]
        except ValueError:
            pass
        
        self._print("无效选择，开始新任务", "yellow")
        return None
    
    def run(self) -> None:
        """运行主循环"""
        self._print_header()
        
        # 检查未完成任务
        checkpoint = self.check_pending_tasks()
        
        if checkpoint:
            self._resume_from_checkpoint(checkpoint)
        else:
            self._start_new_task()
    
    def _start_new_task(self) -> None:
        """开始新任务"""
        # 输入URL
        self._print("支持的对话来源：", "cyan")
        for domain in FetcherFactory.get_supported_domains():
            self._print(f"  • {domain}")
        self._print()
        
        url = self._input("请输入对话分享链接 (输入 q 退出): ").strip()
        
        if url.lower() == 'q':
            self._print("\n再见！👋")
            return
        
        # 验证URL
        if not FetcherFactory.is_supported(url):
            self._print("❌ 不支持的链接格式", "red")
            self._start_new_task()
            return
        
        # 抓取对话
        self._print("\n📡 正在抓取对话...", "cyan")
        
        fetcher = FetcherFactory.get_fetcher(url, page_size=self.PAGE_SIZE)
        if not fetcher:
            self._print("❌ 无法创建抓取器", "red")
            self._start_new_task()
            return
        
        result = fetcher.fetch_all_metadata(url)
        
        if not result.success:
            self._print(f"❌ 抓取失败: {result.error_message}", "red")
            self._start_new_task()
            return
        
        self.current_conversation = result.conversation
        
        # 创建断点
        self.current_checkpoint = Checkpoint(
            task_id="",
            source_url=url,
            status=CheckpointStatus.IN_PROGRESS,
            total_messages=self.current_conversation.total_messages
        )
        self.current_checkpoint.save(self.checkpoint_dir)
        
        # 显示对话概要
        self._show_conversation_overview()
        
        # 进入交互选择
        self._interactive_selection()
    
    def _resume_from_checkpoint(self, checkpoint: Checkpoint) -> None:
        """从断点恢复"""
        self._print(f"\n🔄 正在恢复任务: {checkpoint.source_url}", "cyan")
        
        # 重新抓取
        fetcher = FetcherFactory.get_fetcher(checkpoint.source_url)
        if not fetcher:
            self._print("❌ 无法创建抓取器", "red")
            return
        
        result = fetcher.fetch_all_metadata(checkpoint.source_url)
        
        if not result.success:
            self._print(f"❌ 恢复失败: {result.error_message}", "red")
            return
        
        self.current_conversation = result.conversation
        self.current_checkpoint = checkpoint
        self.selected_indices = checkpoint.selected_indices.copy()
        
        checkpoint.set_status(CheckpointStatus.RECOVERED)
        
        self._show_conversation_overview()
        self._interactive_selection()
    
    def _show_conversation_overview(self) -> None:
        """显示对话概要"""
        conv = self.current_conversation
        
        self._print_separator()
        self._print(f"\n📝 对话标题: {conv.title}", "bold")
        self._print(f"📊 消息数量: {conv.total_messages}")
        self._print(f"🔗 来源: {conv.source_url}", "blue")
        
        if conv.created_at:
            self._print(f"📅 创建时间: {conv.created_at.strftime('%Y-%m-%d %H:%M')}")
        
        self._print()
    
    def _interactive_selection(self) -> None:
        """交互式选择消息"""
        conv = self.current_conversation
        
        while self.is_running:
            self._print_separator()
            self._print(f"\n📖 消息列表 (第 {self.current_page + 1} 页)", "cyan")
            self._print(f"已选择: {len(self.selected_indices)} 条消息", "green")
            self._print()
            
            # 显示当前页消息
            start = self.current_page * self.PAGE_SIZE
            end = min(start + self.PAGE_SIZE, len(conv.messages))

            for i in range(start, end):
                msg = conv.messages[i]
                selected = i in self.selected_indices
                marker = "✓" if selected else " "
                role_icon = "👤" if msg.role == MessageRole.USER else "🤖"
                role_color = "blue" if msg.role == MessageRole.USER else "magenta"
                
                summary = msg.summary or "(无摘要)"
                if len(summary) > 50:
                    summary = summary[:50] + "..."
                
                self._print(f"  [{marker}] {i + 1}. {role_icon} ")
                self._print(f"{msg.role.value}", role_color)
                self._print(f"       {summary}")
            
            self._print()
            
            # 显示命令提示
            total_pages = (conv.total_messages + self.PAGE_SIZE - 1) // self.PAGE_SIZE
            self._print(f"页码: {self.current_page + 1}/{total_pages}", "yellow")
            self._print()
            self._print("命令:")
            self._print("  n/p     - 下一页/上一页")
            self._print("  <编号>  - 选择/取消选择消息 (如: 1, 2-5, 1,3,5)")
            self._print("  a       - 选择当前页全部")
            self._print("  c       - 清除所有选择")
            self._print("  s       - 显示已选消息")
            self._print("  e       - 导出选中消息")
            self._print("  q       - 退出")
            self._print()
            
            command = self._input("请输入命令: ").strip().lower()
            self._process_command(command)
    
    def _process_command(self, command: str) -> None:
        """处理命令"""
        conv = self.current_conversation
        total_pages = (conv.total_messages + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        
        if command == 'n':
            # 下一页
            if self.current_page < total_pages - 1:
                self.current_page += 1
            else:
                self._print("已是最后一页", "yellow")
        
        elif command == 'p':
            # 上一页
            if self.current_page > 0:
                self.current_page -= 1
            else:
                self._print("已是第一页", "yellow")
        
        elif command == 'a':
            # 选择当前页全部
            start = self.current_page * self.PAGE_SIZE
            end = min(start + self.PAGE_SIZE, conv.total_messages)
            for i in range(start, end):
                if i not in self.selected_indices:
                    self.selected_indices.append(i)
            self._print(f"已选择第 {start + 1}-{end} 条消息", "green")
        
        elif command == 'c':
            # 清除所有选择
            self.selected_indices.clear()
            self._print("已清除所有选择", "yellow")
        
        elif command == 's':
            # 显示已选消息
            self._show_selected_messages()
        
        elif command == 'e':
            # 导出
            self._export_selected()
        
        elif command == 'q':
            # 退出
            self._quit()
        
        else:
            # 尝试解析为消息编号
            self._parse_selection(command)
    
    def _parse_selection(self, command: str) -> None:
        """解析选择命令"""
        conv = self.current_conversation
        indices_to_toggle = set()
        
        try:
            # 支持多种格式: "1", "1,2,3", "1-5", "1,2-5,7"
            parts = command.split(',')
            for part in parts:
                part = part.strip()
                if '-' in part:
                    # 范围选择
                    start, end = part.split('-')
                    start = int(start.strip())
                    end = int(end.strip())
                    for i in range(start, end + 1):
                        indices_to_toggle.add(i - 1)  # 转为0-based索引
                else:
                    # 单个选择
                    idx = int(part)
                    indices_to_toggle.add(idx - 1)
            
            # 验证索引
            valid_indices = [i for i in indices_to_toggle if 0 <= i < conv.total_messages]
            
            if not valid_indices:
                self._print("无效的消息编号", "red")
                return
            
            # 切换选择状态
            for idx in valid_indices:
                if idx in self.selected_indices:
                    self.selected_indices.remove(idx)
                else:
                    self.selected_indices.append(idx)
            
            self._print(f"已更新选择 (共 {len(self.selected_indices)} 条)", "green")
            
            # 更新断点
            if self.current_checkpoint:
                self.current_checkpoint.mark_selected(self.selected_indices)
                self.current_checkpoint.save(self.checkpoint_dir)
            
        except ValueError:
            self._print("无效命令", "red")
    
    def _show_selected_messages(self) -> None:
        """显示已选消息"""
        if not self.selected_indices:
            self._print("\n尚未选择任何消息", "yellow")
            return
        
        conv = self.current_conversation
        self._print("\n📋 已选消息：", "cyan")
        
        for idx in sorted(self.selected_indices):
            msg = conv.messages[idx]
            role_icon = "👤" if msg.role == MessageRole.USER else "🤖"
            summary = msg.summary or "(无摘要)"
            if len(summary) > 40:
                summary = summary[:40] + "..."
            self._print(f"  {idx + 1}. {role_icon} {summary}")
        
        self._print()
        self._input("按回车继续...")
    
    def _export_selected(self) -> None:
        """导出选中的消息"""
        if not self.selected_indices:
            self._print("\n❌ 请先选择要导出的消息", "red")
            return
        
        conv = self.current_conversation
        
        self._print(f"\n📤 正在导出 {len(self.selected_indices)} 条消息...", "cyan")
        
        # 获取选中的消息
        selected_messages = [conv.messages[i] for i in sorted(self.selected_indices)]
        
        # 加载消息内容（增量加载）
        for msg in selected_messages:
            if not msg.is_loaded and msg._raw_data_ref:
                content = msg._raw_data_ref.get("content", "")
                if content:
                    # 检查Token限制
                    if self.token_monitor.can_load_content(content):
                        self.token_monitor.use(
                            self.token_monitor.estimate_text_tokens(content),
                            operation=f"load_message_{msg.id}"
                        )
                        msg.load_content(content)
                    else:
                        self._print(f"⚠️ 消息 {msg.id} 内容过长，跳过加载", "yellow")
        
        # 导出选项
        options = ExportOptions(
            include_metadata=True,
            include_timestamps=True,
            include_token_stats=True,
            include_source_url=True
        )
        
        try:
            # 导出
            output_path = self.exporter.export_messages(
                messages=selected_messages,
                title=conv.title,
                source_url=conv.source_url,
                options=options
            )
            
            self._print(f"\n✅ 导出成功！", "green")
            self._print(f"📄 文件路径: {output_path}", "cyan")
            
            # 更新断点
            if self.current_checkpoint:
                self.current_checkpoint.set_status(CheckpointStatus.COMPLETED)
                self.current_checkpoint.mark_exported(self.selected_indices)
                self.current_checkpoint.save(self.checkpoint_dir)
            
            # 询问是否继续
            self._print()
            choice = self._input("是否继续处理其他对话？(y/n): ").strip().lower()
            if choice == 'y':
                self._reset_state()
                self._start_new_task()
            else:
                self._quit()
            
        except Exception as e:
            self._print(f"\n❌ 导出失败: {str(e)}", "red")
    
    def _reset_state(self) -> None:
        """重置状态"""
        self.current_conversation = None
        self.current_checkpoint = None
        self.selected_indices.clear()
        self.current_page = 0
        self.token_monitor.reset()
        self.circuit_breaker.reset()
    
    def _quit(self) -> None:
        """退出程序"""
        if self.selected_indices and self.current_checkpoint:
            # 保存进度
            self.current_checkpoint.set_status(CheckpointStatus.PAUSED)
            self.current_checkpoint.selected_indices = self.selected_indices
            self.current_checkpoint.save(self.checkpoint_dir)
            self._print("\n✅ 进度已保存", "green")
        
        self._print("\n再见！👋")
        self.is_running = False
    
    def _input(self, prompt: str) -> str:
        """获取用户输入"""
        try:
            return input(prompt)
        except EOFError:
            return "q"


def main():
    """主入口"""
    cli = InteractiveCLI()
    cli.run()


if __name__ == "__main__":
    main()
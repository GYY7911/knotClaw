"""
Knotclaw - 大模型对话归档客户端
主入口模块
"""
import sys
import argparse

from .cli import InteractiveCLI
from .models import Conversation, Message, MessageRole, Checkpoint, CheckpointStatus
from .fetcher import FetcherFactory, BaseFetcher, DeepSeekFetcher
from .exporter import MarkdownExporter, ExportOptions
from .monitor import TokenMonitor, CircuitBreaker

__version__ = "1.0.0"
__author__ = "Knotclaw Team"

__all__ = [
    # CLI
    "InteractiveCLI",
    # Models
    "Conversation",
    "Message",
    "MessageRole",
    "Checkpoint",
    "CheckpointStatus",
    # Fetcher
    "FetcherFactory",
    "BaseFetcher",
    "DeepSeekFetcher",
    # Exporter
    "MarkdownExporter",
    "ExportOptions",
    # Monitor
    "TokenMonitor",
    "CircuitBreaker",
]


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(
        description='Knotclaw - 大模型对话归档客户端',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m src.main              # 启动交互式CLI
  python -m src.main --web        # 启动Web界面
  python -m src.main --web --port 3000  # 指定端口
        """
    )

    # Web 模式参数
    parser.add_argument('--web', '-w', action='store_true',
                        help='启动Web界面模式')
    parser.add_argument('--host', default='localhost',
                        help='Web服务器主机地址 (默认: localhost)')
    parser.add_argument('--port', '-p', type=int, default=8080,
                        help='Web服务器端口 (默认: 8080)')
    parser.add_argument('--debug', action='store_true',
                        help='开启调试模式')
    parser.add_argument('--no-browser', action='store_true',
                        help='不自动打开浏览器')

    args = parser.parse_args()

    if args.web:
        # Web 模式
        try:
            from .web import run_server
            run_server(
                host=args.host,
                port=args.port,
                debug=args.debug,
                open_browser=not args.no_browser
            )
        except ImportError as e:
            print(f"错误: 无法加载Web模块，请确保已安装Flask")
            print(f"安装命令: pip install flask")
            print(f"详细错误: {e}")
            sys.exit(1)
    else:
        # CLI 模式
        cli = InteractiveCLI()
        cli.run()


if __name__ == "__main__":
    main()
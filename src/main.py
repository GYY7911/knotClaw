"""
Knotclaw - 大模型对话归档客户端
主入口模块
"""
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
    cli = InteractiveCLI()
    cli.run()


if __name__ == "__main__":
    main()
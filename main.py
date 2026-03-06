#!/usr/bin/env python3
"""
Knotclaw - 大模型对话归档客户端
命令行入口
"""
import sys
import argparse
from pathlib import Path

# 添加src目录到路径
src_path = Path(__file__).parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.cli import InteractiveCLI
from src.web_server import run_web_server


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="Knotclaw - 大模型对话归档客户端")
    parser.add_argument("--web", "-w", action="store_true", help="启动Web界面")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Web服务器端口")
    args = parser.parse_args()

    if args.web:
        # 启动Web界面
        run_web_server(args.port)
    else:
        # 启动命令行界面
        cli = InteractiveCLI()
        cli.run()


if __name__ == "__main__":
    main()
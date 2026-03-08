"""
Knotclaw Web 模块
基于 Flask 的 Web 界面
"""


def create_app(config=None):
    """
    创建Flask应用（延迟导入）

    Args:
        config: 配置字典

    Returns:
        Flask应用实例
    """
    try:
        from flask import Flask
    except ImportError:
        raise ImportError(
            "Flask 未安装。请运行: pip install flask"
        )
    from .app import create_app as _create_app
    return _create_app(config)


def run_server(host='localhost', port=8080, debug=False, open_browser=True):
    """
    启动Web服务器（延迟导入）

    Args:
        host: 主机地址
        port: 端口号
        debug: 是否开启调试模式
        open_browser: 是否自动打开浏览器
    """
    try:
        from flask import Flask
    except ImportError:
        raise ImportError(
            "Flask 未安装。请运行: pip install flask"
        )
    from .app import run_server as _run_server
    _run_server(host, port, debug, open_browser)


__all__ = ['create_app', 'run_server']

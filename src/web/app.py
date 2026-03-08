"""
Flask 应用工厂
组装所有组件，配置应用
"""
import os
import sys
import warnings
import webbrowser
from pathlib import Path
from flask import Flask, send_from_directory

from .middleware.error_handler import init_error_handlers
from .middleware.validator import MAX_CONTENT_LENGTH
from .routes.conversation import conversation_bp
from .routes.export import export_bp


def _get_secret_key() -> str:
    """
    安全获取 SECRET_KEY

    生产环境必须设置环境变量，否则抛出异常。
    开发环境使用默认密钥但会发出警告。

    Returns:
        SECRET_KEY 字符串

    Raises:
        RuntimeError: 生产环境下 SECRET_KEY 未设置
    """
    key = os.environ.get('SECRET_KEY')

    if not key:
        # 检测是否为生产环境
        is_production = (
            os.environ.get('FLASK_ENV') == 'production' or
            os.environ.get('ENVIRONMENT', '').lower() in ('production', 'prod') or
            os.environ.get('GAE_ENV', '').startswith('standard')  # Google App Engine
        )

        if is_production:
            raise RuntimeError(
                "CRITICAL: SECRET_KEY environment variable must be set in production! "
                "Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )

        # 开发环境使用默认密钥，但发出警告
        key = 'dev-secret-key-not-for-production-use'
        warnings.warn(
            "WARNING: Using default SECRET_KEY. This is INSECURE for production! "
            "Set the SECRET_KEY environment variable before deployment.",
            UserWarning,
            stacklevel=3
        )

    # 验证密钥强度
    if len(key) < 16:
        warnings.warn(
            f"WARNING: SECRET_KEY is too short ({len(key)} chars). "
            "Use at least 32 characters for security.",
            UserWarning,
            stacklevel=3
        )

    return key


def create_app(config=None) -> Flask:
    """
    创建Flask应用

    Args:
        config: 配置字典

    Returns:
        Flask应用实例
    """
    # 创建应用
    app = Flask(
        __name__,
        static_folder=_get_static_folder(),
        static_url_path=''
    )

    # 加载配置
    app.config.update({
        'SECRET_KEY': _get_secret_key(),
        'MAX_CONTENT_LENGTH': MAX_CONTENT_LENGTH,
        'JSON_AS_ASCII': False,  # 支持中文JSON响应
    })

    if config:
        app.config.update(config)

    # 注册蓝图
    app.register_blueprint(conversation_bp, url_prefix='/api')
    app.register_blueprint(export_bp, url_prefix='/api')

    # 初始化错误处理
    init_error_handlers(app)

    # 主页路由
    @app.route('/')
    def index():
        """主页"""
        return app.send_static_file('index.html')

    # 请求日志（调试模式）
    if app.debug:
        @app.before_request
        def log_request():
            from flask import request
            app.logger.debug(f"{request.method} {request.path}")

    return app


def _get_static_folder() -> str:
    """获取静态文件目录"""
    # 相对于此文件的路径
    current_dir = Path(__file__).parent
    static_folder = current_dir.parent.parent / 'static'

    if not static_folder.exists():
        # 如果目录不存在，创建一个临时的
        static_folder.mkdir(parents=True, exist_ok=True)
        _create_default_index(static_folder)

    return str(static_folder)


def _create_default_index(static_folder: Path):
    """创建默认的index.html（用于首次运行）"""
    index_path = static_folder / 'index.html'
    if not index_path.exists():
        index_path.write_text("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Knotclaw</title>
</head>
<body>
    <h1>Knotclaw Web</h1>
    <p>请刷新页面加载完整界面...</p>
</body>
</html>
""", encoding='utf-8')


def run_server(host: str = 'localhost', port: int = 8080, debug: bool = False, open_browser: bool = True):
    """
    启动Web服务器

    Args:
        host: 主机地址
        port: 端口号
        debug: 是否开启调试模式
        open_browser: 是否自动打开浏览器
    """
    # 修复Windows终端编码
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    app = create_app({'DEBUG': debug})

    print(f"\n{'='*50}")
    print(f"  Knotclaw Web 服务器")
    print(f"{'='*50}")
    print(f"  地址: http://{host}:{port}")
    print(f"  调试模式: {'开启' if debug else '关闭'}")
    print(f"{'='*50}")
    print(f"  在浏览器中输入分享链接，选择消息后点击导出")
    print(f"{'='*50}\n")

    # 打开浏览器
    if open_browser and not debug:
        webbrowser.open(f'http://{host}:{port}')

    # 启动服务器
    app.run(host=host, port=port, debug=debug, threaded=True)


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='Knotclaw Web 服务器')
    parser.add_argument('--host', default='localhost', help='主机地址')
    parser.add_argument('--port', type=int, default=8080, help='端口号')
    parser.add_argument('--debug', action='store_true', help='开启调试模式')
    parser.add_argument('--no-browser', action='store_true', help='不自动打开浏览器')

    args = parser.parse_args()

    run_server(
        host=args.host,
        port=args.port,
        debug=args.debug,
        open_browser=not args.no_browser
    )


if __name__ == '__main__':
    main()

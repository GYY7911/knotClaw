"""
Simple HTTP Server for Web Interface
Provides a browser-based UI for selecting and exporting conversation messages
"""
import http.server
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from urllib.parse import urlparse
import threading

# 修复Windows终端编码
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# 全局状态
conversation_data: Dict[str, Any] = {}
selected_indices: set = set()


class WebHandler(http.server.BaseHTTPRequestHandler):
    """HTTP请求处理器"""

    def _send_response(self, content: str, content_type: str = "text/html; charset=utf-8"):
        self.send_response_only(200, content.encode('utf-8'))
        self.send_header('Content-type', content_type)
        self.send_header('Content-Length', len(content.encode('utf-8')))
        self.send_header('Access-Control-Allow-Origin', '*')

    def _send_json(self, data: Any):
        self._send_response(json.dumps(data, ensure_ascii=False), "application/json")

    def _send_error(self, message: str, code: int = 400):
        self._send_json({"error": message})

        self.end_headers()

    def do_GET(self):
        """处理GET请求"""
        path = self.path

        if path == "/" or path == "/index.html":
            self._serve_index()
        elif path == "/style.css":
            self._serve_css()
        elif path.startswith("/export"):
            self._handle_export()
        elif path.startswith("/select") or path.startswith("/toggle"):
            self._handle_selection()
        elif path == "/status":
            self._handle_status()
        elif path.startswith("/load"):
            self._handle_load()
        elif path.startswith("/clear"):
            self._handle_clear()
        else:
            self._send_error("Not found", 404)

        self.end_headers()

    def do_POST(self):
        """处理POST请求"""
        path = self.path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        data = json.loads(body.decode('utf-8'))

        if path == "/fetch":
            threading.Thread(target=self._fetch_conversation, args=(data.get("url"),)).start()
            self._send_json({"status": "started"})
        else:
            self._send_error("Unknown endpoint", 404)

        self.end_headers()

    def _serve_index(self):
        """提供主页面"""
        html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Knotclaw - 对话归档</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            text-align: center;
            color: #fff;
            margin-bottom: 30px;
        }
        .input-section {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .input-section input {
            width: 70%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
        }
        .input-section button {
            padding: 12px 24px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }
        .input-section button:hover {
            background: #764ba2;
        }
        .messages-section {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .message-card {
            border: 2px solid #eee;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .message-card:hover {
            border-color: #667eea;
        }
        .message-card.selected {
            border-color: #4CAF50;
            background: #f0f9f0;
        }
        .message-card .role-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 12px;
            margin-bottom: 8px;
        }
        .message-card .role-user {
            background: #e3f2fd;
            color: #1565c0;
        }
        .message-card .role-assistant {
            background: #f3e5f1;
            color: #2e7d32;
        }
        .message-card .content {
            margin-top: 10px;
            line-height: 1.6;
            white-space: pre-wrap;
        }
        .message-card .timestamp {
            font-size: 11px;
            color: #999;
            margin-top: 8px;
        }
        .message-card .checkbox {
            float: right;
            margin-left: 10px;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        .action-bar {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: white;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            display: flex;
            gap: 10px;
        }
        .action-bar button {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
        }
        .btn-export {
            background: #4CAF50;
            color: white;
        }
        .btn-clear {
            background: #f44336;
            color: white;
        }
        .btn-select-all {
            background: #2196F3;
            color: white;
        }
        .stats {
            position: fixed;
            top: 20px;
            right: 20px;
            background: #667eea;
            color: white;
            padding: 10px 15px;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Knotclaw 对话归档</h1>

        <div class="input-section">
            <input type="text" id="url-input" placeholder="输入分享链接...">
            <button onclick="fetchConversation()">获取对话</button>
        </div>

        <div id="loading" class="loading" style="display: none;">
            正在获取页面内容...
        </div>

        <div id="messages" class="messages-section" style="display: none;">
        </ </div>

        <div class="action-bar" id="action-bar" style="display: none;">
            <button class="btn-select-all" onclick="selectAll()">全选</button>
            <button class="btn-clear" onclick="clearSelection()">清除</button>
            <button class="btn-export" onclick="exportSelected()">导出选中</button>
        </div>

        <div class="stats" id="stats"></div>
    </div>

    <script>
        let conversationData = {};
        let selectedIndices = new Set();

        async function fetchConversation() {
            const url = document.getElementById('url-input').value.trim();
            if (!url) {
                alert('请输入链接');
                return;
            }

            document.getElementById('loading').style.display = 'block';
            document.getElementById('messages').style.display = 'none';
            document.getElementById('action-bar').style.display = 'none';

            try {
                const response = await fetch('/fetch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                const result = await response.json();

                if (result.status === 'started') {
                    // Poll for completion
                    const checkInterval = setInterval(async () => {
                        try {
                            const statusRes = await fetch('/status');
                            const status = await statusRes.json();
                            if (status.done) {
                                clearInterval(checkInterval);
                                conversationData = status.data;
                                renderMessages();
                            }
                        } catch (e) {
                            console.error(e);
                        }
                    }, 500);
                }
            } catch (e) {
                alert('获取失败: ' + e.message);
                document.getElementById('loading').style.display = 'none';
            }
        }

        function renderMessages() {
            const data = conversationData;
            if (!data || !data.messages || data.messages.length === 0) {
                document.getElementById('messages').innerHTML = '<p>未找到消息</p>';
                document.getElementById('messages').style.display = 'block';
                return;
            }

            let html = '';
            data.messages.forEach((msg, idx) => {
                const isSelected = selectedIndices.has(idx);
                html += `
                    <div class="message-card ${isSelected ? 'selected' : ''}" data-idx="${idx}" onclick="toggleMessage(${idx})">
                        <input type="checkbox" class="checkbox" ${isSelected ? 'checked' : ''} onclick="event.stopPropagation(); toggleMessage(${idx})">
                        <span class="role-badge ${msg.role === 'user' ? 'role-user' : 'role-assistant'}">
                            ${msg.role === 'user' ? '用户' : '助手'}
                        </span>
                        <div class="content">${escapeHtml(msg.content || '').substring(0, 300)}${msg.content && msg.content.length > 300 ? '...' : ''}</div>
                        <div class="timestamp">消息 #${idx + 1}</div>
                    </div>
                `;
            });

            document.getElementById('messages').innerHTML = html;
            document.getElementById('messages').style.display = 'block';
            document.getElementById('action-bar').style.display = 'flex';
            updateStats();
        }
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        function toggleMessage(idx) {
            if (selectedIndices.has(idx)) {
                selectedIndices.delete(idx);
            } else {
                selectedIndices.add(idx);
            }
            renderMessages();
        }
        function selectAll() {
            if (conversationData && conversationData.messages) {
                conversationData.messages.forEach((_, idx) => {
                    selectedIndices.add(idx);
                });
                renderMessages();
            }
        }
        function clearSelection() {
            selectedIndices.clear();
            renderMessages();
        }
        function updateStats() {
            const total = conversationData ? (conversationData.messages ? conversationData.messages.length : 0) : 0;
            const selected = selectedIndices.size;
            document.getElementById('stats').textContent = `已选择: ${selected} / ${total}`;
        }
        async function exportSelected() {
            if (selectedIndices.size === 0) {
                alert('请先选择消息');
                return;
            }

            const selectedMessages = Array.from(selectedIndices).sort((a, b) => a - b).map(idx => conversationData.messages[idx]);
            const response = await fetch('/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                title: conversationData.title,
                messages: selectedMessages,
                url: conversationData.url
            })
            });

            const result = await response.json();
            if (result.success) {
                alert('导出成功: ' + result.filename);
                window.open(result.filename, '_blank');
            } else {
                alert('导出失败: ' + result.error);
            }
        }
    </script>
</body>
</html>
"""
        self._send_response(html)

        self.end_headers()

    def _serve_css(self):
        """提供CSS样式"""
        self.send_response_only(200, b"""
        body * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        """)
        self.send_header('Content-type', 'text/css')
        self.end_headers()

    def _handle_status(self):
        """处理状态检查请求"""
        global conversation_data
        if conversation_data:
            self._send_json({"done": True, "data": conversation_data})
        else:
            self._send_json({"done": False})

        self.end_headers()

    def _handle_load(self):
        """加载对话数据"""
        global conversation_data
        url = self.path.split('/load/')[-1]
        if url in conversation_data:
            self._send_json(conversation_data[url])
        else:
            self._send_error("Not found", 404)
        self.end_headers()

    def _handle_selection(self):
        """处理选择请求"""
        global selected_indices
        path = self.path
        parts = path.split('/')
        if len(parts) >= 3:
            idx = int(parts[2])
            if selected_indices.has(idx):
                selected_indices.delete(idx)
            else:
                selected_indices.add(idx)
            self._send_json({"selected": list(selected_indices)})

        self.end_headers()

    def _handle_export(self):
        """处理导出请求"""
        global conversation_data, selected_indices

        if not conversation_data or not conversation_data.get("messages"):
            self._send_error("No conversation loaded", 400)
            self.end_headers()
            return

        if not selected_indices:
            self._send_error("No messages selected", 400)
            self.end_headers()
            return

        # 获取选中的消息
        selected_messages = []
        for idx in sorted(selected_indices):
                if idx < len(conversation_data["messages"]):
                    selected_messages.append(conversation_data["messages"][idx])

        # 生成Markdown内容
        title = conversation_data.get("title", "未命名对话")
        markdown = f"# {title}\n\n"
        markdown += f"> 来源: {conversation_data.get('url', '')}\n"
        markdown += f"> 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        markdown += f"> 消息数量: {len(selected_messages)}\n\n"
        markdown += "---\n\n"

        for msg in selected_messages:
            role_label = "**用户**" if msg["role"] == "user" else "**助手**"
            markdown += f"## {role_label}\n\n"
            content = msg.get("content", "")
            markdown += f"{content}\n\n"
            markdown += "---\n\n"

        # 保存文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{title}_{timestamp}.md"
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        output_path = Path("output") / filename
        output_path.mkdir(parents=True, exist_ok=True)

        output_path.write_text(markdown, encoding='utf-8')

        self._send_json({
            "success": True,
            "filename": str(output_path)
        })
        self.end_headers()

    def _fetch_conversation(self, url: str):
        """获取对话内容（在后台线程中运行）"""
        global conversation_data

        try:
            # 使用fetcher获取
            from src.fetcher import FetcherFactory

            fetcher = FetcherFactory.get_fetcher(url)
            if not fetcher:
                raise ValueError("不支持的URL")

            result = fetcher.fetch_all_metadata(url)
            if not result.success:
                raise ValueError(result.error_message)

            conv = result.conversation

            messages = []
            for msg in conv.messages:
                messages.append({
                    "role": msg.role.value,
                    "content": msg.content or msg.summary or "",
                    "timestamp": msg.timestamp.isostrftime('%Y-%m-%d %H:%M') if msg.timestamp else None
                })

            conversation_data = {
                "title": conv.title,
                "url": url,
                "messages": messages
            }
        except Exception as e:
            print(f"Fetch error: {e}")


def run_web_server(port: int = 8080):
    """运行Web服务器"""
    server_address = ('', port)
    httpd = http.server.HTTPServer(server_address, WebHandler)
    print(f"\n🌐 Web界面已启动!")
    print(f"   请在浏览器中打开: http://localhost:{port}")
    print(f"   输入分享链接后，可以在页面中选择要保留的消息")
    print(f"   点击'导出选中'按钮保存为Markdown文件")
    print(f"\n按 Ctrl+C 停止服务器\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")


if __name__ == "__main__":
    run_web_server(8080)

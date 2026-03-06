"""
Web界面
直接运行: python web_cli.py
然后浏览器访问: http://localhost:8888
"""
import http.server
import json
import re
import sys
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Set
import threading
import time

# 修复Windows编码
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# 全局状态
conversation_data: Dict[str, Any] = {}
selected_indices: Set = set()
fetch_status: Dict[str, Any] = {"done": False, "error": None}


class WebHandler(http.server.BaseHTTPRequestHandler):
    """HTTP请求处理器"""

    def log(self, msg: str):
        print(f"[Web] {msg}")

    def _send_html(self, html: str):
        content = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(content))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, data: Any):
        content = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(content))
        self.end_headers()
        self.wfile.write(content)

    def _send_error(self, code: int, message: str):
        self.send_response(code)
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode('utf-8'))

    def do_GET(self):
        """处理GET请求"""
        global fetch_status

        if self.path == "/":
            self._send_html(INDEX_HTML)
        elif self.path == "/status":
            self._send_json(fetch_status)
        elif self.path == "/test":
            self._send_json({"status": "ok"})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """处理POST请求"""
        global conversation_data, selected_indices, fetch_status

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            if self.path == "/fetch":
                self.log(f"开始获取: {data.get('url', '')}")
                fetch_status = {"done": False, "status": "fetching"}

                # 在后台线程获取
                def fetch_thread():
                    global conversation_data, fetch_status
                    try:
                        from src.fetcher import FetcherFactory

                        url = data.get("url", "")
                        fetcher = FetcherFactory.get_fetcher(url)
                        if not fetcher:
                            fetch_status = {"done": True, "error": "不支持的URL"}
                            return

                        result = fetcher.fetch_all_metadata(url)
                        if not result.success:
                            fetch_status = {"done": True, "error": result.error_message}
                            return

                        conv = result.conversation
                        messages = []
                        for msg in conv.messages:
                            messages.append({
                                "role": msg.role.value,
                                "content": msg.content or msg.summary or ""
                            })

                        conversation_data = {
                            "title": conv.title,
                            "url": url,
                            "messages": messages
                        }
                        fetch_status = {"done": True, "data": conversation_data}
                    except Exception as e:
                        fetch_status = {"done": True, "error": str(e)}

                threading.Thread(target=fetch_thread).start()
                self._send_json({"status": "started"})

            elif self.path == "/export":
                if not conversation_data or not selected_indices:
                    self._send_error(400, "No data or selection")
                    return

                # 获取选中的消息
                selected_messages = []
                for idx in sorted(selected_indices):
                    if idx < len(conversation_data["messages"]):
                        selected_messages.append(conversation_data["messages"][idx])

                # 生成Markdown
                title = conversation_data.get("title", "未命名对话")
                markdown = f"# {title}\n\n"
                markdown += f"> 来源: {conversation_data.get('url', '')}\n"
                markdown += f"> 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                markdown += f"> 消息数量: {len(selected_messages)}\n\n"
                markdown += "---\n\n"

                for msg in selected_messages:
                    role_label = "**用户**" if msg["role"] == "user" else "**助手**"
                    markdown += f"## {role_label}\n\n"
                    markdown += f"{msg.get('content', '')}\n\n"
                    markdown += "---\n\n"

                # 保存文件
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{title}_{timestamp}.md"
                filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
                output_path = Path("output") / filename
                output_path.mkdir(parents=True, exist_ok=True)
                output_path.write_text(markdown, encoding='utf-8')

                self._send_json({"success": True, "filename": str(output_path)})

            elif self.path == "/toggle":
                idx = int(data.get("index", 0))
                if idx in selected_indices:
                    selected_indices.remove(idx)
                else:
                    selected_indices.add(idx)
                self._send_json({"selected": list(selected_indices)})

            elif self.path == "/clear":
                selected_indices.clear()
                self._send_json({"selected": []})

            else:
                self._send_error(404, "Unknown endpoint")

        except Exception as e:
            self.log(f"Error: {e}")
            self._send_error(500, str(e))


INDEX_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Knotclaw Web</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui; background: #667eea; min-height: 100vh; color: #333; }
        .container { max-width: 900px; margin: 0 auto; padding: 20px; }
        h1 { color: white; text-align: center; padding: 20px; }
        .card { background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        input[type="text"] { width: 70%; padding: 12px; border: 2px solid #ddd; border-radius: 5px; font-size: 16px; }
        button { padding: 10px 20px; margin: 5px; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; }
        .btn-primary { background: #007bff; color: white; }
        .btn-success { background: #28a745; color: white; }
        .btn-danger { background: #dc3545; color: white; }
        button:hover { opacity: 0.9; }
        .message { border: 2px solid #eee; border-radius: 8px; padding: 15px; margin: 10px 0; cursor: pointer; }
        .message:hover { border-color: #007bff; }
        .message.selected { border-color: #28a745; background: #f0fff0; }
        .role-user { color: #007bff; font-weight: bold; }
        .role-assistant { color: #28a745; font-weight: bold; }
        .content { margin-top: 10px; white-space: pre-wrap; }
        #loading { color: #666; padding: 20px; text-align: center; }
        .hidden { display: none; }
        #actions { margin-top: 20px; }
        #stats { position: fixed; top: 20px; right: 20px; background: #007bff; color: white; padding: 10px 15px; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>Knotclaw 对话归档</h1>
    <div class="container">
        <div class="card">
            <input type="text" id="url" placeholder="输入分享链接...">
            <button class="btn-primary" onclick="fetchData()">获取</button>
        </div>

        <div id="loading" class="hidden">
            <p>正在获取页面内容...</p>
        </div>

        <div id="messages" class="card hidden"></div>

        <div id="actions" class="card hidden">
            <button class="btn-success" onclick="exportData()">导出选中</button>
            <button class="btn-danger" onclick="clearSelection()">清除选择</button>
        </div>
    </div>

    <div id="stats"></div>

    <script>
        let selected = new Set();
        let conversation_data = null;

        async function fetchData() {
            const url = document.getElementById('url').value.trim();
            if (!url) { alert('请输入链接'); return; }

            document.getElementById('loading').classList.remove('hidden');
            document.getElementById('messages').classList.add('hidden');
            document.getElementById('actions').classList.add('hidden');
            selected.clear();

            try {
                await fetch('/fetch', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: url})
                });

                const check = setInterval(async () => {
                    const res = await fetch('/status');
                    const data = await res.json();
                    if (data.done) {
                        clearInterval(check);
                        if (data.error) {
                            alert('错误: ' + data.error);
                        } else {
                            renderMessages(data.data);
                        }
                    }
                }, 500);
            } catch (e) {
                alert('请求失败: ' + e);
            }
        }

        function renderMessages(data) {
            conversation_data = data;
            document.getElementById('loading').classList.add('hidden');
            let html = '';
            data.messages.forEach((msg, i) => {
                const sel = selected.has(i) ? 'selected' : '';
                const content = msg.content || '';
                const preview = content.length > 200 ? content.substring(0, 200) + '...' : content;
                html += '<div class="message ' + sel + '" onclick="toggle(' + i + ')">';
                html += '<span class="role-' + (msg.role === 'user' ? 'role-user' : 'role-assistant') + '">' + (msg.role === 'user' ? '用户' : '助手') + '</span>';
                html += '<div class="content">' + preview + '</div>';
                html += '</div>';
            });
            document.getElementById('messages').innerHTML = html;
            document.getElementById('messages').classList.remove('hidden');
            document.getElementById('actions').classList.remove('hidden');
            updateStats(data.messages.length);
        }

        function toggle(i) {
            if (selected.has(i)) {
                selected.delete(i);
            } else {
                selected.add(i);
            }
            document.querySelectorAll('.message')[i].classList.toggle('selected');
            updateStats();
        }

        function updateStats(total) {
            const t = total || (conversation_data.messages ? conversation_data.messages.length : 0);
            document.getElementById('stats').textContent = '已选: ' + selected.size + ' / ' + t;
        }

        async function exportData() {
            if (selected.size === 0) { alert('请先选择消息'); return; }

            const selectedIdx = Array.from(selected).sort((a, b) => a - b);
            const res = await fetch('/export', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    title: conversation_data.title,
                    url: conversation_data.url,
                    messages: selectedIdx.map(i => conversation_data.messages[i])
                })
            });
            const result = await res.json();
            if (result.success) {
                alert('导出成功: ' + result.filename);
            } else {
                alert('导出失败');
            }
        }

        function clearSelection() {
            selected.clear();
            document.querySelectorAll('.message').forEach(m => m.classList.remove('selected'));
            updateStats();
        }
    </script>
</body>
</html>
"""


def run_server(port=8888):
    server = http.server.HTTPServer(('', port), WebHandler)
    print(f"服务器启动: http://localhost:{port}")
    print("输入分享链接， 选择消息后 导出")
    webbrowser.open(f'http://localhost:{port}')
    server.serve_forever()


if __name__ == "__main__":
    run_server()

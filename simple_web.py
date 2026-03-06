"""
简单的Web服务器测试版本
"""
import http.server
import json
import sys
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Set
import threading

# 修复Windows终端编码
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# 全局状态
conversation_data: Dict[str, Any] = {}
selected_indices: Set = set()


class SimpleHandler(http.server.BaseHTTPRequestHandler):
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

    def do_GET(self):
        if self.path == "/":
            self._send_html(INDEX_HTML)
        elif self.path == "/status":
            self._send_json({
                "done": bool(conversation_data),
                "data": conversation_data if conversation_data else None
            })
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/fetch":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
            url = data.get("url", "")

            # 在后台线程中获取
            def fetch_task():
                global conversation_data
                try:
                    from src.fetcher import FetcherFactory
                    fetcher = FetcherFactory.get_fetcher(url)
                    result = fetcher.fetch_all_metadata(url)
                    if result.success:
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
                except Exception as e:
                    print(f"Error: {e}")

            threading.Thread(target=fetch_task).start()
            self._send_json({"status": "started"})

        elif self.path == "/export":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            # 保存文件
            title = data.get("title", "未命名对话")
            messages = data.get("messages", [])

            markdown = f"# {title}\n\n"
            markdown += f"> 来源: {data.get('url', '')}\n"
            markdown += f"> 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            markdown += "---\n\n"

            for msg in messages:
                role_label = "用户" if msg["role"] == "user" else "助手"
                markdown += f"## {role_label}\n\n{msg.get('content', '')}\n\n---\n\n"

            output_path = Path("output") / f"{title}.md"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown, encoding='utf-8')

            self._send_json({"success": True, "filename": str(output_path)})
        else:
            self.send_response(404)
            self.end_headers()


INDEX_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Knotclaw Web</title>
    <style>
        body { font-family: system-ui; background: #f5f5f5; padding: 20px; }
        .container { max-width: 900px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        h1 { color: #333; }
        input[type="text"] { width: 70%; padding: 10px; font-size: 16px; }
        button { padding: 10px 20px; background: #007bff; color: white; border: none; cursor: pointer; margin: 5px; }
        button:hover { background: #0056b3; }
        .message { border: 1px solid #ddd; padding: 15px; margin: 10px 0; cursor: pointer; }
        .message.selected { border-color: green; background: #f0fff0; }
        .role-user { color: blue; }
        .role-assistant { color: green; }
        #actions { margin-top: 20px; }
        #loading { color: #666; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Knotclaw Web界面</h1>
        <input type="text" id="url" placeholder="输入分享链接...">
        <button onclick="fetchData()">获取</button>

        <div id="loading">正在获取...</div>

        <div id="messages"></div>

        <div id="actions" style="display:none;">
            <button onclick="exportData()">导出选中</button>
            <button onclick="clearAll()">清除选择</button>
            <span id="count"></span>
        </div>
    </div>

    <script>
        let selected = new Set();

        async function fetchData() {
            const url = document.getElementById('url').value;
            if (!url) return alert('请输入链接');

            document.getElementById('loading').style.display = 'block';
            document.getElementById('messages').innerHTML = '';

            await fetch('/fetch', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url})
            });

            // 轮询检查状态
            const check = setInterval(async () => {
                const res = await fetch('/status');
                const data = await res.json();
                if (data.done) {
                    clearInterval(check);
                    renderMessages(data.data);
                }
            }, 500);
        }

        function renderMessages(data) {
            document.getElementById('loading').style.display = 'none';
            let html = '';
            data.messages.forEach((msg, i) => {
                const sel = selected.has(i) ? 'selected' : '';
                html += `<div class="message ${sel}" onclick="toggle(${i})">
                    <span class="role-${msg.role}">${msg.role === 'user' ? '用户' : '助手'}</span>
                    <p>${msg.content.substring(0, 200)}${msg.content.length > 200 ? '...' : ''}</p>
                </div>`;
            });
            document.getElementById('messages').innerHTML = html;
            document.getElementById('actions').style.display = 'block';
            updateCount(data.messages.length);
        }

        function toggle(i) {
            if (selected.has(i)) selected.delete(i);
            else selected.add(i);
            document.querySelectorAll('.message')[i].classList.toggle('selected');
            updateCount();
        }

        function updateCount(total) {
            document.getElementById('count').textContent = `已选: ${selected.size}`;
        }

        function clearAll() {
            selected.clear();
            document.querySelectorAll('.message').forEach(m => m.classList.remove('selected'));
            updateCount();
        }

        async function exportData() {
            const res = await fetch('/status');
            const data = await res.json();
            const msgs = Array.from(selected).map(i => data.data.messages[i]);

            const res2 = await fetch('/export', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    title: data.data.title,
                    url: data.data.url,
                    messages: msgs
                })
            });
            const result = await res2.json();
            if (result.success) {
                alert('导出成功: ' + result.filename);
            }
        }
    </script>
</body>
</html>
"""


def run_server(port=8080):
    print(f"\n启动Web服务器: http://localhost:{port}")
    print("在浏览器中输入分享链接，选择消息后点击导出\n")

    # 打开浏览器
    webbrowser.open(f'http://localhost:{port}')

    server = http.server.HTTPServer(('', port), SimpleHandler)
    server.serve_forever()


if __name__ == "__main__":
    run_server()

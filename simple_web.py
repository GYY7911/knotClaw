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
                                "content": msg.content or msg.summary or "",
                                "isThinking": msg.metadata.get("isThinking", False) if msg.metadata else False
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
        #actions { margin-top: 20px; }
        #loading { color: #666; display: none; }

        /* 对话组样式 */
        .conversation-group { border: 2px solid #e0e0e0; border-radius: 10px; margin: 15px 0; overflow: hidden; }
        .user-question { background: #e3f2fd; padding: 15px; font-weight: bold; border-bottom: 1px solid #bbdefb; }
        .assistant-response { padding: 10px; }
        .thinking-section { background: #fff3e0; padding: 10px 15px; border-bottom: 1px solid #ffe0b2; }
        .thinking-header { cursor: pointer; color: #e65100; font-size: 14px; }
        .thinking-header:hover { text-decoration: underline; }
        .thinking-content { display: none; margin-top: 10px; padding: 10px; background: #fff8e1; border-radius: 5px; font-size: 13px; color: #666; white-space: pre-wrap; max-height: 300px; overflow-y: auto; }
        .thinking-content.show { display: block; }
        .answer-section { background: #f0fff0; padding: 15px; cursor: pointer; border: 2px solid transparent; }
        .answer-section:hover { border-color: #4caf50; }
        .answer-section.selected { border-color: #2e7d32; background: #c8e6c9; }
        .answer-label { color: #2e7d32; font-weight: bold; margin-bottom: 8px; }
        .answer-content { white-space: pre-wrap; }
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
        let allMessages = [];

        async function fetchData() {
            const url = document.getElementById('url').value;
            if (!url) return alert('请输入链接');

            document.getElementById('loading').style.display = 'block';
            document.getElementById('messages').innerHTML = '';
            selected.clear();

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
            allMessages = data.messages;
            let html = '';

            // 调试：显示原始数据
            console.log('收到数据:', data);
            console.log('消息数量:', data.messages ? data.messages.length : 0);
            if (data.messages && data.messages.length > 0) {
                data.messages.forEach((m, idx) => {
                    console.log(`消息${idx}: role=${m.role}, isThinking=${m.isThinking}, content=${m.content ? m.content.substring(0, 30) : 'null'}...`);
                });
            }

            // 按对话组渲染：用户问题 -> 思考过程 -> 实际回答
            let i = 0;
            while (i < data.messages.length) {
                const msg = data.messages[i];

                if (msg.role === 'user') {
                    // 用户问题 - 开始一个新组
                    html += `<div class="conversation-group">`;
                    html += `<div class="user-question">用户: ${escapeHtml(msg.content)}</div>`;

                    // 查找后续的助手消息
                    let thinkingContent = null;
                    let answerContent = null;
                    let thinkingIdx = -1;
                    let answerIdx = -1;

                    let j = i + 1;
                    while (j < data.messages.length && data.messages[j].role === 'assistant') {
                        if (data.messages[j].isThinking && !thinkingContent) {
                            thinkingContent = data.messages[j].content;
                            thinkingIdx = j;
                        } else if (!data.messages[j].isThinking && !answerContent) {
                            answerContent = data.messages[j].content;
                            answerIdx = j;
                        }
                        j++;
                    }

                    html += `<div class="assistant-response">`;

                    // 思考过程（可折叠）
                    if (thinkingContent) {
                        html += `<div class="thinking-section">
                            <div class="thinking-header" onclick="toggleThinking(this)">[+] 点击查看思考过程</div>
                            <div class="thinking-content">${escapeHtml(thinkingContent)}</div>
                        </div>`;
                    }

                    // 实际回答（可选择）
                    if (answerContent) {
                        const selClass = selected.has(answerIdx) ? 'selected' : '';
                        html += `<div class="answer-section ${selClass}" onclick="toggle(${answerIdx})">
                            <div class="answer-label">助手回答 (点击选择)</div>
                            <div class="answer-content">${escapeHtml(answerContent.substring(0, 500))}${answerContent.length > 500 ? '...' : ''}</div>
                        </div>`;
                    }

                    html += `</div></div>`;
                    i = j;
                } else {
                    i++;
                }
            }

            document.getElementById('messages').innerHTML = html;
            document.getElementById('actions').style.display = 'block';
            updateCount(data.messages.length);
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function toggleThinking(header) {
            const content = header.nextElementSibling;
            content.classList.toggle('show');
            header.textContent = content.classList.contains('show') ? '[-] 收起思考过程' : '[+] 点击查看思考过程';
        }

        function toggle(i) {
            if (selected.has(i)) selected.delete(i);
            else selected.add(i);
            renderMessages({messages: allMessages});
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


def run_server(port=8080, open_browser=True):
    print(f"\n启动Web服务器: http://localhost:{port}")
    print("在浏览器中输入分享链接，选择消息后点击导出\n")

    # 打开浏览器
    if open_browser:
        webbrowser.open(f'http://localhost:{port}')

    server = http.server.HTTPServer(('', port), SimpleHandler)
    server.serve_forever()


if __name__ == "__main__":
    run_server(8088)

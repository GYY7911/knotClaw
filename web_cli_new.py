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
                                "content": msg.content or msg.summary or "",
                                "isThinking": msg.isThinking if hasattr(msg, 'isThinking') else (msg.metadata.get('isThinking') if hasattr(msg.metadata, 'isThinking') else False
                            })
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
        body { font-family: system-ui; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; color: #333; }
        .container { max-width: 1000px; margin: 0 auto; padding: 20px; }
        h1 { color: white; text-align: center; padding: 20px; font-size: 28px; }
        .card { background: white; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        input[type="text"] { width: 70%; padding: 12px 15px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 16px; transition: border-color 0.3s; }
        input[type="text"]:focus { border-color: #667eea; outline: none; }
        button { padding: 12px 24px; margin: 5px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.3s; }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); color: white; }
        .btn-success { background: linear-gradient(135deg, #28a745, #20c997); color: white; }
        .btn-danger { background: #dc3545; color: white; }
        .btn-secondary { background: #6c757d; color: white; }
        button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
        button:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

        /* 问题卡片样式 */
        .question-card { border-left: 4px solid #667eea; margin: 15px 0; background: #f8f9fa; border-radius: 0 8px 8px 0; }
        .question-header { padding: 15px 20px; background: #e8f0fe; border-radius: 0 8px 0 0; cursor: pointer; display: flex; align-items: center; justify-content: space-between; }
        .question-header:hover { background: #dce8fc; }
        .question-title { font-weight: 600; color: #333; display: flex; align-items: center; gap: 10px; }
        .question-title .badge { background: #667eea; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px; }
        .question-content { padding: 15px 20px; color: #555; line-height: 1.6; white-space: pre-wrap; border-top: 1px solid #e0e0e0; }
        .toggle-icon { font-size: 18px; transition: transform 0.3s; }
        .toggle-icon.collapsed { transform: rotate(-90deg); }

        /* 方案卡片样式 */
        .answers-container { margin-left: 20px; border-left: 2px dashed #ccc; padding-left: 15px; }
        .answer-card { border: 2px solid #e0e0e0; border-radius: 8px; margin: 10px 0; transition: all 0.3s; }
        .answer-card:hover { border-color: #667eea; }
        .answer-card.selected { border-color: #28a745; background: linear-gradient(135deg, #f0fff0, #e8f5e9); box-shadow: 0 2px 10px rgba(40, 167, 69, 0.2); }
        .answer-header { padding: 10px 15px; background: #f8f9fa; border-radius: 6px 6px 0 0; display: flex; align-items: center; justify-content: space-between; cursor: pointer; }
        .answer-header:hover { background: #f0f0f0; }
        .answer-label { font-weight: 500; color: #28a745; display: flex; align-items: center; gap: 8px; }
        .answer-label .badge { background: #28a745; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; }
        .answer-content { padding: 15px; color: #555; line-height: 1.6; white-space: pre-wrap; max-height: 200px; overflow-y: auto; }
        .answer-actions { padding: 10px 15px; border-top: 1px solid #e0e0e0; display: flex; gap: 10px; }
        .btn-select { background: #28a745; color: white; padding: 6px 12px; font-size: 12px; }
        .btn-unselect { background: #dc3545; color: white; padding: 6px 12px; font-size: 12px; }
        .btn-expand { background: #6c757d; color: white; padding: 6px 12px; font-size: 12px; }

        #loading { color: #666; padding: 40px; text-align: center; }
        #loading .spinner { width: 40px; height: 40px; border: 4px solid #e0e0e0; border-top-color: #667eea; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 15px; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .hidden { display: none; }
        #actions { margin-top: 20px; position: sticky; bottom: 20px; background: white; padding: 15px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.15); display: flex; justify-content: center; gap: 15px; flex-wrap: wrap; }
        #stats { position: fixed; top: 20px; right: 20px; background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 12px 20px; border-radius: 25px; font-weight: 500; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
        .empty-message { text-align: center; color: #999; padding: 40px; font-size: 16px; }
    </style>
</head>
<body>
    <h1>Knotclaw 对话归档</h1>
    <div class="container">
        <div class="card">
            <input type="text" id="url" placeholder="输入分享链接...">
            <button class="btn-primary" onclick="fetchData()">获取对话</button>
        </div>

        <div id="loading" class="hidden">
            <div class="spinner"></div>
            <p>正在获取页面内容...</p>
        </div>

        <div id="messages" class="card hidden"></div>

        <div id="actions" class="hidden">
            <button class="btn-secondary" onclick="expandAll()">展开全部</button>
            <button class="btn-secondary" onclick="collapseAll()">收起全部</button>
            <button class="btn-success" onclick="exportData()">导出选中</button>
            <button class="btn-danger" onclick="clearSelection()">清除选择</button>
        </div>
    </div>

    <div id="stats"></div>

    <script>
        let selected = new Set();  // 存储选中的消息索引
        let conversation_data = null;
        let qa_pairs = [];  // 存储问题-回答对

        async function fetchData() {
            const url = document.getElementById('url').value.trim();
            if (!url) { alert('请输入链接'); return; }

            document.getElementById('loading').classList.remove('hidden');
            document.getElementById('messages').classList.add('hidden');
            document.getElementById('actions').classList.add('hidden');
            selected.clear();
            qa_pairs = [];

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
                            document.getElementById('loading').classList.add('hidden');
                        } else {
                            conversation_data = data.data;
                            console.log('获取到的数据:', conversation_data);
                            buildQAPairs(conversation_data);
                            console.log('构建的QA对:', qa_pairs);
                            renderQAPairs();
                        }
                    }
                }, 500);
            } catch (e) {
                alert('请求失败: ' + e);
                document.getElementById('loading').classList.add('hidden');
            }
        }

        // 构建问题-回答对
        function buildQAPairs(data) {
            qa_pairs = [];
            if (!data || !data.messages) {
                console.error('数据无效:', data);
                return;
            }

            const messages = data.messages;
            console.log('消息列表:', messages);

            let currentQuestion = null;
            let answers = [];

            for (let i = 0; i < messages.length; i++) {
                const msg = messages[i];
                const role = msg.role ? msg.role.toLowerCase() : '';
                console.log('消息' + i + ': role=' + role);

                if (role === 'user') {
                    // 保存上一个问题和它的回答
                    if (currentQuestion !== null) {
                        qa_pairs.push({
                            questionIndex: currentQuestion,
                            question: messages[currentQuestion],
                            answers: answers.slice()
                        });
                    }
                    currentQuestion = i;
                    answers = [];
                } else if (role === 'assistant' && currentQuestion !== null) {
                    answers.push({
                        index: i,
                        message: msg
                    });
                }
            }

            // 保存最后一个问题
            if (currentQuestion !== null) {
                qa_pairs.push({
                    questionIndex: currentQuestion,
                    question: messages[currentQuestion],
                    answers: answers.slice()
                });
            }

            console.log('共构建 ' + qa_pairs.length + ' 个QA对');
        }

        function renderQAPairs() {
            document.getElementById('loading').classList.add('hidden');

            if (qa_pairs.length === 0) {
                let debugInfo = '';
                if (conversation_data && conversation_data.messages) {
                    debugInfo = '<div style="color:#999;font-size:12px;margin-top:20px;">调试: 找到 ' + conversation_data.messages.length + ' 条消息</div>';
                }
                document.getElementById('messages').innerHTML = '<div class="empty-message">未找到对话内容，请检查链接是否正确</div>' + debugInfo;
                document.getElementById('messages').classList.remove('hidden');
                return;
            }

            let html = '';
            qa_pairs.forEach((pair, pairIdx) => {
                const qContent = pair.question.content || '(空内容)';
                const qPreview = qContent.length > 300 ? qContent.substring(0, 300) + '...' : qContent;

                html += '<div class="question-card" data-pair="' + pairIdx + '">';
                html += '<div class="question-header" onclick="toggleQuestion(' + pairIdx + ')">';
                html += '<div class="question-title">';
                html += '<span class="badge">Q' + (pairIdx + 1) + '</span>';
                html += '<span>用户问题</span>';
                html += '</div>';
                html += '<span class="toggle-icon" id="toggle-' + pairIdx + '">▼</span>';
                html += '</div>';
                html += '<div class="question-content" id="q-content-' + pairIdx + '">' + escapeHtml(qPreview) + '</div>';

                // 渲染回答
                if (pair.answers.length > 0) {
                    html += '<div class="answers-container" id="answers-' + pairIdx + '">';
                    pair.answers.forEach((ans, ansIdx) => {
                        const isSelected = selected.has(ans.index);
                        const aContent = ans.message.content || '(空内容)';
                        const aPreview = aContent.length > 500 ? aContent.substring(0, 500) + '...' : aContent;

                        html += '<div class="answer-card ' + (isSelected ? 'selected' : '') + '" id="answer-' + ans.index + '">';
                        html += '<div class="answer-header">';
                        html += '<div class="answer-label">';
                        html += '<span class="badge">A' + (ansIdx + 1) + '</span>';
                        html += '<span>大模型方案' + (ansIdx + 1) + '</span>';
                        if (isSelected) { html += ' ✓ 已选中'; }
                        html += '</div>';
                        html += '</div>';
                        html += '<div class="answer-content" id="a-content-' + ans.index + '">' + escapeHtml(aPreview) + '</div>';
                        html += '<div class="answer-actions">';
                        if (isSelected) {
                            html += '<button class="btn-unselect" onclick="event.stopPropagation(); unselectAnswer(' + ans.index + ')">取消选择</button>';
                        } else {
                            html += '<button class="btn-select" onclick="event.stopPropagation(); selectAnswer(' + ans.index + ', ' + pairIdx + ')">选择此方案</button>';
                        }
                        html += '</div>';
                        html += '</div>';
                    });
                    html += '</div>';
                } else {
                    // 没有回答的情况
                    html += '<div class="answers-container" id="answers-' + pairIdx + '">';
                    html += '<div style="color:#999;padding:10px;font-style:italic;">暂无大模型回答</div>';
                    html += '</div>';
                }

                html += '</div>';
            });

            document.getElementById('messages').innerHTML = html;
            document.getElementById('messages').classList.remove('hidden');
            document.getElementById('actions').classList.remove('hidden');
            updateStats();
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function toggleQuestion(pairIdx) {
            const content = document.getElementById('q-content-' + pairIdx);
            const answers = document.getElementById('answers-' + pairIdx);
            const icon = document.getElementById('toggle-' + pairIdx);

            if (content.style.display === 'none') {
                content.style.display = 'block';
                if (answers) answers.style.display = 'block';
                icon.classList.remove('collapsed');
            } else {
                content.style.display = 'none';
                if (answers) answers.style.display = 'none';
                icon.classList.add('collapsed');
            }
        }

        function toggleAnswerContent(ansIdx) {
            const content = document.getElementById('a-content-' + ansIdx);
            const icon = document.getElementById('a-toggle-' + ansIdx);

            if (content.style.maxHeight === '100px') {
                content.style.maxHeight = 'none';
                icon.classList.remove('collapsed');
            } else {
                content.style.maxHeight = '100px';
                icon.classList.add('collapsed');
            }
        }

        function selectAnswer(ansIdx, pairIdx) {
            // 选择这个回答
            selected.add(ansIdx);
            // 同时也选择对应的问题
            if (pairIdx !== undefined && qa_pairs[pairIdx]) {
                selected.add(qa_pairs[pairIdx].questionIndex);
            }
            renderQAPairs();
        }

        function unselectAnswer(ansIdx) {
            selected.delete(ansIdx);
            renderQAPairs();
        }

        function expandAll() {
            document.querySelectorAll('.question-content').forEach(el => el.style.display = 'block');
            document.querySelectorAll('.answers-container').forEach(el => el.style.display = 'block');
            document.querySelectorAll('.toggle-icon').forEach(el => el.classList.remove('collapsed'));
        }

        function collapseAll() {
            document.querySelectorAll('.question-content').forEach(el => el.style.display = 'none');
            document.querySelectorAll('.answers-container').forEach(el => el.style.display = 'none');
            document.querySelectorAll('.toggle-icon').forEach(el => el.classList.add('collapsed'));
        }

        function updateStats() {
            const total = conversation_data ? (conversation_data.messages ? conversation_data.messages.length : 0) : 0;
            const qaCount = qa_pairs.length;
            document.getElementById('stats').textContent = '已选: ' + selected.size + '条 / ' + qaCount + '个问答对';
        }

        async function exportData() {
            if (selected.size === 0) { alert('请先选择要导出的方案'); return; }

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
            renderQAPairs();
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

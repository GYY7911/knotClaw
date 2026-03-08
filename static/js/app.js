/**
 * Knotclaw Web 前端逻辑
 * 重构版本 - 更好的用户体验
 */

// ========== 状态管理 ==========
const state = {
    currentSessionId: null,
    currentTaskId: null,
    allMessages: [],
    selectedIndices: new Set(),
    // 新增：方案选择状态 { messageIndex: Set([sectionIndex, ...]) }
    selectedSections: {},
    isLoading: false,
    isDarkMode: false
};

// ========== DOM 元素缓存 ==========
const elements = {
    // 输入区域
    urlInput: document.getElementById('url'),
    fetchBtn: document.getElementById('fetchBtn'),
    inputArea: document.getElementById('inputArea'),

    // 加载状态
    loadingArea: document.getElementById('loadingArea'),
    loadingText: document.getElementById('loadingText'),
    progressBar: document.getElementById('progressBar'),

    // 结果区域
    resultArea: document.getElementById('resultArea'),
    messagesContainer: document.getElementById('messages'),
    totalMessages: document.getElementById('totalMessages'),
    selectedCount: document.getElementById('selectedCount'),
    exportCount: document.getElementById('exportCount'),
    exportBtn: document.getElementById('exportBtn'),
    selectAllBtn: document.getElementById('selectAllBtn'),

    // 弹窗
    errorToast: document.getElementById('error'),
    errorText: document.getElementById('errorText'),
    successModal: document.getElementById('successModal'),
    exportPath: document.getElementById('exportPath')
};

// ========== 主题切换 ==========
function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.setAttribute('data-theme', 'dark');
        state.isDarkMode = true;
    }
}

function toggleTheme() {
    state.isDarkMode = !state.isDarkMode;
    document.documentElement.setAttribute('data-theme', state.isDarkMode ? 'dark' : 'light');
    localStorage.setItem('theme', state.isDarkMode ? 'dark' : 'light');
}

// ========== 错误处理 ==========
function showError(message) {
    elements.errorText.textContent = message;
    elements.errorToast.style.display = 'flex';

    // 5秒后自动隐藏
    setTimeout(hideError, 5000);
}

function hideError() {
    elements.errorToast.style.display = 'none';
}

// ========== 加载状态 ==========
function setLoading(show, text = '正在获取对话...') {
    state.isLoading = show;
    elements.loadingArea.style.display = show ? 'flex' : 'none';
    elements.loadingText.textContent = text;
    elements.fetchBtn.disabled = show;

    if (show) {
        elements.progressBar.style.width = '0%';
        elements.progressBar.classList.remove('indeterminate');
        startProgressTimer();
    } else {
        stopProgressTimer();
        elements.progressBar.classList.remove('indeterminate');
    }
}

// 进度计时器
let progressTimer = null;
let progressStartTime = null;
let lastProgressText = '';

function updateProgress(percent, text) {
    elements.progressBar.style.width = `${percent}%`;
    if (text) {
        lastProgressText = text;
    }

    // 更新显示文本（包含时间）
    updateProgressDisplay(percent);

    // 在75%时添加不确定性动画
    if (percent >= 75 && percent < 100) {
        elements.progressBar.classList.add('indeterminate');
    } else {
        elements.progressBar.classList.remove('indeterminate');
    }
}

function updateProgressDisplay(percent) {
    if (!state.isLoading) return;

    const elapsed = Math.floor((Date.now() - progressStartTime) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;

    // 更友好的时间格式
    let timeStr;
    if (minutes > 0) {
        timeStr = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    } else {
        timeStr = `${seconds}s`;
    }

    // 根据进度显示不同的状态文本
    let statusHint = '';
    if (percent >= 75 && percent < 100) {
        statusHint = ' · 正在加载长对话';
    } else if (percent >= 50) {
        statusHint = ' · 请稍候';
    }

    elements.loadingText.textContent = `${lastProgressText} · ${timeStr}${statusHint}`;
}

function startProgressTimer() {
    progressStartTime = Date.now();
    if (progressTimer) clearInterval(progressTimer);

    // 每秒更新显示
    progressTimer = setInterval(() => {
        updateProgressDisplay(parseFloat(elements.progressBar.style.width) || 0);
    }, 1000);
}

function stopProgressTimer() {
    if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
    }
}

// ========== 核心功能：获取对话 ==========
async function startFetch() {
    const url = elements.urlInput.value.trim();

    if (!url) {
        showError('请输入 AI 对话分享链接');
        elements.urlInput.focus();
        return;
    }

    const urlCheck = isValidShareUrl(url);
    if (!urlCheck.valid) {
        showError('链接格式不正确，请输入有效的分享链接');
        return;
    }

    // 重置状态
    resetState();
    setLoading(true);

    try {
        // 创建会话
        updateProgress(5, '正在初始化...');
        const sessionRes = await fetch('/api/session', { method: 'POST' });
        const sessionData = await sessionRes.json();

        if (!sessionData.success) {
            throw new Error(sessionData.error?.message || '创建会话失败');
        }

        state.currentSessionId = sessionData.data.id;

        // 启动获取任务
        updateProgress(10, '正在启动浏览器...');
        const fetchRes = await fetch('/api/fetch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, session_id: state.currentSessionId })
        });
        const fetchData = await fetchRes.json();

        if (!fetchData.success) {
            throw new Error(fetchData.error?.message || '启动获取失败');
        }

        state.currentTaskId = fetchData.data.task_id;

        // 轮询任务状态
        await pollTaskStatus();

    } catch (error) {
        setLoading(false);
        showError(error.message);
        console.error('Fetch error:', error);
    }
}

// 支持的平台列表
const SUPPORTED_PLATFORMS = [
    { name: 'DeepSeek', domains: ['deepseek.com', 'chat.deepseek.com'], pattern: '/share/' },
    { name: 'Gemini', domains: ['gemini.google.com', 'bard.google.com'], pattern: '/share/' }
];

function isValidShareUrl(url) {
    try {
        const urlObj = new URL(url);
        for (const platform of SUPPORTED_PLATFORMS) {
            if (platform.domains.some(d => urlObj.hostname.includes(d)) &&
                url.includes(platform.pattern)) {
                return { valid: true, platform: platform.name };
            }
        }
    } catch (e) {
        // URL 解析失败
    }
    return { valid: false, platform: null };
}

function detectPlatform(url) {
    const result = isValidShareUrl(url);
    return result.valid ? result.platform : null;
}

async function pollTaskStatus() {
    const maxAttempts = 300; // 最多等待150秒（支持WAF验证和页面加载）
    let attempts = 0;
    let lastProgress = 0;

    const poll = async () => {
        attempts++;

        try {
            const res = await fetch(`/api/fetch/${state.currentTaskId}/status`);
            const data = await res.json();

            if (!data.success) {
                throw new Error(data.error?.message || '获取状态失败');
            }

            const task = data.data;
            const taskProgress = task.progress || 0;

            // 使用后端的实际进度，进度条范围 10%-95%
            const displayProgress = Math.min(10 + taskProgress * 0.85, 95);

            // 平滑进度显示：如果后端进度增加，直接使用；否则保持上次的进度
            if (taskProgress >= lastProgress) {
                lastProgress = taskProgress;
                updateProgress(displayProgress, `正在获取对话... ${taskProgress}%`);
            }

            if (task.status === 'completed') {
                updateProgress(100, '获取完成！');
                setTimeout(() => {
                    setLoading(false);
                    renderMessages(data.data.session);
                }, 300);
                return;
            }

            if (task.status === 'failed') {
                setLoading(false);
                showError(task.error_message || '获取失败');
                return;
            }

            if (attempts >= maxAttempts) {
                setLoading(false);
                showError('获取超时，请重试');
                return;
            }

            setTimeout(poll, 500);

        } catch (error) {
            setLoading(false);
            showError(error.message);
        }
    };

    await poll();
}

// ========== 消息渲染 ==========
function renderMessages(session) {
    if (!session?.messages?.length) {
        showError('没有获取到消息');
        return;
    }

    state.allMessages = session.messages;

    // 更新统计
    const conversationCount = session.messages.filter(m => m.role === 'user').length;
    elements.totalMessages.textContent = conversationCount;

    // 构建消息 HTML
    let html = '';
    let i = 0;

    while (i < session.messages.length) {
        const msg = session.messages[i];

        if (msg.role === 'user') {
            html += buildConversationGroup(session.messages, i);
            i = findNextUserIndex(session.messages, i + 1);
        } else {
            i++;
        }
    }

    elements.messagesContainer.innerHTML = html;
    elements.resultArea.style.display = 'block';
    updateSelectionUI();
}

function buildConversationGroup(messages, startIndex) {
    const userMsg = messages[startIndex];
    const userSelected = state.selectedIndices.has(startIndex);

    let html = `<div class="conversation-group">`;

    // 用户消息
    html += `
        <div class="user-message ${userSelected ? 'selected' : ''}" onclick="toggleSelection(${startIndex})">
            <div class="checkbox-indicator">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                    <polyline points="20,6 9,17 4,12"/>
                </svg>
            </div>
            <div class="role-badge">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                    <circle cx="12" cy="7" r="4"/>
                </svg>
                用户
            </div>
            <div class="content">${escapeHtml(userMsg.content)}</div>
        </div>
    `;

    // 查找助手的回复
    let thinkingContent = null;
    let thinkingIdx = -1;
    let answerContent = null;
    let answerIdx = -1;

    let j = startIndex + 1;
    while (j < messages.length && messages[j].role === 'assistant') {
        if (messages[j].isThinking && !thinkingContent) {
            thinkingContent = messages[j].content;
            thinkingIdx = j;
        } else if (!messages[j].isThinking && !answerContent) {
            answerContent = messages[j].content;
            answerIdx = j;
        }
        j++;
    }

    // 思考过程
    if (thinkingContent) {
        const thinkingSelected = state.selectedIndices.has(thinkingIdx);
        html += `
            <div class="thinking-block ${thinkingSelected ? 'selected' : ''}" onclick="toggleSelection(${thinkingIdx}, event)">
                <div class="thinking-header" onclick="handleThinkingClick(event, this, ${thinkingIdx})">
                    <div class="thinking-toggle-btn" title="展开/折叠">
                        <span class="toggle-icon">+</span>
                    </div>
                    <div class="thinking-label">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
                            <line x1="12" y1="17" x2="12.01" y2="17"/>
                        </svg>
                        <span>思考过程</span>
                    </div>
                </div>
                <div class="checkbox-indicator">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                        <polyline points="20,6 9,17 4,12"/>
                    </svg>
                </div>
                <div class="thinking-content">${escapeHtml(thinkingContent)}</div>
            </div>
        `;
    }

    // AI 回答
    if (answerContent) {
        const answerSelected = state.selectedIndices.has(answerIdx);

        // 检测是否包含多个方案
        const sections = parseAnswerSections(answerContent);

        if (sections.length > 1) {
            // 有多个方案，显示可选择的方案列表
            html += `
                <div class="answer-block ${answerSelected ? 'selected' : ''}" onclick="toggleSelection(${answerIdx})">
                    <div class="checkbox-indicator">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                            <polyline points="20,6 9,17 4,12"/>
                        </svg>
                    </div>
                    <div class="answer-header">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/>
                            <path d="M12 16v-4"/>
                            <path d="M12 8h.01"/>
                        </svg>
                        AI 回答 (${sections.length}个方案 · 点击选择全部)
                    </div>
                    <div class="answer-sections">
            `;

            // 渲染每个方案
            sections.forEach((section, secIdx) => {
                const sectionKey = `${answerIdx}-${secIdx}`;
                const sectionSelected = state.selectedSections[answerIdx]?.has(secIdx) || false;
                const previewContent = section.content.length > 200
                    ? section.content.substring(0, 200) + '...'
                    : section.content;

                html += `
                    <div class="answer-section ${sectionSelected ? 'selected' : ''}"
                         onclick="toggleSectionSelection(${answerIdx}, ${secIdx}, event)">
                        <div class="section-header">
                            <div class="section-checkbox">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                                    <polyline points="20,6 9,17 4,12"/>
                                </svg>
                            </div>
                            <span class="section-title">${escapeHtml(section.title)}</span>
                        </div>
                        <div class="section-preview">${escapeHtml(previewContent)}</div>
                    </div>
                `;
            });

            html += `
                    </div>
                </div>
            `;
        } else {
            // 单一方案，保持原有显示
            const previewContent = answerContent.length > 500
                ? answerContent.substring(0, 500) + '...'
                : answerContent;

            html += `
                <div class="answer-block ${answerSelected ? 'selected' : ''}" onclick="toggleSelection(${answerIdx})">
                    <div class="checkbox-indicator">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                            <polyline points="20,6 9,17 4,12"/>
                        </svg>
                    </div>
                    <div class="answer-header">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/>
                            <path d="M12 16v-4"/>
                            <path d="M12 8h.01"/>
                        </svg>
                        AI 回答 (点击选择)
                    </div>
                    <div class="answer-content">${escapeHtml(previewContent)}</div>
                </div>
            `;
        }
    }

    html += `</div>`;
    return html;
}

function findNextUserIndex(messages, startIndex) {
    for (let i = startIndex; i < messages.length; i++) {
        if (messages[i].role === 'user') {
            return i;
        }
    }
    return messages.length;
}

// ========== 方案解析 ==========
/**
 * 解析AI回答中的多个方案
 * 支持识别：方案一/二/三、方案A/B/C、Option 1/2/3、步骤一/二/三 等
 */
function parseAnswerSections(content) {
    if (!content) return [{ title: '完整回答', content: '' }];

    // 方案标题的正则模式
    const sectionPatterns = [
        // 中文方案：方案一、方案二、方案A等
        /(?:^|\n)(方案[一二三四五六七八九十\d]+[：:.]?\s*)/gm,
        /(?:^|\n)(方案[A-Z][：:.]?\s*)/gm,
        // 步骤：步骤一、步骤1等
        /(?:^|\n)(步骤[一二三四五六七八九十\d]+[：:.]?\s*)/gm,
        // 英文方案：Option 1, Solution A 等
        /(?:^|\n)((?:Option|Solution|Approach|Method)\s*[\dA-Z]+[：:.]?\s*)/gim,
        // 数字编号：1. 2. 3. 或 一、二、三、
        /(?:^|\n)(\d+[\.、]\s*[^\n]{2,20})/gm,
        /(?:^|\n)([一二三四五六七八九十]+[、\.]\s*[^\n]{2,20})/gm,
    ];

    let sections = [];
    let allMatches = [];

    // 收集所有匹配
    for (const pattern of sectionPatterns) {
        let match;
        const regex = new RegExp(pattern.source, pattern.flags);
        while ((match = regex.exec(content)) !== null) {
            allMatches.push({
                index: match.index,
                title: match[1].trim(),
                fullMatch: match[0]
            });
        }
    }

    // 去重并排序
    allMatches = allMatches
        .filter((m, i, arr) => arr.findIndex(x => x.index === m.index) === i)
        .sort((a, b) => a.index - b.index);

    // 如果找到至少2个方案，进行拆分
    if (allMatches.length >= 2) {
        for (let i = 0; i < allMatches.length; i++) {
            const start = allMatches[i].index;
            const end = i < allMatches.length - 1 ? allMatches[i + 1].index : content.length;
            const sectionContent = content.substring(start, end).trim();

            sections.push({
                title: allMatches[i].title,
                content: sectionContent
            });
        }
    } else {
        // 没有找到多个方案，返回整体
        sections = [{ title: '完整回答', content: content }];
    }

    return sections;
}

// 方案选择
function toggleSectionSelection(messageIndex, sectionIndex, event) {
    event.stopPropagation();

    if (!state.selectedSections[messageIndex]) {
        state.selectedSections[messageIndex] = new Set();
    }

    const sections = state.selectedSections[messageIndex];
    if (sections.has(sectionIndex)) {
        sections.delete(sectionIndex);
    } else {
        sections.add(sectionIndex);
    }

    // 更新UI
    renderMessages({ messages: state.allMessages });
    updateSelectionUI();
}

// ========== 选择管理 ==========
async function toggleSelection(index, event) {
    // 阻止事件冒泡
    if (event) {
        event.stopPropagation();
    }

    if (state.selectedIndices.has(index)) {
        state.selectedIndices.delete(index);
    } else {
        state.selectedIndices.add(index);
    }

    // 更新 UI（包含全选按钮状态更新）
    renderMessages({ messages: state.allMessages });

    // 同步到服务器
    if (state.currentSessionId) {
        try {
            await fetch(`/api/session/${state.currentSessionId}/selection`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ toggle: index })
            });
        } catch (error) {
            console.error('Update selection error:', error);
        }
    }
}

// 处理思考过程块的点击
function handleThinkingClick(event, header, index) {
    // 阻止事件冒泡到 thinking-block
    event.stopPropagation();

    const block = header.closest('.thinking-block');

    // 点击展开按钮区域时，只切换展开/折叠
    if (event.target.closest('.thinking-toggle-btn')) {
        toggleThinking(block);
        return;
    }

    // 点击其他区域（如标签），切换选择
    toggleSelection(index, null);
}

function toggleSelectAll() {
    // 切换全选/取消全选
    if (state.selectedIndices.size === state.allMessages.length) {
        clearSelection();
    } else {
        state.allMessages.forEach((_, index) => {
            state.selectedIndices.add(index);
        });
        renderMessages({ messages: state.allMessages });
        updateSelectionUI();
    }
}

async function clearSelection() {
    state.selectedIndices.clear();
    renderMessages({ messages: state.allMessages });

    if (state.currentSessionId) {
        try {
            await fetch(`/api/session/${state.currentSessionId}/selection`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clear: true })
            });
        } catch (error) {
            console.error('Clear selection error:', error);
        }
    }
}

function updateSelectionUI() {
    // 统计选中的消息数
    let count = state.selectedIndices.size;

    // 统计选中的方案数
    let sectionCount = 0;
    for (const msgIdx in state.selectedSections) {
        sectionCount += state.selectedSections[msgIdx].size;
    }

    // 显示总选择数
    const totalCount = count + sectionCount;
    elements.selectedCount.textContent = totalCount;
    elements.exportCount.textContent = totalCount;
    elements.exportBtn.disabled = totalCount === 0;

    // 更新全选按钮状态
    if (state.selectedIndices.size === state.allMessages.length && state.allMessages.length > 0) {
        elements.selectAllBtn.classList.add('checked');
    } else {
        elements.selectAllBtn.classList.remove('checked');
    }
}

// ========== 思考内容展开/折叠 ==========
function toggleThinking(block) {
    const content = block.querySelector('.thinking-content');
    const toggleBtn = block.querySelector('.thinking-toggle-btn');

    content.classList.toggle('show');
    toggleBtn.classList.toggle('expanded');

    // 更新图标： + 或 ^
    const icon = toggleBtn.querySelector('.toggle-icon');
    if (content.classList.contains('show')) {
        icon.textContent = '−';
    } else {
        icon.textContent = '+';
    }
}

// ========== 导出功能 ==========
async function exportSelected() {
    // 检查是否有选择
    const hasSelection = state.selectedIndices.size > 0 ||
        Object.keys(state.selectedSections).some(k => state.selectedSections[k].size > 0);

    if (!hasSelection) {
        showError('请先选择要导出的消息或方案');
        return;
    }

    elements.exportBtn.disabled = true;

    try {
        // 构建导出数据
        const exportData = buildExportData();

        const res = await fetch('/api/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.currentSessionId,
                custom_messages: exportData
            })
        });
        const data = await res.json();

        if (!data.success) {
            throw new Error(data.error?.message || '导出失败');
        }

        // 显示成功弹窗
        elements.exportPath.textContent = data.data.path;
        elements.successModal.style.display = 'flex';

    } catch (error) {
        showError(error.message);
        console.error('Export error:', error);
    } finally {
        elements.exportBtn.disabled = false;
    }
}

/**
 * 构建导出数据，处理方案选择
 */
function buildExportData() {
    const messages = [];

    state.allMessages.forEach((msg, index) => {
        if (state.selectedIndices.has(index)) {
            // 完整选中了这条消息
            // 检查是否有方案级别的选择
            if (state.selectedSections[index] && state.selectedSections[index].size > 0) {
                // 有方案选择，只导出选中的方案
                const sections = parseAnswerSections(msg.content);
                const selectedContents = [];

                state.selectedSections[index].forEach(secIdx => {
                    if (sections[secIdx]) {
                        selectedContents.push(sections[secIdx].content);
                    }
                });

                if (selectedContents.length > 0) {
                    messages.push({
                        role: msg.role,
                        content: selectedContents.join('\n\n---\n\n'),
                        isThinking: msg.isThinking
                    });
                }
            } else {
                // 没有方案选择，导出完整消息
                messages.push(msg);
            }
        } else if (state.selectedSections[index] && state.selectedSections[index].size > 0) {
            // 只选中了部分方案
            const sections = parseAnswerSections(msg.content);
            const selectedContents = [];

            state.selectedSections[index].forEach(secIdx => {
                if (sections[secIdx]) {
                    selectedContents.push(sections[secIdx].content);
                }
            });

            if (selectedContents.length > 0) {
                messages.push({
                    role: msg.role,
                    content: selectedContents.join('\n\n---\n\n'),
                    isThinking: msg.isThinking
                });
            }
        }
    });

    return messages;
}

function closeSuccessModal() {
    elements.successModal.style.display = 'none';
}

// ========== 工具函数 ==========
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function resetState() {
    state.currentSessionId = null;
    state.currentTaskId = null;
    state.allMessages = [];
    state.selectedIndices.clear();
    state.selectedSections = {};  // 清除方案选择状态
    elements.resultArea.style.display = 'none';
    elements.successModal.style.display = 'none';
}

// ========== 事件绑定 ==========
elements.urlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        startFetch();
    }
});

// 点击弹窗外部关闭
elements.successModal?.addEventListener('click', (e) => {
    if (e.target === elements.successModal) {
        closeSuccessModal();
    }
});

// ========== 初始化 ==========
initTheme();

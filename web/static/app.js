/**
 * Digital Employee Swarm — Frontend Logic
 */

const API = '';
let token = null;
let currentView = 'overview';

// === DOM ===
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// === Auth ===
$('#login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = $('#username').value;
    const password = $('#password').value;
    try {
        const res = await fetch(`${API}/api/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        if (!res.ok) { alert('登入失敗'); return; }
        const data = await res.json();
        token = data.token;
        $('#user-display').textContent = data.user.display_name;
        $('#user-role').textContent = data.user.role;
        $('#login-screen').classList.add('hidden');
        $('#dashboard').classList.remove('hidden');
        loadDashboard();
    } catch (err) {
        alert('連線失敗: ' + err.message);
    }
});

$('#logout-btn').addEventListener('click', () => {
    token = null;
    $('#dashboard').classList.add('hidden');
    $('#login-screen').classList.remove('hidden');
});

// === Navigation ===
$$('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
        $$('.nav-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        currentView = item.dataset.view;
        $$('.view').forEach(v => v.classList.remove('active'));
        $(`#view-${currentView}`).classList.add('active');
        const titles = {
            overview: '系統總覽', chat: 'Agent 對話',
            agents: 'Agent Fleet', history: '任務歷史', system: '系統監控'
        };
        $('#page-title').textContent = titles[currentView] || '';
        if (currentView === 'history') loadHistory();
        if (currentView === 'agents') loadAgents();
        if (currentView === 'system') loadSystem();
    });
});

// === Dashboard ===
async function loadDashboard() {
    try {
        const res = await fetch(`${API}/api/status?token=${token}`);
        const data = await res.json();

        // Stats
        const agents = Object.values(data.agents);
        const totalTasks = agents.reduce((s, a) => s + a.tasks_completed, 0);
        const mcpHealth = data.mcp;
        const connected = Object.values(mcpHealth).filter(v => v).length;
        const total = Object.keys(mcpHealth).length;

        $('#stat-agents').textContent = agents.length;
        $('#stat-tasks').textContent = totalTasks;
        $('#stat-mcp').textContent = `${connected}/${total}`;
        $('#stat-skills').textContent = data.skills.count;
        $('#stat-vectors').textContent = data.vector_store.documents;

        // LLM badge
        const llm = data.llm;
        if (llm.is_llm) {
            $('#llm-badge').textContent = `LLM: ${llm.active}`;
            $('#llm-badge').className = 'badge';
        } else {
            $('#llm-badge').textContent = '離線模式';
            $('#llm-badge').className = 'badge badge-warn';
        }
        $('#intent-badge').textContent = data.intent_mode;

        // Agent list
        const listEl = $('#agent-status-list');
        listEl.innerHTML = agents.map(a => `
            <div class="agent-row">
                <div class="agent-name">
                    <span class="status-dot ${a.status.toLowerCase()}"></span>
                    ${a.name}
                </div>
                <div class="agent-meta">${a.role} · ${a.tasks_completed} tasks</div>
            </div>
        `).join('');

    } catch (err) {
        console.error('Dashboard load failed:', err);
    }
}

// === Chat ===
$('#chat-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendMessage();
});
$('#chat-send').addEventListener('click', sendMessage);

$$('.quick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        $('#chat-input').value = btn.dataset.prompt;
        sendMessage();
    });
});

async function sendMessage() {
    const input = $('#chat-input');
    const prompt = input.value.trim();
    if (!prompt) return;
    input.value = '';
    input.disabled = true;
    $('#chat-send').disabled = true;

    // Remove welcome
    const welcome = $('.chat-welcome');
    if (welcome) welcome.remove();

    // User message
    appendChat('user', '你', prompt);

    // Processing
    const procId = appendChat('agent', 'Agent', '處理中...', true);

    try {
        const res = await fetch(`${API}/api/dispatch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, token }),
        });
        const data = await res.json();
        updateChat(procId, data.result);
    } catch (err) {
        updateChat(procId, '❌ 錯誤: ' + err.message);
    }

    input.disabled = false;
    $('#chat-send').disabled = false;
    input.focus();
    loadDashboard(); // refresh stats
}

let msgCounter = 0;
function appendChat(type, sender, text, processing = false) {
    const id = `msg-${++msgCounter}`;
    const icon = type === 'user' ? '👤' : '🤖';
    const el = document.createElement('div');
    el.id = id;
    el.className = 'chat-msg';
    el.innerHTML = `
        <div class="chat-avatar ${type}">${icon}</div>
        <div class="chat-bubble">
            <div class="chat-sender">${sender}</div>
            <div class="chat-text ${processing ? 'processing' : ''}">${escapeHtml(text)}</div>
        </div>
    `;
    $('#chat-messages').appendChild(el);
    $('#chat-messages').scrollTop = $('#chat-messages').scrollHeight;
    return id;
}

function updateChat(id, text) {
    const el = document.getElementById(id);
    if (el) {
        const textEl = el.querySelector('.chat-text');
        textEl.textContent = text;
        textEl.classList.remove('processing');
    }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// === Agents View ===
async function loadAgents() {
    try {
        const res = await fetch(`${API}/api/agents?token=${token}`);
        const data = await res.json();
        const grid = $('#agents-grid');
        grid.innerHTML = Object.entries(data.agents).map(([name, a]) => `
            <div class="agent-card">
                <div class="agent-card-header">
                    <h3>${name}</h3>
                    <span class="status-dot ${a.status.toLowerCase()}"></span>
                </div>
                <div class="role">${a.role}</div>
                <div class="desc">${a.description}</div>
                <div class="keywords">
                    ${(a.trigger_keywords || []).map(k => `<span class="keyword-tag">${k}</span>`).join('')}
                </div>
                <div class="meta">
                    <span class="meta-item">Tasks: ${a.tasks_completed}</span>
                    <span class="meta-item">LLM: ${a.llm_provider}</span>
                </div>
            </div>
        `).join('');
    } catch (err) { console.error(err); }
}

// === History ===
async function loadHistory() {
    try {
        const res = await fetch(`${API}/api/history?token=${token}`);
        const data = await res.json();
        const el = $('#history-table');
        if (!data.history.length) {
            el.innerHTML = '<p class="empty-msg">尚無任務記錄</p>';
            return;
        }
        el.innerHTML = `
            <div class="history-row header">
                <span>Agent</span><span>風險</span><span>信心度</span><span>指令</span>
            </div>
            ${data.history.map(h => `
                <div class="history-row">
                    <span class="task-agent">${h.agent}</span>
                    <span>${h.risk}</span>
                    <span>${(h.confidence * 100).toFixed(0)}%</span>
                    <span class="task-prompt">${h.prompt}</span>
                </div>
            `).join('')}
        `;
    } catch (err) { console.error(err); }
}

// === System ===
async function loadSystem() {
    try {
        const [mcpRes, skillsRes] = await Promise.all([
            fetch(`${API}/api/mcp?token=${token}`),
            fetch(`${API}/api/skills?token=${token}`),
        ]);
        const mcp = await mcpRes.json();
        const skills = await skillsRes.json();

        $('#mcp-list').innerHTML = Object.entries(mcp.resources).map(([name, r]) => `
            <div class="resource-item">
                <span>${name}</span>
                <span class="${r.connected ? 'connected' : 'disconnected'}">
                    ${r.connected ? '🟢 連線中' : '🔴 未連線'}
                </span>
            </div>
        `).join('');

        $('#skills-list').innerHTML = skills.skills.map(s => `
            <div class="skill-item">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <span class="skill-name">${s.name}</span>
                    <span class="skill-category">${s.category}</span>
                </div>
                <div class="skill-desc">${s.description}</div>
            </div>
        `).join('');

        // Vector info
        const statusRes = await fetch(`${API}/api/status?token=${token}`);
        const status = await statusRes.json();
        const vs = status.vector_store;
        $('#vector-info').innerHTML = `
            <div class="resource-item"><span>Backend</span><span>${vs.backend}</span></div>
            <div class="resource-item"><span>Collection</span><span>${vs.collection}</span></div>
            <div class="resource-item"><span>Documents</span><span>${vs.documents}</span></div>
        `;
    } catch (err) { console.error(err); }
}

// Auto-refresh
setInterval(loadDashboard, 30000);

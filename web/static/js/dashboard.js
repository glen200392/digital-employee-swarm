/**
 * Dashboard Extension — Tasks, Performance, Integrations views
 * Depends on: app.js (provides `token`, `API`, `escapeHtml`)
 */

/* ======================== */
/*  Tasks View              */
/* ======================== */

let tasksFilter = { agent: '', status: '', risk: '', search: '' };

async function loadTasks() {
    const params = new URLSearchParams({ token });
    if (tasksFilter.agent)  params.set('agent',  tasksFilter.agent);
    if (tasksFilter.status) params.set('status', tasksFilter.status);
    if (tasksFilter.risk)   params.set('risk',   tasksFilter.risk);

    try {
        const res = await fetch(`${API}/api/tasks?${params}`);
        if (!res.ok) return;
        const data = await res.json();
        let tasks = data.tasks || [];

        // Client-side task_id search
        if (tasksFilter.search) {
            const q = tasksFilter.search.toLowerCase();
            tasks = tasks.filter(t =>
                (t.task_id || '').toLowerCase().includes(q) ||
                (t.agent_name || '').toLowerCase().includes(q)
            );
        }

        renderTasksTable(tasks, data.total);
    } catch (err) { console.error('loadTasks error:', err); }
}

function renderTasksTable(tasks, total) {
    const el = document.getElementById('tasks-table-body');
    const countEl = document.getElementById('tasks-count');
    if (countEl) countEl.textContent = `共 ${total} 筆`;
    if (!el) return;

    if (!tasks.length) {
        el.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-secondary,#8b8fa3);padding:2rem">尚無任務記錄</td></tr>';
        return;
    }

    el.innerHTML = tasks.map(t => {
        const statusCls = (t.status || 'completed').toLowerCase();
        const riskCls   = (t.risk_level || 'low').toLowerCase();
        const score     = typeof t.eval_score === 'number' ? (t.eval_score * 100).toFixed(0) + '%' : '—';
        const time      = t.created_at ? t.created_at.slice(0, 16) : '—';
        const shortId   = (t.task_id || '—').slice(0, 12);
        return `<tr>
            <td title="${escapeHtml(t.task_id || '')}">${escapeHtml(shortId)}</td>
            <td>${escapeHtml(t.agent_name || '—')}</td>
            <td><span class="badge-status ${statusCls}">${t.status || '—'}</span></td>
            <td>${score}</td>
            <td><span class="badge-risk ${riskCls}">${t.risk_level || '—'}</span></td>
            <td>${time}</td>
        </tr>`;
    }).join('');
}

function initTasksFilter() {
    const agentSel  = document.getElementById('filter-agent');
    const statusSel = document.getElementById('filter-status');
    const riskSel   = document.getElementById('filter-risk');
    const searchIn  = document.getElementById('filter-search');
    const applyBtn  = document.getElementById('filter-apply');
    const clearBtn  = document.getElementById('filter-clear');

    if (!applyBtn) return;

    applyBtn.addEventListener('click', () => {
        tasksFilter.agent  = agentSel  ? agentSel.value  : '';
        tasksFilter.status = statusSel ? statusSel.value : '';
        tasksFilter.risk   = riskSel   ? riskSel.value   : '';
        tasksFilter.search = searchIn  ? searchIn.value.trim() : '';
        loadTasks();
    });

    clearBtn && clearBtn.addEventListener('click', () => {
        if (agentSel)  agentSel.value  = '';
        if (statusSel) statusSel.value = '';
        if (riskSel)   riskSel.value   = '';
        if (searchIn)  searchIn.value  = '';
        tasksFilter = { agent: '', status: '', risk: '', search: '' };
        loadTasks();
    });
}

/* ======================== */
/*  Performance View        */
/* ======================== */

let perfCharts = {};

async function loadPerformance() {
    try {
        const res = await fetch(`${API}/api/metrics?token=${token}`);
        if (!res.ok) return;
        const data = await res.json();
        renderPerformanceCharts(data);
    } catch (err) { console.error('loadPerformance error:', err); }
}

function destroyChart(id) {
    if (perfCharts[id]) {
        perfCharts[id].destroy();
        delete perfCharts[id];
    }
}

function renderPerformanceCharts(data) {
    const AGENT_COLORS = {
        KM_AGENT:       '#6c5ce7',
        PROCESS_AGENT:  '#e94560',
        TALENT_AGENT:   '#00b894',
        DECISION_AGENT: '#fdcb6e',
    };

    const days  = data.days  || [];
    const trend = data.trend_data || {};
    const rate  = data.success_rate || {};
    const risk  = data.risk_distribution || {};

    // --- Trend line chart ---
    destroyChart('trendChart');
    const trendCtx = document.getElementById('trendChart');
    if (trendCtx) {
        perfCharts.trendChart = new Chart(trendCtx, {
            type: 'line',
            data: {
                labels: days.map(d => d.slice(5)),
                datasets: Object.entries(trend).map(([name, scores]) => ({
                    label: name,
                    data: scores,
                    borderColor: AGENT_COLORS[name] || '#8b8fa3',
                    backgroundColor: (AGENT_COLORS[name] || '#8b8fa3') + '22',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                    pointRadius: 3,
                })),
            },
            options: {
                responsive: true,
                plugins: { legend: { labels: { color: '#e2e8f0', font: { size: 11 } } } },
                scales: {
                    x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                    y: { min: 0, max: 1, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                },
            },
        });
    }

    // --- Success rate bar chart ---
    destroyChart('rateChart');
    const rateCtx = document.getElementById('rateChart');
    if (rateCtx) {
        const agents = Object.keys(rate);
        perfCharts.rateChart = new Chart(rateCtx, {
            type: 'bar',
            data: {
                labels: agents,
                datasets: [{
                    label: '成功率',
                    data: agents.map(a => (rate[a] * 100).toFixed(1)),
                    backgroundColor: agents.map(a => AGENT_COLORS[a] || '#6c5ce7'),
                    borderRadius: 6,
                }],
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { display: false } },
                    y: { min: 0, max: 100, ticks: { color: '#94a3b8', callback: v => v + '%' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                },
            },
        });
    }

    // --- Risk distribution pie chart ---
    destroyChart('riskChart');
    const riskCtx = document.getElementById('riskChart');
    if (riskCtx) {
        perfCharts.riskChart = new Chart(riskCtx, {
            type: 'doughnut',
            data: {
                labels: ['LOW', 'MEDIUM', 'HIGH'],
                datasets: [{
                    data: [risk.LOW || 0, risk.MEDIUM || 0, risk.HIGH || 0],
                    backgroundColor: ['#22c55e', '#f59e0b', '#ef4444'],
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#e2e8f0', font: { size: 11 } } },
                },
                cutout: '65%',
            },
        });
    }

    // Summary stats
    const totalEl = document.getElementById('perf-total-tasks');
    if (totalEl) totalEl.textContent = data.total_tasks || 0;
}

/* ======================== */
/*  Integrations View       */
/* ======================== */

async function loadIntegrations() {
    try {
        const res = await fetch(`${API}/api/integrations?token=${token}`);
        if (!res.ok) return;
        const data = await res.json();
        renderIntegrations(data.integrations || []);
    } catch (err) { console.error('loadIntegrations error:', err); }
}

const INTEG_ICONS = {
    '知識庫': '📚', '報告庫': '📊', '進度日誌': '📝',
    '向量資料庫': '🔍', '企業ERP': '🏢', '企業CRM': '👥',
};

function renderIntegrations(items) {
    const el = document.getElementById('integrations-grid');
    if (!el) return;
    if (!items.length) {
        el.innerHTML = '<p style="color:var(--text-secondary,#8b8fa3)">無整合資源</p>';
        return;
    }
    el.innerHTML = items.map(item => {
        const icon = INTEG_ICONS[item.name] || '🔌';
        const cls  = item.connected ? 'connected' : 'disconnected';
        const label = item.connected ? '🟢 已連線' : '🔴 未連線';
        return `<div class="integration-card">
            <span class="integ-icon">${icon}</span>
            <div>
                <div class="integ-name">${escapeHtml(item.name)}</div>
                <div class="integ-status ${cls}">${label}</div>
            </div>
        </div>`;
    }).join('');
}

/* ======================== */
/*  Init (on DOMContentLoaded) */
/* ======================== */
document.addEventListener('DOMContentLoaded', () => {
    initTasksFilter();
});

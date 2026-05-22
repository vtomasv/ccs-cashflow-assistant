/**
 * CCS Cashflow Assistant v2 — Frontend Application
 * Motor Financiero Modular con Simulación Monte Carlo
 */

// ============================================================================
// Estado Global
// ============================================================================
const API = '';  // Same origin
let state = {
  companyId: null,
  companyName: '',
  companySector: '',
  sessionId: '',
  cashflow: null,
  charts: {},
  generationTaskId: null,
  mcTaskId: null,
};

// ============================================================================
// Inicialización
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  checkReadiness();
  loadCompanies();
});

async function checkReadiness() {
  const overlay = document.getElementById('readiness-overlay');
  const msg = document.getElementById('readiness-msg');
  const bar = document.getElementById('readiness-bar');

  try {
    const r = await fetch(`${API}/api/readiness`);
    const data = await r.json();

    if (data.ready) {
      overlay.classList.add('hidden');
      document.getElementById('ollama-dot').className = 'status-dot ok';
      document.getElementById('ollama-label').textContent = `Ollama OK (${data.models_count} modelos)`;
      return;
    }

    // Not ready yet
    if (data.issues && data.issues.length > 0) {
      msg.textContent = data.issues[0].message;
    }
    bar.style.width = '30%';

    // Poll until ready
    const poll = setInterval(async () => {
      try {
        const r2 = await fetch(`${API}/api/readiness`);
        const d2 = await r2.json();
        if (d2.ready) {
          clearInterval(poll);
          overlay.classList.add('hidden');
          document.getElementById('ollama-dot').className = 'status-dot ok';
          document.getElementById('ollama-label').textContent = `Ollama OK (${d2.models_count} modelos)`;
        } else {
          if (d2.active_pulls && d2.active_pulls.length > 0) {
            const p = d2.active_pulls[0];
            msg.textContent = `Descargando modelo ${p.model}... ${p.progress}%`;
            bar.style.width = `${Math.max(30, p.progress)}%`;
          }
        }
      } catch(e) {}
    }, 3000);
  } catch(e) {
    msg.textContent = 'Error conectando con el servidor...';
    document.getElementById('ollama-dot').className = 'status-dot err';
    document.getElementById('ollama-label').textContent = 'Desconectado';
    setTimeout(() => { overlay.classList.add('hidden'); }, 3000);
  }
}

// ============================================================================
// Navegación
// ============================================================================
function switchPage(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById(`page-${page}`).classList.add('active');

  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(n => {
    if (n.getAttribute('onclick') === `switchPage('${page}')`) n.classList.add('active');
  });

  const titles = {
    interview: 'Entrevista Financiera',
    dashboard: 'Dashboard — Flujo de Caja',
    simulation: 'Simulación Interactiva',
    montecarlo: 'Simulación Monte Carlo',
    scenarios: 'Escenarios y Versiones',
    metrics: 'Métricas Financieras',
    settings: 'Configuración',
  };
  document.getElementById('page-title').textContent = titles[page] || page;

  // Load data for specific pages
  if (page === 'dashboard' && state.companyId) loadCashflow();
  if (page === 'scenarios' && state.companyId) { loadScenarios(); loadVersions(); }
  if (page === 'metrics' && state.companyId) loadMetrics();
  if (page === 'settings') loadSettings();
}

// ============================================================================
// Empresas
// ============================================================================
async function loadCompanies() {
  try {
    const r = await fetch(`${API}/api/companies`);
    const data = await r.json();
    const select = document.getElementById('company-select');
    select.innerHTML = '<option value="">Seleccionar...</option>';
    (data.companies || []).forEach(c => {
      select.innerHTML += `<option value="${c.id}">${c.name}</option>`;
    });
    // Auto-select if only one
    if (data.companies && data.companies.length === 1) {
      select.value = data.companies[0].id;
      selectCompany(data.companies[0].id);
    }
  } catch(e) { console.error('Error loading companies:', e); }
}

async function selectCompany(id) {
  if (!id) return;
  state.companyId = id;
  state.sessionId = '';
  try {
    const r = await fetch(`${API}/api/companies/${id}`);
    const company = await r.json();
    state.companyName = company.name;
    state.companySector = company.sector;

    // Load sessions to restore chat
    const sr = await fetch(`${API}/api/companies/${id}/sessions`);
    const sessions = await sr.json();
    const interviewSessions = (sessions.sessions || []).filter(s => s.type === 'interview' || s.type === 'interview_v2');

    if (interviewSessions.length > 0) {
      const lastSession = interviewSessions[interviewSessions.length - 1];
      state.sessionId = lastSession.id;
      await loadSession(id, lastSession.id);
    } else {
      // Start new interview
      const chatDiv = document.getElementById('chat-messages');
      chatDiv.innerHTML = `<div class="chat-msg system">Bienvenido. Soy tu analista financiero. Vamos a construir el modelo de flujo de caja para <strong>${company.name}</strong>. Cuéntame sobre tu negocio.</div>`;
    }

    // Show generate button if company has enough data
    if (company.status === 'interviewing' || company.status === 'complete') {
      document.getElementById('btn-generate').style.display = 'flex';
    }

    // Load cashflow if exists
    if (company.status === 'complete') {
      loadCashflow();
    }

    updateInterviewTopics();
  } catch(e) { console.error('Error selecting company:', e); }
}

async function loadSession(companyId, sessionId) {
  try {
    const r = await fetch(`${API}/api/companies/${companyId}/sessions/${sessionId}`);
    const session = await r.json();
    const chatDiv = document.getElementById('chat-messages');
    chatDiv.innerHTML = '';
    (session.messages || []).forEach(msg => {
      addChatBubble(msg.role, msg.content);
    });
    chatDiv.scrollTop = chatDiv.scrollHeight;
  } catch(e) {}
}

function openModal(id) { document.getElementById(id).classList.add('open'); }
function closeModal(id) { document.getElementById(id).classList.remove('open'); }

async function createCompany() {
  const name = document.getElementById('new-name').value.trim();
  const sector = document.getElementById('new-sector').value.trim();
  const desc = document.getElementById('new-desc').value.trim();
  if (!name) return alert('Ingresa un nombre');

  try {
    const r = await fetch(`${API}/api/companies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, sector, description: desc })
    });
    const company = await r.json();
    closeModal('modal-new-company');
    document.getElementById('new-name').value = '';
    document.getElementById('new-sector').value = '';
    document.getElementById('new-desc').value = '';
    await loadCompanies();
    document.getElementById('company-select').value = company.id;
    selectCompany(company.id);
  } catch(e) { alert('Error creando empresa'); }
}

// ============================================================================
// Chat / Entrevista
// ============================================================================
async function sendMessage() {
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if (!msg || !state.companyId) return;

  input.value = '';
  addChatBubble('user', msg);

  try {
    const r = await fetch(`${API}/api/chat/interview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company_id: state.companyId, message: msg, session_id: state.sessionId })
    });
    const data = await r.json();
    state.sessionId = data.session_id;
    addChatBubble('assistant', data.response);

    // Show generate button
    document.getElementById('btn-generate').style.display = 'flex';
    updateInterviewTopics();
  } catch(e) {
    addChatBubble('system', 'Error comunicando con el servidor. Verifica que Ollama esté activo.');
  }
}

function addChatBubble(role, content) {
  const chatDiv = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = `chat-msg ${role}`;
  // Simple markdown rendering
  div.innerHTML = content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>');
  chatDiv.appendChild(div);
  chatDiv.scrollTop = chatDiv.scrollHeight;
}

function updateInterviewTopics() {
  const topics = [
    { id: 'business', label: 'Tipo de negocio', icon: 'fa-store' },
    { id: 'products', label: 'Productos/Servicios', icon: 'fa-box' },
    { id: 'revenue', label: 'Modelo de ingresos', icon: 'fa-dollar-sign' },
    { id: 'costs', label: 'Costos y gastos', icon: 'fa-receipt' },
    { id: 'growth', label: 'Crecimiento esperado', icon: 'fa-chart-line' },
    { id: 'seasonality', label: 'Estacionalidad', icon: 'fa-calendar' },
    { id: 'cash', label: 'Caja y financiamiento', icon: 'fa-piggy-bank' },
    { id: 'risks', label: 'Riesgos principales', icon: 'fa-shield-alt' },
  ];

  const container = document.getElementById('interview-topics');
  container.innerHTML = topics.map(t =>
    `<div style="display:flex; align-items:center; gap:8px; padding:6px 8px; border-radius:6px; margin-bottom:4px; background:rgba(58,109,222,0.05); border:1px solid var(--border);">
      <i class="fas ${t.icon}" style="font-size:11px; color:var(--text-muted); width:16px;"></i>
      <span style="font-size:11px; color:var(--text-muted);">${t.label}</span>
    </div>`
  ).join('');
}

// ============================================================================
// Generación de Cashflow
// ============================================================================
async function generateCashflow() {
  if (!state.companyId) return;

  switchPage('dashboard');
  const panel = document.getElementById('gen-progress-panel');
  panel.style.display = 'block';

  try {
    // Use V2 endpoint
    const r = await fetch(`${API}/api/v2/companies/${state.companyId}/generate-cashflow`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ months: 12, use_market_data: true, run_monte_carlo: true, monte_carlo_iterations: 500 })
    });
    const data = await r.json();

    if (data.task_id) {
      state.generationTaskId = data.task_id;
      pollGenerationProgress(data.task_id);
    }
  } catch(e) {
    // Fallback to V1
    try {
      const r = await fetch(`${API}/api/companies/${state.companyId}/generate-cashflow`, { method: 'POST' });
      const data = await r.json();
      if (data.task_id) {
        state.generationTaskId = data.task_id;
        pollGenerationProgressV1(data.task_id);
      }
    } catch(e2) {
      panel.innerHTML = '<p style="color:var(--danger);">Error iniciando generación</p>';
    }
  }
}

function pollGenerationProgress(taskId) {
  const poll = setInterval(async () => {
    try {
      const r = await fetch(`${API}/api/v2/generation/${taskId}/progress`);
      const data = await r.json();

      document.getElementById('gen-bar').style.width = `${data.progress}%`;
      document.getElementById('gen-pct').textContent = `${data.progress}%`;
      document.getElementById('gen-step').textContent = data.step || '';

      // Show notifications
      if (data.notifications && data.notifications.length > 0) {
        const notifDiv = document.getElementById('gen-notifications');
        notifDiv.innerHTML = data.notifications.map(n =>
          `<div class="notification-item">${n.message}</div>`
        ).join('');
        notifDiv.scrollTop = notifDiv.scrollHeight;
      }

      if (data.status === 'done') {
        clearInterval(poll);
        document.getElementById('gen-progress-panel').style.display = 'none';
        loadCashflow();
      } else if (data.status === 'error') {
        clearInterval(poll);
        document.getElementById('gen-step').textContent = `Error: ${data.error}`;
        document.getElementById('gen-bar').style.background = 'var(--danger)';
      }
    } catch(e) {}
  }, 1500);
}

function pollGenerationProgressV1(taskId) {
  const poll = setInterval(async () => {
    try {
      const r = await fetch(`${API}/api/generation/${taskId}/progress`);
      const data = await r.json();
      document.getElementById('gen-bar').style.width = `${data.progress}%`;
      document.getElementById('gen-pct').textContent = `${data.progress}%`;
      document.getElementById('gen-step').textContent = data.step || '';

      if (data.status === 'done') {
        clearInterval(poll);
        document.getElementById('gen-progress-panel').style.display = 'none';
        loadCashflow();
      } else if (data.status === 'error') {
        clearInterval(poll);
        document.getElementById('gen-step').textContent = `Error: ${data.error}`;
      }
    } catch(e) {}
  }, 2000);
}

// ============================================================================
// Dashboard
// ============================================================================
async function loadCashflow() {
  if (!state.companyId) return;
  try {
    const r = await fetch(`${API}/api/companies/${state.companyId}/cashflow`);
    if (!r.ok) return;
    state.cashflow = await r.json();
    renderDashboard();
  } catch(e) {}
}

function renderDashboard() {
  const cf = state.cashflow;
  if (!cf || !cf.months || cf.months.length === 0) return;

  const summary = cf.summary || {};
  const months = cf.months;
  const metrics = cf.metrics || {};

  // Stats
  renderStats(summary, metrics);
  // Charts
  renderCashflowChart(months);
  renderBalanceChart(months);
  renderExpensesPie(months);
  renderIncomeExpensesChart(months);
  // Table
  renderMonthlyTable(months);
  // Alerts
  renderAlerts(cf.alerts || []);
}

function renderStats(summary, metrics) {
  const stats = document.getElementById('dashboard-stats');
  const fmt = (n) => {
    if (Math.abs(n) >= 1000000) return `$${(n/1000000).toFixed(1)}M`;
    if (Math.abs(n) >= 1000) return `$${(n/1000).toFixed(0)}K`;
    return `$${n.toFixed(0)}`;
  };

  const items = [
    { label: 'Ingresos Totales', value: fmt(summary.total_income || 0), color: 'green' },
    { label: 'Gastos Totales', value: fmt(summary.total_expenses || 0), color: 'red' },
    { label: 'Flujo Neto', value: fmt(summary.net_cashflow || 0), color: (summary.net_cashflow || 0) >= 0 ? 'green' : 'red' },
    { label: 'Promedio Mensual', value: fmt(summary.average_monthly_balance || 0), color: '' },
    { label: 'Margen Bruto', value: metrics.margen_bruto_pct ? `${metrics.margen_bruto_pct.toFixed(1)}%` : '-', color: 'purple' },
    { label: 'Runway', value: metrics.runway_meses ? `${metrics.runway_meses} meses` : '-', color: 'yellow' },
  ];

  stats.innerHTML = items.map(i =>
    `<div class="stat-card ${i.color}"><div class="stat-label">${i.label}</div><div class="stat-value" style="font-size:18px;">${i.value}</div></div>`
  ).join('');
}

function renderCashflowChart(months) {
  const ctx = document.getElementById('chart-cashflow');
  if (state.charts.cashflow) state.charts.cashflow.destroy();

  state.charts.cashflow = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: months.map(m => m.label || m.month),
      datasets: [
        { label: 'Ingresos', data: months.map(m => m.income?.total || 0), backgroundColor: 'rgba(34,197,94,0.7)', borderRadius: 4 },
        { label: 'Gastos', data: months.map(m => -(m.expenses?.total || 0)), backgroundColor: 'rgba(239,68,68,0.7)', borderRadius: 4 },
        { label: 'Flujo Neto', data: months.map(m => m.net_flow || 0), type: 'line', borderColor: '#3b82f6', borderWidth: 2, pointRadius: 3, fill: false }
      ]
    },
    options: chartOptions('Monto ($)')
  });
}

function renderBalanceChart(months) {
  const ctx = document.getElementById('chart-balance');
  if (state.charts.balance) state.charts.balance.destroy();

  const balances = months.map(m => m.cumulative_balance || 0);
  const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 200);
  gradient.addColorStop(0, 'rgba(59,130,246,0.3)');
  gradient.addColorStop(1, 'rgba(59,130,246,0.0)');

  state.charts.balance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: months.map(m => m.label || m.month),
      datasets: [{
        label: 'Saldo Acumulado',
        data: balances,
        borderColor: '#3b82f6',
        backgroundColor: gradient,
        fill: true,
        tension: 0.3,
        pointRadius: 3,
      }]
    },
    options: chartOptions('Saldo ($)')
  });
}

function renderExpensesPie(months) {
  const ctx = document.getElementById('chart-expenses');
  if (state.charts.expenses) state.charts.expenses.destroy();

  let totals = { variable_costs: 0, fixed_costs: 0, variable_expenses: 0, debt_payments: 0, taxes: 0, investments: 0 };
  months.forEach(m => {
    const e = m.expenses || {};
    totals.variable_costs += e.variable_costs || 0;
    totals.fixed_costs += e.fixed_costs || 0;
    totals.variable_expenses += e.variable_expenses || 0;
    totals.debt_payments += e.debt_payments || 0;
    totals.taxes += e.taxes || 0;
    totals.investments += e.investments || 0;
  });

  state.charts.expenses = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['C. Variables', 'C. Fijos', 'Gastos Var.', 'Deudas', 'Impuestos', 'Inversiones'],
      datasets: [{
        data: Object.values(totals),
        backgroundColor: ['#ef4444', '#f97316', '#eab308', '#8b5cf6', '#06b6d4', '#22c55e'],
      }]
    },
    options: { responsive: true, plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } } } }
  });
}

function renderIncomeExpensesChart(months) {
  const ctx = document.getElementById('chart-income-expenses');
  if (state.charts.incomeExpenses) state.charts.incomeExpenses.destroy();

  state.charts.incomeExpenses = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: months.map(m => m.label || m.month),
      datasets: [
        { label: 'Ingresos', data: months.map(m => m.income?.total || 0), backgroundColor: 'rgba(34,197,94,0.6)', borderRadius: 3 },
        { label: 'Gastos', data: months.map(m => m.expenses?.total || 0), backgroundColor: 'rgba(239,68,68,0.6)', borderRadius: 3 },
      ]
    },
    options: chartOptions('')
  });
}

function renderMonthlyTable(months) {
  const tbody = document.getElementById('monthly-tbody');
  tbody.innerHTML = months.map(m => {
    const nf = m.net_flow || 0;
    const bal = m.cumulative_balance || 0;
    return `<tr>
      <td>${m.label || m.month}</td>
      <td style="text-align:right;">${fmtMoney(m.income?.total || 0)}</td>
      <td style="text-align:right;">${fmtMoney(m.expenses?.variable_costs || 0)}</td>
      <td style="text-align:right;">${fmtMoney(m.expenses?.fixed_costs || 0)}</td>
      <td style="text-align:right;">${fmtMoney((m.expenses?.variable_expenses || 0) + (m.expenses?.debt_payments || 0) + (m.expenses?.taxes || 0))}</td>
      <td style="text-align:right;" class="${nf >= 0 ? 'positive' : 'negative'}">${fmtMoney(nf)}</td>
      <td style="text-align:right;" class="${bal >= 0 ? 'positive' : 'negative'}">${fmtMoney(bal)}</td>
    </tr>`;
  }).join('');
}

function renderAlerts(alerts) {
  const div = document.getElementById('alerts-list');
  if (!alerts || alerts.length === 0) {
    div.innerHTML = '<p style="color:var(--text-muted); font-size:12px;">Sin alertas activas</p>';
    return;
  }
  div.innerHTML = alerts.map(a =>
    `<div class="alert-item ${a.type}">
      <i class="fas ${a.type === 'danger' ? 'fa-exclamation-circle' : 'fa-exclamation-triangle'}" style="color:${a.type === 'danger' ? 'var(--danger)' : 'var(--warning)'};"></i>
      <div><strong style="font-size:11px;">${a.month}</strong><br><span style="font-size:11px;">${a.message}</span></div>
    </div>`
  ).join('');
}

// ============================================================================
// Simulación
// ============================================================================
function updateSlider(name) {
  const val = document.getElementById(`sl-${name}`).value;
  const suffix = name === 'hires' ? '' : '%';
  document.getElementById(`val-${name}`).textContent = `${val}${suffix}`;
}

function resetSliders() {
  ['sales', 'costs', 'fixed', 'inflation', 'hires', 'taxes'].forEach(n => {
    document.getElementById(`sl-${n}`).value = 0;
    updateSlider(n);
  });
}

async function runSimulation() {
  if (!state.companyId) return alert('Selecciona una empresa');

  const params = {
    sales_change_pct: parseInt(document.getElementById('sl-sales').value),
    costs_change_pct: parseInt(document.getElementById('sl-costs').value),
    fixed_costs_change_pct: parseInt(document.getElementById('sl-fixed').value),
    inflation_annual_pct: parseInt(document.getElementById('sl-inflation').value),
    new_hires: parseInt(document.getElementById('sl-hires').value),
    tax_change_pct: parseInt(document.getElementById('sl-taxes').value),
  };

  try {
    const r = await fetch(`${API}/api/companies/${state.companyId}/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instruction: 'Simulación interactiva', params })
    });
    const data = await r.json();

    if (data.task_id) {
      pollSimulation(data.task_id);
    }
  } catch(e) { alert('Error ejecutando simulación'); }
}

function pollSimulation(taskId) {
  const poll = setInterval(async () => {
    try {
      const r = await fetch(`${API}/api/generation/${taskId}/progress`);
      const data = await r.json();

      if (data.status === 'done' && data.scenario_id) {
        clearInterval(poll);
        loadScenarioResult(data.scenario_id);
      } else if (data.status === 'error') {
        clearInterval(poll);
        alert('Error: ' + data.error);
      }
    } catch(e) {}
  }, 1000);
}

async function loadScenarioResult(scenarioId) {
  try {
    const r = await fetch(`${API}/api/scenarios/${scenarioId}`);
    const scenario = await r.json();
    renderSimulationChart(scenario);
    renderSimulationImpact(scenario);
    renderSimulationRecs(scenario);
  } catch(e) {}
}

function renderSimulationChart(scenario) {
  const ctx = document.getElementById('chart-sim');
  if (state.charts.sim) state.charts.sim.destroy();

  const baseMonths = state.cashflow?.months || [];
  const simMonths = scenario.months || [];

  state.charts.sim = new Chart(ctx, {
    type: 'line',
    data: {
      labels: simMonths.map(m => m.label || m.month),
      datasets: [
        { label: 'Base', data: baseMonths.map(m => m.cumulative_balance || 0), borderColor: '#64748b', borderWidth: 2, borderDash: [5,5], pointRadius: 2, fill: false },
        { label: 'Simulado', data: simMonths.map(m => m.cumulative_balance || 0), borderColor: '#8b5cf6', borderWidth: 2, pointRadius: 3, fill: false },
      ]
    },
    options: chartOptions('Saldo ($)')
  });
}

function renderSimulationImpact(scenario) {
  const div = document.getElementById('sim-impact');
  const content = document.getElementById('sim-impact-content');
  const impact = scenario.impact_summary;
  if (!impact) { div.style.display = 'none'; return; }

  div.style.display = 'block';
  content.innerHTML = `
    <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px;">
      <div class="stat-card ${impact.income_change >= 0 ? 'green' : 'red'}"><div class="stat-label">Ingresos</div><div class="stat-value" style="font-size:14px;">${fmtMoney(impact.income_change)}</div></div>
      <div class="stat-card ${impact.expenses_change <= 0 ? 'green' : 'red'}"><div class="stat-label">Gastos</div><div class="stat-value" style="font-size:14px;">${fmtMoney(impact.expenses_change)}</div></div>
      <div class="stat-card ${impact.net_change >= 0 ? 'green' : 'red'}"><div class="stat-label">Neto</div><div class="stat-value" style="font-size:14px;">${fmtMoney(impact.net_change)}</div></div>
    </div>
    <p style="font-size:12px; color:var(--text-muted); margin-top:8px;">${impact.description || ''}</p>
  `;
}

function renderSimulationRecs(scenario) {
  const div = document.getElementById('sim-recs');
  const content = document.getElementById('sim-recs-content');
  const recs = scenario.recommendations;
  if (!recs || recs.length === 0) { div.style.display = 'none'; return; }

  div.style.display = 'block';
  content.innerHTML = recs.map(r => `<div style="font-size:12px; padding:6px 0; border-bottom:1px solid var(--border);">• ${r}</div>`).join('');
}

// ============================================================================
// Monte Carlo
// ============================================================================
async function runMonteCarlo() {
  if (!state.companyId) return alert('Selecciona una empresa');
  const iterations = parseInt(document.getElementById('mc-iterations').value) || 500;

  document.getElementById('mc-progress').style.display = 'block';
  document.getElementById('mc-results').style.display = 'none';

  try {
    const r = await fetch(`${API}/api/v2/companies/${state.companyId}/monte-carlo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ iterations })
    });
    const data = await r.json();

    if (data.task_id) {
      pollMonteCarlo(data.task_id);
    }
  } catch(e) {
    alert('Error ejecutando Monte Carlo. Verifica que tengas un cashflow generado.');
    document.getElementById('mc-progress').style.display = 'none';
  }
}

function pollMonteCarlo(taskId) {
  const poll = setInterval(async () => {
    try {
      const r = await fetch(`${API}/api/v2/generation/${taskId}/progress`);
      const data = await r.json();

      document.getElementById('mc-bar').style.width = `${data.progress}%`;
      document.getElementById('mc-pct').textContent = `${data.progress}%`;

      if (data.status === 'done') {
        clearInterval(poll);
        document.getElementById('mc-progress').style.display = 'none';
        renderMonteCarloResults(data.result);
      } else if (data.status === 'error') {
        clearInterval(poll);
        document.getElementById('mc-progress').style.display = 'none';
        alert('Error: ' + data.error);
      }
    } catch(e) {}
  }, 1500);
}

function renderMonteCarloResults(results) {
  if (!results) return;
  document.getElementById('mc-results').style.display = 'block';

  // Stats
  document.getElementById('mc-insolvency').textContent = `${(results.probabilidad_insolvencia_pct || 0).toFixed(1)}%`;
  document.getElementById('mc-min').textContent = fmtCompact(results.percentiles?.p5 || 0);
  document.getElementById('mc-median').textContent = fmtCompact(results.percentiles?.p50 || 0);
  document.getElementById('mc-max').textContent = fmtCompact(results.percentiles?.p95 || 0);

  // Risk badge
  const risk = results.nivel_riesgo || {};
  const riskDiv = document.getElementById('mc-risk');
  const badge = document.getElementById('mc-risk-badge');
  riskDiv.style.display = 'block';
  badge.textContent = risk.nivel || 'N/A';
  badge.style.background = risk.color || '#334155';
  badge.style.color = '#fff';

  // Distribution chart
  renderMCDistribution(results);
  // Bands chart
  renderMCBands(results);
}

function renderMCDistribution(results) {
  const ctx = document.getElementById('chart-mc-dist');
  if (state.charts.mcDist) state.charts.mcDist.destroy();

  const hist = results.histograma || [];
  if (hist.length === 0) return;

  state.charts.mcDist = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: hist.map(h => fmtCompact(h.rango_min)),
      datasets: [{
        label: 'Frecuencia',
        data: hist.map(h => h.frecuencia),
        backgroundColor: hist.map(h => h.rango_min < 0 ? 'rgba(239,68,68,0.6)' : 'rgba(34,197,94,0.6)'),
        borderRadius: 3,
      }]
    },
    options: { ...chartOptions('Iteraciones'), plugins: { legend: { display: false } } }
  });
}

function renderMCBands(results) {
  const ctx = document.getElementById('chart-mc-bands');
  if (state.charts.mcBands) state.charts.mcBands.destroy();

  const bands = results.bandas_mensuales || [];
  if (bands.length === 0) return;

  state.charts.mcBands = new Chart(ctx, {
    type: 'line',
    data: {
      labels: bands.map((_, i) => `Mes ${i + 1}`),
      datasets: [
        { label: 'P95', data: bands.map(b => b.p95), borderColor: 'rgba(34,197,94,0.5)', backgroundColor: 'rgba(34,197,94,0.1)', fill: '+1', pointRadius: 0 },
        { label: 'Mediana', data: bands.map(b => b.p50), borderColor: '#3b82f6', borderWidth: 2, pointRadius: 2, fill: false },
        { label: 'P5', data: bands.map(b => b.p5), borderColor: 'rgba(239,68,68,0.5)', backgroundColor: 'rgba(239,68,68,0.1)', fill: '-1', pointRadius: 0 },
      ]
    },
    options: chartOptions('Saldo ($)')
  });
}

// ============================================================================
// Escenarios y Versiones
// ============================================================================
async function loadScenarios() {
  if (!state.companyId) return;
  try {
    const r = await fetch(`${API}/api/companies/${state.companyId}/scenarios`);
    const data = await r.json();
    const list = document.getElementById('scenarios-list');

    if (!data.scenarios || data.scenarios.length === 0) {
      list.innerHTML = '<p style="color:var(--text-muted); font-size:12px;">Sin escenarios. Crea uno desde Simulación.</p>';
      return;
    }

    list.innerHTML = data.scenarios.map(s =>
      `<div style="display:flex; align-items:center; justify-content:space-between; padding:8px; border:1px solid var(--border); border-radius:8px; margin-bottom:6px;">
        <div>
          <div style="font-size:12px; font-weight:600;">${s.scenario_name || 'Escenario'}</div>
          <div style="font-size:10px; color:var(--text-muted);">${s.created_at?.substring(0, 10) || ''} — ${s.simulation_mode || 'local'}</div>
        </div>
        <button class="btn btn-sm btn-secondary" onclick="deleteScenario('${s.id}')"><i class="fas fa-trash"></i></button>
      </div>`
    ).join('');

    // Render comparison chart
    renderComparisonChart(data.scenarios);
  } catch(e) {}
}

async function loadVersions() {
  if (!state.companyId) return;
  try {
    const r = await fetch(`${API}/api/v2/companies/${state.companyId}/cashflow-versions`);
    const data = await r.json();
    const list = document.getElementById('versions-list');

    if (!data.versions || data.versions.length === 0) {
      list.innerHTML = '<p style="color:var(--text-muted); font-size:12px;">Sin versiones guardadas.</p>';
      return;
    }

    list.innerHTML = data.versions.map(v =>
      `<div style="display:flex; align-items:center; justify-content:space-between; padding:8px; border:1px solid var(--border); border-radius:8px; margin-bottom:6px;">
        <div>
          <div style="font-size:12px; font-weight:600;">${v.name}</div>
          <div style="font-size:10px; color:var(--text-muted);">${v.months} meses — ${v.version}</div>
        </div>
        ${!v.is_current ? `<button class="btn btn-sm btn-secondary" onclick="restoreVersion('${v.id}')"><i class="fas fa-undo"></i> Restaurar</button>` : '<span style="font-size:10px; color:var(--success);">Actual</span>'}
      </div>`
    ).join('');
  } catch(e) {}
}

async function saveVersion() {
  if (!state.companyId) return;
  const name = prompt('Nombre de la versión:', `Versión ${new Date().toLocaleDateString()}`);
  if (!name) return;

  try {
    await fetch(`${API}/api/v2/companies/${state.companyId}/cashflow-versions?name=${encodeURIComponent(name)}`, { method: 'POST' });
    loadVersions();
  } catch(e) { alert('Error guardando versión'); }
}

async function restoreVersion(versionId) {
  if (!confirm('¿Restaurar esta versión? Se guardará un backup de la actual.')) return;
  try {
    await fetch(`${API}/api/v2/companies/${state.companyId}/cashflow-versions/${versionId}/restore`, { method: 'PUT' });
    loadCashflow();
    loadVersions();
  } catch(e) { alert('Error restaurando versión'); }
}

async function deleteScenario(id) {
  if (!confirm('¿Eliminar este escenario?')) return;
  try {
    await fetch(`${API}/api/scenarios/${id}`, { method: 'DELETE' });
    loadScenarios();
  } catch(e) {}
}

function renderComparisonChart(scenarios) {
  const ctx = document.getElementById('chart-compare');
  if (state.charts.compare) state.charts.compare.destroy();

  const datasets = [];
  const colors = ['#3b82f6', '#8b5cf6', '#22c55e', '#f59e0b', '#ef4444', '#06b6d4'];

  // Base
  if (state.cashflow && state.cashflow.months) {
    datasets.push({
      label: 'Plan Base',
      data: state.cashflow.months.map(m => m.cumulative_balance || 0),
      borderColor: '#64748b',
      borderWidth: 2,
      borderDash: [5, 5],
      pointRadius: 2,
      fill: false,
    });
  }

  scenarios.slice(0, 5).forEach((s, i) => {
    if (s.months) {
      datasets.push({
        label: s.scenario_name || `Escenario ${i + 1}`,
        data: s.months.map(m => m.cumulative_balance || 0),
        borderColor: colors[i % colors.length],
        borderWidth: 2,
        pointRadius: 2,
        fill: false,
      });
    }
  });

  const maxLabels = Math.max(...datasets.map(d => d.data.length), 0);
  const labels = Array.from({ length: maxLabels }, (_, i) => `Mes ${i + 1}`);

  state.charts.compare = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: chartOptions('Saldo ($)')
  });
}

// ============================================================================
// Métricas
// ============================================================================
async function loadMetrics() {
  if (!state.companyId) return;
  try {
    const r = await fetch(`${API}/api/v2/companies/${state.companyId}/metrics`);
    if (!r.ok) return;
    const metrics = await r.json();
    renderMetricsCards(metrics);
  } catch(e) {}
}

function renderMetricsCards(metrics) {
  const container = document.getElementById('metrics-cards');
  const items = [
    { label: 'Caja Mínima', value: fmtCompact(metrics.caja_minima || 0), color: metrics.caja_minima < 0 ? 'red' : 'green', desc: metrics.mes_caja_minima || '' },
    { label: 'Mes Caja Negativa', value: metrics.primer_mes_caja_negativa || 'Ninguno', color: metrics.primer_mes_caja_negativa ? 'red' : 'green', desc: '' },
    { label: 'Break-even Operativo', value: metrics.breakeven_mes || 'N/A', color: '', desc: '' },
    { label: 'Runway', value: metrics.runway_meses ? `${metrics.runway_meses} meses` : 'Indefinido', color: 'yellow', desc: '' },
    { label: 'Margen Bruto', value: metrics.margen_bruto_pct ? `${metrics.margen_bruto_pct.toFixed(1)}%` : '-', color: 'green', desc: '' },
    { label: 'Margen EBITDA', value: metrics.margen_ebitda_pct ? `${metrics.margen_ebitda_pct.toFixed(1)}%` : '-', color: 'purple', desc: '' },
    { label: 'Necesidad Financiamiento', value: fmtCompact(metrics.necesidad_max_financiamiento || 0), color: 'red', desc: '' },
    { label: 'Prob. Insolvencia (MC)', value: metrics.probabilidad_insolvencia_mc ? `${metrics.probabilidad_insolvencia_mc.toFixed(1)}%` : '-', color: 'red', desc: '' },
    { label: 'Meses Proyectados', value: metrics.num_meses || '-', color: '', desc: '' },
  ];

  container.innerHTML = items.map(i =>
    `<div class="stat-card ${i.color}">
      <div class="stat-label">${i.label}</div>
      <div class="stat-value" style="font-size:16px;">${i.value}</div>
      ${i.desc ? `<div class="stat-sub">${i.desc}</div>` : ''}
    </div>`
  ).join('');
}

async function runSensitivity() {
  if (!state.companyId) return;
  const variable = document.getElementById('sens-var').value;

  try {
    const r = await fetch(`${API}/api/v2/companies/${state.companyId}/sensitivity`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ variable, range_pct: 30, steps: 7 })
    });
    const data = await r.json();
    renderSensitivityChart(data);
  } catch(e) { alert('Error ejecutando análisis de sensibilidad'); }
}

function renderSensitivityChart(data) {
  const ctx = document.getElementById('chart-sensitivity');
  if (state.charts.sensitivity) state.charts.sensitivity.destroy();

  const results = data.results || [];
  state.charts.sensitivity = new Chart(ctx, {
    type: 'line',
    data: {
      labels: results.map(r => `${r.cambio_pct > 0 ? '+' : ''}${r.cambio_pct}%`),
      datasets: [{
        label: 'Caja Final',
        data: results.map(r => r.caja_final_promedio || r.caja_final),
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245,158,11,0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 4,
      }]
    },
    options: chartOptions('Caja Final ($)')
  });
}

// ============================================================================
// Exportación
// ============================================================================
function exportExcel() {
  if (!state.companyId) return;
  window.open(`${API}/api/companies/${state.companyId}/export/excel`, '_blank');
}

function exportCSV() {
  if (!state.companyId) return;
  window.open(`${API}/api/companies/${state.companyId}/export/csv`, '_blank');
}

// ============================================================================
// Settings
// ============================================================================
async function loadSettings() {
  try {
    const r = await fetch(`${API}/api/agents`);
    const data = await r.json();
    const list = document.getElementById('agents-list');
    list.innerHTML = (data.agents || []).map(a =>
      `<div style="display:flex; align-items:center; justify-content:space-between; padding:10px; border:1px solid var(--border); border-radius:8px; margin-bottom:8px;">
        <div>
          <div style="font-size:13px; font-weight:600;">${a.role || a.id}</div>
          <div style="font-size:11px; color:var(--text-muted);">Modelo: ${a.model} | Temp: ${a.temperature}</div>
        </div>
      </div>`
    ).join('');

    const hr = await fetch(`${API}/api/hardware/performance`);
    const hw = await hr.json();
    const hwDiv = document.getElementById('hardware-info');
    hwDiv.innerHTML = `
      <div style="font-size:12px; color:var(--text-muted);">
        <p>CPU: ${hw.hardware?.cpu_count || '?'} cores | RAM: ${hw.hardware?.ram_gb || '?'} GB | GPU: ${hw.hardware?.gpu_name || 'N/A'}</p>
      </div>
    `;
  } catch(e) {}
}

// ============================================================================
// Utilidades
// ============================================================================
function fmtMoney(n) {
  return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(n);
}

function fmtCompact(n) {
  if (Math.abs(n) >= 1000000) return `$${(n / 1000000).toFixed(1)}M`;
  if (Math.abs(n) >= 1000) return `$${(n / 1000).toFixed(0)}K`;
  return `$${Math.round(n)}`;
}

function chartOptions(yLabel) {
  return {
    responsive: true,
    interaction: { intersect: false, mode: 'index' },
    scales: {
      x: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: 'rgba(100,116,139,0.1)' } },
      y: { ticks: { color: '#64748b', font: { size: 10 }, callback: v => fmtCompact(v) }, grid: { color: 'rgba(100,116,139,0.1)' }, title: { display: !!yLabel, text: yLabel, color: '#64748b', font: { size: 10 } } }
    },
    plugins: {
      legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
      tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${fmtMoney(ctx.parsed.y)}` } }
    }
  };
}

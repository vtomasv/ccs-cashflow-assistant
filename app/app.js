/**
 * CCS Cashflow Assistant v2.1 — Frontend Application
 * Motor Financiero Modular con estilos CCS Brand
 */

// ============================================================================
// Estado Global
// ============================================================================
const API = '';
let state = {
  companyId: null,
  companyName: '',
  companySector: '',
  sessionId: '',
  cashflow: null,
  companies: [],
  charts: {},
  generationTaskId: null,
  mcTaskId: null,
  currentPage: 'home',
  wizardStep: 1,
};

// ============================================================================
// Inicialización
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  checkOllama();
  loadCompanies();
});

async function checkOllama() {
  try {
    const r = await fetch(`${API}/api/readiness`);
    const data = await r.json();
    const dot = document.getElementById('ollamaDot');
    const text = document.getElementById('ollamaStatusText');

    if (data.ready) {
      dot.className = 'status-dot online';
      text.textContent = `Ollama OK (${data.models_count} modelos)`;
      showReadinessBanner(true);
    } else {
      dot.className = 'status-dot loading';
      text.textContent = 'Preparando...';
      showReadinessBanner(false, data.issues ? data.issues[0]?.message : 'Preparando modelos...');
      pollOllama();
    }
  } catch(e) {
    document.getElementById('ollamaDot').className = 'status-dot';
    document.getElementById('ollamaStatusText').textContent = 'Desconectado';
    showReadinessBanner(false, 'No se pudo conectar con el servidor');
  }
}

function pollOllama() {
  const poll = setInterval(async () => {
    try {
      const r = await fetch(`${API}/api/readiness`);
      const d = await r.json();
      if (d.ready) {
        clearInterval(poll);
        document.getElementById('ollamaDot').className = 'status-dot online';
        document.getElementById('ollamaStatusText').textContent = `Ollama OK (${d.models_count} modelos)`;
        document.getElementById('readinessBanner').innerHTML = '';
      }
    } catch(e) {}
  }, 4000);
}

function showReadinessBanner(ready, message) {
  const el = document.getElementById('readinessBanner');
  if (ready) {
    el.innerHTML = '';
  } else {
    el.innerHTML = `<div class="readiness-banner not-ready">
      <div style="font-size:20px;">&#9888;&#65039;</div>
      <div><div style="font-weight:700;">Sistema preparándose</div><div style="font-size:12px;opacity:0.8;">${message || 'Verificando modelos de IA...'}</div></div>
    </div>`;
  }
}

// ============================================================================
// Navegación
// ============================================================================
function navigateTo(page) {
  state.currentPage = page;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  const pageEl = document.getElementById(`page-${page}`);
  if (pageEl) pageEl.classList.add('active');

  const navEl = document.getElementById(`nav-${page}`);
  if (navEl) navEl.classList.add('active');

  const titles = {
    home: 'Inicio',
    companies: 'Mis Empresas',
    interview: 'Entrevista Financiera',
    dashboard: 'Dashboard — Flujo de Caja',
    simulation: 'Simulación Interactiva',
    montecarlo: 'Simulación Monte Carlo',
    scenarios: 'Escenarios y Versiones',
    metrics: 'Métricas Financieras',
    settings: 'Configuración',
  };
  document.getElementById('pageTitle').textContent = titles[page] || page;

  // Load data for specific pages
  if (page === 'dashboard' && state.companyId) loadCashflow();
  if (page === 'scenarios' && state.companyId) loadVersions();
  if (page === 'metrics' && state.companyId) loadMetrics();
  if (page === 'simulation' && state.companyId) renderSimulationControls();
  if (page === 'settings') loadSettings();
}

// ============================================================================
// Empresas
// ============================================================================
async function loadCompanies() {
  try {
    const r = await fetch(`${API}/api/companies`);
    const data = await r.json();
    state.companies = data.companies || [];
    document.getElementById('companiesBadge').textContent = state.companies.length;
    renderCompaniesGrid();
    renderHomeCompanies();

    // Auto-select if only one
    if (state.companies.length === 1 && !state.companyId) {
      selectCompany(state.companies[0].id);
    }
  } catch(e) { console.error('Error loading companies:', e); }
}

function renderCompaniesGrid() {
  const grid = document.getElementById('companiesGrid');
  if (!state.companies.length) {
    grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1;">
      <div class="empty-icon"><i class="fas fa-building"></i></div>
      <div class="empty-title">No hay empresas registradas</div>
      <div class="empty-desc">Crea tu primera empresa para comenzar a proyectar flujos de caja</div>
      <button class="btn btn-primary" onclick="openModal('newCompanyModal')"><i class="fas fa-plus"></i> Crear Empresa</button>
    </div>`;
    return;
  }

  grid.innerHTML = state.companies.map(c => {
    const initial = (c.name || '?')[0].toUpperCase();
    const statusClass = c.status === 'complete' ? 'status-complete' : c.status === 'interviewing' ? 'status-interviewing' : 'status-pending';
    const statusText = c.status === 'complete' ? 'Cashflow listo' : c.status === 'interviewing' ? 'En entrevista' : 'Pendiente';
    const selected = c.id === state.companyId ? 'selected' : '';
    return `<div class="company-card ${selected}" onclick="selectCompany('${c.id}')">
      <div class="company-avatar">${initial}</div>
      <div class="company-name">${c.name}</div>
      <div class="company-sector">${c.sector || 'Sin sector'}</div>
      <div class="company-status ${statusClass}">${statusText}</div>
    </div>`;
  }).join('');
}

function renderHomeCompanies() {
  const el = document.getElementById('homeCompaniesList');
  if (!state.companies.length) { el.innerHTML = ''; return; }

  el.innerHTML = `<div class="card">
    <div class="card-header">
      <div><div class="card-title">Tus Empresas</div><div class="card-subtitle">Selecciona una empresa para continuar</div></div>
      <button class="btn btn-sm btn-secondary" onclick="navigateTo('companies')">Ver todas</button>
    </div>
    <div class="grid-3">${state.companies.slice(0, 3).map(c => {
      const initial = (c.name || '?')[0].toUpperCase();
      const statusClass = c.status === 'complete' ? 'status-complete' : c.status === 'interviewing' ? 'status-interviewing' : 'status-pending';
      const statusText = c.status === 'complete' ? 'Cashflow listo' : c.status === 'interviewing' ? 'En entrevista' : 'Pendiente';
      return `<div class="company-card" onclick="selectCompany('${c.id}')">
        <div class="company-avatar">${initial}</div>
        <div class="company-name">${c.name}</div>
        <div class="company-sector">${c.sector || 'Sin sector'}</div>
        <div class="company-status ${statusClass}">${statusText}</div>
      </div>`;
    }).join('')}</div>
  </div>`;
}

async function selectCompany(id) {
  if (!id) return;
  state.companyId = id;
  state.sessionId = '';

  showGlobalLoading('Cargando empresa...');

  try {
    const r = await fetch(`${API}/api/companies/${id}`);
    const company = await r.json();
    state.companyName = company.name;
    state.companySector = company.sector;

    // Show company tools in sidebar
    document.getElementById('companyToolsSection').style.display = 'block';
    document.getElementById('activeCompanyLabel').textContent = company.name;
    document.getElementById('interviewCompanyName').textContent = `— ${company.name}`;

    // Load sessions
    const sr = await fetch(`${API}/api/companies/${id}/sessions`);
    const sessions = await sr.json();
    const interviewSessions = (sessions.sessions || []).filter(s => s.type === 'interview' || s.type === 'interview_v2');

    if (interviewSessions.length > 0) {
      const lastSession = interviewSessions[interviewSessions.length - 1];
      state.sessionId = lastSession.id;
      await loadSession(id, lastSession.id);
    } else {
      const chatDiv = document.getElementById('chatMessages');
      chatDiv.innerHTML = `<div class="chat-message system-msg">Bienvenido. Soy tu analista financiero. Vamos a construir el modelo de flujo de caja para <strong>${company.name}</strong>. Cuéntame sobre tu negocio.</div>`;
    }

    // Enable chat
    document.getElementById('chatInput').disabled = false;
    document.getElementById('btnSendChat').disabled = false;

    // Show generate button if has enough data
    if (company.status === 'interviewing' || company.status === 'complete') {
      document.getElementById('btnGenerateCashflow').style.display = 'inline-flex';
    }

    // Load cashflow if exists
    if (company.status === 'complete') {
      await loadCashflow();
    }

    updateInterviewTopics();
    renderCompaniesGrid();
    hideGlobalLoading();

    // Navigate to interview
    navigateTo('interview');
    notify('success', `Empresa "${company.name}" seleccionada`);
  } catch(e) {
    hideGlobalLoading();
    notify('error', 'Error cargando la empresa');
  }
}

async function loadSession(companyId, sessionId) {
  try {
    const r = await fetch(`${API}/api/companies/${companyId}/sessions/${sessionId}`);
    const session = await r.json();
    const chatDiv = document.getElementById('chatMessages');
    chatDiv.innerHTML = '';
    (session.messages || []).forEach(msg => {
      addChatBubble(msg.role, msg.content);
    });
    chatDiv.scrollTop = chatDiv.scrollHeight;
  } catch(e) {}
}

// ============================================================================
// Wizard de Creación de Empresa
// ============================================================================
function wizardNext(step) {
  if (step === 1) {
    const name = document.getElementById('companyName').value.trim();
    const sector = document.getElementById('companySector').value;
    if (!name) { notify('error', 'Ingresa el nombre de la empresa'); return; }
    if (!sector) { notify('error', 'Selecciona un sector'); return; }
  }

  if (step === 2) {
    renderCompanySummary();
  }

  // Update wizard UI
  document.getElementById(`wizardStep${step}`).style.display = 'none';
  document.getElementById(`wizardStep${step + 1}`).style.display = 'block';
  document.getElementById(`ws-${step}`).className = 'wizard-step done';
  document.getElementById(`wc-${step}`).className = 'wizard-connector done';
  document.getElementById(`ws-${step + 1}`).className = 'wizard-step active';
  state.wizardStep = step + 1;
}

function wizardBack(step) {
  document.getElementById(`wizardStep${step}`).style.display = 'none';
  document.getElementById(`wizardStep${step - 1}`).style.display = 'block';
  document.getElementById(`ws-${step}`).className = 'wizard-step';
  document.getElementById(`wc-${step - 1}`).className = 'wizard-connector';
  document.getElementById(`ws-${step - 1}`).className = 'wizard-step active';
  state.wizardStep = step - 1;
}

function renderCompanySummary() {
  const name = document.getElementById('companyName').value.trim();
  const sector = document.getElementById('companySector').value;
  const size = document.getElementById('companySize').value;
  const country = document.getElementById('companyCountry').value;
  const currency = document.getElementById('companyCurrency').value;
  const cash = document.getElementById('companyInitialCash').value;
  const employees = document.getElementById('companyEmployees').value;
  const age = document.getElementById('companyAge').value;

  const sizeLabels = { micro: 'Micro (1-9)', pequena: 'Pequeña (10-49)', mediana: 'Mediana (50-199)' };
  const ageLabels = { nuevo: 'Menos de 1 año', joven: '1-3 años', establecido: '3-5 años', maduro: 'Más de 5 años' };

  document.getElementById('companySummary').innerHTML = `
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:12px;">
      <div><span style="color:var(--text-muted);">Nombre:</span> <strong>${name}</strong></div>
      <div><span style="color:var(--text-muted);">Sector:</span> <strong>${sector}</strong></div>
      ${size ? `<div><span style="color:var(--text-muted);">Tamaño:</span> <strong>${sizeLabels[size] || size}</strong></div>` : ''}
      ${country ? `<div><span style="color:var(--text-muted);">País:</span> <strong>${country}</strong></div>` : ''}
      ${currency ? `<div><span style="color:var(--text-muted);">Moneda:</span> <strong>${currency}</strong></div>` : ''}
      ${cash ? `<div><span style="color:var(--text-muted);">Caja inicial:</span> <strong>${formatCurrency(cash)}</strong></div>` : ''}
      ${employees ? `<div><span style="color:var(--text-muted);">Empleados:</span> <strong>${employees}</strong></div>` : ''}
      ${age ? `<div><span style="color:var(--text-muted);">Antigüedad:</span> <strong>${ageLabels[age] || age}</strong></div>` : ''}
    </div>`;
}

async function createCompany() {
  const name = document.getElementById('companyName').value.trim();
  const sector = document.getElementById('companySector').value;
  const size = document.getElementById('companySize').value;
  const desc = document.getElementById('companyDescription').value.trim();
  const country = document.getElementById('companyCountry').value;
  const currency = document.getElementById('companyCurrency').value;
  const cash = document.getElementById('companyInitialCash').value;
  const employees = document.getElementById('companyEmployees').value;
  const age = document.getElementById('companyAge').value;

  if (!name) { notify('error', 'Ingresa el nombre de la empresa'); return; }

  showGlobalLoading('Creando empresa...', 'Preparando el entorno de análisis financiero');

  try {
    const r = await fetch(`${API}/api/companies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name, sector, size, description: desc,
        country, currency, initial_cash: cash ? parseFloat(cash) : 0,
        employees: employees ? parseInt(employees) : 0, age
      })
    });
    const company = await r.json();

    // Reset wizard
    closeModal('newCompanyModal');
    resetWizard();

    // Reload and select
    await loadCompanies();
    hideGlobalLoading();
    await selectCompany(company.id);

    notify('success', `Empresa "${name}" creada exitosamente`);
  } catch(e) {
    hideGlobalLoading();
    notify('error', 'Error creando la empresa');
  }
}

function resetWizard() {
  state.wizardStep = 1;
  document.getElementById('wizardStep1').style.display = 'block';
  document.getElementById('wizardStep2').style.display = 'none';
  document.getElementById('wizardStep3').style.display = 'none';
  document.getElementById('ws-1').className = 'wizard-step active';
  document.getElementById('ws-2').className = 'wizard-step';
  document.getElementById('ws-3').className = 'wizard-step';
  document.getElementById('wc-1').className = 'wizard-connector';
  document.getElementById('wc-2').className = 'wizard-connector';
  // Clear fields
  document.getElementById('companyName').value = '';
  document.getElementById('companySector').value = '';
  document.getElementById('companySize').value = '';
  document.getElementById('companyDescription').value = '';
  document.getElementById('companyInitialCash').value = '';
  document.getElementById('companyEmployees').value = '';
  document.getElementById('companyAge').value = '';
}

// ============================================================================
// Chat / Entrevista
// ============================================================================
function handleChatKey(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
}

async function sendMessage() {
  const input = document.getElementById('chatInput');
  const msg = input.value.trim();
  if (!msg || !state.companyId) return;

  input.value = '';
  input.style.height = 'auto';
  addChatBubble('user', msg);

  // Show typing indicator
  const typingId = showTyping();

  try {
    const r = await fetch(`${API}/api/chat/interview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company_id: state.companyId, message: msg, session_id: state.sessionId })
    });
    const data = await r.json();
    state.sessionId = data.session_id;

    removeTyping(typingId);
    addChatBubble('assistant', data.response);

    // Show generate button
    document.getElementById('btnGenerateCashflow').style.display = 'inline-flex';
    updateInterviewTopics();
  } catch(e) {
    removeTyping(typingId);
    addChatBubble('system-msg', 'Error comunicando con el servidor. Verifica que Ollama esté activo.');
  }
}

function addChatBubble(role, content) {
  const chatDiv = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = `chat-message ${role}`;
  // Simple markdown rendering
  const sanitized = typeof DOMPurify !== 'undefined' ? DOMPurify.sanitize(content) : content;
  div.innerHTML = sanitized
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>');
  chatDiv.appendChild(div);
  chatDiv.scrollTop = chatDiv.scrollHeight;
}

function showTyping() {
  const chatDiv = document.getElementById('chatMessages');
  const id = 'typing-' + Date.now();
  const div = document.createElement('div');
  div.className = 'chat-message assistant';
  div.id = id;
  div.innerHTML = '<div class="loading-spinner" style="width:14px;height:14px;border-width:2px;"></div> <span style="font-size:12px;color:var(--text-muted);margin-left:6px;">Analizando...</span>';
  chatDiv.appendChild(div);
  chatDiv.scrollTop = chatDiv.scrollHeight;
  return id;
}

function removeTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function updateInterviewTopics() {
  const topics = [
    { id: 'business', label: 'Tipo de negocio', icon: 'fa-store' },
    { id: 'products', label: 'Productos/Servicios', icon: 'fa-box' },
    { id: 'segments', label: 'Segmentos de clientes', icon: 'fa-users' },
    { id: 'revenue', label: 'Modelo de ingresos', icon: 'fa-dollar-sign' },
    { id: 'prices', label: 'Precios y volúmenes', icon: 'fa-tag' },
    { id: 'growth', label: 'Crecimiento esperado', icon: 'fa-chart-line' },
    { id: 'seasonality', label: 'Estacionalidad', icon: 'fa-calendar' },
    { id: 'costs', label: 'Costos y gastos', icon: 'fa-receipt' },
    { id: 'salaries', label: 'Salarios', icon: 'fa-user-tie' },
    { id: 'cash', label: 'Caja y financiamiento', icon: 'fa-piggy-bank' },
    { id: 'risks', label: 'Riesgos principales', icon: 'fa-shield-alt' },
  ];

  const container = document.getElementById('interviewTopics');
  container.innerHTML = topics.map(t =>
    `<div class="topic-item"><span class="topic-icon"><i class="fas ${t.icon}"></i></span> ${t.label}</div>`
  ).join('');
}

// ============================================================================
// Generación de Cashflow
// ============================================================================
async function generateCashflow() {
  if (!state.companyId) return;

  navigateTo('dashboard');
  const panel = document.getElementById('genProgressPanel');
  panel.style.display = 'block';
  document.getElementById('genBar').style.width = '0%';
  document.getElementById('genPct').textContent = '0%';
  document.getElementById('genStep').textContent = 'Iniciando generación...';
  document.getElementById('genNotifications').innerHTML = '';

  try {
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
      document.getElementById('genStep').textContent = 'Error iniciando generación';
      notify('error', 'Error al generar el flujo de caja');
    }
  }
}

function pollGenerationProgress(taskId) {
  const poll = setInterval(async () => {
    try {
      const r = await fetch(`${API}/api/v2/generation/${taskId}/progress`);
      const data = await r.json();

      const pct = data.progress_pct || 0;
      document.getElementById('genBar').style.width = `${pct}%`;
      document.getElementById('genPct').textContent = `${Math.round(pct)}%`;
      document.getElementById('genStep').textContent = data.current_step || 'Procesando...';

      // Add notifications
      if (data.notifications && data.notifications.length > 0) {
        const container = document.getElementById('genNotifications');
        const existing = container.querySelectorAll('.notification-item').length;
        data.notifications.slice(existing).forEach(n => {
          container.innerHTML += `<div class="notification-item"><i class="fas fa-info-circle" style="color:var(--ccs-azul);margin-right:6px;"></i>${n}</div>`;
        });
        container.scrollTop = container.scrollHeight;
      }

      if (data.status === 'completed' || pct >= 100) {
        clearInterval(poll);
        document.getElementById('genProgressPanel').style.display = 'none';
        loadCashflow();
        notify('success', 'Flujo de caja generado exitosamente');
      } else if (data.status === 'error') {
        clearInterval(poll);
        document.getElementById('genStep').textContent = 'Error: ' + (data.error || 'Error desconocido');
        notify('error', 'Error en la generación');
      }
    } catch(e) {}
  }, 2000);
}

function pollGenerationProgressV1(taskId) {
  const poll = setInterval(async () => {
    try {
      const r = await fetch(`${API}/api/generation/${taskId}/progress`);
      const data = await r.json();
      const pct = data.progress || 0;
      document.getElementById('genBar').style.width = `${pct}%`;
      document.getElementById('genPct').textContent = `${Math.round(pct)}%`;
      document.getElementById('genStep').textContent = data.step || 'Procesando...';

      if (data.status === 'completed' || pct >= 100) {
        clearInterval(poll);
        document.getElementById('genProgressPanel').style.display = 'none';
        loadCashflow();
        notify('success', 'Flujo de caja generado');
      }
    } catch(e) {}
  }, 3000);
}

// ============================================================================
// Dashboard
// ============================================================================
async function loadCashflow() {
  try {
    const r = await fetch(`${API}/api/companies/${state.companyId}/cashflow`);
    const data = await r.json();
    state.cashflow = data;
    renderDashboard(data);
  } catch(e) {
    document.getElementById('dashboardStats').innerHTML = `<div class="empty-state" style="grid-column:1/-1;">
      <div class="empty-icon"><i class="fas fa-chart-line"></i></div>
      <div class="empty-title">Sin flujo de caja</div>
      <div class="empty-desc">Completa la entrevista y genera el flujo de caja para ver el dashboard</div>
    </div>`;
  }
}

function renderDashboard(data) {
  const months = data.months || data.cashflow?.months || [];
  if (!months.length) return;

  // Stats
  const totalIncome = months.reduce((s, m) => s + (m.income?.total || m.income_total || 0), 0);
  const totalExpenses = months.reduce((s, m) => s + (m.expenses?.total || m.expenses_total || 0), 0);
  const lastBalance = months[months.length - 1]?.cumulative_balance || 0;
  const netFlow = totalIncome - totalExpenses;

  document.getElementById('dashboardStats').innerHTML = `
    <div class="stat-card"><div class="stat-label">Ingresos Totales</div><div class="stat-value">${formatCurrencyShort(totalIncome)}</div><div class="stat-sub">12 meses</div></div>
    <div class="stat-card green"><div class="stat-label">Flujo Neto</div><div class="stat-value ${netFlow >= 0 ? 'positive' : 'negative'}">${formatCurrencyShort(netFlow)}</div><div class="stat-sub">acumulado</div></div>
    <div class="stat-card blue"><div class="stat-label">Saldo Final</div><div class="stat-value">${formatCurrencyShort(lastBalance)}</div><div class="stat-sub">proyectado</div></div>
    <div class="stat-card celeste"><div class="stat-label">Gastos Totales</div><div class="stat-value">${formatCurrencyShort(totalExpenses)}</div><div class="stat-sub">12 meses</div></div>
  `;

  // Charts
  renderCashflowChart(months);
  renderIncomeExpenseChart(months);
  renderDashboardTable(months);
}

function renderCashflowChart(months) {
  const ctx = document.getElementById('chartCashflow');
  if (state.charts.cashflow) state.charts.cashflow.destroy();

  state.charts.cashflow = new Chart(ctx, {
    type: 'line',
    data: {
      labels: months.map(m => m.label || m.month),
      datasets: [{
        label: 'Saldo Acumulado',
        data: months.map(m => m.cumulative_balance),
        borderColor: '#0D3DA6',
        backgroundColor: 'rgba(13,61,166,0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 4,
        pointBackgroundColor: '#0D3DA6',
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { ticks: { callback: v => formatCurrencyShort(v) } }
      }
    }
  });
}

function renderIncomeExpenseChart(months) {
  const ctx = document.getElementById('chartIncomeExpense');
  if (state.charts.incomeExpense) state.charts.incomeExpense.destroy();

  state.charts.incomeExpense = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: months.map(m => m.label || m.month),
      datasets: [
        { label: 'Ingresos', data: months.map(m => m.income?.total || m.income_total || 0), backgroundColor: 'rgba(61,174,43,0.7)', borderRadius: 4 },
        { label: 'Gastos', data: months.map(m => m.expenses?.total || m.expenses_total || 0), backgroundColor: 'rgba(220,38,38,0.6)', borderRadius: 4 },
      ]
    },
    options: {
      responsive: true,
      plugins: { legend: { position: 'top' } },
      scales: { y: { ticks: { callback: v => formatCurrencyShort(v) } } }
    }
  });
}

function renderDashboardTable(months) {
  const container = document.getElementById('dashboardTable');
  container.innerHTML = `<table class="data-table">
    <thead><tr><th>Mes</th><th>Ingresos</th><th>Gastos</th><th>Flujo Neto</th><th>Saldo</th></tr></thead>
    <tbody>${months.map(m => {
      const income = m.income?.total || m.income_total || 0;
      const expenses = m.expenses?.total || m.expenses_total || 0;
      const net = m.net_flow || (income - expenses);
      return `<tr>
        <td><strong>${m.label || m.month}</strong></td>
        <td>${formatCurrency(income)}</td>
        <td>${formatCurrency(expenses)}</td>
        <td class="${net >= 0 ? 'positive' : 'negative'}">${formatCurrency(net)}</td>
        <td><strong>${formatCurrency(m.cumulative_balance)}</strong></td>
      </tr>`;
    }).join('')}</tbody>
  </table>`;
}

// ============================================================================
// Simulación
// ============================================================================
function renderSimulationControls() {
  const container = document.getElementById('simulationControls');
  container.innerHTML = `
    <div class="slider-group"><label><span>Variación de ventas</span><span id="sliderSalesVal">0%</span></label>
      <input type="range" min="-50" max="100" value="0" id="sliderSales" oninput="document.getElementById('sliderSalesVal').textContent=this.value+'%'"></div>
    <div class="slider-group"><label><span>Costos variables</span><span id="sliderCostsVal">0%</span></label>
      <input type="range" min="-30" max="50" value="0" id="sliderCosts" oninput="document.getElementById('sliderCostsVal').textContent=this.value+'%'"></div>
    <div class="slider-group"><label><span>Costos fijos</span><span id="sliderFixedVal">0%</span></label>
      <input type="range" min="-20" max="40" value="0" id="sliderFixed" oninput="document.getElementById('sliderFixedVal').textContent=this.value+'%'"></div>
    <div class="slider-group"><label><span>Inflación anual</span><span id="sliderInflVal">0%</span></label>
      <input type="range" min="0" max="30" value="0" id="sliderInfl" oninput="document.getElementById('sliderInflVal').textContent=this.value+'%'"></div>
    <div class="slider-group"><label><span>Nuevos clientes</span><span id="sliderClientsVal">0%</span></label>
      <input type="range" min="-20" max="50" value="0" id="sliderClients" oninput="document.getElementById('sliderClientsVal').textContent=this.value+'%'"></div>
  `;
}

function resetSliders() {
  ['Sales','Costs','Fixed','Infl','Clients'].forEach(s => {
    const el = document.getElementById(`slider${s}`);
    if (el) { el.value = 0; document.getElementById(`slider${s}Val`).textContent = '0%'; }
  });
}

async function applySimulation() {
  if (!state.companyId) return;
  const params = {
    sales_change_pct: parseFloat(document.getElementById('sliderSales')?.value || 0),
    variable_costs_change_pct: parseFloat(document.getElementById('sliderCosts')?.value || 0),
    fixed_costs_change_pct: parseFloat(document.getElementById('sliderFixed')?.value || 0),
    inflation_pct: parseFloat(document.getElementById('sliderInfl')?.value || 0),
    new_clients_pct: parseFloat(document.getElementById('sliderClients')?.value || 0),
  };

  try {
    const r = await fetch(`${API}/api/v2/companies/${state.companyId}/custom-scenario`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Simulación manual', multipliers: params })
    });
    const data = await r.json();
    if (data.months) renderSimulationChart(data.months);
    notify('success', 'Simulación aplicada');
  } catch(e) {
    // Fallback to V1
    try {
      const r = await fetch(`${API}/api/companies/${state.companyId}/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
      });
      const data = await r.json();
      if (data.months) renderSimulationChart(data.months);
    } catch(e2) { notify('error', 'Error en simulación'); }
  }
}

function renderSimulationChart(months) {
  const ctx = document.getElementById('chartSimulation');
  if (state.charts.simulation) state.charts.simulation.destroy();

  state.charts.simulation = new Chart(ctx, {
    type: 'line',
    data: {
      labels: months.map(m => m.label || m.month),
      datasets: [{
        label: 'Saldo Simulado',
        data: months.map(m => m.cumulative_balance),
        borderColor: '#3A6DDE',
        backgroundColor: 'rgba(58,109,222,0.08)',
        fill: true,
        tension: 0.3,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { y: { ticks: { callback: v => formatCurrencyShort(v) } } }
    }
  });
}

// ============================================================================
// Monte Carlo
// ============================================================================
async function runMonteCarlo() {
  if (!state.companyId) return;
  showGlobalLoading('Ejecutando Monte Carlo...', 'Simulando miles de escenarios');

  try {
    const r = await fetch(`${API}/api/v2/companies/${state.companyId}/monte-carlo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ iterations: 1000 })
    });
    const data = await r.json();
    hideGlobalLoading();
    renderMonteCarloResults(data);
    notify('success', 'Simulación Monte Carlo completada');
  } catch(e) {
    hideGlobalLoading();
    notify('error', 'Error ejecutando Monte Carlo');
  }
}

function renderMonteCarloResults(data) {
  // Stats
  document.getElementById('mcStats').innerHTML = `
    <div class="stat-card ${data.probabilidad_insolvencia_pct > 20 ? 'red' : 'green'}">
      <div class="stat-label">Prob. Insolvencia</div>
      <div class="stat-value">${data.probabilidad_insolvencia_pct?.toFixed(1) || 0}%</div>
    </div>
    <div class="stat-card blue">
      <div class="stat-label">Nivel de Riesgo</div>
      <div class="stat-value" style="font-size:18px;">${data.nivel_riesgo?.nivel || 'N/A'}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">VaR 95%</div>
      <div class="stat-value" style="font-size:16px;">${formatCurrencyShort(data.var_95 || 0)}</div>
    </div>
    <div class="stat-card celeste">
      <div class="stat-label">Iteraciones</div>
      <div class="stat-value">${data.iteraciones || 0}</div>
    </div>
  `;

  // Bands chart
  if (data.bandas_mensuales) {
    const ctx = document.getElementById('chartMC');
    if (state.charts.mc) state.charts.mc.destroy();

    const labels = data.bandas_mensuales.map((_, i) => `Mes ${i + 1}`);
    state.charts.mc = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'P95', data: data.bandas_mensuales.map(b => b.p95), borderColor: 'rgba(61,174,43,0.5)', fill: false, borderDash: [5,5], pointRadius: 0 },
          { label: 'P75', data: data.bandas_mensuales.map(b => b.p75), borderColor: 'rgba(61,174,43,0.3)', backgroundColor: 'rgba(61,174,43,0.05)', fill: '+1', pointRadius: 0 },
          { label: 'Mediana', data: data.bandas_mensuales.map(b => b.p50), borderColor: '#0D3DA6', borderWidth: 2, pointRadius: 3 },
          { label: 'P25', data: data.bandas_mensuales.map(b => b.p25), borderColor: 'rgba(220,38,38,0.3)', backgroundColor: 'rgba(220,38,38,0.05)', fill: '+1', pointRadius: 0 },
          { label: 'P5', data: data.bandas_mensuales.map(b => b.p5), borderColor: 'rgba(220,38,38,0.5)', fill: false, borderDash: [5,5], pointRadius: 0 },
        ]
      },
      options: { responsive: true, plugins: { legend: { position: 'bottom' } }, scales: { y: { ticks: { callback: v => formatCurrencyShort(v) } } } }
    });
  }
}

// ============================================================================
// Métricas
// ============================================================================
async function loadMetrics() {
  if (!state.companyId) return;
  try {
    const r = await fetch(`${API}/api/v2/companies/${state.companyId}/metrics`);
    const data = await r.json();
    renderMetrics(data);
  } catch(e) {
    document.getElementById('metricsContent').innerHTML = '<div class="empty-state"><div class="empty-title">Sin métricas disponibles</div><div class="empty-desc">Genera el flujo de caja primero</div></div>';
  }
}

function renderMetrics(data) {
  const container = document.getElementById('metricsContent');
  const m = data.metrics || data;

  container.innerHTML = `
    <div class="grid-3" style="margin-bottom:16px;">
      ${renderMetricCard('Caja Mínima', formatCurrency(m.caja_minima?.valor || 0), m.caja_minima?.mes || '', m.caja_minima?.es_negativa ? 'red' : 'green')}
      ${renderMetricCard('Break-even', formatCurrency(m.break_even_operativo?.ventas_mensuales_necesarias || 0), 'ventas/mes necesarias', 'blue')}
      ${renderMetricCard('Runway', m.runway_meses?.meses === Infinity ? '∞' : (m.runway_meses?.meses || 0) + ' meses', m.runway_meses?.mensaje || '', 'celeste')}
    </div>
    <div class="grid-3" style="margin-bottom:16px;">
      ${renderMetricCard('Margen Bruto', (m.margen_bruto_pct?.pct || 0).toFixed(1) + '%', formatCurrency(m.margen_bruto_pct?.absoluto || 0), 'green')}
      ${renderMetricCard('Margen EBITDA', (m.margen_ebitda_pct?.pct || 0).toFixed(1) + '%', formatCurrency(m.margen_ebitda_pct?.absoluto || 0), 'blue')}
      ${renderMetricCard('Financiamiento', m.necesidad_financiamiento?.necesita_financiamiento ? formatCurrency(m.necesidad_financiamiento?.monto || 0) : 'No necesita', m.necesidad_financiamiento?.mensaje || '', m.necesidad_financiamiento?.necesita_financiamiento ? 'yellow' : 'green')}
    </div>
    ${m.resumen_ejecutivo ? `<div class="card"><div class="card-title" style="color:${m.resumen_ejecutivo.color || 'var(--ccs-azul-oscuro)'}"><i class="fas fa-heartbeat"></i> Salud Financiera: ${m.resumen_ejecutivo.salud} (${m.resumen_ejecutivo.score}/100)</div></div>` : ''}
  `;
}

function renderMetricCard(label, value, sub, color) {
  return `<div class="stat-card ${color}"><div class="stat-label">${label}</div><div class="stat-value" style="font-size:18px;">${value}</div><div class="stat-sub">${sub}</div></div>`;
}

// ============================================================================
// Versiones y Escenarios
// ============================================================================
async function loadVersions() {
  if (!state.companyId) return;
  try {
    const r = await fetch(`${API}/api/v2/companies/${state.companyId}/cashflow-versions`);
    const data = await r.json();
    renderVersions(data.versions || []);
  } catch(e) {}
}

function renderVersions(versions) {
  const container = document.getElementById('scenariosList');
  if (!versions.length) {
    container.innerHTML = '<div class="empty-state"><div class="empty-title">Sin versiones guardadas</div><div class="empty-desc">Guarda versiones del cashflow para comparar escenarios</div></div>';
    return;
  }
  container.innerHTML = versions.map(v => `
    <div class="card" style="margin-bottom:8px;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div><strong>${v.name || v.id}</strong><br><span style="font-size:11px;color:var(--text-muted);">${v.created_at || ''}</span></div>
        <button class="btn btn-sm btn-secondary" onclick="restoreVersion('${v.id}')"><i class="fas fa-undo"></i> Restaurar</button>
      </div>
    </div>
  `).join('');
}

async function saveVersion() {
  if (!state.companyId) return;
  const name = prompt('Nombre de la versión:');
  if (!name) return;
  try {
    await fetch(`${API}/api/v2/companies/${state.companyId}/cashflow-versions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    notify('success', 'Versión guardada');
    loadVersions();
  } catch(e) { notify('error', 'Error guardando versión'); }
}

async function restoreVersion(versionId) {
  if (!state.companyId) return;
  try {
    await fetch(`${API}/api/v2/companies/${state.companyId}/cashflow-versions/${versionId}/restore`, { method: 'PUT' });
    notify('success', 'Versión restaurada');
    loadCashflow();
  } catch(e) { notify('error', 'Error restaurando versión'); }
}

// ============================================================================
// Exportación
// ============================================================================
async function exportCSV() {
  if (!state.companyId) return;
  try {
    const r = await fetch(`${API}/api/companies/${state.companyId}/export/csv`);
    const blob = await r.blob();
    downloadBlob(blob, `cashflow_${state.companyName}.csv`);
  } catch(e) { notify('error', 'Error exportando CSV'); }
}

async function exportExcel() {
  if (!state.companyId) return;
  try {
    const r = await fetch(`${API}/api/companies/${state.companyId}/export/excel`);
    const blob = await r.blob();
    downloadBlob(blob, `cashflow_${state.companyName}.xlsx`);
  } catch(e) { notify('error', 'Error exportando Excel'); }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}

// ============================================================================
// Settings
// ============================================================================
async function loadSettings() {
  try {
    const r = await fetch(`${API}/api/agents`);
    const data = await r.json();
    document.getElementById('settingsContent').innerHTML = `
      <div style="margin-top:12px;">
        <div class="card-subtitle" style="margin-bottom:12px;">Agentes de IA configurados</div>
        ${(data.agents || []).map(a => `
          <div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--border);">
            <i class="fas fa-robot" style="color:var(--ccs-azul);"></i>
            <div><strong style="font-size:13px;">${a.name}</strong><br><span style="font-size:11px;color:var(--text-muted);">${a.model} — ${a.description || ''}</span></div>
          </div>
        `).join('')}
      </div>
    `;
  } catch(e) {
    document.getElementById('settingsContent').innerHTML = '<p style="color:var(--text-muted);">Error cargando configuración</p>';
  }
}

// ============================================================================
// Utilidades
// ============================================================================
function openModal(id) { document.getElementById(id).classList.add('open'); }
function closeModal(id) { document.getElementById(id).classList.remove('open'); }

function showGlobalLoading(label, sublabel) {
  document.getElementById('globalLoadingLabel').textContent = label || 'Procesando...';
  document.getElementById('globalLoadingSublabel').textContent = sublabel || '';
  document.getElementById('globalLoadingOverlay').classList.add('active');
}
function hideGlobalLoading() { document.getElementById('globalLoadingOverlay').classList.remove('active'); }

function notify(type, message) {
  const area = document.getElementById('notificationArea');
  const el = document.createElement('div');
  el.className = `notification ${type}`;
  el.innerHTML = `<span>${message}</span>`;
  area.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function formatCurrency(value) {
  if (value === null || value === undefined) return '$0';
  return '$' + Math.round(value).toLocaleString('es-CL');
}

function formatCurrencyShort(value) {
  if (value === null || value === undefined) return '$0';
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 1e9) return sign + '$' + (abs / 1e9).toFixed(1) + 'B';
  if (abs >= 1e6) return sign + '$' + (abs / 1e6).toFixed(1) + 'M';
  if (abs >= 1e3) return sign + '$' + (abs / 1e3).toFixed(0) + 'K';
  return sign + '$' + Math.round(abs).toLocaleString('es-CL');
}

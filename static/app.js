/* ConstructrAI frontend. Supabase handles authentication; all operational data uses FastAPI. */
const state = { supabase: null, session: null, dashboard: null, mode: 'signin', toastTimer: null };
const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
const managerRoles = new Set(['admin', 'manager']);

const escapeHTML = (value = '') => String(value).replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
const slug = (value = '') => String(value).toLowerCase().replace(/\s+/g, '-');
const initials = (value = '') => value.split(/\s+/).filter(Boolean).map(word => word[0]).join('').slice(0, 2).toUpperCase() || 'U';
const formatMoney = value => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(Number(value || 0));
const formatDate = value => { if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', year: 'numeric' }).format(date); };
const formatTimestamp = value => { if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date); };
const statusBadge = value => `<span class="status-badge ${slug(value)}">${escapeHTML(value)}</span>`;
const severityBadge = value => `<span class="severity-badge ${slug(value)}">${escapeHTML(value)}</span>`;

function toast(message, error = false) { const node = $('#toast'); node.textContent = message; node.style.background = error ? '#954441' : ''; node.classList.add('show'); clearTimeout(state.toastTimer); state.toastTimer = setTimeout(() => node.classList.remove('show'), 3600); }
function setScreen(id) { ['boot', 'authShell', 'setupShell', 'appShell'].forEach(name => $(`#${name}`).classList.toggle('hidden', name !== id)); }
function setAuthMode(mode) { state.mode = mode; $$('.auth-tabs button').forEach(button => button.classList.toggle('active', button.dataset.authMode === mode)); $('.signup-field').classList.toggle('hidden', mode !== 'signup'); $('#authTitle').textContent = mode === 'signin' ? 'Welcome back' : 'Create your portal account'; $('#authSubtitle').textContent = mode === 'signin' ? 'Sign in to your construction workspace.' : 'Use your verified organization email.'; $('#authSubmit').textContent = mode === 'signin' ? 'Sign in →' : 'Create account →'; $('#authForm [name="password"]').autocomplete = mode === 'signin' ? 'current-password' : 'new-password'; $('#authError').textContent = ''; }

async function api(path, options = {}) {
  const session = state.session || (await state.supabase.auth.getSession()).data.session;
  if (!session) throw new Error('Your session has expired. Please sign in again.');
  state.session = session;
  const response = await fetch(path, { ...options, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${session.access_token}`, ...(options.headers || {}) } });
  if (!response.ok) { let detail = 'The request could not be completed.'; try { detail = (await response.json()).detail || detail; } catch (_) {} if (response.status === 401) { await signOut(); } throw new Error(detail); }
  return response.status === 204 ? null : response.json();
}

async function start() {
  try {
    const response = await fetch('/api/public-config');
    if (!response.ok) throw new Error('The deployment has not been connected to Supabase. Add the required Render environment variables.');
    const config = await response.json();
    if (!window.supabase) throw new Error('Supabase client library did not load. Check your network connection.');
    state.supabase = window.supabase.createClient(config.supabase_url, config.supabase_anon_key);
    state.supabase.auth.onAuthStateChange((_event, session) => { state.session = session; });
    const { data: { session } } = await state.supabase.auth.getSession();
    state.session = session;
    if (session) await resolveAccount(); else setScreen('authShell');
  } catch (error) { $('#boot').innerHTML = `<div class="brand-mark"><i></i><i></i><i></i></div><strong>Constructr<span>AI</span></strong><p>${escapeHTML(error.message)}</p>`; }
}

async function resolveAccount() {
  try {
    const account = await api('/api/me');
    if (account.setup_required) { $('#setupForm [name="full_name"]').value = account.user.metadata?.full_name || ''; setScreen('setupShell'); return; }
    await loadDashboard();
    setScreen('appShell');
  } catch (error) { setScreen('authShell'); toast(error.message, true); }
}

async function signOut() { if (state.supabase) await state.supabase.auth.signOut(); state.session = null; state.dashboard = null; setScreen('authShell'); setAuthMode('signin'); }

async function loadDashboard(showToast = false) { const data = await api('/api/dashboard'); state.dashboard = data; renderDashboard(data); if (showToast) toast('Workspace refreshed.'); }
function roleSetup(profile) {
  const isAdmin = profile.role === 'admin';
  const isManager = profile.role === 'manager';
  const isEmployee = profile.role === 'employee';
  const isCustomer = profile.role === 'customer';
  const isStaff = profile.role !== 'customer';

  // Strict DOM removal (not just CSS hidden) for admin-only sections
  $$('.manager-only').forEach(node => {
    if (isAdmin || isManager) {
      node.classList.remove('hidden');
      node.style.display = '';
    } else {
      node.classList.add('hidden');
      node.style.display = 'none';
      // Fully remove interactive buttons from DOM for non-managers
      if (!isAdmin && !isManager) {
        node.querySelectorAll('button, a').forEach(btn => btn.remove());
        node.innerHTML = '<span class="restricted-label">Restricted to managers and admins</span>';
      }
    }
  });

  $$('.staff-only').forEach(node => {
    if (isStaff) {
      node.classList.remove('hidden');
      node.style.display = '';
    } else {
      node.classList.add('hidden');
      node.style.display = 'none';
    }
  });

  // Admin-only strict removal
  $$('.admin-only').forEach(node => {
    if (!isAdmin && !isManager) {
      node.classList.add('hidden');
      node.style.display = 'none';
    } else {
      node.classList.remove('hidden');
      node.style.display = '';
    }
  });

  const adminOnlySections = document.querySelectorAll('#audit');
  adminOnlySections.forEach(node => {
    if (!isAdmin && !isManager) {
      node.classList.add('hidden');
      node.style.display = 'none';
    }
  });

  $('#userName').textContent = profile.full_name;
  $('#userRole').textContent = profile.role;
  $('#userInitials').textContent = initials(profile.full_name);

  // Different UI titles per role
  const roleLabels = {
    admin: 'ADMIN COMMAND CENTER',
    manager: 'MANAGER DASHBOARD',
    employee: 'EMPLOYEE WORKSPACE',
    customer: 'CUSTOMER PORTAL'
  };
  $('#dashboardRole').textContent = (roleLabels[profile.role] || profile.role.toUpperCase() + ' PORTAL');

  const subtitles = {
    admin: 'Full organization control, audit, AI settings, risk assessment, and team management.',
    manager: 'Department oversight, team actions, customer relationships, and delivery tracking.',
    employee: 'Your assigned tasks, open actions, project updates, and complaints.',
    customer: 'Only your assigned projects, tasks, and complaint records.'
  };
  $('#dashboardSubtitle').textContent = subtitles[profile.role] || 'Your role-aware workspace.';

  $('#dashboardGreeting').textContent = `Welcome, ${profile.full_name.split(' ')[0]}`;

  // Role-based color theme
  document.body.className = document.body.className.replace(/role-[a-z]+/g, '').trim();
  document.body.classList.add(`role-${profile.role}`);
  $('#appShell').classList.add(`role-${profile.role}`);
}
function renderDashboard(data) {
  roleSetup(data.profile);
  const organizationName = data.organization?.name || 'Construction workspace'; $('#organizationLabel').textContent = organizationName; $('#orgInitial').textContent = initials(organizationName).slice(0, 1);
  const roleCaption = data.profile.role === 'customer' ? 'Your open actions' : data.profile.role === 'employee' ? 'Assigned work' : data.profile.role === 'manager' ? 'Team actions' : 'All workspace actions';
  $('#metricProjects').textContent = data.metrics.active_projects; $('#metricRisk').textContent = data.metrics.at_risk_projects; $('#metricComplaints').textContent = data.metrics.open_complaints; $('#metricTasks').textContent = data.metrics.open_tasks; $('#metricTaskCaption').textContent = data.metrics.late_tasks ? `${data.metrics.late_tasks} past due / needs review (${roleCaption.toLowerCase()})` : roleCaption; $('#projectBadge').textContent = data.metrics.active_projects; $('#taskBadge').textContent = data.metrics.open_tasks; $('#complaintBadge').textContent = data.metrics.open_complaints;
  renderPriority(data.projects); renderCompactTasks(data.tasks); renderCompactComplaints(data.complaints); renderProjects(data); renderDepartments(data); renderEmployees(data); renderCustomers(data); renderTasks(data); renderComplaints(data); renderDocuments(data); renderAudit(data); populateSelectors(data);
}
function renderPriority(projects) { const records = projects.filter(item => ['At risk', 'Watch'].includes(item.status)); $('#priorityProjects').innerHTML = records.length ? records.map(item => `<article class="priority-item"><div class="priority-top"><strong>${escapeHTML(item.name)}</strong>${statusBadge(item.status)}</div><div class="priority-meta"><span>${escapeHTML(item.project_type)}</span><span>${item.days_remaining} days remaining</span></div><div class="progress-track"><div class="progress-bar ${item.status === 'At risk' ? 'critical' : 'risk'}" style="width:${item.progress}%"></div></div></article>`).join('') : '<p class="empty-state">No accessible projects are marked Watch or At risk.</p>'; }
function renderCompactTasks(tasks) { const records = tasks.filter(item => item.status !== 'Done').slice(0, 4); $('#latestTasks').innerHTML = records.length ? records.map(item => `<article class="compact-item"><span class="compact-symbol task">✓</span><div class="compact-copy"><strong>${escapeHTML(item.title)}</strong><p>${escapeHTML(item.status)}${item.due_date ? ` · due ${formatDate(item.due_date)}` : ''}</p></div>${severityBadge(item.priority)}</article>`).join('') : '<p class="empty-state">No open actions.</p>'; }
function renderCompactComplaints(complaints) { const records = complaints.filter(item => item.status !== 'Resolved').slice(0, 4); $('#latestComplaints').innerHTML = records.length ? records.map(item => `<article class="compact-item"><span class="compact-symbol complaint">◉</span><div class="compact-copy"><strong>${escapeHTML(item.category)} issue</strong><p>${escapeHTML(item.description)}</p></div>${severityBadge(item.priority)}</article>`).join('') : '<p class="empty-state">No open complaints.</p>'; }
function renderProjects(data) {
  const customers = new Map(data.customers.map(item => [item.id, item.company_name])); const departments = new Map(data.departments.map(item => [item.id, item.name]));
  $('#projectTable').innerHTML = data.projects.length ? data.projects.map(item => `<tr><td><span class="project-name">${escapeHTML(item.name)}</span><span class="project-type">${escapeHTML(item.project_type)}</span></td><td>${escapeHTML(customers.get(item.customer_id) || '—')}<span class="cell-muted">${escapeHTML(departments.get(item.department_id) || 'No department')}</span></td><td><div class="mini-progress"><span>${Number(item.progress).toFixed(0)}% complete</span><div class="progress-track"><div class="progress-bar ${item.status === 'At risk' ? 'critical' : item.status === 'Watch' ? 'risk' : ''}" style="width:${item.progress}%"></div></div></div></td><td>${item.days_remaining} days left<span class="cell-muted">${item.delay_days} delay day(s)</span></td><td>${formatMoney(item.budget)}</td><td>${statusBadge(item.status)}</td><td class="staff-only">${data.profile.role !== 'customer' ? `<button class="row-action" data-risk="${item.id}" type="button">Assess risk</button>` : ''}</td></tr>`).join('') : '<tr><td colspan="7" class="empty-state">No projects yet. An admin or manager can create the first delivery record.</td></tr>';
  $$('[data-risk]').forEach(button => button.addEventListener('click', () => { const project = data.projects.find(item => item.id === button.dataset.risk); if (!project) return; showView('projects'); const form = $('#riskForm'); Object.entries({ project_id: project.id, project_name: project.name, progress: project.progress, days_remaining: project.days_remaining, planned_duration: project.planned_duration, team_size: project.team_size, delay_days: project.delay_days }).forEach(([key, value]) => form.elements[key].value = value ?? ''); form.elements.high_priority_complaints.value = data.complaints.filter(c => c.project_id === project.id && ['High', 'Critical'].includes(c.priority) && c.status !== 'Resolved').length; setTimeout(() => form.scrollIntoView({ behavior: 'smooth', block: 'center' }), 30); }));
}
function renderDepartments(data) { const projects = data.projects; const tasks = data.tasks; const employees = data.employees; $('#departmentGrid').innerHTML = data.departments.map(department => { const dp = projects.filter(item => item.department_id === department.id); const dt = tasks.filter(item => item.department_id === department.id && item.status !== 'Done'); const de = employees.filter(item => item.department_id === department.id); return `<article class="department-card" data-department="${department.id}" style="--department-color:${escapeHTML(department.color)}"><p class="eyebrow">${escapeHTML(department.code)}</p><h2>${escapeHTML(department.name)}</h2><p>${escapeHTML(department.description || 'Construction operating unit')}</p><div class="department-stats"><span><strong>${dp.length}</strong>projects</span><span><strong>${dt.length}</strong>open work</span><span><strong>${de.length}</strong>people</span></div></article>`; }).join('') || '<p class="empty-state">No departments are configured.</p>'; $$('[data-department]').forEach(card => card.addEventListener('click', () => loadDepartment(card.dataset.department)));
}
async function loadDepartment(id) { try { const detail = await api(`/api/departments/${id}/dashboard`); const node = $('#departmentDetail'); node.classList.remove('hidden'); node.innerHTML = `<p class="eyebrow">DEPARTMENT HUB</p><h2>${escapeHTML(detail.department.name)}</h2><div class="detail-grid"><article class="detail-number"><strong>${detail.metrics.projects}</strong><small>projects</small></article><article class="detail-number"><strong>${detail.metrics.open_tasks}</strong><small>open actions</small></article><article class="detail-number"><strong>${detail.metrics.employees}</strong><small>employees</small></article></div><p class="panel-intro">Projects: ${detail.projects.map(p => escapeHTML(p.name)).join(', ') || 'none'}<br>Open actions: ${detail.tasks.filter(t => t.status !== 'Done').map(t => escapeHTML(t.title)).join(', ') || 'none'}</p>`; node.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); } catch (error) { toast(error.message, true); } }
function renderEmployees(data) { const departments = new Map(data.departments.map(item => [item.id, item.name])); $('#employeeTable').innerHTML = data.employees.length ? data.employees.map(item => `<tr><td><span class="project-name">${escapeHTML(item.full_name)}</span></td><td>${escapeHTML(departments.get(item.department_id) || '—')}</td><td>${escapeHTML(item.job_title)}</td><td>${statusBadge(item.status)}</td><td>${escapeHTML(item.email)}<span class="cell-muted">${escapeHTML(item.phone || '—')}</span></td><td>${managerRoles.has(data.profile.role) && !item.profile_id ? `<button class="row-action" data-invite="${item.id}" type="button">Invite</button>` : ''}</td></tr>`).join('') : '<tr><td colspan="6" class="empty-state">No employee records are visible.</td></tr>'; $$('[data-invite]').forEach(button => button.addEventListener('click', () => inviteEmployee(button.dataset.invite, button)) ); }
async function inviteEmployee(id, button) { button.disabled = true; button.textContent = 'Sending…'; try { await api(`/api/employees/${id}/invite`, { method: 'POST' }); toast('Employee invitation sent through Supabase Auth.'); await loadDashboard(); } catch (error) { toast(error.message, true); button.disabled = false; button.textContent = 'Invite'; } }
function renderCustomers(data) { const count = data.projects.reduce((acc, item) => ({ ...acc, [item.customer_id]: (acc[item.customer_id] || 0) + 1 }), {}); $('#customerTable').innerHTML = data.customers.length ? data.customers.map(item => `<tr><td><span class="project-name">${escapeHTML(item.company_name)}</span></td><td>${escapeHTML(item.contact_name)}</td><td>${escapeHTML(item.email)}<span class="cell-muted">${escapeHTML(item.phone || '—')}</span></td><td>${statusBadge(item.status)}</td><td>${count[item.id] || 0}</td><td>${managerRoles.has(data.profile.role) && !item.profile_id ? `<button class="row-action" data-customer-invite="${item.id}" type="button">Invite</button>` : ''}</td></tr>`).join('') : '<tr><td colspan="6" class="empty-state">No customer records are visible.</td></tr>'; $$('[data-customer-invite]').forEach(button => button.addEventListener('click', () => inviteCustomer(button.dataset.customerInvite, button))); }
async function inviteCustomer(id, button) { button.disabled = true; button.textContent = 'Sending…'; try { await api(`/api/customers/${id}/invite`, { method: 'POST' }); toast('Customer portal invitation sent through Supabase Auth.'); await loadDashboard(); } catch (error) { toast(error.message, true); button.disabled = false; button.textContent = 'Invite'; } }
function renderTasks(data) { const projects = new Map(data.projects.map(item => [item.id, item.name])); $('#taskTable').innerHTML = data.tasks.length ? data.tasks.map(item => `<tr><td>${severityBadge(item.priority)}</td><td><span class="project-name">${escapeHTML(item.title)}</span><span class="cell-muted">${escapeHTML(item.description || '')}</span></td><td>${escapeHTML(projects.get(item.project_id) || 'General')}</td><td>${formatDate(item.due_date)}</td><td>${statusBadge(item.status)}</td><td>${item.status !== 'Done' && data.profile.role !== 'customer' ? `<button class="row-action" data-task-done="${item.id}" type="button">Mark done</button>` : ''}</td></tr>`).join('') : '<tr><td colspan="6" class="empty-state">No actions recorded.</td></tr>'; $$('[data-task-done]').forEach(button => button.addEventListener('click', () => finishTask(button.dataset.taskDone, button))); }
async function finishTask(id, button) { button.disabled = true; try { await api(`/api/tasks/${id}`, { method: 'PATCH', body: JSON.stringify({ status: 'Done' }) }); toast('Action marked done.'); await loadDashboard(); } catch (error) { toast(error.message, true); button.disabled = false; } }
function renderComplaints(data) { const projects = new Map(data.projects.map(item => [item.id, item.name])); $('#complaintTable').innerHTML = data.complaints.length ? data.complaints.map(item => `<tr><td>${severityBadge(item.priority)}</td><td>${escapeHTML(item.category)}</td><td class="issue-cell">${escapeHTML(item.description)}</td><td>${escapeHTML(projects.get(item.project_id) || 'General')}</td><td>${statusBadge(item.status)}</td><td class="cell-muted">${formatTimestamp(item.created_at)}</td></tr>`).join('') : '<tr><td colspan="6" class="empty-state">No complaints have been logged.</td></tr>'; }
function renderDocuments(data) { $('#documentList').innerHTML = data.documents?.length ? data.documents.map(item => `<article class="document-card"><span>▤</span><strong title="${escapeHTML(item.name)}">${escapeHTML(item.name)}</strong><small>${escapeHTML(item.document_type)} · ${formatTimestamp(item.created_at)}</small><a href="${escapeHTML(item.url)}" target="_blank" rel="noopener noreferrer">Open approved link →</a></article>`).join('') : '<p class="empty-state">No documents are registered. Add approved HTTPS document links here; configure Supabase Storage for managed file uploads.</p>'; }
function renderAudit(data) { $('#auditTable').innerHTML = data.audit_events.length ? data.audit_events.map(item => `<tr><td>${severityBadge(item.severity)}</td><td class="project-name">${escapeHTML(item.actor_name)}</td><td>${escapeHTML(item.action)}</td><td>${escapeHTML(item.entity_type)}<span class="cell-muted">${escapeHTML(item.entity_name)}</span></td><td class="cell-muted">${formatTimestamp(item.created_at)}</td></tr>`).join('') : '<tr><td colspan="5" class="empty-state">Audit activity is available to Admin and Manager roles.</td></tr>'; }

async function loadAIDev() {
  if (!state.dashboard || (state.dashboard.profile.role !== 'admin' && state.dashboard.profile.role !== 'manager')) return;
  try {
    const [config, usage, status] = await Promise.all([
      api('/api/ai/config'),
      api('/api/ai/usage'),
      api('/api/system/status'),
    ]);
    $('#aiConfigPanel').innerHTML = `<article class="compact-item"><span class="compact-symbol">✦</span><div class="compact-copy"><strong>Provider</strong><p>${escapeHTML(config.ai_provider)} · ${escapeHTML(config.model)}</p><small>Temp: ${config.temperature} · Max tokens: ${config.max_tokens}</small></div></article>` +
      `<article class="compact-item"><span class="compact-symbol">◒</span><div class="compact-copy"><strong>Grounding</strong><p>${escapeHTML(config.data_grounding)}</p></div></article>` +
      `<article class="compact-item"><span class="compact-symbol">✓</span><div class="compact-copy"><strong>Audit logging</strong><p>${escapeHTML(config.audit_logging)}</p></div></article>` +
      `<article class="compact-item"><span class="compact-symbol">📊</span><div class="compact-copy"><strong>Integration health</strong><p>Supabase: ${config.integration_health.supabase_configured ? 'OK' : 'Missing'} · AI: ${config.integration_health.ai_available ? 'OK' : 'Missing'} · ML: ${config.integration_health.ml_model_ready ? 'Ready' : 'Not ready'}</p></div></article>`;
    $('#aiUsagePanel').innerHTML = `<article class="compact-item"><span class="compact-symbol">✦</span><div class="compact-copy"><strong>Total AI requests</strong><p>${usage.total_requests}</p></div></article>` +
      `<article class="compact-item"><span class="compact-symbol">◉</span><div class="compact-copy"><strong>Local copilot</strong><p>${usage.sources.local} requests</p></div></article>` +
      `<article class="compact-item"><span class="compact-symbol">◫</span><div class="compact-copy"><strong>Hosted AI</strong><p>${usage.sources.hosted} requests</p></div></article>` +
      `<article class="compact-item"><span class="compact-symbol">◒</span><div class="compact-copy"><strong>Latest source</strong><p>${usage.latest.length ? usage.latest[0].source : 'None'}</p></div></article>`;
    $('#systemStatusPanel').innerHTML = `<article class="compact-item"><span class="compact-symbol">✦</span><div class="compact-copy"><strong>Service</strong><p>${escapeHTML(status.service)}</p></div></article>` +
      `<article class="compact-item"><span class="compact-symbol">◉</span><div class="compact-copy"><strong>AI integration</strong><p>Local: active · Hosted: ${escapeHTML(status.ai_integration.hosted_provider)}</p></div></article>` +
      `<article class="compact-item"><span class="compact-symbol">◫</span><div class="compact-copy"><strong>ML predictor</strong><p>${escapeHTML(status.ml_integration.predictor)} · Data: ${escapeHTML(status.ml_integration.dataset_type)}</p></div></article>` +
      `<article class="compact-item"><span class="compact-symbol">✓</span><div class="compact-copy"><strong>Environment configured</strong><p>${status.environment_variables_configured ? 'Yes' : 'No'}</p></div></article>` +
      `<article class="compact-item"><span class="compact-symbol">📊</span><div class="compact-copy"><strong>Rate limit</strong><p>${escapeHTML(status.security.rate_limit)}</p></div></article>` +
      `<article class="compact-item"><span class="compact-symbol">📊</span><div class="compact-copy"><strong>Security headers</strong><p>${escapeHTML(status.security.headers)}</p></div></article>`;
  } catch (err) { console.error('Failed to load AI/dev data:', err); }
}
function populateSelectors(data) { const options = (records, label) => records.map(item => `<option value="${item.id}">${escapeHTML(item[label])}</option>`).join(''); $$('.project-select').forEach(select => { const chosen = select.value; select.innerHTML = '<option value="">Not assigned</option>' + options(data.projects, 'name'); select.value = chosen; }); $$('.customer-select').forEach(select => { const chosen = select.value; select.innerHTML = '<option value="">Not assigned</option>' + options(data.customers, 'company_name'); select.value = chosen; }); $$('.department-select').forEach(select => { const chosen = select.value; select.innerHTML = '<option value="">Not assigned</option>' + options(data.departments, 'name'); select.value = chosen; }); const portalEmployees = data.employees.filter(employee => employee.profile_id); $$('.employee-select').forEach(select => { const chosen = select.value; select.innerHTML = '<option value="">Unassigned</option>' + portalEmployees.map(employee => `<option value="${employee.profile_id}">${escapeHTML(employee.full_name)}</option>`).join(''); select.value = chosen; }); }
function appendMessage(kind, text, source = '') { const node = $('#chatWindow'); node.insertAdjacentHTML('beforeend', `<div class="message ${kind}"><span class="message-icon">${kind === 'assistant' ? '✦' : 'U'}</span><div><p>${escapeHTML(text)}</p>${source ? `<span class="cell-muted">${escapeHTML(source)}</span>` : ''}</div></div>`); node.scrollTop = node.scrollHeight; }
async function askAI(text) { const message = text.trim(); if (!message) return; appendMessage('user', message); $('#chatInput').value = ''; const button = $('#chatForm button'); button.disabled = true; button.textContent = '…'; try { const result = await api('/api/ai/ask', { method: 'POST', body: JSON.stringify({ message }) }); appendMessage('assistant', result.answer, result.source); $('#aiSource').textContent = result.source === 'hosted AI' ? 'Hosted AI' : 'Local data'; } catch (error) { appendMessage('assistant', `I could not complete that request: ${error.message}`); } finally { button.disabled = false; button.textContent = '↑'; } }
function renderRisk(result) { const node = $('#riskResult'); node.className = 'risk-result filled'; node.innerHTML = `<div class="risk-score"><strong>${result.risk_score}%</strong>${statusBadge(result.risk_level)}<small>${result.confidence}% model decisiveness</small></div><div class="risk-copy"><h3>Signals</h3><ul>${result.drivers.map(item => `<li>${escapeHTML(item)}</li>`).join('')}</ul></div><div class="risk-copy"><h3>Review actions</h3><ul>${result.recommendations.map(item => `<li>${escapeHTML(item)}</li>`).join('')}</ul></div><p class="model-note">${escapeHTML(result.model_note)}</p>`; }
function showView(id) { $$('.view').forEach(node => node.classList.toggle('active', node.id === id)); $$('.nav-item[data-view]').forEach(node => node.classList.toggle('active', node.dataset.view === id)); $('#sidebar').classList.remove('open'); document.getElementById(id).scrollIntoView({ behavior: 'smooth', block: 'start' }); if (id === 'ai-dev') { loadAIDev(); } }
function openDialog(id) { document.getElementById(id).showModal(); }
function closeDialog(id) { document.getElementById(id).close(); }
function cleanPayload(form) { const payload = Object.fromEntries(new FormData(form)); for (const [key, value] of Object.entries(payload)) { if (value === '') payload[key] = null; } return payload; }
async function submitForm(form, endpoint, success) { const error = $('.form-error', form); error.textContent = ''; const button = $('button[type="submit"]', form); button.disabled = true; try { await api(endpoint, { method: 'POST', body: JSON.stringify(cleanPayload(form)) }); closeDialog(form.closest('dialog').id); form.reset(); await loadDashboard(); toast(success); } catch (err) { error.textContent = err.message; } finally { button.disabled = false; } }
function wireEvents() {
  $$('.auth-tabs button').forEach(button => button.addEventListener('click', () => setAuthMode(button.dataset.authMode)));
  $('#authForm').addEventListener('submit', async event => { event.preventDefault(); const form = event.currentTarget; const error = $('#authError'); error.textContent = ''; const values = Object.fromEntries(new FormData(form)); const button = $('#authSubmit'); button.disabled = true; try { if (state.mode === 'signin') { const { error: signInError } = await state.supabase.auth.signInWithPassword({ email: values.email, password: values.password }); if (signInError) throw signInError; const { data: { session } } = await state.supabase.auth.getSession(); state.session = session; await resolveAccount(); } else { const { data, error: signUpError } = await state.supabase.auth.signUp({ email: values.email, password: values.password, options: { data: { full_name: values.full_name } } }); if (signUpError) throw signUpError; if (!data.session) { toast('Account created. Confirm your email, then sign in.'); setAuthMode('signin'); } else { state.session = data.session; await resolveAccount(); } } } catch (err) { error.textContent = err.message || 'Authentication failed.'; } finally { button.disabled = false; } });
  $('#setupForm').addEventListener('submit', async event => { event.preventDefault(); const form = event.currentTarget; const error = $('#setupError'); error.textContent = ''; const button = $('button[type="submit"]', form); button.disabled = true; try { await api('/api/onboarding', { method: 'POST', body: JSON.stringify(cleanPayload(form)) }); await loadDashboard(); setScreen('appShell'); const selectedRole = cleanPayload(form).role || 'user'; toast(`Workspace created. Role assigned: ${selectedRole}.`); } catch (err) { error.textContent = err.message; } finally { button.disabled = false; } });
  $('#setupSignout').addEventListener('click', signOut); $('#logoutButton').addEventListener('click', signOut); $('#mobileMenu').addEventListener('click', () => $('#sidebar').classList.toggle('open')); $('#refreshButton').addEventListener('click', async () => { try { await loadDashboard(true); } catch (err) { toast(err.message, true); } }); $('#quickTask').addEventListener('click', () => openDialog('taskDialog')); $('#aboutButton').addEventListener('click', () => openDialog('aboutDialog'));
  $$('.nav-item[data-view], a[data-view]').forEach(node => node.addEventListener('click', event => { event.preventDefault(); showView(node.dataset.view); })); $$('[data-open]').forEach(button => button.addEventListener('click', () => openDialog(button.dataset.open))); $$('[data-close]').forEach(button => button.addEventListener('click', () => closeDialog(button.dataset.close)));
  $('#chatForm').addEventListener('submit', event => { event.preventDefault(); askAI($('#chatInput').value); }); $$('#suggestions button').forEach(button => button.addEventListener('click', () => askAI(button.textContent)));
  $('#riskForm').addEventListener('submit', async event => { event.preventDefault(); const form = event.currentTarget; const values = cleanPayload(form); ['progress', 'days_remaining', 'planned_duration', 'team_size', 'delay_days', 'high_priority_complaints'].forEach(key => values[key] = Number(values[key])); const button = $('button[type="submit"]', form); button.disabled = true; button.textContent = 'Assessing…'; try { renderRisk(await api('/api/predict-risk', { method: 'POST', body: JSON.stringify(values) })); toast('Assessment logged to audit activity.'); } catch (err) { toast(err.message, true); } finally { button.disabled = false; button.textContent = 'Assess risk →'; } });
  $('#projectForm').addEventListener('submit', event => { event.preventDefault(); submitForm(event.currentTarget, '/api/projects', 'Project created and audited.'); }); $('#departmentForm').addEventListener('submit', event => { event.preventDefault(); submitForm(event.currentTarget, '/api/departments', 'Department created.'); }); $('#employeeForm').addEventListener('submit', event => { event.preventDefault(); submitForm(event.currentTarget, '/api/employees', 'Employee record created. Use Invite to create portal access.'); }); $('#customerForm').addEventListener('submit', event => { event.preventDefault(); submitForm(event.currentTarget, '/api/customers', 'Customer record created.'); }); $('#taskForm').addEventListener('submit', event => { event.preventDefault(); submitForm(event.currentTarget, '/api/tasks', 'Action item created.'); }); $('#complaintForm').addEventListener('submit', event => { event.preventDefault(); submitForm(event.currentTarget, '/api/complaints', 'Complaint logged and audited.'); }); $('#documentForm').addEventListener('submit', event => { event.preventDefault(); submitForm(event.currentTarget, '/api/documents', 'Document link registered.'); });
}
document.addEventListener('DOMContentLoaded', () => { wireEvents(); start(); });

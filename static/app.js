const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const api = async (url, options = {}) => {
  const response = await fetch(url, { headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || data.message || 'Request failed');
  return data;
};
const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[char]));
const badge = (value) => `<span class="badge badge-${String(value || '').toLowerCase().replaceAll(' ', '-')}">${esc(value || '—')}</span>`;
const toast = (message, error = false) => { const el = $('#toast'); el.textContent = message; el.style.background = error ? '#8f3737' : '#173d2d'; el.classList.add('show'); setTimeout(() => el.classList.remove('show'), 3300); };

function showView(name) {
  $$('.nav-item').forEach((item) => item.classList.toggle('active', item.dataset.view === name));
  $$('.view').forEach((view) => view.classList.toggle('active', view.id === `view-${name}`));
  if (name === 'dashboard') loadDashboard();
  if (name === 'handler') loadHandlers();
  if (name === 'routing') loadRouting();
  if (name === 'analytics') loadAnalytics();
}
$$('.nav-item').forEach((item) => item.addEventListener('click', () => showView(item.dataset.view)));
$('#refresh-button').addEventListener('click', () => { const active = $('.nav-item.active')?.dataset.view || 'dashboard'; showView(active); toast('Dashboard refreshed'); });

const appShell = $('.app-shell');
const panelToggle = $('#panel-toggle');
const savedPanelState = localStorage.getItem('fieldsafe-sidebar-collapsed');
const initiallyCollapsed = savedPanelState === null ? window.matchMedia('(max-width: 650px)').matches : savedPanelState === 'true';
appShell.classList.toggle('sidebar-collapsed', initiallyCollapsed);
function syncPanelToggle() {
  const expanded = !appShell.classList.contains('sidebar-collapsed');
  panelToggle.setAttribute('aria-expanded', String(expanded));
  panelToggle.setAttribute('aria-label', `${expanded ? 'Collapse' : 'Expand'} side panel`);
  panelToggle.title = `${expanded ? 'Collapse' : 'Expand'} side panel`;
}
syncPanelToggle();
panelToggle.addEventListener('click', () => {
  const collapsed = appShell.classList.toggle('sidebar-collapsed');
  localStorage.setItem('fieldsafe-sidebar-collapsed', String(collapsed));
  syncPanelToggle();
});

$('#report-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const errors = $('#form-errors'); errors.textContent = '';
  const button = form.querySelector('button[type="submit"]'); button.disabled = true; button.textContent = 'Validating and dispatching…';
  try {
    const payload = Object.fromEntries(new FormData(form).entries());
    const result = await api('/api/reports', { method: 'POST', body: JSON.stringify(payload) });
    const output = $('#submission-result'); output.classList.remove('hidden'); output.classList.add('success');
    const rejected = result.validation_status === 'rejected' || result.status === 'Rejected';
    output.classList.toggle('success', !rejected); output.classList.toggle('error-result', rejected);
    output.innerHTML = `<div class="result-title"><div><h2>${rejected ? 'Report rejected before dispatch' : 'Report accepted and routed'}</h2><p class="muted">${rejected ? 'Correct the highlighted validation issue and submit again.' : 'Validation, classification and dispatch completed successfully.'}</p></div><span class="result-id">${esc(result.id)}</span></div><div class="result-details"><div><small>Category</small><strong>${badge(result.category)}</strong></div><div><small>Validation</small><strong>${esc(result.validation_status)}</strong></div><div><small>Assignment</small><strong>${esc(result.handler_name || result.assignment_status || 'No dispatch')}</strong></div><div><small>Status</small><strong>${badge(result.status)}</strong></div></div><div class="inline-note"><span class="info-icon">i</span><span>${esc(result.decision || result.validation_message || '')}</span></div>`;
    if (!rejected) form.reset(); toast(rejected ? 'Report rejected: validation required' : `Report ${result.id} created`, rejected);
  } catch (error) { errors.textContent = error.message; toast(error.message, true); } finally { button.disabled = false; button.innerHTML = 'Validate & dispatch report <span>→</span>'; }
});

async function loadDashboard() {
  try {
    const [stats, reports] = await Promise.all([api('/api/dashboard/stats'), api(`/api/reports?search=${encodeURIComponent($('#report-search')?.value || '')}&status=${encodeURIComponent($('#status-filter')?.value || '')}`)]);
    const cards = [['Total reports', stats.total], ['Pending queue', stats.pending], ['Assigned', stats.assigned], ['In progress', stats.in_progress], ['Resolved', stats.resolved]];
    $('#stats-grid').innerHTML = cards.map(([label, value]) => `<div class="stat-card"><span class="label">${label}</span><strong>${value}</strong><div class="bar"><span style="width:${Math.min(100, stats.total ? value / stats.total * 100 : 5)}%"></span></div></div>`).join('');
    $('#reports-table').innerHTML = reports.reports.length ? reports.reports.map((report) => `<tr><td><span class="report-link">${esc(report.id)}</span><span class="subtext">${esc(report.inspector_id)} · ${esc(report.reporter_name)}</span></td><td>${badge(report.category)}<span class="subtext">${esc(report.violation_code)}</span></td><td>${esc(report.zone_key || 'Fallback')}<span class="subtext">${esc(report.handler_name || 'Correction queue')}</span></td><td>${badge(report.status)}</td><td>${new Date(report.created_at).toLocaleString()}</td></tr>`).join('') : '<tr><td colspan="5" class="muted">No reports match this search.</td></tr>';
  } catch (error) { toast(error.message, true); }
}
let searchTimer; $('#report-search').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadDashboard, 250); }); $('#status-filter').addEventListener('change', loadDashboard);

async function loadHandlers() { try { const data = await api('/api/handlers'); $('#handlers-table').innerHTML = data.handlers.map((handler) => `<tr><td><strong>${esc(handler.name)}</strong><span class="subtext">Handler #${handler.id}</span></td><td>${esc(handler.zone_key)}</td><td>${esc(handler.role)}</td><td><strong>${handler.open_cases}</strong> / ${handler.capacity}</td><td><div class="handler-controls"><button class="toggle ${handler.available ? 'on' : ''}" aria-label="Set ${esc(handler.name)} ${handler.available ? 'away' : 'available'}" aria-pressed="${Boolean(handler.available)}" title="Toggle availability" data-handler="${handler.id}" data-available="${handler.available ? 0 : 1}"></button><span>${handler.available ? 'Available' : 'Away'}</span></div></td><td><div class="handler-controls"><input type="number" min="1" max="10" value="${handler.capacity}" data-capacity="${handler.id}" aria-label="Capacity for ${esc(handler.name)}"><button class="secondary-button save-capacity" data-handler="${handler.id}">Save</button></div></td><td></td></tr>`).join(''); $$('.toggle').forEach((button) => button.addEventListener('click', async () => { try { await api(`/api/handlers/${button.dataset.handler}`, { method:'PATCH', body:JSON.stringify({ available:Number(button.dataset.available) }) }); toast('Availability updated'); await loadHandlers(); } catch (error) { toast(error.message, true); } })); $$('.save-capacity').forEach((button) => button.addEventListener('click', async () => { const input = $(`[data-capacity="${button.dataset.handler}"]`); try { await api(`/api/handlers/${button.dataset.handler}`, { method:'PATCH', body:JSON.stringify({ capacity:Number(input.value) }) }); toast('Capacity updated'); await loadHandlers(); } catch (error) { toast(error.message, true); } })); const assigned = await api('/api/reports?status=Assigned'); $('#handler-reports-table').innerHTML = assigned.reports.length ? assigned.reports.map((report) => `<tr><td><span class="report-link">${esc(report.id)}</span><span class="subtext">${esc(report.inspector_id)}</span></td><td>${badge(report.category)}</td><td>P${report.priority}</td><td>${esc(report.handler_name || '—')}</td><td>${new Date(report.created_at).toLocaleString()}</td><td><select class="status-action" data-report="${esc(report.id)}" aria-label="Update status for ${esc(report.id)}"><option>Assigned</option><option>In Progress</option><option>Resolved</option></select></td></tr>`).join('') : '<tr><td colspan="6" class="muted">No assigned reports.</td></tr>'; $$('.status-action').forEach((select) => select.addEventListener('change', async () => { try { await api(`/api/reports/${select.dataset.report}/status`, { method:'PATCH', body:JSON.stringify({ status: select.value }) }); toast('Report status updated'); await loadHandlers(); } catch (error) { toast(error.message, true); } })); } catch (error) { toast(error.message, true); } }
$('#handler-refresh').addEventListener('click', async () => { await loadHandlers(); toast('Roster refreshed'); });

async function loadRouting() { try { const [data, roster, pending] = await Promise.all([api('/api/routing'), api('/api/handlers'), api('/api/reports?status=Pending')]); const byZone = Object.groupBy ? Object.groupBy(roster.handlers, (h) => h.zone_key) : roster.handlers.reduce((acc, h) => ((acc[h.zone_key] ||= []).push(h), acc), {}); $('#routing-grid').innerHTML = data.routing_table.map((route) => { const handlers = byZone[route.zone_key] || []; const primary = handlers.find((h) => h.role === 'District Officer'); const backup = handlers.find((h) => h.role === 'Deputy Officer'); return `<div class="card route-card"><div class="route-top"><h3>${esc(route.zone_name)}</h3><span class="zone-key">${esc(route.zone_key)}</span></div><p>PIN prefix <strong>${esc(route.pin_prefix)}</strong> · ${esc(route.authority)}</p><div class="route-meta"><div><small>Primary load</small><strong>${primary ? `${primary.open_cases}/${primary.capacity}` : '—'}</strong></div><div><small>Backup load</small><strong>${backup ? `${backup.open_cases}/${backup.capacity}` : '—'}</strong></div><div><small>Branch</small><strong>${esc(route.branch)}</strong></div><div><small>Dispatch</small><strong>Primary → Deputy</strong></div></div></div>`; }).join(''); $('#routing-note').innerHTML = `<strong>Fallback policy:</strong> ${esc(data.fallback)} receives valid reports with unknown PIN zones. ${pending.reports.length} report(s) are currently pending; handlers must be available and below the maximum 10 open cases. Critical reports and Emergency urgency can use the cross-zone priority override; every decision is persisted with priority and timestamp.`; } catch (error) { toast(error.message, true); } }

function renderBars(selector, values) { const max = Math.max(...values.map((item) => item.value), 1); $(selector).innerHTML = values.length ? values.map((item) => `<div class="bar-item"><span class="bar-value">${item.value}</span><div class="bar-fill" style="height:${Math.max(4, item.value / max * 150)}px"></div><span class="bar-label">${esc(item.label)}</span></div>`).join('') : '<p class="muted">No data yet.</p>'; }
async function loadAnalytics() { try { const [data, stats] = await Promise.all([api('/api/analytics'), api('/api/dashboard/stats')]); $('#analytics-kpis').innerHTML = [['Resolved', stats.resolved], ['Unresolved', stats.total - stats.resolved - stats.rejected], ['Queued', stats.queued], ['Rejected', stats.rejected]].map(([label, value]) => `<div class="stat-card"><span class="label">${label}</span><strong>${Math.max(0, value)}</strong></div>`).join(''); renderBars('#category-chart', data.by_category); renderBars('#zone-chart', data.by_zone); const container = $('#assignment-chart'); const max = Math.max(...data.by_assignment.map((item) => item.value), 1); container.innerHTML = data.by_assignment.length ? data.by_assignment.map((item) => `<div class="bar-item"><span class="bar-label">${esc(item.label)}</span><div class="bar-fill" style="width:${item.value / max * 100}%"></div><span class="bar-value">${item.value}</span></div>`).join('') : '<p class="muted">No dispatches yet.</p>'; } catch (error) { toast(error.message, true); } }

showView('submit');

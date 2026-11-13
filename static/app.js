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

function refreshActiveDashboard() {
  if (document.visibilityState !== 'visible') return;
  const activeView = $('.view.active')?.id;
  if (activeView === 'view-dashboard') loadDashboard();
  else if (activeView === 'view-handler') loadHandlers();
  else if (activeView === 'view-routing') loadRouting();
  else if (activeView === 'view-analytics') loadAnalytics();
}
window.setInterval(refreshActiveDashboard, 60_000);

let activeReport = null;
const reportDialog = $('#report-dialog');
$('#close-report-dialog').addEventListener('click', () => reportDialog.close());
async function openReport(reportId) {
  try {
    activeReport = await api(`/api/reports/${encodeURIComponent(reportId)}`);
    const report = activeReport;
    const fields = [
      ['Report ID', report.id], ['Submitted', new Date(report.created_at).toLocaleString()],
      ['Reporter', report.reporter_name], ['Reporter email', report.reporter_email],
      ['Inspector ID', report.inspector_id], ['Violation code', report.violation_code],
      ['PIN code', report.pin_code], ['Zone', report.zone_key || 'Central correction queue'],
      ['Category', report.category], ['Priority', `P${report.priority} · ${report.urgency}`],
      ['Status', report.status], ['Validation', report.validation_status],
      ['Assigned handler', report.handler_name || 'Unassigned'], ['Branch', report.branch || '—'],
      ['Team / depot', [report.team, report.depot].filter(Boolean).join(' / ') || '—'],
      ['Authority', report.authority || '—'], ['Routing decision', report.decision || 'Not dispatched'],
      ['Classification reason', report.classification_reason], ['Validation message', report.validation_message],
      ['Description', report.description],
    ];
    $('#report-detail-content').innerHTML = `<div class="detail-grid">${fields.map(([label, value]) => `<div class="detail-field"><small>${esc(label)}</small><div>${esc(value)}</div></div>`).join('')}</div><h3>Status history</h3><ol class="history-list">${report.status_history.map((entry) => `<li><strong>${esc(entry.to_status)}</strong><span>${esc(entry.note || '')}</span><time>${new Date(entry.changed_at).toLocaleString()}</time></li>`).join('')}</ol>`;
    reportDialog.showModal();
  } catch (error) { toast(error.message, true); }
}
function downloadReport(format) {
  if (!activeReport) return;
  const content = format === 'json' ? JSON.stringify(activeReport, null, 2) : [
    Object.keys(activeReport).join(','),
    Object.values(activeReport).map((value) => `"${String(typeof value === 'object' ? JSON.stringify(value) : value ?? '').replaceAll('"', '""')}"`).join(','),
  ].join('\r\n');
  const blob = new Blob([content], { type: format === 'json' ? 'application/json' : 'text/csv;charset=utf-8' });
  const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `${activeReport.id}.${format}`; link.click(); URL.revokeObjectURL(link.href);
}
$('#report-json').addEventListener('click', () => downloadReport('json'));
$('#report-csv').addEventListener('click', () => downloadReport('csv'));
$('#report-pdf').addEventListener('click', () => {
  if (!activeReport) return;
  const report = activeReport;
  const values = [['Report ID', report.id], ['Submitted', new Date(report.created_at).toLocaleString()], ['Reporter', report.reporter_name], ['Inspector ID', report.inspector_id], ['Violation code', report.violation_code], ['PIN / zone', `${report.pin_code} / ${report.zone_key || 'Fallback'}`], ['Category / priority', `${report.category} / P${report.priority}`], ['Status', report.status], ['Handler', report.handler_name || 'Unassigned'], ['Description', report.description], ['Validation', report.validation_message], ['Classification', report.classification_reason], ['Routing decision', report.decision || 'Not dispatched']];
  const printWindow = window.open('', '_blank', 'width=900,height=700');
  if (!printWindow) { toast('Allow pop-ups to print or save the report as PDF.', true); return; }
  printWindow.document.write(`<!doctype html><html><head><title>${esc(report.id)}</title><style>body{font:14px Arial,sans-serif;color:#183127;margin:36px}h1{color:#1d6b50}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid #dce5df;vertical-align:top}th{width:190px;color:#52655a}footer{margin-top:28px;color:#68776f;font-size:11px}</style></head><body><h1>Food Safety Inspection Report</h1><table>${values.map(([label,value])=>`<tr><th>${esc(label)}</th><td>${esc(value)}</td></tr>`).join('')}</table><footer>Generated by FieldSafe Food Safety Inspection Portal</footer><script>window.onload=()=>window.print()<\/script></body></html>`);
  printWindow.document.close();
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
    $('#reports-table').innerHTML = reports.reports.length ? reports.reports.map((report) => `<tr><td><button class="report-link report-open" data-report="${esc(report.id)}" type="button">${esc(report.id)}</button><span class="subtext">${esc(report.inspector_id)} · ${esc(report.reporter_name)}</span></td><td>${badge(report.category)}<span class="subtext">${esc(report.violation_code)}</span></td><td>${esc(report.zone_key || 'Fallback')}<span class="subtext">${esc(report.handler_name || 'Correction queue')}</span></td><td>${badge(report.status)}</td><td>${new Date(report.created_at).toLocaleString()}</td></tr>`).join('') : '<tr><td colspan="5" class="muted">No reports match this search.</td></tr>';
    $$('.report-open').forEach((button) => button.addEventListener('click', () => openReport(button.dataset.report)));
  } catch (error) { toast(error.message, true); }
}
let searchTimer; $('#report-search').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadDashboard, 250); }); $('#status-filter').addEventListener('change', loadDashboard);

async function loadHandlers() { try { const data = await api('/api/handlers'); $('#handlers-table').innerHTML = data.handlers.map((handler) => `<tr><td><strong>${esc(handler.name)}</strong><span class="subtext">Handler #${handler.id}</span></td><td>${esc(handler.zone_key)}</td><td>${esc(handler.role)}</td><td><strong>${handler.open_cases}</strong> / ${handler.capacity}</td><td><div class="handler-controls"><button class="toggle ${handler.available ? 'on' : ''}" aria-label="Set ${esc(handler.name)} ${handler.available ? 'away' : 'available'}" aria-pressed="${Boolean(handler.available)}" title="Toggle availability" data-handler="${handler.id}" data-available="${handler.available ? 0 : 1}"></button><span>${handler.available ? 'Available' : 'Away'}</span></div></td><td><div class="handler-controls"><input type="number" min="1" max="10" value="${handler.capacity}" data-capacity="${handler.id}" aria-label="Capacity for ${esc(handler.name)}"><button class="secondary-button save-capacity" data-handler="${handler.id}">Save</button></div></td><td></td></tr>`).join(''); $$('.toggle').forEach((button) => button.addEventListener('click', async () => { try { await api(`/api/handlers/${button.dataset.handler}`, { method:'PATCH', body:JSON.stringify({ available:Number(button.dataset.available) }) }); toast('Availability updated'); await loadHandlers(); } catch (error) { toast(error.message, true); } })); $$('.save-capacity').forEach((button) => button.addEventListener('click', async () => { const input = $(`[data-capacity="${button.dataset.handler}"]`); try { await api(`/api/handlers/${button.dataset.handler}`, { method:'PATCH', body:JSON.stringify({ capacity:Number(input.value) }) }); toast('Capacity updated'); await loadHandlers(); } catch (error) { toast(error.message, true); } })); const assigned = await api('/api/reports?status=Assigned'); $('#handler-reports-table').innerHTML = assigned.reports.length ? assigned.reports.map((report) => `<tr><td><span class="report-link">${esc(report.id)}</span><span class="subtext">${esc(report.inspector_id)}</span></td><td>${badge(report.category)}</td><td>P${report.priority}</td><td>${esc(report.handler_name || '—')}</td><td>${new Date(report.created_at).toLocaleString()}</td><td><select class="status-action" data-report="${esc(report.id)}" aria-label="Update status for ${esc(report.id)}"><option>Assigned</option><option>In Progress</option><option>Resolved</option></select></td></tr>`).join('') : '<tr><td colspan="6" class="muted">No assigned reports.</td></tr>'; $$('.status-action').forEach((select) => select.addEventListener('change', async () => { try { await api(`/api/reports/${select.dataset.report}/status`, { method:'PATCH', body:JSON.stringify({ status: select.value }) }); toast('Report status updated'); await loadHandlers(); } catch (error) { toast(error.message, true); } })); } catch (error) { toast(error.message, true); } }
$('#handler-refresh').addEventListener('click', async () => { await loadHandlers(); toast('Roster refreshed'); });

async function loadRouting() { try { const [data, roster, pending] = await Promise.all([api('/api/routing'), api('/api/handlers'), api('/api/reports?status=Pending')]); const byZone = Object.groupBy ? Object.groupBy(roster.handlers, (h) => h.zone_key) : roster.handlers.reduce((acc, h) => ((acc[h.zone_key] ||= []).push(h), acc), {}); $('#routing-grid').innerHTML = data.routing_table.map((route) => { const handlers = byZone[route.zone_key] || []; const primary = handlers.find((h) => h.role === 'District Officer'); const backup = handlers.find((h) => h.role === 'Deputy Officer'); return `<div class="card route-card"><div class="route-top"><h3>${esc(route.zone_name)}</h3><span class="zone-key">${esc(route.zone_key)}</span></div><p>PIN prefix <strong>${esc(route.pin_prefix)}</strong> · ${esc(route.authority)}</p><div class="route-meta"><div><small>Primary load</small><strong>${primary ? `${primary.open_cases}/${primary.capacity}` : '—'}</strong></div><div><small>Backup load</small><strong>${backup ? `${backup.open_cases}/${backup.capacity}` : '—'}</strong></div><div><small>Branch</small><strong>${esc(route.branch)}</strong></div><div><small>Dispatch</small><strong>Primary → Deputy</strong></div></div></div>`; }).join(''); $('#routing-note').innerHTML = `<strong>Fallback policy:</strong> ${esc(data.fallback)} receives valid reports with unknown PIN zones. ${pending.reports.length} report(s) are currently pending; handlers must be available and below the maximum 10 open cases. Critical reports and Emergency urgency can use the cross-zone priority override; every decision is persisted with priority and timestamp.`; } catch (error) { toast(error.message, true); } }

function renderBars(selector, values) { const max = Math.max(...values.map((item) => item.value), 1); $(selector).innerHTML = values.length ? values.map((item) => `<div class="bar-item"><span class="bar-value">${item.value}</span><div class="bar-fill" style="height:${Math.max(4, item.value / max * 150)}px"></div><span class="bar-label">${esc(item.label)}</span></div>`).join('') : '<p class="muted">No data yet.</p>'; }
async function loadAnalytics() { try { const [data, stats] = await Promise.all([api('/api/analytics'), api('/api/dashboard/stats')]); $('#analytics-kpis').innerHTML = [['Resolved', stats.resolved], ['Unresolved', stats.total - stats.resolved - stats.rejected], ['Queued', stats.queued], ['Rejected', stats.rejected]].map(([label, value]) => `<div class="stat-card"><span class="label">${label}</span><strong>${Math.max(0, value)}</strong></div>`).join(''); renderBars('#category-chart', data.by_category); renderBars('#zone-chart', data.by_zone); const container = $('#assignment-chart'); const max = Math.max(...data.by_assignment.map((item) => item.value), 1); container.innerHTML = data.by_assignment.length ? data.by_assignment.map((item) => `<div class="bar-item"><span class="bar-label">${esc(item.label)}</span><div class="bar-fill" style="width:${item.value / max * 100}%"></div><span class="bar-value">${item.value}</span></div>`).join('') : '<p class="muted">No dispatches yet.</p>'; } catch (error) { toast(error.message, true); } }

showView('submit');

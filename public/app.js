/**
 * Local Lead Scout - Frontend Dashboard Application
 */

// Application State
const state = {
  currentTab: 'prospects', // 'prospects' | 'all'
  allLeads: [],
  prospectLeads: [],
  selectedLeadIds: new Set(),
  sortColumn: 'reviewCount',
  sortDirection: 'desc', // 'asc' | 'desc'
  isScraping: false,
  isVerifyingWa: false,
  activeEventSource: null,
  currentJobId: null,
  systemStatus: null,
  persistedLeads: [],
  pipelineAnalytics: null,
  campaignSettings: null,
  gmailStatus: null,
  pipelineBusy: false,
  currentBatchId: null
};

// DOM Elements
const elements = {
  systemStatus: document.getElementById('systemStatus'),
  scrapeForm: document.getElementById('scrapeForm'),
  nichesInput: document.getElementById('nichesInput'),
  cityInput: document.getElementById('cityInput'),
  maxResultsInput: document.getElementById('maxResultsInput'),
  startBtn: document.getElementById('startBtn'),
  
  scrapeStatusBox: document.getElementById('scrapeStatusBox'),
  statusTitle: document.getElementById('statusTitle'),
  statusSubtitle: document.getElementById('statusSubtitle'),
  engineSourceTag: document.getElementById('engineSourceTag'),
  statusSpinner: document.getElementById('statusSpinner'),
  logTerminal: document.getElementById('logTerminal'),
  toggleLogsBtn: document.getElementById('toggleLogsBtn'),

  sourceBanner: document.getElementById('sourceBanner'),
  sourceBannerTitle: document.getElementById('sourceBannerTitle'),
  sourceBannerDetail: document.getElementById('sourceBannerDetail'),
  sourceBannerIcon: document.getElementById('sourceBannerIcon'),

  resultsSection: document.getElementById('resultsSection'),
  tabFiltered: document.getElementById('tabFiltered'),
  tabAll: document.getElementById('tabAll'),
  countProspects: document.getElementById('countProspects'),
  countAll: document.getElementById('countAll'),
  
  verifyWhatsAppBtn: document.getElementById('verifyWhatsAppBtn'),
  verifyWhatsAppText: document.getElementById('verifyWhatsAppText'),
  selectedCountBadge: document.getElementById('selectedCountBadge'),
  downloadCsvBtn: document.getElementById('downloadCsvBtn'),
  
  selectAllCheckbox: document.getElementById('selectAllCheckbox'),
  selectionSummary: document.getElementById('selectionSummary'),
  tableFilterInput: document.getElementById('tableFilterInput'),
  leadsTable: document.getElementById('leadsTable'),
  leadsTableBody: document.getElementById('leadsTableBody'),
  tableFooterStats: document.getElementById('tableFooterStats'),

  whatsappModal: document.getElementById('whatsappModal'),
  modalCheckCount: document.getElementById('modalCheckCount'),
  modalCostEstimate: document.getElementById('modalCostEstimate'),
  largeBatchAlert: document.getElementById('largeBatchAlert'),
  batchCountSpan: document.getElementById('batchCountSpan'),
  closeModalBtn: document.getElementById('closeModalBtn'),
  cancelModalBtn: document.getElementById('cancelModalBtn'),
  confirmVerifyBtn: document.getElementById('confirmVerifyBtn'),

  toastContainer: document.getElementById('toastContainer'),

  pipelineStatus: document.getElementById('pipelineStatus'),
  refreshPipelineBtn: document.getElementById('refreshPipelineBtn'),
  enrichLeadsBtn: document.getElementById('enrichLeadsBtn'),
  generateEmailsBtn: document.getElementById('generateEmailsBtn'),
  saveCampaignBtn: document.getElementById('saveCampaignBtn'),
  campaignOfferInput: document.getElementById('campaignOfferInput'),
  campaignCtaInput: document.getElementById('campaignCtaInput'),
  sendingMethodSelect: document.getElementById('sendingMethodSelect'),
  campaignNameInput: document.getElementById('campaignNameInput'),
  workflowModeSelect: document.getElementById('workflowModeSelect'),
  automaticEnabledInput: document.getElementById('automaticEnabledInput'),
  groqModelSelect: document.getElementById('groqModelSelect'),
  promptTemplateInput: document.getElementById('promptTemplateInput'),
  dailyCapInput: document.getElementById('dailyCapInput'),
  hourlyCapInput: document.getElementById('hourlyCapInput'),
  lookbackInput: document.getElementById('lookbackInput'),
  bounceThresholdInput: document.getElementById('bounceThresholdInput'),
  complaintThresholdInput: document.getElementById('complaintThresholdInput'),
  circuitWindowInput: document.getElementById('circuitWindowInput'),
  gmailCapacity: document.getElementById('gmailCapacity'),
  gmailSetupPanel: document.getElementById('gmailSetupPanel'),
  gmailRedirectUri: document.getElementById('gmailRedirectUri'),
  gmailConnectionLabel: document.getElementById('gmailConnectionLabel'),
  gmailConnectionDetail: document.getElementById('gmailConnectionDetail'),
  connectGmailBtn: document.getElementById('connectGmailBtn'),
  disconnectGmailBtn: document.getElementById('disconnectGmailBtn'),
  pipelineTableBody: document.getElementById('pipelineTableBody'),
  pipelineFooterStats: document.getElementById('pipelineFooterStats'),
  metricTotal: document.getElementById('metricTotal'),
  metricQualified: document.getElementById('metricQualified'),
  metricSendable: document.getElementById('metricSendable'),
  metricSent: document.getElementById('metricSent'),
  metricOpened: document.getElementById('metricOpened'),
  metricReplyRate: document.getElementById('metricReplyRate'),
  draftModal: document.getElementById('draftModal'),
  draftBody: document.getElementById('draftBody'),
  draftModalSubtitle: document.getElementById('draftModalSubtitle'),
  closeDraftModalBtn: document.getElementById('closeDraftModalBtn'),
  closeDraftBtn: document.getElementById('closeDraftBtn'),
  approveBatchBtn: document.getElementById('approveBatchBtn'),
  currentUserEmail: document.getElementById('currentUserEmail'),
  logoutBtn: document.getElementById('logoutBtn')
};

// ==========================================
// Initialization & Environment Check
// ==========================================
async function initApp() {
  const identity = await fetch('/api/auth/me');
  if (identity.status === 401) return window.location.assign('/login');
  const identityData = await identity.json();
  elements.currentUserEmail.textContent = identityData.user?.email || '';
  setupEventListeners();
  await checkSystemStatus();
  await loadPipeline();
  handleOAuthReturn();
}

async function checkSystemStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    state.systemStatus = data;

    const dot = elements.systemStatus.querySelector('.status-dot');
    const text = elements.systemStatus.querySelector('.status-text');

    if (data.dockerRunning || data.gosomApiReachable || data.apifyConfigured) {
      dot.className = 'status-dot online';
      text.textContent = 'Discovery: Ready';
    } else {
      dot.className = 'status-dot offline';
      text.textContent = 'Discovery: Setup required';
    }
    if (data.leadEngine?.available === false) {
      elements.pipelineStatus.textContent = 'Python lead engine is offline. Start it to enable account data and outreach workflows.';
      elements.pipelineStatus.className = 'pipeline-status error';
    }
  } catch (err) {
    console.error('Failed to fetch status:', err);
  }
}

// ==========================================
// Event Listeners Setup
// ==========================================
function setupEventListeners() {
  // Form Submit
  elements.scrapeForm.addEventListener('submit', handleScrapeSubmit);

  // Tabs
  elements.tabFiltered.addEventListener('click', () => switchTab('prospects'));
  elements.tabAll.addEventListener('click', () => switchTab('all'));

  // Toggle Logs
  elements.toggleLogsBtn.addEventListener('click', toggleLogsVisibility);

  // Table Search Filter
  elements.tableFilterInput.addEventListener('input', () => renderTable());

  // Select All Checkbox
  elements.selectAllCheckbox.addEventListener('change', handleSelectAll);

  // Table Sorting
  elements.leadsTable.querySelectorAll('th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.sort;
      if (state.sortColumn === col) {
        state.sortDirection = state.sortDirection === 'asc' ? 'desc' : 'asc';
      } else {
        state.sortColumn = col;
        state.sortDirection = (col === 'rating' || col === 'reviewCount') ? 'desc' : 'asc';
      }
      renderTable();
    });
  });

  // WhatsApp Verification
  elements.verifyWhatsAppBtn.addEventListener('click', openWhatsAppModal);
  elements.closeModalBtn.addEventListener('click', closeWhatsAppModal);
  elements.cancelModalBtn.addEventListener('click', closeWhatsAppModal);
  elements.confirmVerifyBtn.addEventListener('click', executeWhatsAppVerification);

  // CSV Export
  elements.downloadCsvBtn.addEventListener('click', handleDownloadCsv);

  // Persistent lead pipeline
  elements.refreshPipelineBtn.addEventListener('click', loadPipeline);
  elements.enrichLeadsBtn.addEventListener('click', handleEnrichLeads);
  elements.generateEmailsBtn.addEventListener('click', handleGenerateEmails);
  elements.saveCampaignBtn.addEventListener('click', handleSaveCampaign);
  elements.connectGmailBtn.addEventListener('click', handleConnectGmail);
  elements.disconnectGmailBtn.addEventListener('click', handleDisconnectGmail);
  elements.closeDraftModalBtn.addEventListener('click', closeDraftModal);
  elements.closeDraftBtn.addEventListener('click', closeDraftModal);
  elements.approveBatchBtn.addEventListener('click', handleApproveBatch);
  elements.logoutBtn.addEventListener('click', async () => { await fetch('/api/auth/logout', { method: 'POST' }); window.location.assign('/login'); });
  elements.draftModal.addEventListener('click', event => {
    if (event.target === elements.draftModal) closeDraftModal();
  });
}

// ==========================================
// Scraping Workflow
// ==========================================
async function handleScrapeSubmit(e) {
  e.preventDefault();
  if (state.isScraping) return;

  const niches = elements.nichesInput.value.trim();
  const city = elements.cityInput.value.trim();
  const maxResults = parseInt(elements.maxResultsInput.value, 10) || 50;

  if (!niches || !city) {
    showToast('Please enter both niche(s) and city.', 'error');
    return;
  }

  state.isScraping = true;
  state.currentJobId = `job-${Date.now()}`;
  updateScrapeUI(true);

  // Clear previous results & logs
  state.allLeads = [];
  state.prospectLeads = [];
  state.selectedLeadIds.clear();
  elements.logTerminal.innerHTML = '';
  appendLog(`[Initiated] Starting search for "${niches}" in "${city}"...`, 'system');

  // Connect SSE for live activity stream
  connectSSE(state.currentJobId);

  try {
    const res = await fetch('/api/scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        niches,
        city,
        maxResults,
        jobId: state.currentJobId
      })
    });

    const data = await res.json();

    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Scraping failed');
    }

    // Populate data
    state.allLeads = data.allLeads || [];
    state.prospectLeads = data.prospects || [];

    // Pre-select all prospect leads with phones by default
    state.prospectLeads.forEach(l => {
      if (l.phone) state.selectedLeadIds.add(l.id);
    });

    // Update counts
    elements.countProspects.textContent = state.prospectLeads.length;
    elements.countAll.textContent = state.allLeads.length;

    // Show source banner
    renderSourceBanner(data.source, data.isFallback, data.fallbackReason);

    // Show results section
    elements.resultsSection.classList.remove('hidden');
    switchTab('prospects');
    showToast(`Scrape completed! Extracted ${state.allLeads.length} leads (${state.prospectLeads.length} prospects).`, 'success');
    await loadPipeline();

  } catch (err) {
    console.error(err);
    appendLog(`❌ Error: ${err.message}`, 'error');
    showToast(`Scrape failed: ${err.message}`, 'error');
  } finally {
    state.isScraping = false;
    updateScrapeUI(false);
    if (state.activeEventSource) {
      state.activeEventSource.close();
      state.activeEventSource = null;
    }
  }
}

function connectSSE(jobId) {
  if (state.activeEventSource) {
    state.activeEventSource.close();
  }

  const evtSource = new EventSource(`/api/events/${jobId}`);
  state.activeEventSource = evtSource;

  evtSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      const safeMessage = String(data.message || '')
        .replace(/self-hosted\s*\(gosom\)|gosom/gi, 'discovery service')
        .replace(/docker/gi, 'local discovery runtime')
        .replace(/apify google maps scraper|apify actor/gi, 'cloud discovery service');
      appendLog(safeMessage, data.type);

      if (data.message && data.message.includes('Activating automatic fallback')) {
        elements.statusTitle.textContent = 'Continuing discovery…';
        elements.statusSubtitle.textContent = 'The discovery service is recovering this search automatically.';
      }
    } catch (e) {
      appendLog(event.data);
    }
  };

  evtSource.onerror = () => {
    // SSE disconnected or closed
  };
}

function updateScrapeUI(isRunning) {
  elements.startBtn.disabled = isRunning;
  elements.startBtn.querySelector('.btn-text').textContent = isRunning ? 'Scraping...' : 'Start Scrape';

  if (isRunning) {
    elements.scrapeStatusBox.classList.remove('hidden');
    elements.statusSpinner.classList.remove('hidden');
    elements.statusTitle.textContent = 'Discovering local businesses…';
    elements.statusSubtitle.textContent = 'Running queries and extracting contact details...';
    elements.engineSourceTag.textContent = 'Discovery active';
    elements.engineSourceTag.className = 'source-tag';
    elements.sourceBanner.classList.add('hidden');
  } else {
    elements.statusSpinner.classList.add('hidden');
    elements.statusTitle.textContent = 'Scrape Job Completed';
    elements.statusSubtitle.textContent = 'Review filtered prospects and verify WhatsApp status below.';
  }
}

function renderSourceBanner(source, isFallback, fallbackReason) {
  elements.sourceBanner.classList.remove('hidden');
  elements.sourceBanner.className = 'source-banner gosom';
  elements.sourceBannerIcon.textContent = '✓';
  elements.sourceBannerTitle.textContent = 'Discovery completed';
  elements.sourceBannerDetail.textContent = 'Results are ready for qualification, enrichment, and account-scoped storage.';
}

function appendLog(msg, type = 'info') {
  const line = document.createElement('div');
  line.className = `log-line log-${type}`;
  line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  elements.logTerminal.appendChild(line);
  elements.logTerminal.scrollTop = elements.logTerminal.scrollHeight;
}

function toggleLogsVisibility() {
  const isCollapsed = elements.logTerminal.style.display === 'none';
  elements.logTerminal.style.display = isCollapsed ? 'flex' : 'none';
  elements.toggleLogsBtn.textContent = isCollapsed ? 'Hide Logs' : 'Show Logs';
}

// ==========================================
// Table Rendering & Tab Switching
// ==========================================
function switchTab(tabName) {
  state.currentTab = tabName;
  elements.tabFiltered.classList.toggle('active', tabName === 'prospects');
  elements.tabAll.classList.toggle('active', tabName === 'all');
  renderTable();
}

function getVisibleLeads() {
  const baseList = state.currentTab === 'prospects' ? state.prospectLeads : state.allLeads;
  const filterQuery = (elements.tableFilterInput.value || '').trim().toLowerCase();

  let list = baseList.slice();

  if (filterQuery) {
    list = list.filter(lead => {
      return (
        (lead.name && lead.name.toLowerCase().includes(filterQuery)) ||
        (lead.phone && lead.phone.toLowerCase().includes(filterQuery)) ||
        (lead.niche && lead.niche.toLowerCase().includes(filterQuery)) ||
        (lead.email && lead.email.toLowerCase().includes(filterQuery)) ||
        (lead.address && lead.address.toLowerCase().includes(filterQuery))
      );
    });
  }

  // Sort
  list.sort((a, b) => {
    let valA = a[state.sortColumn];
    let valB = b[state.sortColumn];

    if (state.sortColumn === 'rating' || state.sortColumn === 'reviewCount' || state.sortColumn === 'rank') {
      valA = typeof valA === 'number' ? valA : parseFloat(valA) || 0;
      valB = typeof valB === 'number' ? valB : parseFloat(valB) || 0;
    } else {
      valA = (valA || '').toString().toLowerCase();
      valB = (valB || '').toString().toLowerCase();
    }

    if (valA < valB) return state.sortDirection === 'asc' ? -1 : 1;
    if (valA > valB) return state.sortDirection === 'asc' ? 1 : -1;
    return 0;
  });

  return list;
}

function renderTable() {
  const visibleLeads = getVisibleLeads();
  elements.leadsTableBody.innerHTML = '';

  if (visibleLeads.length === 0) {
    const emptyRow = document.createElement('tr');
    emptyRow.innerHTML = `
      <td colspan="11" class="text-center" style="padding: 32px; color: var(--text-muted);">
        No leads match the current filters.
      </td>
    `;
    elements.leadsTableBody.appendChild(emptyRow);
    elements.tableFooterStats.textContent = 'Showing 0 leads';
    updateSelectionUI();
    return;
  }

  visibleLeads.forEach((lead, index) => {
    const tr = document.createElement('tr');
    const isSelected = state.selectedLeadIds.has(lead.id);
    if (isSelected) tr.classList.add('row-selected');

    // Rank Badge
    let rankBadgeClass = 'rank-badge';
    if (lead.rank <= 3) rankBadgeClass += ' top-rank';
    else rankBadgeClass += ' prospect-rank';

    // WhatsApp Badge
    let waHtml = '<span class="wa-badge unverified">-</span>';
    if (lead.whatsappVerified === true) {
      waHtml = '<span class="wa-badge verified" title="Verified on WhatsApp">✓ Yes</span>';
    } else if (lead.whatsappVerified === false) {
      waHtml = '<span class="wa-badge unverified" title="Not active on WhatsApp">✗ No</span>';
    }

    // Website Link
    let websiteHtml = '<span style="color: var(--text-muted);">-</span>';
    if (lead.website) {
      const safeUrl = safeExternalUrl(lead.website);
      if (safeUrl) websiteHtml = `<a href="${escapeHtml(safeUrl)}" target="_blank" rel="noopener noreferrer" class="link-btn">Visit ↗</a>`;
    }

    // Email Link
    let emailHtml = '<span style="color: var(--text-muted);">-</span>';
    if (lead.email) {
      emailHtml = `<a href="mailto:${encodeURIComponent(lead.email)}" class="link-btn">${escapeHtml(lead.email)}</a>`;
    }

    tr.innerHTML = `
      <td class="text-center" style="color: var(--text-muted); font-size: 0.78rem;">${index + 1}</td>
      <td class="text-center">
        <label class="checkbox-container">
          <input type="checkbox" class="row-checkbox" data-id="${escapeHtml(lead.id)}" ${isSelected ? 'checked' : ''}>
          <span class="checkmark"></span>
        </label>
      </td>
      <td><span class="${rankBadgeClass}">#${lead.rank || (index + 1)}</span></td>
      <td><strong class="biz-name">${escapeHtml(lead.name)}</strong></td>
      <td><span class="niche-tag">${escapeHtml(lead.niche || 'General')}</span></td>
      <td>
        <div class="rating-box">
          <span class="star-icon">★</span>
          <span>${lead.rating ? lead.rating.toFixed(1) : '0.0'}</span>
          <span class="reviews-cnt">(${lead.reviewCount || 0})</span>
        </div>
      </td>
      <td>${lead.phone ? `<code>${escapeHtml(lead.phone)}</code>` : '<span style="color: var(--text-muted);">-</span>'}</td>
      <td class="text-center">${waHtml}</td>
      <td>${emailHtml}</td>
      <td>${websiteHtml}</td>
      <td style="max-width: 220px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(lead.address)}">
        ${escapeHtml(lead.address || '-')}
      </td>
    `;

    // Row Checkbox Event
    const checkbox = tr.querySelector('.row-checkbox');
    checkbox.addEventListener('change', (e) => {
      if (e.target.checked) {
        state.selectedLeadIds.add(lead.id);
        tr.classList.add('row-selected');
      } else {
        state.selectedLeadIds.delete(lead.id);
        tr.classList.remove('row-selected');
      }
      updateSelectionUI();
    });

    elements.leadsTableBody.appendChild(tr);
  });

  const totalCurrent = state.currentTab === 'prospects' ? state.prospectLeads.length : state.allLeads.length;
  elements.tableFooterStats.textContent = `Showing ${visibleLeads.length} of ${totalCurrent} ${state.currentTab === 'prospects' ? 'filtered prospects' : 'results'}`;
  updateSelectionUI();
}

function handleSelectAll(e) {
  const visibleLeads = getVisibleLeads();
  if (e.target.checked) {
    visibleLeads.forEach(l => {
      if (l.phone) state.selectedLeadIds.add(l.id);
    });
  } else {
    visibleLeads.forEach(l => state.selectedLeadIds.delete(l.id));
  }
  renderTable();
}

function updateSelectionUI() {
  const count = state.selectedLeadIds.size;
  elements.selectedCountBadge.textContent = count;
  elements.verifyWhatsAppBtn.disabled = count === 0 || state.isVerifyingWa;
  elements.selectionSummary.textContent = `${count} business${count === 1 ? '' : 'es'} selected`;

  const visibleLeads = getVisibleLeads();
  const selectableLeads = visibleLeads.filter(l => l.phone);
  const visibleSelectedCount = selectableLeads.filter(l => state.selectedLeadIds.has(l.id)).length;
  elements.selectAllCheckbox.checked = selectableLeads.length > 0 && visibleSelectedCount === selectableLeads.length;
  elements.selectAllCheckbox.indeterminate = visibleSelectedCount > 0 && visibleSelectedCount < selectableLeads.length;
}

// ==========================================
// WhatsApp Verification Flow
// ==========================================
async function openWhatsAppModal() {
  const selectedLeads = getSelectedLeads();
  const leadsWithPhone = selectedLeads.filter(l => Boolean(l.phone));

  if (leadsWithPhone.length === 0) {
    showToast('None of the selected businesses have a phone number.', 'error');
    return;
  }

  try {
    // Fetch cost estimation
    const res = await fetch('/api/whatsapp/estimate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count: leadsWithPhone.length })
    });
    const estimate = await res.json();

    elements.modalCheckCount.textContent = `${leadsWithPhone.length} valid phone numbers`;
    elements.modalCostEstimate.textContent = `~$${estimate.estimatedCostUsd} USD`;

    if (estimate.requiresWarning) {
      elements.largeBatchAlert.classList.remove('hidden');
      elements.batchCountSpan.textContent = leadsWithPhone.length;
    } else {
      elements.largeBatchAlert.classList.add('hidden');
    }

    elements.whatsappModal.classList.remove('hidden');
  } catch (err) {
    showToast(`Error calculating estimate: ${err.message}`, 'error');
  }
}

function closeWhatsAppModal() {
  elements.whatsappModal.classList.add('hidden');
}

function getSelectedLeads() {
  const allMap = new Map();
  state.allLeads.forEach(l => allMap.set(l.id, l));
  state.prospectLeads.forEach(l => allMap.set(l.id, l));

  return Array.from(state.selectedLeadIds).map(id => allMap.get(id)).filter(Boolean);
}

async function executeWhatsAppVerification() {
  closeWhatsAppModal();
  if (state.isVerifyingWa) return;

  const selectedLeads = getSelectedLeads();
  const leadsWithPhone = selectedLeads.filter(l => Boolean(l.phone));

  state.isVerifyingWa = true;
  elements.verifyWhatsAppBtn.disabled = true;
  elements.verifyWhatsAppText.textContent = `Verifying ${leadsWithPhone.length} on WhatsApp…`;

  showToast(`Verifying ${leadsWithPhone.length} numbers via Apify WhatsApp Checker...`, 'info');

  const waJobId = `wa-${Date.now()}`;
  connectSSE(waJobId);

  try {
    const res = await fetch('/api/whatsapp/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        leads: selectedLeads,
        locationContext: elements.cityInput.value,
        jobId: waJobId
      })
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Verification failed');
    }

    // Merge updated verification back into lists
    const updatedMap = new Map(data.updatedLeads.map(l => [l.id, l.whatsappVerified]));
    
    state.allLeads.forEach(l => {
      if (updatedMap.has(l.id)) l.whatsappVerified = updatedMap.get(l.id);
    });
    state.prospectLeads.forEach(l => {
      if (updatedMap.has(l.id)) l.whatsappVerified = updatedMap.get(l.id);
    });

    renderTable();
    showToast(`WhatsApp check finished! ${data.verifiedCount} of ${data.checkedCount} numbers active on WhatsApp.`, 'success');

  } catch (err) {
    console.error(err);
    showToast(`Verification error: ${err.message}`, 'error');
  } finally {
    state.isVerifyingWa = false;
    elements.verifyWhatsAppText.textContent = 'Verify Selected on WhatsApp';
    elements.selectedCountBadge.textContent = state.selectedLeadIds.size;
    elements.verifyWhatsAppBtn.disabled = state.selectedLeadIds.size === 0;
    if (state.activeEventSource) {
      state.activeEventSource.close();
      state.activeEventSource = null;
    }
    await loadPipeline();
  }
}

// ==========================================
// Persistent Lead Pipeline
// ==========================================
async function loadPipeline() {
  if (state.pipelineBusy) return;
  state.pipelineBusy = true;
  setPipelineBusy(true, 'Loading persisted leads…');
  try {
    const [leadsResponse, analyticsResponse, settingsResponse] = await Promise.all([
      fetch('/api/pipeline/leads?limit=500&qualified_only=false'),
      fetch('/api/pipeline/analytics'),
      fetch('/api/pipeline/settings')
    ]);
    const leadsData = await leadsResponse.json();
    const analyticsData = await analyticsResponse.json();
    const settingsData = await settingsResponse.json();
    if (!leadsResponse.ok || !leadsData.success) throw new Error(leadsData.error || 'Lead engine unavailable');
    if (!analyticsResponse.ok || !analyticsData.success) throw new Error(analyticsData.error || 'Analytics unavailable');
    if (!settingsResponse.ok || !settingsData.success) throw new Error(settingsData.error || 'Campaign settings unavailable');
    state.persistedLeads = leadsData.leads || [];
    state.pipelineAnalytics = analyticsData;
    state.campaignSettings = settingsData.campaign || null;
    state.gmailStatus = settingsData.gmail || null;
    renderPipeline();
    renderOutreachSettings();
    elements.pipelineStatus.textContent = `${state.persistedLeads.length} leads loaded from SQLite. Duplicate outreach protection is active.`;
    elements.pipelineStatus.className = 'pipeline-status success';
  } catch (error) {
    elements.pipelineStatus.textContent = error.message;
    elements.pipelineStatus.className = 'pipeline-status error';
    renderPipelineEmpty('Start the Python lead engine to load persisted lead state.');
  } finally {
    state.pipelineBusy = false;
    setPipelineBusy(false);
  }
}

function setPipelineBusy(busy, message = '') {
  elements.refreshPipelineBtn.disabled = busy;
  elements.enrichLeadsBtn.disabled = busy;
  elements.generateEmailsBtn.disabled = busy;
  elements.saveCampaignBtn.disabled = busy;
  const gmail = state.gmailStatus || {};
  const gmailLimit = gmail.maxConnectedUsers || 100;
  elements.connectGmailBtn.disabled = busy || !gmail.configured || (!gmail.connected && (gmail.connectedCount || 0) >= gmailLimit);
  elements.disconnectGmailBtn.disabled = busy || !gmail.connected;
  if (message) elements.pipelineStatus.textContent = message;
}

function renderPipeline() {
  const stats = state.pipelineAnalytics || {};
  elements.metricTotal.textContent = stats.total || 0;
  elements.metricQualified.textContent = stats.qualified || 0;
  elements.metricSendable.textContent = stats.sendable || 0;
  elements.metricSent.textContent = stats.sent || 0;
  elements.metricOpened.textContent = stats.opened || 0;
  elements.metricReplyRate.textContent = `${stats.replyRate || 0}%`;
  elements.pipelineFooterStats.textContent = `${stats.total || 0} persisted · ${stats.qualified || 0} qualified · ${stats.replied || 0} replied`;

  if (state.persistedLeads.length === 0) {
    renderPipelineEmpty('No persisted leads yet. Run a scrape or import existing CSV files.');
    return;
  }
  elements.pipelineTableBody.innerHTML = '';
  state.persistedLeads.forEach(lead => {
    const row = document.createElement('tr');
    const emailStatus = lead.email
      ? `${escapeHtml(lead.email)}<br><span class="micro-status ${lead.email_valid && lead.mx_valid ? 'ok' : 'pending'}">${lead.email_valid && lead.mx_valid ? 'Format + MX valid' : 'Needs validation'}</span>`
      : '<span class="micro-status pending">Not found</span>';
    const consentConfirmed = lead.consent_status === 'confirmed';
    row.innerHTML = `
      <td><strong class="biz-name">${escapeHtml(lead.name)}</strong><br><span class="micro-status">${escapeHtml(lead.niche || '')}</span></td>
      <td>${escapeHtml(lead.city || '-')}</td>
      <td class="issue-cell">${escapeHtml(lead.issue_detected || 'No weakness detected')}</td>
      <td>${emailStatus}</td>
      <td>
        <button type="button" class="status-action consent-action ${consentConfirmed ? 'confirmed' : ''}" data-lead-id="${lead.id}" data-confirmed="${consentConfirmed}">
          ${consentConfirmed ? 'Confirmed' : 'Consent required'}
        </button>
      </td>
      <td>${lead.contacted_at ? statusMark(lead.contacted_at, 'Sent') : `<button type="button" class="status-action contacted-action" data-lead-id="${lead.id}">Mark contacted</button>`}</td>
      <td>${statusMark(lead.opened_at, 'Opened')}</td>
      <td>${lead.replied_at ? statusMark(lead.replied_at, 'Replied') : `<button type="button" class="status-action reply-action" data-lead-id="${lead.id}">Mark replied</button>`}</td>
    `;
    const replyButton = row.querySelector('.reply-action');
    if (replyButton) replyButton.addEventListener('click', () => markPipelineReply(lead.id));
    const contactedButton = row.querySelector('.contacted-action');
    if (contactedButton) contactedButton.addEventListener('click', () => markPipelineContacted(lead.id));
    const consentButton = row.querySelector('.consent-action');
    consentButton.addEventListener('click', () => updatePipelineConsent(lead.id, !consentConfirmed));
    elements.pipelineTableBody.appendChild(row);
  });
}

function renderOutreachSettings() {
  const campaign = state.campaignSettings || {};
  const gmail = state.gmailStatus || {};
  elements.campaignOfferInput.value = campaign.offer || '';
  elements.campaignCtaInput.value = campaign.cta || '';
  elements.sendingMethodSelect.value = campaign.sending_method || 'sendgrid';
  elements.campaignNameInput.value = campaign.name || '';
  elements.workflowModeSelect.value = campaign.workflow_mode || 'manual';
  elements.automaticEnabledInput.checked = Boolean(campaign.automatic_enabled);
  elements.groqModelSelect.value = campaign.groq_model || 'openai/gpt-oss-120b';
  elements.promptTemplateInput.value = campaign.prompt_template || '';
  elements.dailyCapInput.value = campaign.daily_cap || 10;
  elements.hourlyCapInput.value = campaign.hourly_cap || 3;
  elements.lookbackInput.value = campaign.duplicate_lookback_days || 90;
  elements.bounceThresholdInput.value = campaign.bounce_threshold_pct ?? 5;
  elements.complaintThresholdInput.value = campaign.complaint_threshold_pct ?? 0.3;
  elements.circuitWindowInput.value = campaign.circuit_breaker_window || 100;
  const limit = gmail.maxConnectedUsers || 100;
  if (elements.gmailCapacity) elements.gmailCapacity.textContent = `${gmail.connectedCount || 0} / ${limit}`;
  const setupRequired = gmail.setupRequired ?? !gmail.configured;
  if (elements.gmailSetupPanel) elements.gmailSetupPanel.classList.toggle('hidden', !setupRequired);
  if (elements.gmailRedirectUri) elements.gmailRedirectUri.textContent = gmail.redirectUri || `${window.location.origin}/api/gmail/oauth/callback`;
  elements.gmailConnectionLabel.textContent = gmail.connected
    ? 'Gmail connected'
    : setupRequired
      ? 'Gmail connector awaiting setup'
      : 'Gmail ready to connect';
  if (gmail.connected) {
    const connectedAt = gmail.connectedAt ? new Date(gmail.connectedAt).toLocaleString() : 'recently';
    elements.gmailConnectionDetail.textContent = `Connected ${connectedAt} with gmail.send only. Access tokens refresh automatically.`;
  } else if (setupRequired) {
    elements.gmailConnectionDetail.textContent = 'Google OAuth credentials are required in .env before connecting.';
  } else {
    elements.gmailConnectionDetail.textContent = 'Authorize an approved Google test account with the minimum gmail.send permission.';
  }
  elements.connectGmailBtn.textContent = gmail.connected ? 'Reconnect Gmail' : 'Connect Gmail';
  elements.disconnectGmailBtn.classList.toggle('hidden', !gmail.connected);
  elements.connectGmailBtn.disabled = state.pipelineBusy || !gmail.configured || (!gmail.connected && (gmail.connectedCount || 0) >= limit);
}

async function handleSaveCampaign() {
  if (state.pipelineBusy) return;
  const offer = elements.campaignOfferInput.value.trim();
  const cta = elements.campaignCtaInput.value.trim();
  if (!offer || !cta) {
    showToast('Add both a campaign offer and call to action before saving.', 'error');
    return;
  }
  state.pipelineBusy = true;
  setPipelineBusy(true, 'Saving campaign settings…');
  try {
    const response = await fetch('/api/pipeline/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: elements.campaignNameInput.value.trim(),
        sending_method: elements.sendingMethodSelect.value,
        workflow_mode: elements.workflowModeSelect.value,
        automatic_enabled: elements.automaticEnabledInput.checked,
        offer,
        cta,
        prompt_template: elements.promptTemplateInput.value.trim(),
        groq_model: elements.groqModelSelect.value,
        daily_cap: Number(elements.dailyCapInput.value),
        hourly_cap: Number(elements.hourlyCapInput.value),
        duplicate_lookback_days: Number(elements.lookbackInput.value),
        bounce_threshold_pct: Number(elements.bounceThresholdInput.value),
        complaint_threshold_pct: Number(elements.complaintThresholdInput.value),
        circuit_breaker_window: Number(elements.circuitWindowInput.value)
      })
    });
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || data.detail || 'Campaign settings were not saved');
    showToast('Campaign settings saved for this user.', 'success');
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    state.pipelineBusy = false;
    setPipelineBusy(false);
    await loadPipeline();
  }
}

async function handleConnectGmail() {
  if (state.pipelineBusy) return;
  state.pipelineBusy = true;
  setPipelineBusy(true, 'Preparing Google authorization…');
  try {
    const response = await fetch('/api/pipeline/gmail/connect', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}'
    });
    const data = await response.json();
    if (!response.ok || !data.success || !data.authorizationUrl) throw new Error(data.error || data.detail || 'Unable to start Gmail authorization');
    window.location.assign(data.authorizationUrl);
  } catch (error) {
    state.pipelineBusy = false;
    setPipelineBusy(false);
    renderOutreachSettings();
    showToast(error.message, 'error');
  }
}

async function handleDisconnectGmail() {
  if (state.pipelineBusy || !window.confirm('Disconnect Gmail and switch this user back to SendGrid?')) return;
  state.pipelineBusy = true;
  setPipelineBusy(true, 'Disconnecting Gmail…');
  try {
    const response = await fetch('/api/pipeline/gmail/disconnect', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}'
    });
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || data.detail || 'Gmail could not be disconnected');
    showToast('Gmail disconnected. SendGrid is selected again.', 'success');
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    state.pipelineBusy = false;
    setPipelineBusy(false);
    await loadPipeline();
  }
}

function handleOAuthReturn() {
  const params = new URLSearchParams(window.location.search);
  const result = params.get('gmail');
  if (!result) return;
  if (result === 'connected') showToast('Gmail connected successfully with gmail.send access.', 'success');
  else showToast(`Gmail connection failed: ${params.get('message') || 'authorization was not completed'}`, 'error');
  window.history.replaceState({}, document.title, window.location.pathname);
}

function renderPipelineEmpty(message) {
  elements.pipelineTableBody.innerHTML = `<tr><td colspan="8" class="empty-cell">${escapeHtml(message)}</td></tr>`;
}

function statusMark(timestamp, label) {
  if (!timestamp) return '<span class="micro-status pending">No</span>';
  const date = new Date(timestamp);
  const title = Number.isNaN(date.getTime()) ? timestamp : date.toLocaleString();
  return `<span class="micro-status ok" title="${escapeHtml(title)}">${escapeHtml(label)}</span>`;
}

async function handleEnrichLeads() {
  if (state.pipelineBusy) return;
  state.pipelineBusy = true;
  setPipelineBusy(true, 'Scraping business websites and checking MX records…');
  try {
    const response = await fetch('/api/pipeline/enrich', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limit: 25 })
    });
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || 'Enrichment failed');
    showToast(`Enrichment checked ${data.processed} leads; ${data.valid} now have validated emails.`, 'success');
  } catch (error) {
    showToast(`Enrichment error: ${error.message}`, 'error');
  } finally {
    state.pipelineBusy = false;
    setPipelineBusy(false);
    await loadPipeline();
  }
}

async function handleGenerateEmails() {
  if (state.pipelineBusy) return;
  state.pipelineBusy = true;
  setPipelineBusy(true, 'Generating personalized emails with Groq…');
  try {
    const response = await fetch('/api/pipeline/outreach/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ limit: 25 }) });
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || (data.errors || []).join('; ') || 'Email generation failed');
    state.currentBatchId = data.batchId;
    renderDraftBatch(data);
    elements.draftModal.classList.remove('hidden');
  } catch (error) {
    showToast(`Generation error: ${error.message}`, 'error');
  } finally {
    state.pipelineBusy = false;
    setPipelineBusy(false);
    await loadPipeline();
  }
}

function renderDraftBatch(data) {
  const items = data.items || [];
  const automatic = data.workflowMode === 'automatic';
  elements.draftModalSubtitle.textContent = automatic ? 'This automatic campaign validated and queued the generated emails.' : 'These drafts are stored. Approve this batch when the copy is ready.';
  elements.approveBatchBtn.classList.toggle('hidden', automatic);
  const summary = `<div class="draft-summary"><strong>${data.generated || 0} Groq-generated emails</strong><span>${escapeHtml(data.workflowMode || 'manual')} workflow · ${data.failed || 0} failed</span></div>`;
  const cards = items.length ? items.map(item => `
    <article class="draft-email">
      <div class="draft-email-head"><strong>${escapeHtml(item.business)}</strong><span>${new Date(item.scheduledFor).toLocaleString()}</span></div>
      <div><span class="micro-status">To</span> ${escapeHtml(item.email)}</div>
      <div><span class="micro-status">Subject</span> ${escapeHtml(item.subject)}</div>
      <div><span class="micro-status">State</span> ${escapeHtml(item.status)}</div>
      <pre>${escapeHtml(item.body)}</pre>
    </article>
  `).join('') : '<p>No eligible leads were generated. Confirm consent and run email enrichment first.</p>';
  elements.draftBody.innerHTML = summary + cards;
}

async function handleApproveBatch() {
  if (!state.currentBatchId || state.pipelineBusy) return;
  state.pipelineBusy = true;
  elements.approveBatchBtn.disabled = true;
  try {
    const response = await fetch(`/api/pipeline/outreach/batches/${encodeURIComponent(state.currentBatchId)}/approve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || 'Batch approval failed');
    showToast(`${data.queued} emails queued; ${data.blocked} blocked by validation.`, 'success');
    closeDraftModal();
  } catch (error) { showToast(error.message, 'error'); }
  finally { state.pipelineBusy = false; elements.approveBatchBtn.disabled = false; await loadPipeline(); }
}

function closeDraftModal() {
  elements.draftModal.classList.add('hidden');
}

async function markPipelineReply(leadId) {
  try {
    const response = await fetch(`/api/pipeline/leads/${leadId}/reply`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || 'Unable to update reply');
    await loadPipeline();
  } catch (error) { showToast(error.message, 'error'); }
}

async function markPipelineContacted(leadId) {
  if (!window.confirm('Mark this business as previously contacted? This permanently excludes it from automatic outreach.')) return;
  try {
    const response = await fetch(`/api/pipeline/leads/${leadId}/contacted`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || 'Unable to mark contact history');
    await loadPipeline();
  } catch (error) { showToast(error.message, 'error'); }
}

async function updatePipelineConsent(leadId, confirmed) {
  if (confirmed && !window.confirm('Confirm that you have documented affirmative consent from this recipient to receive this campaign.')) return;
  try {
    const response = await fetch(`/api/pipeline/leads/${leadId}/consent`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirmed })
    });
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || 'Unable to update consent');
    await loadPipeline();
  } catch (error) { showToast(error.message, 'error'); }
}

// ==========================================
// CSV Export Flow (Requirement 6)
// ==========================================
async function handleDownloadCsv() {
  if (state.prospectLeads.length === 0) {
    showToast('No filtered prospects available to export. Run a scrape first!', 'error');
    return;
  }

  showToast('Generating sorted prospect CSV file...', 'info');

  try {
    const res = await fetch('/api/export/csv', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        leads: state.prospectLeads,
        onlyProspects: true,
        filename: `filtered_prospects_${Date.now()}.csv`
      })
    });

    if (!res.ok) throw new Error('Failed to generate CSV');

    const csvText = await res.text();
    const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' });
    const fileName = `prospect_leads_${new Date().toISOString().slice(0, 10)}.csv`;

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    
    setTimeout(() => {
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    }, 200);

    showToast(`Prospects CSV downloaded successfully (${fileName})`, 'success');
  } catch (err) {
    showToast(`Export error: ${err.message}`, 'error');
  }
}

// ==========================================
// Helpers & Toasts
// ==========================================
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✓' : type === 'error' ? '⚠️' : 'ℹ️'}</span>
    <span>${escapeHtml(message)}</span>
  `;
  elements.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function safeExternalUrl(value) {
  if (!value) return '';
  try {
    const candidate = /^https?:\/\//i.test(value) ? value : `https://${value}`;
    const parsed = new URL(candidate);
    return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : '';
  } catch (_) {
    return '';
  }
}

// Run on page load
document.addEventListener('DOMContentLoaded', initApp);

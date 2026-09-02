const ENGINE_URL = (process.env.LEAD_ENGINE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const ENGINE_TOKEN = process.env.LEAD_ENGINE_TOKEN || '';

async function engineRequest(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs || 15000);
  const headers = { ...(options.headers || {}) };
  if (ENGINE_TOKEN) headers['X-Lead-Engine-Token'] = ENGINE_TOKEN;
  if (options.sessionToken) headers['X-Lead-Session-Token'] = options.sessionToken;
  try {
    const response = await fetch(`${ENGINE_URL}${path}`, { method: options.method || 'GET', headers, body: options.body, signal: controller.signal });
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = typeof payload === 'string' ? payload : (payload.detail || payload.error || JSON.stringify(payload));
      const error = new Error(`Lead engine HTTP ${response.status}: ${detail}`);
      error.status = response.status;
      throw error;
    }
    return payload;
  } finally { clearTimeout(timeout); }
}

function jsonRequest(path, body, sessionToken = '', timeoutMs = 30000, method = 'POST') {
  return engineRequest(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}), sessionToken, timeoutMs });
}

module.exports = {
  engineRequest,
  getEngineHealth: () => engineRequest('/health', { timeoutMs: 3000 }),
  register: body => jsonRequest('/api/auth/register', body),
  login: body => jsonRequest('/api/auth/login', body),
  logout: token => jsonRequest('/api/auth/logout', {}, token),
  me: token => engineRequest('/api/auth/me', { sessionToken: token }),
  ingestLeads: (token, leads, source, query) => jsonRequest('/api/leads/ingest', { leads, source, query }, token),
  listPersistedLeads: (token, query = '') => engineRequest(`/api/leads${query}`, { sessionToken: token }),
  getAnalytics: token => engineRequest('/api/analytics', { sessionToken: token }),
  enrichPersistedLeads: (token, limit) => jsonRequest('/api/enrich', { limit }, token, 180000),
  generateEmails: (token, limit) => jsonRequest('/api/outreach/generate', { limit }, token, 180000),
  approveBatch: (token, batchId) => jsonRequest(`/api/outreach/batches/${encodeURIComponent(batchId)}/approve`, {}, token),
  getBatches: token => engineRequest('/api/outreach/batches', { sessionToken: token }),
  getSendLogs: token => engineRequest('/api/outreach/logs', { sessionToken: token }),
  getCampaignSettings: token => engineRequest('/api/settings/campaign', { sessionToken: token }),
  saveCampaignSettings: (token, body) => jsonRequest('/api/settings/campaign', body, token, 30000, 'PUT'),
  getGmailStatus: token => engineRequest('/api/gmail/status', { sessionToken: token }),
  startGmailConnect: token => jsonRequest('/api/gmail/connect', {}, token),
  completeGmailConnect: (token, code, state) => jsonRequest('/api/gmail/oauth/callback', { code, state }, token),
  disconnectGmail: token => jsonRequest('/api/gmail/disconnect', {}, token),
  markLeadReplied: (token, id) => jsonRequest(`/api/leads/${id}/reply`, {}, token),
  markLeadContacted: (token, id) => jsonRequest(`/api/leads/${id}/contacted`, {}, token),
  setLeadConsent: (token, id, confirmed) => jsonRequest(`/api/leads/${id}/consent`, { confirmed }, token),
  proxyUnsubscribe: (token, method = 'GET') => engineRequest(`/unsubscribe/${encodeURIComponent(token)}`, { method }),
  proxySendgridEvents: (events, token, headers = {}) => engineRequest(`/api/webhooks/sendgrid?token=${encodeURIComponent(token || '')}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: Buffer.isBuffer(events) ? events : JSON.stringify(events), timeoutMs: 15000
  })
};

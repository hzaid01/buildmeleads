const ENGINE_URL = (process.env.LEAD_ENGINE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const ENGINE_TOKEN = process.env.LEAD_ENGINE_TOKEN || '';

async function engineRequest(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs || 15000);
  const headers = { ...(options.headers || {}) };
  if (ENGINE_TOKEN) headers['X-Lead-Engine-Token'] = ENGINE_TOKEN;
  try {
    const response = await fetch(`${ENGINE_URL}${path}`, {
      method: options.method || 'GET',
      headers,
      body: options.body,
      signal: controller.signal
    });
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = typeof payload === 'string' ? payload : (payload.detail || payload.error || JSON.stringify(payload));
      throw new Error(`Lead engine HTTP ${response.status}: ${detail}`);
    }
    return payload;
  } finally {
    clearTimeout(timeout);
  }
}

function jsonRequest(path, body, timeoutMs = 30000) {
  return engineRequest(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
    timeoutMs
  });
}

module.exports = {
  engineRequest,
  jsonRequest,
  getEngineHealth: () => engineRequest('/health', { timeoutMs: 3000 }),
  ingestLeads: (leads, source, query) => jsonRequest('/api/leads/ingest', { leads, source, query }, 30000),
  listPersistedLeads: (query = '') => engineRequest(`/api/leads${query}`),
  getAnalytics: () => engineRequest('/api/analytics'),
  enrichPersistedLeads: (limit) => jsonRequest('/api/enrich', { limit }, 180000),
  planOutreach: () => jsonRequest('/api/outreach/plan', {}),
  markLeadReplied: (leadId) => jsonRequest(`/api/leads/${leadId}/reply`, {}),
  markLeadContacted: (leadId) => jsonRequest(`/api/leads/${leadId}/contacted`, {}),
  setLeadConsent: (leadId, confirmed) => jsonRequest(`/api/leads/${leadId}/consent`, { confirmed }),
  proxyUnsubscribe: (token, method = 'GET') => engineRequest(`/unsubscribe/${encodeURIComponent(token)}`, { method }),
  proxySendgridEvents: (events, token, headers = {}) => engineRequest(`/api/webhooks/sendgrid?token=${encodeURIComponent(token || '')}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: Buffer.isBuffer(events) ? events : JSON.stringify(events),
    timeoutMs: 15000
  })
};

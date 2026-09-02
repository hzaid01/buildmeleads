require('dotenv').config();
const express = require('express');
const fs = require('fs');
const path = require('path');
const { executeLeadScrape } = require('./services/scraperManager');
const { isDockerRunning, isGosomApiReachable } = require('./services/gosomScraper');
const { estimateWhatsAppCost, verifyLeadsWhatsApp } = require('./services/whatsappChecker');
const { generateProspectsCsv } = require('./services/csvExporter');
const {
  getEngineHealth,
  ingestLeads,
  listPersistedLeads,
  getAnalytics,
  enrichPersistedLeads,
  generateEmails,
  approveBatch,
  getBatches,
  getSendLogs,
  getCampaignSettings,
  saveCampaignSettings,
  getGmailStatus,
  startGmailConnect,
  completeGmailConnect,
  disconnectGmail,
  markLeadContacted,
  markLeadReplied,
  setLeadConsent,
  proxyUnsubscribe,
  proxySendgridEvents,
  register,
  login,
  logout,
  me
} = require('./services/leadEngineClient');

const app = express();
const PORT = process.env.PORT || 3000;
const HOST = process.env.HOST || '127.0.0.1';
const PID_FILE = path.join(__dirname, 'data', 'node.pid');
const SESSION_COOKIE = 'scaper_session';
const COOKIE_SECURE = String(process.env.SESSION_COOKIE_SECURE || 'true').toLowerCase() !== 'false';

// Event listeners for SSE logging per job
const jobEventEmitters = new Map();

app.use(express.json({
  limit: '10mb',
  verify: (req, res, buffer) => {
    if (req.originalUrl.startsWith('/api/webhooks/sendgrid')) req.rawBody = Buffer.from(buffer);
  }
}));
app.use(express.urlencoded({ extended: true, limit: '2mb' }));
app.use(express.static(path.join(__dirname, 'public'), { index: false }));

function cookies(req) {
  return Object.fromEntries(String(req.headers.cookie || '').split(';').map(v => v.trim()).filter(Boolean).map(v => {
    const index = v.indexOf('=');
    return [decodeURIComponent(index < 0 ? v : v.slice(0, index)), decodeURIComponent(index < 0 ? '' : v.slice(index + 1))];
  }));
}

function setSessionCookie(res, token) {
  const parts = [`${SESSION_COOKIE}=${encodeURIComponent(token)}`, 'Path=/', 'HttpOnly', 'SameSite=Lax', 'Max-Age=604800'];
  if (COOKIE_SECURE) parts.push('Secure');
  res.setHeader('Set-Cookie', parts.join('; '));
}

function clearSessionCookie(res) {
  const parts = [`${SESSION_COOKIE}=`, 'Path=/', 'HttpOnly', 'SameSite=Lax', 'Max-Age=0'];
  if (COOKIE_SECURE) parts.push('Secure');
  res.setHeader('Set-Cookie', parts.join('; '));
}

const authAttempts = new Map();
function authRateLimit(req, res, next) {
  const key = req.ip || req.socket.remoteAddress || 'local';
  const now = Date.now();
  const recent = (authAttempts.get(key) || []).filter(stamp => now - stamp < 15 * 60 * 1000);
  if (recent.length >= 10) return res.status(429).json({ success: false, error: 'Too many authentication attempts. Try again in 15 minutes.' });
  recent.push(now); authAttempts.set(key, recent); next();
}

app.post('/api/auth/register', authRateLimit, async (req, res) => {
  try { const result = await register(req.body); setSessionCookie(res, result.sessionToken); res.json({ success: true, user: result.user }); }
  catch (error) { engineErrorResponse(res, error); }
});
app.post('/api/auth/login', authRateLimit, async (req, res) => {
  try { const result = await login(req.body); setSessionCookie(res, result.sessionToken); res.json({ success: true, user: result.user }); }
  catch (error) { engineErrorResponse(res, error); }
});
app.post('/api/auth/logout', async (req, res) => {
  try { await logout(cookies(req)[SESSION_COOKIE] || ''); } catch (_) {}
  clearSessionCookie(res); res.json({ success: true });
});
app.get('/api/auth/me', async (req, res) => {
  try { res.json(await me(cookies(req)[SESSION_COOKIE] || '')); }
  catch (error) { clearSessionCookie(res); engineErrorResponse(res, error); }
});

app.use('/api', async (req, res, next) => {
  if (req.path === '/status' || req.path.startsWith('/auth/') || req.path.startsWith('/webhooks/sendgrid')) return next();
  const token = cookies(req)[SESSION_COOKIE] || '';
  if (!token) return res.status(401).json({ success: false, error: 'Authentication required' });
  try { const identity = await me(token); req.sessionToken = token; req.user = identity.user; next(); }
  catch (_) { clearSessionCookie(res); res.status(401).json({ success: false, error: 'Authentication required' }); }
});

function normalizeJobId(value, prefix = 'job') {
  const candidate = String(value || '');
  return /^[A-Za-z0-9_-]{1,80}$/.test(candidate) ? candidate : `${prefix}-${Date.now()}`;
}

function cleanupJob(jobId, delayMs = 30000) {
  setTimeout(() => jobEventEmitters.delete(jobId), delayMs);
}

/**
 * SSE Job Stream Helper
 */
function sendJobLog(jobId, message, type = 'info') {
  const clients = jobEventEmitters.get(jobId) || [];
  const payload = JSON.stringify({ message, type, time: new Date().toLocaleTimeString() });
  clients.forEach(res => {
    res.write(`data: ${payload}\n\n`);
  });
}

/**
 * Health & System Status Endpoint
 */
app.get('/api/status', async (req, res) => {
  try {
    const dockerOk = await isDockerRunning();
    const gosomOk = await isGosomApiReachable();
    const hasApifyToken = Boolean(process.env.APIFY_TOKEN && process.env.APIFY_TOKEN.trim());
    let leadEngine = { available: false };
    try {
      leadEngine = { available: true, ...(await getEngineHealth()) };
    } catch (engineError) {
      leadEngine.error = engineError.message;
    }

    res.json({
      success: true,
      dockerRunning: dockerOk,
      gosomApiReachable: gosomOk,
      apifyConfigured: hasApifyToken,
      port: PORT,
      timestamp: new Date().toISOString(),
      leadEngine
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

/**
 * SSE Event Stream for Live Scraper Logs
 */
app.get('/api/events/:jobId', (req, res) => {
  const jobId = normalizeJobId(req.params.jobId);
  if (jobId !== req.params.jobId) return res.status(400).end();

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  if (!jobEventEmitters.has(jobId)) {
    jobEventEmitters.set(jobId, []);
  }
  jobEventEmitters.get(jobId).push(res);

  // Send initial connect ping
  res.write(`data: ${JSON.stringify({ message: 'Connected to live scraper console', type: 'system', time: new Date().toLocaleTimeString() })}\n\n`);

  const heartbeat = setInterval(() => res.write(': heartbeat\n\n'), 15000);

  req.on('close', () => {
    clearInterval(heartbeat);
    const clients = jobEventEmitters.get(jobId) || [];
    const remaining = clients.filter(c => c !== res);
    if (remaining.length > 0) jobEventEmitters.set(jobId, remaining);
    else jobEventEmitters.delete(jobId);
  });
});

/**
 * Lead Generation Scraping Endpoint
 */
app.post('/api/scrape', async (req, res) => {
  const { niches, city, maxResults = 50 } = req.body;
  const jobId = normalizeJobId(req.body.jobId);

  if (!niches) {
    return res.status(400).json({ success: false, error: 'Please specify at least one niche.' });
  }
  if (!city) {
    return res.status(400).json({ success: false, error: 'Please specify a city/location.' });
  }

  const logHandler = (msg, type = 'info') => {
    console.log(`[Job ${jobId}] ${msg}`);
    sendJobLog(jobId, msg, type);
  };

  try {
    const result = await executeLeadScrape({
      niches,
      city,
      maxResults: Math.max(1, Math.min(parseInt(maxResults, 10) || 50, 200)),
      apifyToken: process.env.APIFY_TOKEN,
      onLog: logHandler
    });

    let persistence = { available: false };
    try {
      persistence = {
        available: true,
        ...(await ingestLeads(req.sessionToken, result.allLeads || [], result.source, `${niches} in ${city}`))
      };
      logHandler(`💾 Persisted lead state: ${persistence.inserted || 0} new, ${persistence.updated || 0} updated.`, 'success');
    } catch (engineError) {
      persistence.error = engineError.message;
      logHandler(`⚠️ Lead engine unavailable; browser results remain usable but were not persisted: ${engineError.message}`, 'warn');
    }

    res.json({
      success: true,
      jobId,
      ...result,
      persistence
    });
  } catch (err) {
    logHandler(`Error: ${err.message}`, 'error');
    res.status(500).json({
      success: false,
      jobId,
      error: err.message
    });
  } finally {
    cleanupJob(jobId);
  }
});

/**
 * WhatsApp Cost Estimation Endpoint
 */
app.post('/api/whatsapp/estimate', (req, res) => {
  const { count = 0, leads = [] } = req.body;
  const totalCount = leads.length > 0 ? leads.filter(l => l.phone).length : parseInt(count, 10) || 0;
  const estimate = estimateWhatsAppCost(totalCount);
  res.json({ success: true, ...estimate });
});

/**
 * WhatsApp Number Verification Endpoint (Apify)
 */
app.post('/api/whatsapp/verify', async (req, res) => {
  const { leads = [], locationContext } = req.body;
  const jobId = normalizeJobId(req.body.jobId, 'wa');

  if (!Array.isArray(leads) || leads.length === 0) {
    return res.status(400).json({ success: false, error: 'No leads provided for WhatsApp verification.' });
  }

  const logHandler = (msg, type = 'info') => {
    console.log(`[WhatsApp Job ${jobId}] ${msg}`);
    sendJobLog(jobId, msg, type);
  };

  try {
    const result = await verifyLeadsWhatsApp(leads, {
      token: process.env.APIFY_TOKEN,
      locationContext,
      onLog: logHandler
    });

    if (!result.success) {
      return res.status(500).json({ success: false, error: result.error });
    }

    try {
      await ingestLeads(req.sessionToken, result.updatedLeads || [], 'whatsapp-update', locationContext || '');
    } catch (engineError) {
      logHandler(`⚠️ WhatsApp flags could not be persisted: ${engineError.message}`, 'warn');
    }

    res.json({
      success: true,
      jobId,
      ...result
    });
  } catch (err) {
    logHandler(`Error: ${err.message}`, 'error');
    res.status(500).json({ success: false, error: err.message });
  } finally {
    cleanupJob(jobId);
  }
});

/**
 * CSV Export Endpoint
 */
app.post('/api/export/csv', (req, res) => {
  const { leads = [], onlyProspects = true, filename = 'prospect-leads-export.csv' } = req.body;

  try {
    const csvContent = generateProspectsCsv(leads, { onlyProspects });
    res.setHeader('Content-Type', 'text/csv');
    const safeFilename = path.basename(String(filename)).replace(/[^A-Za-z0-9._-]/g, '_') || 'prospect-leads-export.csv';
    res.setHeader('Content-Disposition', `attachment; filename="${safeFilename}"`);
    res.send(csvContent);
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

function engineErrorResponse(res, error) {
  const upstreamStatus = String(error.message || '').match(/Lead engine HTTP (\d{3})/);
  const status = upstreamStatus ? Number(upstreamStatus[1]) : (/not found/i.test(error.message) ? 404 : 503);
  return res.status(status).json({ success: false, error: error.message });
}

app.get('/api/pipeline/leads', async (req, res) => {
  try {
    const params = new URLSearchParams();
    params.set('limit', String(Math.max(1, Math.min(parseInt(req.query.limit, 10) || 250, 1000))));
    params.set('offset', String(Math.max(0, parseInt(req.query.offset, 10) || 0)));
    params.set('qualified_only', req.query.qualified_only === 'true' ? 'true' : 'false');
    res.json(await listPersistedLeads(req.sessionToken, `?${params.toString()}`));
  } catch (error) { engineErrorResponse(res, error); }
});

app.get('/api/pipeline/analytics', async (req, res) => {
  try { res.json(await getAnalytics(req.sessionToken)); }
  catch (error) { engineErrorResponse(res, error); }
});

app.post('/api/pipeline/enrich', async (req, res) => {
  try {
    const limit = Math.max(1, Math.min(parseInt(req.body.limit, 10) || 25, 100));
    res.json(await enrichPersistedLeads(req.sessionToken, limit));
  } catch (error) { engineErrorResponse(res, error); }
});

app.post('/api/pipeline/outreach/generate', async (req, res) => {
  try { res.json(await generateEmails(req.sessionToken, Math.max(1, Math.min(parseInt(req.body.limit, 10) || 25, 100)))); }
  catch (error) { engineErrorResponse(res, error); }
});

app.post('/api/pipeline/outreach/batches/:batchId/approve', async (req, res) => {
  try { res.json(await approveBatch(req.sessionToken, req.params.batchId)); }
  catch (error) { engineErrorResponse(res, error); }
});

app.get('/api/pipeline/outreach/batches', async (req, res) => {
  try { res.json(await getBatches(req.sessionToken)); }
  catch (error) { engineErrorResponse(res, error); }
});

app.get('/api/pipeline/outreach/logs', async (req, res) => {
  try { res.json(await getSendLogs(req.sessionToken)); }
  catch (error) { engineErrorResponse(res, error); }
});

app.get('/api/pipeline/settings', async (req, res) => {
  try {
    const [campaign, gmail] = await Promise.all([getCampaignSettings(req.sessionToken), getGmailStatus(req.sessionToken)]);
    res.json({ success: true, campaign, gmail });
  } catch (error) { engineErrorResponse(res, error); }
});

app.put('/api/pipeline/settings', async (req, res) => {
  try {
    const payload = {
      sending_method: req.body.sending_method,
      offer: req.body.offer,
      cta: req.body.cta,
      name: req.body.name,
      workflow_mode: req.body.workflow_mode,
      automatic_enabled: req.body.automatic_enabled === true,
      prompt_template: req.body.prompt_template,
      groq_model: req.body.groq_model,
      daily_cap: req.body.daily_cap,
      hourly_cap: req.body.hourly_cap,
      duplicate_lookback_days: req.body.duplicate_lookback_days,
      bounce_threshold_pct: req.body.bounce_threshold_pct,
      complaint_threshold_pct: req.body.complaint_threshold_pct,
      circuit_breaker_window: req.body.circuit_breaker_window
    };
    res.json(await saveCampaignSettings(req.sessionToken, payload));
  } catch (error) { engineErrorResponse(res, error); }
});

app.post('/api/pipeline/gmail/connect', async (req, res) => {
  try { res.json(await startGmailConnect(req.sessionToken)); }
  catch (error) { engineErrorResponse(res, error); }
});

app.get('/api/gmail/oauth/callback', async (req, res) => {
  const code = String(req.query.code || '');
  const state = String(req.query.state || '');
  const oauthError = String(req.query.error || '');
  if (oauthError) return res.redirect(`/?gmail=error&message=${encodeURIComponent(oauthError)}`);
  try {
    await completeGmailConnect(cookies(req)[SESSION_COOKIE] || '', code, state);
    return res.redirect('/?gmail=connected');
  } catch (error) {
    return res.redirect(`/?gmail=error&message=${encodeURIComponent(error.message)}`);
  }
});

app.post('/api/pipeline/gmail/disconnect', async (req, res) => {
  try { res.json(await disconnectGmail(req.sessionToken)); }
  catch (error) { engineErrorResponse(res, error); }
});

app.post('/api/pipeline/leads/:leadId/reply', async (req, res) => {
  try { res.json(await markLeadReplied(req.sessionToken, parseInt(req.params.leadId, 10))); }
  catch (error) { engineErrorResponse(res, error); }
});

app.post('/api/pipeline/leads/:leadId/contacted', async (req, res) => {
  try { res.json(await markLeadContacted(req.sessionToken, parseInt(req.params.leadId, 10))); }
  catch (error) { engineErrorResponse(res, error); }
});

app.post('/api/pipeline/leads/:leadId/consent', async (req, res) => {
  try { res.json(await setLeadConsent(req.sessionToken, parseInt(req.params.leadId, 10), req.body.confirmed === true)); }
  catch (error) { engineErrorResponse(res, error); }
});

app.post('/api/webhooks/sendgrid', async (req, res) => {
  try {
    const headers = {
      'X-Twilio-Email-Event-Webhook-Signature': req.get('X-Twilio-Email-Event-Webhook-Signature') || '',
      'X-Twilio-Email-Event-Webhook-Timestamp': req.get('X-Twilio-Email-Event-Webhook-Timestamp') || ''
    };
    const payload = req.rawBody || Buffer.from(JSON.stringify(req.body));
    res.json(await proxySendgridEvents(payload, req.query.token, headers));
  } catch (error) { engineErrorResponse(res, error); }
});

app.all('/unsubscribe/:token', async (req, res) => {
  try {
    const html = await proxyUnsubscribe(req.params.token, req.method === 'POST' ? 'POST' : 'GET');
    res.type('html').send(html);
  } catch (error) {
    res.status(404).type('html').send('<h1>Unsubscribe link not found</h1>');
  }
});

app.get('/login', (req, res) => res.sendFile(path.join(__dirname, 'public', 'login.html')));
app.get('/signup', (req, res) => res.sendFile(path.join(__dirname, 'public', 'signup.html')));
app.get('/', async (req, res) => {
  const token = cookies(req)[SESSION_COOKIE] || '';
  if (!token) return res.redirect('/login');
  try { await me(token); return res.sendFile(path.join(__dirname, 'public', 'index.html')); }
  catch (_) { clearSessionCookie(res); return res.redirect('/login'); }
});
app.get('*', (req, res) => res.redirect('/'));

// Start Server
const server = app.listen(PORT, HOST, () => {
  fs.mkdirSync(path.dirname(PID_FILE), { recursive: true });
  fs.writeFileSync(PID_FILE, String(process.pid), 'ascii');
  console.log(`=======================================================`);
  console.log(`🚀 Local Business Lead Generator running on port ${PORT}`);
  console.log(`🌐 Dashboard URL: http://${HOST === '0.0.0.0' ? 'localhost' : HOST}:${PORT}`);
  console.log(`=======================================================`);
});

server.on('error', (error) => {
  console.error(`Server startup failed: ${error.message}`);
  process.exitCode = 1;
});

function cleanupPidFile() {
  try {
    if (fs.existsSync(PID_FILE) && fs.readFileSync(PID_FILE, 'ascii').trim() === String(process.pid)) {
      fs.unlinkSync(PID_FILE);
    }
  } catch (_) {}
}

process.on('SIGINT', () => server.close(() => { cleanupPidFile(); process.exit(0); }));
process.on('SIGTERM', () => server.close(() => { cleanupPidFile(); process.exit(0); }));
process.on('exit', cleanupPidFile);

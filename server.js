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
  planOutreach,
  markLeadContacted,
  markLeadReplied,
  setLeadConsent,
  proxyUnsubscribe,
  proxySendgridEvents
} = require('./services/leadEngineClient');

const app = express();
const PORT = process.env.PORT || 3000;
const HOST = process.env.HOST || '127.0.0.1';
const PID_FILE = path.join(__dirname, 'data', 'node.pid');

// Event listeners for SSE logging per job
const jobEventEmitters = new Map();

app.use(express.json({
  limit: '10mb',
  verify: (req, res, buffer) => {
    if (req.originalUrl.startsWith('/api/webhooks/sendgrid')) req.rawBody = Buffer.from(buffer);
  }
}));
app.use(express.urlencoded({ extended: true, limit: '2mb' }));
app.use(express.static(path.join(__dirname, 'public')));

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
    let leadEngine = { available: false, dryRun: true };
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
        ...(await ingestLeads(result.allLeads || [], result.source, `${niches} in ${city}`))
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
      await ingestLeads(result.updatedLeads || [], 'whatsapp-update', locationContext || '');
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
  const status = /not found/i.test(error.message) ? 404 : 503;
  return res.status(status).json({ success: false, error: error.message });
}

app.get('/api/pipeline/leads', async (req, res) => {
  try {
    const params = new URLSearchParams();
    params.set('limit', String(Math.max(1, Math.min(parseInt(req.query.limit, 10) || 250, 1000))));
    params.set('offset', String(Math.max(0, parseInt(req.query.offset, 10) || 0)));
    params.set('qualified_only', req.query.qualified_only === 'true' ? 'true' : 'false');
    res.json(await listPersistedLeads(`?${params.toString()}`));
  } catch (error) { engineErrorResponse(res, error); }
});

app.get('/api/pipeline/analytics', async (req, res) => {
  try { res.json(await getAnalytics()); }
  catch (error) { engineErrorResponse(res, error); }
});

app.post('/api/pipeline/enrich', async (req, res) => {
  try {
    const limit = Math.max(1, Math.min(parseInt(req.body.limit, 10) || 25, 100));
    res.json(await enrichPersistedLeads(limit));
  } catch (error) { engineErrorResponse(res, error); }
});

app.post('/api/pipeline/outreach/plan', async (req, res) => {
  try { res.json(await planOutreach()); }
  catch (error) { engineErrorResponse(res, error); }
});

app.post('/api/pipeline/leads/:leadId/reply', async (req, res) => {
  try { res.json(await markLeadReplied(parseInt(req.params.leadId, 10))); }
  catch (error) { engineErrorResponse(res, error); }
});

app.post('/api/pipeline/leads/:leadId/contacted', async (req, res) => {
  try { res.json(await markLeadContacted(parseInt(req.params.leadId, 10))); }
  catch (error) { engineErrorResponse(res, error); }
});

app.post('/api/pipeline/leads/:leadId/consent', async (req, res) => {
  try { res.json(await setLeadConsent(parseInt(req.params.leadId, 10), req.body.confirmed === true)); }
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

// Fallback to index.html for SPA
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

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

const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const http = require('http');
const https = require('https');

/**
 * Helper to make HTTP requests
 */
function httpRequest(url, options = {}, data = null) {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const client = parsedUrl.protocol === 'https:' ? https : http;

    const req = client.request(url, options, (res) => {
      let body = '';
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => {
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          body
        });
      });
    });

    req.on('error', (err) => reject(err));
    req.setTimeout(options.timeout || 15000, () => {
      req.destroy();
      reject(new Error('Request timed out'));
    });

    if (data) {
      req.write(typeof data === 'string' ? data : JSON.stringify(data));
    }
    req.end();
  });
}

/**
 * Check if Docker daemon is running
 */
function isDockerRunning() {
  return new Promise((resolve) => {
    exec('docker info', { timeout: 4000 }, (error) => {
      resolve(!error);
    });
  });
}

/**
 * Check if gosom REST API is reachable
 */
async function isGosomApiReachable(apiUrl = process.env.GOSOM_API_URL || 'http://localhost:8080') {
  try {
    const res = await httpRequest(`${apiUrl}/api/v1/jobs`, { method: 'GET', timeout: 3000 });
    return res.statusCode >= 200 && res.statusCode < 500;
  } catch (err) {
    return false;
  }
}

/**
 * Parse CSV line handling quotes
 */
function parseCsvLine(line) {
  const result = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === ',' && !inQuotes) {
      result.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  result.push(current);
  return result;
}

/**
 * Parse CSV text to array of objects
 */
function parseCsvText(csvText) {
  if (!csvText) return [];
  const lines = csvText.split(/\r?\n/).filter(line => line.trim().length > 0);
  if (lines.length < 2) return [];

  const headers = parseCsvLine(lines[0]).map(h => h.trim().toLowerCase().replace(/\s+/g, '_'));
  const results = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCsvLine(lines[i]);
    const obj = {};
    for (let h = 0; h < headers.length; h++) {
      obj[headers[h]] = values[h] !== undefined ? values[h].trim() : '';
    }
    results.push(obj);
  }

  return results;
}

function extractFirstEmail(value) {
  const match = String(value || '').match(/[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}/i);
  return match ? match[0].toLowerCase() : '';
}

function countPhotos(images, thumbnail) {
  let count = 0;
  if (Array.isArray(images)) count = images.filter(Boolean).length;
  else if (images && typeof images === 'object') count = Object.values(images).filter(Boolean).length;
  else if (typeof images === 'string' && images.trim()) {
    try {
      const parsed = JSON.parse(images);
      count = Array.isArray(parsed) ? parsed.filter(Boolean).length : (parsed ? 1 : 0);
    } catch (_) {
      count = images.split(/[,;\n]/).filter(Boolean).length;
    }
  }
  return count || (thumbnail ? 1 : 0);
}

function extractLastReviewAt(value) {
  if (!value) return null;
  let reviews = value;
  if (typeof reviews === 'string') {
    try { reviews = JSON.parse(reviews); } catch (_) { return null; }
  }
  if (!Array.isArray(reviews) && reviews && typeof reviews === 'object') {
    reviews = reviews.reviews || reviews.items || [reviews];
  }
  if (!Array.isArray(reviews)) return null;
  const dates = reviews.flatMap(review => {
    if (!review || typeof review !== 'object') return [];
    const value = review.publishedAtDate || review.published_at || review.date || review.timestamp || review.time || review.reviewDate;
    if (!value) return [];
    const numeric = Number(value);
    const date = Number.isFinite(numeric) && String(value).trim() !== ''
      ? new Date(numeric > 10000000000 ? numeric : numeric * 1000)
      : new Date(value);
    return Number.isNaN(date.getTime()) ? [] : [date];
  });
  if (!dates.length) return null;
  return new Date(Math.max(...dates.map(date => date.getTime()))).toISOString();
}

/**
 * Map raw gosom item to standard Lead object
 */
function mapGosomItemToLead(item, niche, city, index) {
  const rating = parseFloat(item.rating || item.review_rating || item.total_score || item.score || 0) || 0;
  const reviewCount = parseInt(item.reviews || item.review_count || item.reviews_count || item.user_ratings_total || 0, 10) || 0;
  const rank = parseInt(item.rank || item.position || (index + 1), 10);
  
  const statusStr = (item.status || item.business_status || '').toLowerCase();
  const isClosed = statusStr.includes('closed') || item.is_closed === 'true' || item.is_closed === true;

  return {
    id: `gosom-${Date.now()}-${index}-${Math.random().toString(36).substr(2, 6)}`,
    name: item.title || item.name || item.business_name || 'Unknown Business',
    niche: niche || item.category || 'General',
    city: city || item.city || '',
    phone: item.phone || item.phone_number || item.international_phone || '',
    website: item.website || item.web || item.link || '',
    email: extractFirstEmail(item.email || item.emails),
    rating: rating,
    reviewCount: reviewCount,
    rank: rank,
    address: item.address || item.complete_address || item.formatted_address || '',
    latitude: parseFloat(item.latitude || item.lat || 0),
    longitude: parseFloat(item.longitude || item.longtitude || item.lng || 0),
    placeId: item.place_id || '',
    cid: item.cid || '',
    dataId: item.data_id || '',
    category: item.category || niche || '',
    timezone: item.timezone || '',
    photoCount: countPhotos(item.images, item.thumbnail),
    lastReviewAt: extractLastReviewAt(item.user_reviews || item.user_reviews_extended),
    mapsUrl: item.link || '',
    isClosed: isClosed,
    source: 'self-hosted (gosom)',
    whatsappVerified: null
  };
}

/**
 * Scrape Google Maps using gosom/google-maps-scraper (Docker / CLI / API)
 * @param {Object} options
 * @param {Array<string>} options.niches - List of niches (e.g. ['plumbers', 'roofers'])
 * @param {string} options.city - City/State/Country string
 * @param {number} options.maxResults - Max results per niche
 * @param {Function} options.onLog - Progress log callback
 * @returns {Promise<{ success: boolean, leads?: Array<Object>, error?: string }>}
 */
async function scrapeGosom(options = {}) {
  const { niches = [], city = '', maxResults = 50, onLog = () => {} } = options;
  const log = (msg) => onLog(`[gosom] ${msg}`);

  log('Checking self-hosted gosom scraper availability...');

  const apiReachable = await isGosomApiReachable();
  const dockerAvailable = await isDockerRunning();

  if (!apiReachable && !dockerAvailable) {
    const msg = 'Neither Docker daemon nor gosom API server (http://localhost:8080) is running.';
    log(`⚠️ ${msg}`);
    return { success: false, error: msg };
  }

  const allScrapedLeads = [];
  const failedNiches = [];
  const depth = Math.max(1, Math.ceil(maxResults / 20));

  // Ensure directories exist
  const tempDir = path.join(__dirname, '..', 'data', 'temp');
  const outDir = path.join(__dirname, '..', 'data', 'out');
  fs.mkdirSync(tempDir, { recursive: true });
  fs.mkdirSync(outDir, { recursive: true });

  for (const niche of niches) {
    const query = `${niche} in ${city}`.trim();
    log(`Starting scrape for query: "${query}" (depth=${depth}, limit=${maxResults})...`);

    const queryFileName = `query_${Date.now()}_${Math.random().toString(36).substr(2, 4)}.txt`;
    const resultsFileName = `results_${Date.now()}_${Math.random().toString(36).substr(2, 4)}.csv`;
    const queryFile = path.join(tempDir, queryFileName);
    const resultsFile = path.join(outDir, resultsFileName);

    fs.writeFileSync(queryFile, `${query}\n`, 'utf8');

    try {
      if (dockerAvailable) {
        // Format paths for Docker on Windows
        const normalizedQuery = path.resolve(queryFile).replace(/\\/g, '/');
        const normalizedOut = path.resolve(outDir).replace(/\\/g, '/');

        const dockerCmd = `docker run --rm -v "${normalizedQuery}:/queries.txt:ro" -v "${normalizedOut}:/out" gosom/google-maps-scraper -input /queries.txt -results /out/${resultsFileName} -depth ${depth} -email -exit-on-inactivity 1m`;
        
        log(`Executing: ${dockerCmd}`);
        
        await new Promise((resolve) => {
          exec(dockerCmd, { timeout: 180000 }, (error, stdout, stderr) => {
            // Even if an error or timeout occurred for single email, check if output was created
            if (error) {
              log(`Docker execution note: ${stderr ? stderr.slice(0, 300) : error.message}`);
            }
            resolve(stdout);
          });
        });

        // Read results if generated
        if (fs.existsSync(resultsFile)) {
          const content = fs.readFileSync(resultsFile, 'utf8');
          const parsed = parseCsvText(content);
          log(`Scraped ${parsed.length} raw results for "${niche}" via Docker.`);

          parsed.slice(0, maxResults).forEach((item, idx) => {
            allScrapedLeads.push(mapGosomItemToLead(item, niche, city, idx));
          });
        } else {
          throw new Error('Output results file was not created by gosom container');
        }
      } else if (apiReachable) {
        log(`Triggering scrape via gosom REST API at ${process.env.GOSOM_API_URL || 'http://localhost:8080'}...`);
        const apiUrl = process.env.GOSOM_API_URL || 'http://localhost:8080';
        
        const createJobRes = await httpRequest(`${apiUrl}/api/v1/jobs`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          timeout: 10000
        }, {
          query: query,
          depth: depth,
          email: false,
          limit: maxResults
        });

        if (createJobRes.statusCode >= 400) {
          throw new Error(`Gosom API returned HTTP ${createJobRes.statusCode}: ${createJobRes.body}`);
        }

        const jobData = JSON.parse(createJobRes.body || '{}');
        const jobId = jobData.id || jobData.job_id;
        log(`Job ${jobId} created. Polling for completion...`);

        let completed = false;
        let attempts = 0;
        while (!completed && attempts < 60) {
          await new Promise(r => setTimeout(r, 3000));
          attempts++;
          const checkRes = await httpRequest(`${apiUrl}/api/v1/jobs/${jobId}`, { method: 'GET', timeout: 5000 });
          const statusData = JSON.parse(checkRes.body || '{}');
          if (statusData.status === 'completed' || statusData.status === 'finished') {
            completed = true;
          } else if (statusData.status === 'failed' || statusData.status === 'error') {
            throw new Error(`Gosom job failed: ${statusData.error || 'Unknown error'}`);
          }
        }

        if (!completed) throw new Error('Gosom scraping job timed out');

        const dlRes = await httpRequest(`${apiUrl}/api/v1/jobs/${jobId}/download`, { method: 'GET', timeout: 15000 });
        const parsed = parseCsvText(dlRes.body);
        log(`Scraped ${parsed.length} results for "${niche}" via API.`);
        parsed.slice(0, maxResults).forEach((item, idx) => {
          allScrapedLeads.push(mapGosomItemToLead(item, niche, city, idx));
        });
      }
      const nicheCount = allScrapedLeads.filter(lead => lead.niche === niche).length;
      if (nicheCount === 0) throw new Error('gosom returned no rows for this niche');
    } catch (err) {
      log(`Error scraping "${niche}" with gosom: ${err.message}`);
      failedNiches.push(niche);
    } finally {
      try { if (fs.existsSync(queryFile)) fs.unlinkSync(queryFile); } catch (e) {}
    }
  }

  if (allScrapedLeads.length === 0) {
    return { success: false, error: 'gosom scraper returned 0 results', failedNiches: niches };
  }

  log(`Successfully scraped total ${allScrapedLeads.length} leads via self-hosted gosom.`);
  return { success: true, leads: allScrapedLeads, failedNiches };
}

module.exports = {
  scrapeGosom,
  isDockerRunning,
  isGosomApiReachable
};

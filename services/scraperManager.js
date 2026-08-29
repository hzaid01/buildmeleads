const { scrapeGosom } = require('./gosomScraper');
const { scrapeApify } = require('./apifyScraper');
const { processAndFilterLeads } = require('./leadFilter');

/**
 * Split and clean comma-separated niches
 * @param {string|Array<string>} nichesInput 
 * @returns {Array<string>}
 */
function parseNiches(nichesInput) {
  if (Array.isArray(nichesInput)) {
    return nichesInput.map(n => String(n).trim()).filter(Boolean);
  }
  if (typeof nichesInput === 'string') {
    return nichesInput
      .split(',')
      .map(n => n.trim())
      .filter(Boolean);
  }
  return [];
}

/**
 * Orchestrate Lead Generation scraping with self-hosted Gosom + Apify fallback
 * @param {Object} params
 * @param {string|Array<string>} params.niches - Niche(s)
 * @param {string} params.city - City, State, Country
 * @param {number} [params.maxResults=50] - Number of results per niche
 * @param {string} [params.apifyToken] - Optional override token
 * @param {Function} [params.onLog] - Real-time log callback
 * @returns {Promise<Object>}
 */
async function executeLeadScrape(params = {}) {
  const {
    niches: rawNiches,
    city,
    maxResults = 50,
    apifyToken = process.env.APIFY_TOKEN,
    onLog = () => {}
  } = params;

  const niches = parseNiches(rawNiches);
  if (niches.length === 0) {
    throw new Error('At least one niche is required.');
  }
  if (!city || !city.trim()) {
    throw new Error('City / location is required.');
  }

  const resultsLimit = Math.max(1, parseInt(maxResults, 10) || 50);

  onLog(`🚀 Initializing lead search for ${niches.length} niche(s): [${niches.join(', ')}] in "${city.trim()}" (Target: ${resultsLimit} per niche)`);

  let leads = [];
  let source = 'self-hosted (gosom)';
  let isFallback = false;
  let fallbackReason = null;

  // 1. Try primary method: gosom/google-maps-scraper
  onLog('🔍 Attempting primary extraction via self-hosted gosom scraper...');
  const gosomResult = await scrapeGosom({
    niches,
    city: city.trim(),
    maxResults: resultsLimit,
    onLog
  });

  if (gosomResult.success && Array.isArray(gosomResult.leads) && gosomResult.leads.length > 0) {
    leads = gosomResult.leads;
    source = 'self-hosted (gosom)';
    isFallback = false;
    onLog(`✅ Successfully completed scrape with self-hosted gosom (${leads.length} leads extracted).`);
    const missingNiches = Array.isArray(gosomResult.failedNiches) ? gosomResult.failedNiches : [];
    if (missingNiches.length > 0) {
      fallbackReason = `gosom failed for: ${missingNiches.join(', ')}`;
      onLog(`🔄 Using Apify only for ${missingNiches.length} failed niche(s), preserving gosom results...`);
      const partialFallback = await scrapeApify({
        niches: missingNiches,
        city: city.trim(),
        maxResults: resultsLimit,
        token: apifyToken,
        onLog
      });
      if (partialFallback.success && Array.isArray(partialFallback.leads)) {
        leads.push(...partialFallback.leads);
        source = 'mixed (gosom + apify fallback)';
        isFallback = true;
      } else {
        onLog(`⚠️ Apify could not recover failed niches: ${partialFallback.error || 'no results'}`);
      }
    }
  } else {
    // 2. Gosom failed / offline -> Fallback to Apify
    fallbackReason = gosomResult.error || 'gosom scraper did not return results';
    onLog(`⚠️ Primary scraper unavailable or failed: "${fallbackReason}".`);
    onLog(`🔄 Activating automatic fallback to Apify Google Maps Scraper actor...`);

    const apifyResult = await scrapeApify({
      niches,
      city: city.trim(),
      maxResults: resultsLimit,
      token: apifyToken,
      onLog
    });

    if (apifyResult.success && Array.isArray(apifyResult.leads) && apifyResult.leads.length > 0) {
      leads = apifyResult.leads;
      source = 'apify (fallback)';
      isFallback = true;
      onLog(`✅ Successfully completed scrape via Apify Fallback (${leads.length} leads extracted).`);
    } else {
      const errorDetail = apifyResult.error || 'Apify scraper returned no results.';
      onLog(`❌ Both primary and fallback scraping methods failed.`);
      throw new Error(`Scraping failed. Primary (gosom): ${fallbackReason}. Fallback (Apify): ${errorDetail}`);
    }
  }

  // 3. Process and Filter Leads using weak-GBP qualification rules.
  onLog('📊 Qualifying leads with no website or at least one weak Google Business Profile indicator...');
  const filtered = processAndFilterLeads(leads);

  onLog(`✨ Processing complete! Found ${filtered.stats.total} total leads, including ${filtered.stats.prospectsCount} qualified prospect leads.`);

  return {
    source,
    isFallback,
    fallbackReason,
    niches,
    city: city.trim(),
    maxResults: resultsLimit,
    timestamp: new Date().toISOString(),
    stats: filtered.stats,
    allLeads: filtered.all,
    prospects: filtered.prospects
  };
}

module.exports = {
  parseNiches,
  executeLeadScrape
};

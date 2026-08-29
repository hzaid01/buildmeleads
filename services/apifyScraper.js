const { ApifyClient } = require('apify-client');

/**
 * Clean & extract email from various Apify formats
 */
function extractEmail(item) {
  if (item.email && typeof item.email === 'string') return item.email;
  if (Array.isArray(item.emails) && item.emails.length > 0) return item.emails[0];
  if (item.contactEmail && typeof item.contactEmail === 'string') return item.contactEmail;
  if (item.contactEmails && Array.isArray(item.contactEmails) && item.contactEmails.length > 0) return item.contactEmails[0];
  if (item.socialMedia && item.socialMedia.email) return item.socialMedia.email;
  return '';
}

/**
 * Map raw Apify Google Maps item to unified Lead object
 */
function mapApifyItemToLead(item, defaultNiche, city, index) {
  const rating = parseFloat(item.totalScore || item.stars || item.rating || 0) || 0;
  const reviewCount = parseInt(item.reviewsCount || item.reviews_count || item.reviewCount || 0, 10) || 0;
  const rank = typeof item.rank === 'number' ? item.rank : (index + 1);
  const isClosed = item.isPermanentlyClosed === true || item.temporarilyClosed === true || (typeof item.permanentlyClosed === 'boolean' && item.permanentlyClosed);

  let address = item.address || item.fullAddress || item.street || '';
  if (!address && item.neighborhood) address = item.neighborhood;

  return {
    id: `apify-${item.placeId || item.id || Date.now()}-${index}-${Math.random().toString(36).substr(2, 5)}`,
    name: item.title || item.name || 'Unknown Business',
    niche: defaultNiche || item.categoryName || item.categories?.[0] || 'General',
    city: city || item.city || '',
    phone: item.phone || item.phoneUnformatted || item.internationalPhone || '',
    website: item.website || item.url || '',
    email: extractEmail(item),
    rating: rating,
    reviewCount: reviewCount,
    rank: rank,
    address: address,
    latitude: item.location?.lat || item.latitude || 0,
    longitude: item.location?.lng || item.longitude || 0,
    placeId: item.placeId || '',
    cid: item.cid || '',
    category: item.categoryName || item.categories?.[0] || defaultNiche || '',
    timezone: item.timeZone || item.timezone || '',
    photoCount: item.imagesCount || item.imageCount || item.imageUrls?.length || item.images?.length || 0,
    lastReviewAt: item.reviews?.[0]?.publishedAtDate || item.reviews?.[0]?.date || null,
    mapsUrl: item.url || item.placeUrl || '',
    isClosed: isClosed,
    source: 'apify (fallback)',
    whatsappVerified: null
  };
}

/**
 * Scrape Google Maps using Apify actor fallback
 * @param {Object} options
 * @param {Array<string>} options.niches - Niches list
 * @param {string} options.city - City/State/Country
 * @param {number} options.maxResults - Max places per niche
 * @param {string} [options.token] - Apify API token (or from process.env.APIFY_TOKEN)
 * @param {Function} options.onLog - Progress log callback
 * @returns {Promise<{ success: boolean, leads?: Array<Object>, error?: string }>}
 */
async function scrapeApify(options = {}) {
  const { niches = [], city = '', maxResults = 50, token = process.env.APIFY_TOKEN, onLog = () => {} } = options;
  const log = (msg) => onLog(`[Apify Fallback] ${msg}`);

  if (!token) {
    const errorMsg = 'Apify API token is not configured in .env (APIFY_TOKEN=...). Please add your Apify token to use the fallback scraper.';
    log(`❌ ${errorMsg}`);
    return { success: false, error: errorMsg };
  }

  const client = new ApifyClient({ token });
  const allLeads = [];

  for (const niche of niches) {
    const searchString = `${niche} in ${city}`.trim();
    log(`Calling Apify Google Maps Scraper for "${searchString}" (limit: ${maxResults})...`);

    const input = {
      searchStringsArray: [searchString],
      locationQuery: city,
      maxCrawledPlacesPerSearch: parseInt(maxResults, 10) || 50,
      language: 'en',
      maxReviews: 3,
      reviewsSort: 'newest'
    };

    try {
      log(`Starting Apify Actor "compass/crawler-google-places"...`);
      const run = await client.actor('compass/crawler-google-places').call(input);

      log(`Actor finished with status: ${run.status}. Fetching results from dataset ${run.defaultDatasetId}...`);

      const { items } = await client.dataset(run.defaultDatasetId).listItems({
        limit: parseInt(maxResults, 10) || 50
      });

      log(`Fetched ${items.length} items from Apify for "${niche}".`);

      items.forEach((item, idx) => {
        allLeads.push(mapApifyItemToLead(item, niche, city, idx));
      });
    } catch (err) {
      log(`Error running Apify Actor for "${niche}": ${err.message}`);
      return { success: false, error: `Apify error: ${err.message}` };
    }
  }

  log(`Apify scraping completed. Total leads gathered: ${allLeads.length}`);
  return { success: true, leads: allLeads };
}

module.exports = {
  scrapeApify,
  mapApifyItemToLead
};

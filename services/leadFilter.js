/**
 * Lead Filter Service
 * 
 * Qualification criteria:
 * - no website, OR at least one weak Google Business Profile indicator
 * - weak indicators: stale reviews, missing photos/category, rating below 4,
 *   or fewer than 10 reviews
 * - closed businesses never qualify
 */

const WEAKNESS_LABELS = {
  no_website: 'No website listed',
  stale_reviews: 'No recent reviews in 6+ months',
  missing_photos: 'Missing profile photos',
  incomplete_category: 'Incomplete business category',
  low_rating: 'Rating below 4.0',
  few_reviews: 'Fewer than 10 reviews'
};

function parseDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function detectLeadWeaknesses(lead, now = new Date()) {
  if (!lead) return [];
  const weaknesses = [];
  const website = String(lead.website || lead.url || '').trim();
  if (!website) weaknesses.push('no_website');

  const rating = Number.parseFloat(lead.rating);
  if (!Number.isFinite(rating) || rating < 4.0) weaknesses.push('low_rating');

  const reviewCount = Number.parseInt(lead.reviewCount ?? lead.review_count, 10);
  if (!Number.isFinite(reviewCount) || reviewCount < 10) weaknesses.push('few_reviews');

  const category = String(lead.category || lead.niche || '').trim().toLowerCase();
  if (['', 'general', 'business', 'establishment', 'unknown'].includes(category)) {
    weaknesses.push('incomplete_category');
  }

  const photoCount = Number.parseInt(lead.photoCount ?? lead.photo_count, 10);
  if (!Number.isFinite(photoCount) || photoCount <= 0) weaknesses.push('missing_photos');

  const lastReviewAt = parseDate(lead.lastReviewAt || lead.last_review_at);
  if (lastReviewAt && now.getTime() - lastReviewAt.getTime() >= 183 * 24 * 60 * 60 * 1000) {
    weaknesses.push('stale_reviews');
  }
  return [...new Set(weaknesses)];
}

function summarizeWeaknesses(weaknesses = []) {
  return weaknesses.map(code => WEAKNESS_LABELS[code] || code.replace(/_/g, ' ')).join('; ');
}

/**
 * Check if a single lead qualifies as a high-value prospect
 * @param {Object} lead 
 * @returns {boolean}
 */
function isProspectLead(lead) {
  if (!lead) return false;
  if (lead.isClosed === true || lead.permanentlyClosed === true) {
    return false;
  }
  if (typeof lead.status === 'string') {
    const statusLower = lead.status.toLowerCase();
    if (statusLower.includes('closed') || statusLower.includes('permanently')) {
      return false;
    }
  }
  return detectLeadWeaknesses(lead).length > 0;
}

/**
 * Filter an array of leads into all and prospects
 * @param {Array<Object>} leads 
 * @returns {{ all: Array<Object>, prospects: Array<Object>, stats: Object }}
 */
function processAndFilterLeads(leads = []) {
  const allLeads = [];
  const prospectLeads = [];

  for (let i = 0; i < leads.length; i++) {
    const raw = leads[i];
    const weaknesses = detectLeadWeaknesses(raw);
    const isProspect = isProspectLead(raw);

    const lead = {
      ...raw,
      id: raw.id || `lead-${Date.now()}-${i}`,
      isProspect: isProspect,
      weaknesses,
      issueDetected: summarizeWeaknesses(weaknesses),
      rating: typeof raw.rating === 'number' ? raw.rating : (parseFloat(raw.rating) || 0),
      reviewCount: typeof raw.reviewCount === 'number' ? raw.reviewCount : (parseInt(raw.reviewCount, 10) || 0),
      rank: typeof raw.rank === 'number' ? raw.rank : (parseInt(raw.rank, 10) || (i + 1)),
      whatsappVerified: raw.whatsappVerified === true ? true : (raw.whatsappVerified === false ? false : null)
    };

    allLeads.push(lead);
    if (isProspect) {
      prospectLeads.push(lead);
    }
  }

  return {
    all: allLeads,
    prospects: prospectLeads,
    stats: {
      total: allLeads.length,
      prospectsCount: prospectLeads.length,
      filteredOutCount: allLeads.length - prospectLeads.length
    }
  };
}

module.exports = {
  isProspectLead,
  processAndFilterLeads,
  detectLeadWeaknesses,
  summarizeWeaknesses
};

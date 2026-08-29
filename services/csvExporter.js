/**
 * CSV Export Service
 * 
 * Exports Filtered Prospects with exact required columns:
 * 1. Business Name
 * 2. Niche
 * 3. City
 * 4. Rating
 * 5. Review Count
 * 6. Maps Rank Position
 * 7. Phone Number
 * 8. WhatsApp Verified (only show the phone number again if verified Yes, otherwise leave blank)
 * 9. Email
 * 10. Website
 * 11. Address
 * 
 * Sorted by Review Count descending.
 */

const { isProspectLead } = require('./leadFilter');

/**
 * Escape CSV field value
 * @param {any} val 
 * @returns {string}
 */
function escapeCsvValue(val) {
  if (val === null || val === undefined) return '';
  const str = String(val);
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Generate CSV string from leads
 * @param {Array<Object>} leads 
 * @param {Object} options
 * @param {boolean} options.onlyProspects - If true, only exports leads passing phase 4 filter (default true)
 * @returns {string} CSV formatted text with UTF-8 BOM
 */
function generateProspectsCsv(leads = [], options = { onlyProspects: true }) {
  // Filter if needed
  let exportList = options.onlyProspects ? leads.filter(isProspectLead) : leads.slice();

  // Sort by Review Count descending
  exportList.sort((a, b) => {
    const revA = typeof a.reviewCount === 'number' ? a.reviewCount : (parseInt(a.reviewCount, 10) || 0);
    const revB = typeof b.reviewCount === 'number' ? b.reviewCount : (parseInt(b.reviewCount, 10) || 0);
    return revB - revA;
  });

  const headers = [
    'Business Name',
    'Niche',
    'City',
    'Rating',
    'Review Count',
    'Maps Rank Position',
    'Phone Number',
    'WhatsApp Verified',
    'Email',
    'Website',
    'Address'
  ];

  const rows = [headers.map(escapeCsvValue).join(',')];

  for (const lead of exportList) {
    const phone = lead.phone || lead.phoneNumber || '';
    
    // Exact requirement: "WhatsApp Verified (Yes/No) — only show the number again in this column if Yes, otherwise leave blank"
    const whatsappValue = (lead.whatsappVerified === true && phone) ? phone : '';

    const row = [
      escapeCsvValue(lead.name || lead.title || lead.businessName || ''),
      escapeCsvValue(lead.niche || ''),
      escapeCsvValue(lead.city || ''),
      escapeCsvValue(lead.rating !== undefined ? lead.rating : ''),
      escapeCsvValue(lead.reviewCount !== undefined ? lead.reviewCount : 0),
      escapeCsvValue(lead.rank || lead.mapsRankPosition || ''),
      escapeCsvValue(phone),
      escapeCsvValue(whatsappValue),
      escapeCsvValue(lead.email || (Array.isArray(lead.emails) ? lead.emails.join(', ') : '') || ''),
      escapeCsvValue(lead.website || lead.url || ''),
      escapeCsvValue(lead.address || lead.fullAddress || lead.street || '')
    ];

    rows.push(row.join(','));
  }

  // Prepend UTF-8 BOM (\uFEFF) for Excel compatibility on Windows
  return '\uFEFF' + rows.join('\r\n');
}

module.exports = {
  generateProspectsCsv,
  escapeCsvValue
};

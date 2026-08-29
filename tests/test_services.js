const assert = require('assert');
const { processAndFilterLeads, isProspectLead } = require('../services/leadFilter');
const { normalizeToE164, inferCountryCode } = require('../services/phoneNormalizer');
const { generateProspectsCsv } = require('../services/csvExporter');
const { estimateWhatsAppCost } = require('../services/whatsappChecker');
const { parseNiches } = require('../services/scraperManager');

console.log('🧪 Running Lead Generation Tool Service Tests...\n');

// 1. Test Phone Normalizer
console.log('1️⃣ Testing Phone Normalizer to E.164:');
assert.strictEqual(normalizeToE164('(813) 555-0199', 'Tampa, FL, USA'), '+18135550199');
assert.strictEqual(normalizeToE164('+1 813 555 0199', 'Tampa, FL, USA'), '+18135550199');
assert.strictEqual(normalizeToE164('020 7946 0991', 'London, UK'), '+442079460991');
console.log('   ✅ Phone normalization to E.164 passed.\n');

// 2. Test Lead Filtering (no website OR any weak GBP signal, open only)
console.log('2️⃣ Testing Weak GBP Lead Filter Rules:');
const strongProfile = {
  website: 'https://example.test',
  category: 'Plumber',
  photoCount: 5,
  lastReviewAt: new Date().toISOString(),
  isClosed: false
};
const mockLeads = [
  { id: '1', name: 'Strong Profile', rating: 4.8, reviewCount: 500, rank: 1, ...strongProfile },
  { id: '2', name: 'No Website', rating: 4.9, reviewCount: 300, rank: 2, ...strongProfile, website: '' },
  { id: '3', name: 'Low Rating', rating: 3.7, reviewCount: 200, rank: 3, ...strongProfile },
  { id: '4', name: 'Few Reviews', rating: 4.8, reviewCount: 9, rank: 4, ...strongProfile },
  { id: '5', name: 'Missing Photos', rating: 4.6, reviewCount: 80, rank: 5, ...strongProfile, photoCount: 0 },
  { id: '6', name: 'Closed Biz', rating: 3.5, reviewCount: 5, rank: 6, ...strongProfile, isClosed: true },
];

assert.strictEqual(isProspectLead(mockLeads[0]), false, 'Strong complete profile must not qualify');
assert.strictEqual(isProspectLead(mockLeads[1]), true, 'No website must qualify');
assert.strictEqual(isProspectLead(mockLeads[2]), true, 'Rating below 4.0 must qualify');
assert.strictEqual(isProspectLead(mockLeads[3]), true, 'Fewer than 10 reviews must qualify');
assert.strictEqual(isProspectLead(mockLeads[4]), true, 'Missing photos must qualify');
assert.strictEqual(isProspectLead(mockLeads[5]), false, 'Closed business must never qualify');

const filterResult = processAndFilterLeads(mockLeads);
assert.strictEqual(filterResult.all.length, 6);
assert.strictEqual(filterResult.prospects.length, 4);
assert.ok(filterResult.prospects[0].issueDetected.length > 0);
console.log('   ✅ Lead filtering passed (no website or weak GBP indicator, open only).\n');

// 3. Test CSV Exporter
console.log('3️⃣ Testing CSV Exporter (11 exact columns, sort by reviewCount DESC):');
const testCsvLeads = [
  {
    name: 'Alpha Roofing',
    niche: 'roofers',
    city: 'Tampa, FL, USA',
    rating: 4.6,
    reviewCount: 90,
    rank: 5,
    phone: '+18135550101',
    whatsappVerified: true, // Should show phone in WhatsApp column
    email: 'contact@alpharoofing.com',
    website: 'https://alpharoofing.com',
    address: '123 Main St, Tampa, FL',
    isClosed: false
  },
  {
    name: 'Beta Roofing',
    niche: 'roofers',
    city: 'Tampa, FL, USA',
    rating: 4.8,
    reviewCount: 300, // Higher review count -> Should appear FIRST
    rank: 6,
    phone: '+18135550102',
    whatsappVerified: false, // Should be BLANK in WhatsApp column
    email: 'info@betaroofing.com',
    website: 'https://betaroofing.com',
    address: '456 Oak Ave, Tampa, FL',
    isClosed: false
  }
];

const csvOutput = generateProspectsCsv(testCsvLeads, { onlyProspects: true });
const csvLines = csvOutput.split('\r\n');

const expectedHeader = 'Business Name,Niche,City,Rating,Review Count,Maps Rank Position,Phone Number,WhatsApp Verified,Email,Website,Address';
const actualHeader = csvLines[0].replace(/^\uFEFF/, '');
assert.strictEqual(actualHeader, expectedHeader, 'Headers must match exact requirements');

// Beta Roofing has 300 reviews, so it should be line 1 after header
assert.ok(csvLines[1].includes('Beta Roofing'), 'Sorted by review count descending: Beta Roofing (300) first');
// Beta Roofing is not WhatsApp verified -> WhatsApp column must be blank
assert.ok(csvLines[1].includes('+18135550102,,info@betaroofing.com'), 'Unverified WhatsApp column must be blank');

// Alpha Roofing has 90 reviews, line 2
assert.ok(csvLines[2].includes('Alpha Roofing'), 'Alpha Roofing second');
// Alpha Roofing is verified -> WhatsApp column must contain phone number
assert.ok(csvLines[2].includes('+18135550101,+18135550101,contact@alpharoofing.com'), 'Verified WhatsApp column must show phone number');

console.log('   ✅ CSV Exporter passed with exact columns and descending review count sort.\n');

// 4. Test WhatsApp Cost Estimator
console.log('4️⃣ Testing WhatsApp Cost Estimator:');
const estSmall = estimateWhatsAppCost(20);
assert.strictEqual(estSmall.requiresWarning, false);
assert.strictEqual(estSmall.estimatedCostUsd, '0.080');

const estLarge = estimateWhatsAppCost(75);
assert.strictEqual(estLarge.requiresWarning, true);
assert.strictEqual(estLarge.estimatedCostUsd, '0.300');
console.log('   ✅ WhatsApp cost estimation and warning logic passed.\n');

// 5. Test Multi-Niche Parser
console.log('5️⃣ Testing Multi-Niche Parser:');
const niches = parseNiches('plumbers, roofers, dentists, electricians');
assert.deepStrictEqual(niches, ['plumbers', 'roofers', 'dentists', 'electricians']);
console.log('   ✅ Multi-niche parsing passed.\n');

console.log('🎉 All automated tests passed successfully!');

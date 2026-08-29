const { PhoneNumberUtil, PhoneNumberFormat } = require('google-libphonenumber');
const phoneUtil = PhoneNumberUtil.getInstance();

/**
 * Infer ISO 3166-1 alpha-2 country code from location string
 * @param {string} location 
 * @returns {string} 2-letter country code (default 'US')
 */
function inferCountryCode(location = '') {
  const loc = (location || '').toLowerCase();
  if (loc.includes('uk') || loc.includes('united kingdom') || loc.includes('england') || loc.includes('london')) return 'GB';
  if (loc.includes('canada') || loc.includes('toronto') || loc.includes('vancouver') || loc.includes('ontario')) return 'CA';
  if (loc.includes('australia') || loc.includes('sydney') || loc.includes('melbourne') || loc.includes('brisbane')) return 'AU';
  if (loc.includes('germany') || loc.includes('deutschland') || loc.includes('berlin')) return 'DE';
  if (loc.includes('france') || loc.includes('paris')) return 'FR';
  if (loc.includes('india') || loc.includes('mumbai') || loc.includes('delhi')) return 'IN';
  if (loc.includes('uae') || loc.includes('dubai') || loc.includes('abu dhabi')) return 'AE';
  if (loc.includes('brazil') || loc.includes('brasil')) return 'BR';
  if (loc.includes('mexico')) return 'MX';
  if (loc.includes('spain') || loc.includes('madrid')) return 'ES';
  if (loc.includes('italy') || loc.includes('rome')) return 'IT';
  
  // Default to US for North America / general
  return 'US';
}

/**
 * Normalize raw phone string to E.164 format (+1XXXXXXXXXX)
 * @param {string} rawPhone 
 * @param {string} locationContext 
 * @returns {string|null} E.164 phone string or null if invalid
 */
function normalizeToE164(rawPhone, locationContext = '') {
  if (!rawPhone || typeof rawPhone !== 'string') return null;
  
  // Clean raw string
  const cleaned = rawPhone.trim();
  if (!cleaned) return null;

  const defaultRegion = inferCountryCode(locationContext);

  try {
    // If starts with +, parse without region
    if (cleaned.startsWith('+')) {
      const parsed = phoneUtil.parseAndKeepRawInput(cleaned);
      if (phoneUtil.isValidNumber(parsed)) {
        return phoneUtil.format(parsed, PhoneNumberFormat.E164);
      }
    }

    // Try parsing with inferred region
    const parsed = phoneUtil.parse(cleaned, defaultRegion);
    if (phoneUtil.isValidNumber(parsed) || phoneUtil.isPossibleNumber(parsed)) {
      return phoneUtil.format(parsed, PhoneNumberFormat.E164);
    }
  } catch (err) {
    // Fallback manual cleanup for digits
    const digitsOnly = cleaned.replace(/\D/g, '');
    if (digitsOnly.length === 10 && defaultRegion === 'US') {
      return `+1${digitsOnly}`;
    }
    if (digitsOnly.length === 11 && digitsOnly.startsWith('1') && defaultRegion === 'US') {
      return `+${digitsOnly}`;
    }
    if (digitsOnly.length >= 10 && digitsOnly.length <= 15) {
      return `+${digitsOnly}`;
    }
  }

  return null;
}

module.exports = {
  inferCountryCode,
  normalizeToE164
};

const { ApifyClient } = require('apify-client');
const { normalizeToE164 } = require('./phoneNormalizer');

// Estimated cost per phone number verification in USD on Apify
const COST_PER_NUMBER_USD = 0.004;

/**
 * Calculate estimated Apify cost for checking phone numbers
 * @param {number} count - Total numbers to check
 * @returns {{ count: number, estimatedCostUsd: string, requiresWarning: boolean }}
 */
function estimateWhatsAppCost(count) {
  const cost = (count * COST_PER_NUMBER_USD).toFixed(3);
  return {
    count,
    costPerNumber: COST_PER_NUMBER_USD,
    estimatedCostUsd: cost,
    requiresWarning: count > 50
  };
}

/**
 * Split array into chunks of given size
 */
function chunkArray(array, size = 100) {
  const chunks = [];
  for (let i = 0; i < array.length; i += size) {
    chunks.push(array.slice(i, i + size));
  }
  return chunks;
}

/**
 * Verify phone numbers on WhatsApp via Apify Actor (maged120/whatsapp-number-checker)
 * @param {Array<Object>} leads - Leads to verify (must contain phone and id)
 * @param {Object} options
 * @param {string} [options.token] - Apify Token
 * @param {string} [options.locationContext] - For country code inference
 * @param {Function} [options.onLog] - Log callback
 * @returns {Promise<{ success: boolean, updatedLeads?: Array<Object>, verifiedCount?: number, failedCount?: number, error?: string }>}
 */
async function verifyLeadsWhatsApp(leads = [], options = {}) {
  const { token = process.env.APIFY_TOKEN, locationContext = '', onLog = () => {} } = options;
  const log = (msg) => onLog(`[WhatsApp Verification] ${msg}`);

  if (!token) {
    const err = 'Apify API token is required for WhatsApp verification. Please configure APIFY_TOKEN in .env.';
    log(`❌ ${err}`);
    return { success: false, error: err };
  }

  // 1. Filter leads with phone numbers and map to E.164
  const leadPhoneMap = new Map(); // e164 -> Array of lead objects
  const leadsToVerify = [];
  const invalidPhones = [];

  for (const lead of leads) {
    const rawPhone = lead.phone || lead.phoneNumber || '';
    if (!rawPhone) {
      lead.whatsappVerified = false;
      continue;
    }

    const e164 = normalizeToE164(rawPhone, lead.city || locationContext);
    if (!e164) {
      log(`⚠️ Could not format phone "${rawPhone}" for ${lead.name}. Marked as unverified.`);
      lead.whatsappVerified = false;
      invalidPhones.push(lead.id);
      continue;
    }

    lead.normalizedPhone = e164;
    leadsToVerify.push(lead);

    if (!leadPhoneMap.has(e164)) {
      leadPhoneMap.set(e164, []);
    }
    leadPhoneMap.get(e164).push(lead);
  }

  const uniquePhones = Array.from(leadPhoneMap.keys());
  log(`Found ${uniquePhones.length} valid unique phone numbers to check across ${leadsToVerify.length} selected leads.`);

  if (uniquePhones.length === 0) {
    return {
      success: true,
      updatedLeads: leads,
      verifiedCount: 0,
      checkedCount: 0
    };
  }

  const client = new ApifyClient({ token });
  const verificationMap = new Map(); // e164 -> boolean
  const phoneBatches = chunkArray(uniquePhones, 100);

  let batchIndex = 0;
  for (const batch of phoneBatches) {
    batchIndex++;
    log(`Running batch ${batchIndex}/${phoneBatches.length} (${batch.length} numbers) on actor "maged120/whatsapp-number-checker"...`);

    try {
      const input = {
        phone_numbers: batch
      };

      const run = await client.actor('maged120/whatsapp-number-checker').call(input, {
        timeout: 180
      });

      log(`Batch ${batchIndex} actor completed with status: ${run.status}. Fetching results...`);
      const { items } = await client.dataset(run.defaultDatasetId).listItems();

      log(`Received ${items.length} verification results from Apify dataset.`);

      // Process dataset items
      for (const item of items) {
        const rawNum = item.number || item.phone || item.phone_number || item.input_number || '';
        const normalized = normalizeToE164(rawNum, locationContext) || rawNum.replace(/\s+/g, '');
        
        // Determine verification status strictly
        const isVerified = (
          item.hasWhatsApp === true ||
          item.whatsapp === true ||
          item.exists === true ||
          item.isRegistered === true ||
          item.is_whatsapp === true ||
          item.status === 'valid' ||
          item.status === 'VALID' ||
          item.status === 'active' ||
          item.status === 'ACTIVE' ||
          item.registered === true
        );

        if (normalized) {
          verificationMap.set(normalized, isVerified);
        }
      }
    } catch (err) {
      log(`❌ Error checking batch ${batchIndex}: ${err.message}`);
      return { success: false, error: `WhatsApp verification error: ${err.message}` };
    }
  }

  // 2. Update lead verification flags
  let verifiedLeadCount = 0;
  for (const lead of leads) {
    if (lead.normalizedPhone && verificationMap.has(lead.normalizedPhone)) {
      const verified = verificationMap.get(lead.normalizedPhone);
      lead.whatsappVerified = verified === true;
      if (verified) verifiedLeadCount++;
    } else if (lead.whatsappVerified === undefined) {
      lead.whatsappVerified = false;
    }
  }

  const verifiedUniqueCount = Array.from(verificationMap.values()).filter(Boolean).length;
  log(`Verification complete! ${verifiedUniqueCount} of ${uniquePhones.length} unique numbers confirmed active on WhatsApp (${verifiedLeadCount} leads).`);

  return {
    success: true,
    updatedLeads: leads,
    verifiedCount: verifiedUniqueCount,
    verifiedLeadCount,
    checkedCount: uniquePhones.length
  };
}

module.exports = {
  estimateWhatsAppCost,
  verifyLeadsWhatsApp,
  COST_PER_NUMBER_USD
};

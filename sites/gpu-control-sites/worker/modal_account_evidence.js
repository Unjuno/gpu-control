const PRICE_SOURCE = "https://modal.com/pricing";
const EVIDENCE_KEYS = ["charges_usd", "credits_used_usd", "environment", "evidence_id", "expires_at",
  "gpu", "hourly_price_usd", "price_source", "schema_version", "usage_limit_usd", "verified_at", "workspace"];

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function usdToMicrousd(value, decimals) {
  if (typeof value !== "string" || !new RegExp(`^(?:0|[1-9][0-9]*)\\.[0-9]{${decimals}}$`).test(value)) return null;
  const [whole, fraction] = value.split(".");
  return Number(BigInt(whole) * 1_000_000n + BigInt(fraction.padEnd(6, "0")));
}

function ceilMicrousdToCents(value) {
  return Math.floor((value + 9_999) / 10_000);
}

async function sha256(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

/** Validate short-lived, operator-observed Modal account evidence for one exact GPU lane. */
export async function readModalGpuAccountEvidence(env, {
  key = "MODAL_GPU_ACCOUNT_EVIDENCE_JSON", gpu, usageLimitUsd, expectedHourlyMicrousd = null,
  requiredHeadroomMicrousd = 10_000, now = Math.floor(Date.now() / 1000),
} = {}) {
  const raw = env?.[key];
  if (typeof raw !== "string" || raw.length < 2 || raw.length > 4096 ||
      !["T4", "L4"].includes(gpu) || typeof usageLimitUsd !== "string" ||
      !Number.isSafeInteger(requiredHeadroomMicrousd) || requiredHeadroomMicrousd < 0 ||
      !Number.isSafeInteger(now) || now < 0) return null;
  let evidence;
  try { evidence = JSON.parse(raw); } catch { return null; }
  if (!evidence || typeof evidence !== "object" || Array.isArray(evidence) ||
      Object.keys(evidence).sort().join(",") !== EVIDENCE_KEYS.join(",") || evidence.schema_version !== 1 ||
      evidence.workspace !== "unjuno" || evidence.environment !== "main" ||
      evidence.usage_limit_usd !== usageLimitUsd || evidence.gpu !== gpu || evidence.price_source !== PRICE_SOURCE ||
      typeof evidence.evidence_id !== "string" || !/^[0-9a-f]{64}$/.test(evidence.evidence_id) ||
      typeof evidence.credits_used_usd !== "string" || typeof evidence.charges_usd !== "string" ||
      typeof evidence.hourly_price_usd !== "string" ||
      !/^0\.[0-9]{6}$/.test(evidence.hourly_price_usd) ||
      !Number.isSafeInteger(evidence.verified_at) || !Number.isSafeInteger(evidence.expires_at) ||
      evidence.verified_at > now || evidence.expires_at < now ||
      evidence.expires_at <= evidence.verified_at || evidence.expires_at - evidence.verified_at > 3600) return null;
  const usageLimitMicrousd = usdToMicrousd(usageLimitUsd, 2);
  const creditsMicrousd = usdToMicrousd(evidence.credits_used_usd, 2);
  const chargesMicrousd = usdToMicrousd(evidence.charges_usd, 2);
  const hourlyMicrousd = usdToMicrousd(evidence.hourly_price_usd, 6);
  if (usageLimitMicrousd === null || creditsMicrousd === null || chargesMicrousd === null ||
      hourlyMicrousd === null || hourlyMicrousd <= 0 ||
      expectedHourlyMicrousd !== null && hourlyMicrousd !== expectedHourlyMicrousd ||
      creditsMicrousd + chargesMicrousd + requiredHeadroomMicrousd > usageLimitMicrousd) return null;
  const { evidence_id: _evidenceId, ...body } = evidence;
  return await sha256(canonical(body)) === evidence.evidence_id ? evidence : null;
}

export function modalGpuAccountEvidencePriceMicrousd(evidence) {
  return typeof evidence?.hourly_price_usd === "string"
    ? usdToMicrousd(evidence.hourly_price_usd, 6) : null;
}

export function modalGpuAccountEvidenceHeadroomCents(microusd) {
  return Number.isSafeInteger(microusd) && microusd >= 0 ? ceilMicrousdToCents(microusd) : null;
}

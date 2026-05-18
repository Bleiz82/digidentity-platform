/**
 * Sense v0 — deterministic rule-based visitor classification — BIBLE-v3 §6.1.
 *
 * Pure functions: no I/O, no state. Edge-runtime compatible (Web APIs only).
 *
 * Personas scored (map to pack real-estate-luxury personas where applicable):
 *   family_relocating      — school/family/relocation signals
 *   international_investor — investment/ROI/property + cpc signals
 *   luxury_retiree         — lifestyle/wellness/resort signals
 *   holiday_seeker         — vacation/holiday/rent signals
 *   browsing               — default / no strong signal
 */

import type {
  DeviceSignal,
  DeviceType,
  PersonaScore,
  ReferrerSignal,
  ReferrerType,
  UtmSignal,
} from "./types";

// ── UTM ───────────────────────────────────────────────────────────────────────

export function parseUtm(searchParams: URLSearchParams): Record<string, string> {
  const keys: (keyof UtmSignal)[] = [
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
  ];
  const result: Record<string, string> = {};
  for (const key of keys) {
    const val = searchParams.get(key);
    if (val) result[key] = val;
  }
  return result;
}

// ── Referrer ──────────────────────────────────────────────────────────────────

const _ORGANIC = ["google", "bing", "yahoo", "duckduckgo", "yandex", "baidu"];
const _SOCIAL = [
  "facebook",
  "instagram",
  "twitter",
  "x.com",
  "linkedin",
  "tiktok",
  "pinterest",
  "youtube",
];

export function parseReferrer(referer: string | null | undefined): ReferrerSignal {
  if (!referer) return { referrer_domain: "", referrer_type: "direct" };

  let hostname: string;
  try {
    hostname = new URL(referer).hostname.replace(/^www\./, "");
  } catch {
    return { referrer_domain: "", referrer_type: "direct" };
  }

  let referrer_type: ReferrerType = "referral";
  if (_ORGANIC.some((d) => hostname.includes(d))) referrer_type = "organic";
  else if (_SOCIAL.some((d) => hostname.includes(d))) referrer_type = "social";

  return { referrer_domain: hostname, referrer_type };
}

// ── Device ────────────────────────────────────────────────────────────────────

export function parseDevice(userAgent: string): DeviceSignal {
  const ua = userAgent;

  let device_type: DeviceType = "desktop";
  if (/iPad|Android.*Tablet|Tablet/i.test(ua)) {
    device_type = "tablet";
  } else if (/iPhone|Android|Mobile|BlackBerry|Windows Phone/i.test(ua)) {
    device_type = "mobile";
  }

  let os = "unknown";
  if (/Windows/i.test(ua)) os = "windows";
  else if (/iPhone|iPad/i.test(ua)) os = "ios";
  else if (/Android/i.test(ua)) os = "android";
  else if (/Macintosh|Mac OS X/i.test(ua)) os = "macos";
  else if (/Linux/i.test(ua)) os = "linux";

  let browser = "unknown";
  if (/Edg\//i.test(ua)) browser = "edge";
  else if (/Chrome/i.test(ua) && !/Chromium/i.test(ua)) browser = "chrome";
  else if (/Firefox/i.test(ua)) browser = "firefox";
  else if (/Safari/i.test(ua) && !/Chrome/i.test(ua)) browser = "safari";

  return { device_type, os, browser };
}

// ── Persona inference ─────────────────────────────────────────────────────────

interface SenseContext {
  utm: Record<string, string>;
  referrer: ReferrerSignal;
  device: DeviceSignal;
}

export function inferPersona(ctx: SenseContext): PersonaScore[] {
  const src = (ctx.utm.utm_source ?? "").toLowerCase();
  const term = (ctx.utm.utm_term ?? "").toLowerCase();
  const campaign = (ctx.utm.utm_campaign ?? "").toLowerCase();
  const medium = (ctx.utm.utm_medium ?? "").toLowerCase();

  const scores: Record<string, number> = {
    international_investor: 0,
    family_relocating: 0,
    luxury_retiree: 0,
    holiday_seeker: 0,
    browsing: 0.1,
  };

  // international_investor signals
  if (/invest|roi|yield|rendimento|capital/.test(term)) scores.international_investor += 0.5;
  if (/invest|roi/.test(campaign)) scores.international_investor += 0.3;
  if (medium === "cpc" && /invest|property|immobil/.test(term))
    scores.international_investor += 0.2;
  if (src === "linkedin" && /invest|real.?estate/.test(term))
    scores.international_investor += 0.2;

  // family_relocating signals
  if (/school|scuola|famil|bambini|kids/.test(term)) scores.family_relocating += 0.5;
  if (/school|famil|relocat|trasferiment/.test(campaign)) scores.family_relocating += 0.4;
  if (/relocat|move|sposta/.test(term)) scores.family_relocating += 0.2;

  // luxury_retiree signals
  if (/lifestyle|wellness|resort|pensionat|retiree|concierge/.test(term))
    scores.luxury_retiree += 0.5;
  if (/lifestyle|wellness|luxury/.test(campaign)) scores.luxury_retiree += 0.3;
  if (ctx.referrer.referrer_type === "organic" && /villa|luxury|esclusiv/.test(term))
    scores.luxury_retiree += 0.2;

  // holiday_seeker signals
  if (/holiday|vacation|vacanza|ferie|rent|affitto/.test(term))
    scores.holiday_seeker += 0.5;
  if (/holiday|summer|estate|vacanza/.test(campaign)) scores.holiday_seeker += 0.3;

  // browsing: no strong signal → default
  const maxScore = Math.max(...Object.values(scores));
  if (maxScore <= 0.1) scores.browsing = 0.5;

  return Object.entries(scores)
    .filter(([, s]) => s > 0)
    .sort(([, a], [, b]) => b - a)
    .map(([persona_id, score]) => ({
      persona_id,
      score: Math.min(1.0, Math.round(score * 100) / 100),
    }));
}

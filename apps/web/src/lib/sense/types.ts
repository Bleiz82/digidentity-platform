/**
 * Sense engine types — mirrors Python SenseSignals + PersonaScore (BIBLE-v3 §7.1).
 * Compatible with VisitorPriorInput in types/rendering.ts.
 */

export type DeviceType = "mobile" | "tablet" | "desktop";

export type ReferrerType = "organic" | "social" | "direct" | "paid" | "referral";

export interface UtmSignal {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_term?: string;
  utm_content?: string;
}

export interface ReferrerSignal {
  referrer_domain: string;
  referrer_type: ReferrerType;
}

export interface DeviceSignal {
  device_type: DeviceType;
  os: string;
  browser: string;
}

export interface PersonaScore {
  persona_id: string;
  score: number;
}

export interface SenseSignals {
  device_class: DeviceType;
  utm: Record<string, string>;
  is_returning: boolean;
  referrer?: string | null;
  geo_city?: string | null;
  language?: string | null;
}

/** Full VisitorPrior — mirrors BIBLE §7.1 / schemas/visitor.py */
export interface VisitorPrior {
  session_id: string;
  tenant_id: string;
  visitor_hash: string;
  inferred_personas: PersonaScore[];
  signals: SenseSignals;
  confidence: number;
  created_at: string;
  updated_at: string;
}

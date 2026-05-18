import { describe, it, expect } from "vitest";
import { parseUtm, parseReferrer, parseDevice, inferPersona } from "@/lib/sense/rules";

// ── parseUtm ─────────────────────────────────────────────────────────────────

describe("parseUtm", () => {
  it("extracts known utm keys", () => {
    const p = new URLSearchParams("utm_source=google&utm_medium=cpc&utm_campaign=invest");
    const result = parseUtm(p);
    expect(result).toEqual({ utm_source: "google", utm_medium: "cpc", utm_campaign: "invest" });
  });

  it("ignores unknown keys and returns empty for blank params", () => {
    const p = new URLSearchParams("foo=bar");
    expect(parseUtm(p)).toEqual({});
  });
});

// ── parseReferrer ─────────────────────────────────────────────────────────────

describe("parseReferrer", () => {
  it("classifies google as organic", () => {
    const r = parseReferrer("https://www.google.com/search?q=villa");
    expect(r.referrer_type).toBe("organic");
    expect(r.referrer_domain).toBe("google.com");
  });

  it("classifies instagram as social", () => {
    const r = parseReferrer("https://instagram.com/p/abc123");
    expect(r.referrer_type).toBe("social");
  });

  it("returns direct for null referrer", () => {
    const r = parseReferrer(null);
    expect(r.referrer_type).toBe("direct");
    expect(r.referrer_domain).toBe("");
  });

  it("returns referral for unknown domain", () => {
    const r = parseReferrer("https://someportal.it/listing/123");
    expect(r.referrer_type).toBe("referral");
  });
});

// ── parseDevice ───────────────────────────────────────────────────────────────

describe("parseDevice", () => {
  it("detects mobile from iPhone UA", () => {
    const ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15";
    const d = parseDevice(ua);
    expect(d.device_type).toBe("mobile");
    expect(d.os).toBe("ios");
  });

  it("detects desktop from Chrome/Windows UA", () => {
    const ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36";
    const d = parseDevice(ua);
    expect(d.device_type).toBe("desktop");
    expect(d.os).toBe("windows");
    expect(d.browser).toBe("chrome");
  });
});

// ── inferPersona ──────────────────────────────────────────────────────────────

describe("inferPersona", () => {
  const base = { referrer: { referrer_domain: "", referrer_type: "direct" as const }, device: { device_type: "desktop" as const, os: "windows", browser: "chrome" } };

  it("scores international_investor for invest term", () => {
    const scores = inferPersona({ ...base, utm: { utm_term: "invest" } });
    expect(scores[0].persona_id).toBe("international_investor");
    expect(scores[0].score).toBeGreaterThan(0.4);
  });

  it("defaults to browsing when no signals", () => {
    const scores = inferPersona({ ...base, utm: {} });
    expect(scores[0].persona_id).toBe("browsing");
  });

  it("caps scores at 1.0", () => {
    const scores = inferPersona({ ...base, utm: { utm_term: "invest roi rendimento", utm_campaign: "invest roi", utm_medium: "cpc" } });
    for (const s of scores) {
      expect(s.score).toBeLessThanOrEqual(1.0);
    }
  });
});

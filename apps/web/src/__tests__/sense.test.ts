import { describe, it, expect, vi, afterEach } from "vitest";
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

  it("returns only canonical persona ids — no legacy ids like luxury_investor or business_traveler", () => {
    const legacyIds = new Set(["luxury_investor", "business_traveler"]);
    const canonicalIds = new Set([
      "international_investor",
      "family_relocating",
      "luxury_retiree",
      "holiday_seeker",
      "browsing",
    ]);
    const inputs: Array<{ utm: Record<string, string> }> = [
      { utm: { utm_term: "invest roi" } },
      { utm: { utm_term: "school famil" } },
      { utm: { utm_term: "lifestyle wellness" } },
      { utm: { utm_term: "holiday vacation" } },
      { utm: {} },
    ];
    for (const utm of inputs) {
      const scores = inferPersona({ ...base, ...utm });
      for (const s of scores) {
        expect(legacyIds.has(s.persona_id)).toBe(false);
        expect(canonicalIds.has(s.persona_id)).toBe(true);
      }
    }
  });
});

// ── useVisitorPrior upsert call ───────────────────────────────────────────────

describe("useVisitorPrior persistToBackend", () => {
  afterEach(() => vi.restoreAllMocks());

  it("calls /api/v1/visitor-sessions/upsert with visitor data from cookie", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ session_id: "abc", is_new: true, last_seen_at: "2026-01-01T00:00:00Z" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    const prior = {
      session_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      tenant_id: "00000000-0000-0000-0000-000000000001",
      visitor_hash: "abcdef1234567890abcdef12",
      inferred_personas: [{ persona_id: "browsing", score: 0.5 }],
      signals: { device_class: "desktop" as const, utm: {}, is_returning: false },
      confidence: 0.5,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };

    // Invoke persistToBackend by importing the module
    const mod = await import("../hooks/useVisitorPrior");
    // Access via the exported function indirectly — call the hook in a controlled way
    // by mocking cookie and checking fetch was called
    vi.spyOn(
      await import("@/lib/sense/client"),
      "readVisitorPriorFromCookie"
    ).mockReturnValue(prior);

    // Trigger the effect manually
    const { renderHook } = await import("@testing-library/react");
    const { act } = await import("react");
    const { result } = renderHook(() => mod.useVisitorPrior());
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(fetchSpy).toHaveBeenCalledOnce();
    const [url, opts] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/visitor-sessions/upsert");
    expect((opts.headers as Record<string, string>)["X-Tenant-Id"]).toBe(prior.tenant_id);
    const body = JSON.parse(opts.body as string);
    expect(body.visitor_id).toBe(prior.session_id);
  });
});

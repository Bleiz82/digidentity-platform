"use client";

/**
 * /demo/adaptive — interactive demo for the Adaptive Renderer Decision Engine.
 * Simulates VisitorPrior (persona + utm_source) and shows live morphing output.
 * Press D to open the debug panel.
 */

import { useState, useMemo } from "react";
import { useAdaptiveRender } from "@/hooks/useAdaptiveRender";
import { AdaptiveSection } from "@/components/AdaptiveSection";
import { DirectiveDebugPanel } from "@/components/DirectiveDebugPanel";
import type { VisitorPriorInput } from "@/types/rendering";

const PACK_ID = "real-estate-luxury";
const DEMO_TENANT = "00000000-0000-0000-0000-000000000001";

type PersonaKey =
  | "none"
  | "family_relocating"
  | "international_investor"
  | "luxury_retiree";

const PERSONA_LABELS: Record<PersonaKey, string> = {
  none: "— nessuna (default layout) —",
  family_relocating: "Famiglia in trasferimento",
  international_investor: "Investitore internazionale",
  luxury_retiree: "Pensionato lifestyle",
};

export default function AdaptiveDemoPage() {
  const [persona, setPersona] = useState<PersonaKey>("none");
  const [utmSource, setUtmSource] = useState("");
  // Stable session + creation time for the lifetime of this page load
  const [sessionId] = useState<string>(() => crypto.randomUUID());
  const [createdAt] = useState<string>(() => new Date().toISOString());

  const prior: VisitorPriorInput = useMemo(
    () => ({
      session_id: sessionId,
      tenant_id: DEMO_TENANT,
      visitor_hash: "demo1234567890ab",
      inferred_personas:
        persona !== "none" ? [{ persona_id: persona, score: 0.9 }] : [],
      signals: {
        device_class: "desktop",
        utm: (utmSource ? { source: utmSource } : {}) as Record<string, string>,
        is_returning: false,
      },
      confidence: 0.8,
      created_at: createdAt,
      updated_at: new Date().toISOString(),
    }),
    // session stays stable; refetch only when persona or utm changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sessionId, persona, utmSource]
  );

  const { directives, matched_rules, loading, error, latency_ms } =
    useAdaptiveRender(prior, "homepage", PACK_ID);

  const heroMorph = directives.find(
    (d) => d.target === "hero_section" && d.type === "morph_section"
  );

  return (
    <main className="min-h-screen bg-gray-950 text-white p-8">
      <h1 className="text-2xl font-bold mb-2">Adaptive Renderer Demo</h1>
      <p className="text-gray-500 text-sm mb-8">
        BIBLE-v3 §6.2 — Decision Engine backend + RSC morph skeleton
      </p>

      {/* Simulator */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8 max-w-lg">
        <h2 className="text-base font-semibold mb-4 text-gray-300">
          Simula VisitorPrior
        </h2>

        <label className="block mb-1 text-xs text-gray-400 uppercase tracking-wide">
          Persona
        </label>
        <select
          value={persona}
          onChange={(e) => setPersona(e.target.value as PersonaKey)}
          className="w-full bg-gray-800 text-white rounded-lg px-3 py-2 mb-4 border border-gray-700 focus:outline-none focus:border-green-500"
        >
          {(Object.keys(PERSONA_LABELS) as PersonaKey[]).map((k) => (
            <option key={k} value={k}>
              {PERSONA_LABELS[k]}
            </option>
          ))}
        </select>

        <label className="block mb-1 text-xs text-gray-400 uppercase tracking-wide">
          UTM Source
        </label>
        <input
          type="text"
          value={utmSource}
          onChange={(e) => setUtmSource(e.target.value)}
          placeholder="google, instagram, luxury-search…"
          className="w-full bg-gray-800 text-white rounded-lg px-3 py-2 border border-gray-700 focus:outline-none focus:border-green-500"
        />

        <div className="mt-4 min-h-5 text-xs">
          {loading && <span className="text-yellow-400">⏳ Fetching directives…</span>}
          {error && <span className="text-red-400">Error: {error}</span>}
          {!loading && !error && latency_ms !== null && (
            <span className="text-green-400">
              ✓ {directives.length} directive(s) · {latency_ms.toFixed(1)}ms
              {matched_rules.length > 0 && (
                <span className="text-gray-400"> · {matched_rules.join(", ")}</span>
              )}
            </span>
          )}
        </div>

        <p className="mt-3 text-xs text-gray-600">
          Press <kbd className="bg-gray-800 px-1 rounded">D</kbd> for debug panel
        </p>
      </div>

      {/* Morphable sections */}
      <div className="space-y-4 max-w-2xl">
        <AdaptiveSection
          sectionId="hero_section"
          directives={directives}
          className="bg-gray-800 border border-gray-700 rounded-xl p-6"
        >
          <h2 className="text-lg font-semibold">
            {heroMorph
              ? `Hero → ${heroMorph.params.template as string}`
              : "Hero Section — Default"}
          </h2>
          <p className="text-gray-400 mt-1 text-sm">
            Benvenuto nel Living Site.
          </p>
        </AdaptiveSection>

        <AdaptiveSection
          sectionId="school_proximity_badge"
          directives={directives}
          className="bg-emerald-900/30 border border-emerald-800/50 rounded-xl p-4 text-sm"
        >
          🏫 Scuole nelle vicinanze — top 3 rated
        </AdaptiveSection>

        <AdaptiveSection
          sectionId="investment_roi_widget"
          directives={directives}
          className="bg-blue-900/30 border border-blue-800/50 rounded-xl p-4 text-sm"
        >
          📈 ROI stimato: 4–6% annuo · Costa Smeralda
        </AdaptiveSection>

        <AdaptiveSection
          sectionId="above_fold_slot"
          directives={directives}
          className="bg-violet-900/30 border border-violet-800/50 rounded-xl p-4 text-sm"
        >
          ✨ Above the fold slot
        </AdaptiveSection>
      </div>

      <DirectiveDebugPanel
        directives={directives}
        matched_rules={matched_rules}
        latency_ms={latency_ms}
      />
    </main>
  );
}

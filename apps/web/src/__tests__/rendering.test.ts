import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, renderHook, waitFor, fireEvent } from "@testing-library/react";
import { createElement } from "react";

// ── 1. Zod schema: decideResponseSchema parses valid backend payload ───────────

import { decideResponseSchema } from "@/types/rendering";

describe("decideResponseSchema", () => {
  it("parses a valid backend DecideResponse", () => {
    const raw = {
      directives: [
        {
          type: "morph_section",
          target: "hero_section",
          params: { template: "family_hero_v1" },
          priority: 100,
          reason: "rule:family-relocating-hero",
        },
      ],
      matched_rules: ["family-relocating-hero"],
      latency_ms: 14.6,
    };
    const result = decideResponseSchema.parse(raw);
    expect(result.matched_rules).toEqual(["family-relocating-hero"]);
    expect(result.directives).toHaveLength(1);
    expect(result.directives[0].type).toBe("morph_section");
    expect(result.directives[0].params).toEqual({ template: "family_hero_v1" });
    expect(result.latency_ms).toBe(14.6);
  });

  it("rejects unknown directive type", () => {
    expect(() =>
      decideResponseSchema.parse({
        directives: [{ type: "flash_banner", target: "x", params: {}, priority: 100, reason: "r" }],
        matched_rules: [],
        latency_ms: 1,
      })
    ).toThrow();
  });
});

// ── 2. useAdaptiveRender: loading → success ───────────────────────────────────

vi.mock("@/lib/rendering-client", () => ({
  fetchDirectives: vi.fn(),
}));

import { fetchDirectives } from "@/lib/rendering-client";
import { useAdaptiveRender } from "@/hooks/useAdaptiveRender";
import type { RenderingDirective } from "@/types/rendering";

const mockFetch = vi.mocked(fetchDirectives);

const _now = new Date().toISOString();
const _prior = {
  session_id: "sess-abc",
  tenant_id: "tenant-1",
  visitor_hash: "abcdef1234567890",
  inferred_personas: [{ persona_id: "family_relocating", score: 0.9 }],
  signals: { device_class: "desktop", utm: {}, is_returning: false },
  confidence: 0.8,
  created_at: _now,
  updated_at: _now,
};

describe("useAdaptiveRender", () => {
  beforeEach(() => vi.clearAllMocks());

  it("transitions from loading to success with directives", async () => {
    const mockDirectives: RenderingDirective[] = [
      { type: "show", target: "hero_section", params: {}, priority: 100, reason: "rule:test" },
    ];
    mockFetch.mockResolvedValueOnce({
      directives: mockDirectives,
      matched_rules: ["test-rule"],
      latency_ms: 5.2,
    });

    const { result } = renderHook(() =>
      useAdaptiveRender(_prior, "homepage", "real-estate-luxury")
    );

    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.directives).toEqual(mockDirectives);
    expect(result.current.matched_rules).toEqual(["test-rule"]);
    expect(result.current.latency_ms).toBe(5.2);
    expect(result.current.error).toBeNull();
  });

  it("sets error state when fetchDirectives rejects", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    const { result } = renderHook(() =>
      useAdaptiveRender(_prior, "homepage", "real-estate-luxury")
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Network error");
    expect(result.current.directives).toHaveLength(0);
  });
});

// ── 3 & 4. AdaptiveSection: show/hide + morph_section ────────────────────────

import { AdaptiveSection } from "@/components/AdaptiveSection";

describe("AdaptiveSection", () => {
  it("hides the section when a hide directive targets it", () => {
    const directives: RenderingDirective[] = [
      { type: "hide", target: "investment_roi_widget", params: {}, priority: 100, reason: "r" },
    ];
    const { container } = render(
      createElement(
        AdaptiveSection,
        { sectionId: "investment_roi_widget", directives },
        createElement("span", null, "ROI widget")
      )
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows the section when a show directive targets it (no hide)", () => {
    const directives: RenderingDirective[] = [
      { type: "show", target: "school_proximity_badge", params: {}, priority: 100, reason: "r" },
    ];
    render(
      createElement(
        AdaptiveSection,
        { sectionId: "school_proximity_badge", directives },
        createElement("span", null, "School badge")
      )
    );
    expect(screen.getByText("School badge")).not.toBeNull();
  });

  it("applies morph_section variant via data-variant attribute", () => {
    const directives: RenderingDirective[] = [
      {
        type: "morph_section",
        target: "hero_section",
        params: { template: "family_hero_v1" },
        priority: 100,
        reason: "r",
      },
    ];
    render(
      createElement(
        AdaptiveSection,
        { sectionId: "hero_section", directives },
        createElement("span", null, "Hero content")
      )
    );
    const section = screen.getByText("Hero content").closest("section");
    expect(section?.getAttribute("data-variant")).toBe("family_hero_v1");
  });
});

// ── 5. DirectiveDebugPanel: shows latency on keydown D ───────────────────────

import { DirectiveDebugPanel } from "@/components/DirectiveDebugPanel";

describe("DirectiveDebugPanel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows latency_ms in the debug panel after pressing D", () => {
    render(
      createElement(DirectiveDebugPanel, {
        directives: [],
        matched_rules: ["family-relocating-hero"],
        latency_ms: 42.75,
      })
    );

    // Panel hidden initially
    expect(screen.queryByTestId("debug-panel")).toBeNull();

    // Press D to show
    fireEvent.keyDown(window, { key: "d" });

    expect(screen.getByTestId("debug-panel")).not.toBeNull();
    expect(screen.getByTestId("latency").textContent).toBe("42.75ms");
  });
});

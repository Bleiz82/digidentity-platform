import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSpatialSync } from "@/hooks/useSpatialSync";
import type { SceneId } from "@/hooks/useSpatialSync";

// ── Mock EventSource ──────────────────────────────────────────────────────────

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  close() {}

  emit(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }

  emitError() {
    this.onerror?.(new Event("error"));
  }
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
  vi.stubGlobal("crypto", {
    randomUUID: () => "test-uuid-" + Math.random().toString(36).slice(2),
  });
});

// ── 1. useSpatialSync: initial state ─────────────────────────────────────────

describe("useSpatialSync", () => {
  it("initialises with the provided scene and idle stream state", () => {
    const { result } = renderHook(() =>
      useSpatialSync("master-suite" as SceneId),
    );

    expect(result.current.activeScene).toBe("master-suite");
    expect(result.current.streamState).toBe("idle");
    expect(result.current.messages).toHaveLength(0);
    expect(result.current.currentStreaming).toBe("");
  });

  it("defaults to villa-entrance when no initialScene provided", () => {
    const { result } = renderHook(() => useSpatialSync());
    expect(result.current.activeScene).toBe("villa-entrance");
  });

  // ── 2. useSpatialSync: scene update from tool_result ─────────────────────

  it("updates activeScene when a spatial_navigate tool_result arrives", () => {
    const { result } = renderHook(() => useSpatialSync("villa-entrance"));

    act(() => {
      result.current.sendMessage("mostrami la piscina");
    });

    const es = MockEventSource.instances[0];
    expect(es).toBeDefined();

    act(() => {
      es.emit({
        type: "tool_result",
        data: {
          name: "spatial_navigate",
          tool_use_id: "tu-001",
          result: {
            emitted: true,
            scene_id: "infinity-pool",
            directive: {
              type: "spatial_navigate",
              target: "infinity-pool",
              params: { target_scene_id: "infinity-pool", transition: "fade" },
              priority: 200,
              reason: "visitor asked about pool",
            },
          },
        },
      });
    });

    expect(result.current.activeScene).toBe("infinity-pool");
  });

  // ── 3. useSpatialSync: ignores tool_result for other tools ───────────────

  it("does not change scene for non-spatial_navigate tool_result events", () => {
    const { result } = renderHook(() => useSpatialSync("master-suite"));

    act(() => {
      result.current.sendMessage("cerca ville");
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es.emit({
        type: "tool_result",
        data: {
          name: "kg_search",
          tool_use_id: "tu-002",
          result: { query: "villa lusso", results: [] },
        },
      });
    });

    expect(result.current.activeScene).toBe("master-suite"); // unchanged
  });

  // ── 4. useSpatialSync: text accumulation and done ────────────────────────

  it("accumulates text events and finalises message on done", () => {
    const { result } = renderHook(() => useSpatialSync());

    act(() => {
      result.current.sendMessage("ciao");
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es.emit({ type: "text", data: { text: "Villa " } });
      es.emit({ type: "text", data: { text: "Cervo." } });
    });

    expect(result.current.currentStreaming).toBe("Villa Cervo.");

    act(() => {
      es.emit({ type: "done", data: { iterations: 1, lead_score: 0.1 } });
    });

    expect(result.current.currentStreaming).toBe("");
    expect(result.current.streamState).toBe("complete");
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[1].role).toBe("assistant");
    expect(result.current.messages[1].content).toBe("Villa Cervo.");
  });
});

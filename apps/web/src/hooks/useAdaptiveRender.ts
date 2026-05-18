"use client";

/**
 * Hook that fetches RenderingDirectives from the Decision Engine — BIBLE-v3 §6.2.
 * Re-fetches when session_id, target_page, or pack_id change.
 */

import { useState, useEffect } from "react";
import { fetchDirectives } from "@/lib/rendering-client";
import type { RenderingDirective, VisitorPriorInput } from "@/types/rendering";

export interface AdaptiveRenderState {
  directives: RenderingDirective[];
  matched_rules: string[];
  loading: boolean;
  error: string | null;
  latency_ms: number | null;
}

export function useAdaptiveRender(
  prior: VisitorPriorInput | null,
  target_page: string,
  pack_id: string
): AdaptiveRenderState {
  const [state, setState] = useState<AdaptiveRenderState>({
    directives: [],
    matched_rules: [],
    loading: false,
    error: null,
    latency_ms: null,
  });

  // Depend on session_id scalar — avoids effect loops from object identity changes
  const sessionId = prior?.session_id ?? null;

  useEffect(() => {
    if (!prior) return;

    setState((s) => ({ ...s, loading: true, error: null }));

    fetchDirectives(prior, target_page, pack_id, prior.tenant_id)
      .then((data) => {
        setState({
          directives: data.directives,
          matched_rules: data.matched_rules,
          loading: false,
          error: null,
          latency_ms: data.latency_ms,
        });
      })
      .catch((err: Error) => {
        setState((s) => ({ ...s, loading: false, error: err.message }));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, target_page, pack_id]);

  return state;
}

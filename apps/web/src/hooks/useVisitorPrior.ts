import { useState, useEffect } from "react";
import { readVisitorPriorFromCookie } from "@/lib/sense/client";
import type { VisitorPrior } from "@/lib/sense/types";

const DEMO_TENANT = "00000000-0000-0000-0000-000000000001";

function makeFallback(): VisitorPrior {
  const now = new Date().toISOString();
  return {
    session_id: crypto.randomUUID(),
    tenant_id: DEMO_TENANT,
    visitor_hash: "fallback0000000000000000",
    inferred_personas: [{ persona_id: "browsing", score: 0.5 }],
    signals: {
      device_class: "desktop",
      utm: {},
      is_returning: false,
    },
    confidence: 0.1,
    created_at: now,
    updated_at: now,
  };
}

export function useVisitorPrior(): VisitorPrior {
  const [prior, setPrior] = useState<VisitorPrior>(makeFallback);

  useEffect(() => {
    const fromCookie = readVisitorPriorFromCookie();
    if (fromCookie) setPrior(fromCookie);
  }, []);

  return prior;
}

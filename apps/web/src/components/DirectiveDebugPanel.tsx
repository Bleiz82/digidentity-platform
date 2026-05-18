"use client";

/**
 * Dev-mode overlay showing matched rules, latency, and directives.
 * Toggle with keyboard key "D". Hidden in production by convention (no env check here —
 * caller should conditionally render based on NODE_ENV).
 */

import { useState, useEffect } from "react";
import type { RenderingDirective } from "@/types/rendering";

interface DirectiveDebugPanelProps {
  directives: RenderingDirective[];
  matched_rules: string[];
  latency_ms: number | null;
}

export function DirectiveDebugPanel({
  directives,
  matched_rules,
  latency_ms,
}: DirectiveDebugPanelProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "d" || e.key === "D") {
        setVisible((v) => !v);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  if (!visible) return null;

  return (
    <div
      data-testid="debug-panel"
      style={{
        position: "fixed",
        bottom: 16,
        right: 16,
        background: "rgba(0,0,0,0.88)",
        color: "#4ade80",
        padding: "16px 20px",
        borderRadius: 10,
        fontFamily: "monospace",
        fontSize: 12,
        maxWidth: 420,
        zIndex: 9999,
        overflowY: "auto",
        maxHeight: "60vh",
        boxShadow: "0 0 20px rgba(74,222,128,0.2)",
      }}
    >
      <div style={{ fontWeight: "bold", marginBottom: 8, fontSize: 13 }}>
        Adaptive Renderer Debug
      </div>
      <div>
        Latency:{" "}
        <span data-testid="latency" style={{ color: "#fff" }}>
          {latency_ms !== null ? `${latency_ms.toFixed(2)}ms` : "—"}
        </span>
      </div>
      <div style={{ marginTop: 4 }}>
        Matched rules:{" "}
        <span style={{ color: "#fff" }}>
          {matched_rules.length > 0 ? matched_rules.join(", ") : "none"}
        </span>
      </div>
      <div style={{ marginTop: 8, borderTop: "1px solid #4ade8040", paddingTop: 8 }}>
        Directives ({directives.length}):
      </div>
      {directives.map((d, i) => (
        <div
          key={i}
          style={{
            paddingLeft: 8,
            borderLeft: "2px solid #4ade80",
            marginTop: 4,
            color: "#fff",
          }}
        >
          <span style={{ color: "#4ade80" }}>[{d.type}]</span> {d.target}
          {d.params && Object.keys(d.params).length > 0 && (
            <span style={{ color: "#a3a3a3" }}>
              {" "}
              {JSON.stringify(d.params).slice(0, 60)}
            </span>
          )}
        </div>
      ))}
      <div style={{ marginTop: 10, fontSize: 10, color: "#6b7280" }}>
        Press D to close
      </div>
    </div>
  );
}

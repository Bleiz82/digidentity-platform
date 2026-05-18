"use client";

/**
 * Wrapper component that applies RenderingDirectives to its children — BIBLE-v3 §6.2.
 *
 * Supported directives (by target matching sectionId):
 *   hide          → returns null (section removed from DOM)
 *   show          → explicitly visible (overrides default hidden CSS, if any)
 *   morph_section → sets data-variant attribute for CSS/variant switching
 *   inject        → renders placeholder divs for prepend/append slots
 *   reorder       → TODO: STEP 9d (requires DOM patch layer)
 *   rewrite_copy  → TODO: STEP 9d (requires copy variant registry)
 *   trigger_agent → TODO: STEP 10 (requires agent loop)
 *   track         → TODO: STEP 11 (requires analytics layer)
 */

import { useMemo, type ReactNode } from "react";
import type { RenderingDirective } from "@/types/rendering";

interface AdaptiveSectionProps {
  sectionId: string;
  directives: RenderingDirective[];
  children: ReactNode;
  className?: string;
}

export function AdaptiveSection({
  sectionId,
  directives,
  children,
  className,
}: AdaptiveSectionProps) {
  const mine = useMemo(
    () => directives.filter((d) => d.target === sectionId),
    [directives, sectionId]
  );

  const isHidden = mine.some((d) => d.type === "hide");
  const isShown = mine.some((d) => d.type === "show");
  const morphSection = mine.find((d) => d.type === "morph_section");
  const prepends = mine.filter(
    (d) => d.type === "inject" && d.params?.position === "prepend"
  );
  const appends = mine.filter(
    (d) => d.type === "inject" && d.params?.position === "append"
  );

  // hide wins unless an explicit show overrides it
  if (isHidden && !isShown) return null;

  const variant = morphSection?.params?.template as string | undefined;

  return (
    <section
      id={sectionId}
      className={className}
      data-variant={variant ?? undefined}
      data-directives={mine.length || undefined}
    >
      {prepends.map((d, i) => (
        <div
          key={`pre-${i}`}
          data-injected={d.params?.component as string | undefined}
          data-slot="prepend"
        />
      ))}
      {children}
      {appends.map((d, i) => (
        <div
          key={`app-${i}`}
          data-injected={d.params?.component as string | undefined}
          data-slot="append"
        />
      ))}
    </section>
  );
}

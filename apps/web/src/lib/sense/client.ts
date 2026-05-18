import type { VisitorPrior } from "./types";

const COOKIE_NAME = "dg_visitor_prior";

export function readVisitorPriorFromCookie(): VisitorPrior | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${COOKIE_NAME}=`));
  if (!match) return null;
  try {
    return JSON.parse(decodeURIComponent(match.slice(COOKIE_NAME.length + 1))) as VisitorPrior;
  } catch {
    return null;
  }
}

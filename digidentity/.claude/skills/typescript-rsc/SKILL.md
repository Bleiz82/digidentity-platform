---
name: typescript-rsc
description: React Server Components patterns for DigIdentity frontend — Next.js 15 + React 19. Covers Server/Client boundary, data fetching, streaming RSC, Tailwind 4 conventions, and the Adaptive Renderer client integration.
---

# TypeScript + RSC Patterns

DigIdentity frontend uses Next.js 15 App Router with React Server Components. This is the canonical playbook.

## Stack baseline

- Next.js 15 (App Router, React 19)
- TypeScript 5.x, strict mode
- Tailwind CSS 4
- Biome (lint + format, single tool)
- React Three Fiber + drei for Spatial Engine
- Marzipano (vanilla) wrapped in a client component
- @livekit/components-react for voice

## Server vs Client component decision

Default to Server Components. Client components are an exception, not the rule.

**Server Component (default, no directive)** — use when:
- Fetching data from KG.
- Rendering content that doesn't need interactivity.
- Loading heavy libraries that would bloat the client bundle.
- Reading server-only secrets or env.

**Client Component (`"use client"` at file top)** — use when:
- Need `useState`, `useEffect`, event handlers.
- Need browser APIs (window, navigator).
- Listening to SSE/WebSocket.
- Rendering Three.js or Marzipano (need DOM).
- Receiving streamed agent directives.

## Project structure (Next.js App Router)

```
app/
├── [tenant_slug]/
│   ├── layout.tsx                  # tenant-aware root layout (server)
│   ├── page.tsx                    # homepage entry, runs morph
│   ├── properties/
│   │   ├── page.tsx                # listing index (server, SSR'd)
│   │   └── [slug]/
│   │       ├── page.tsx            # property detail (server)
│   │       └── _components/
│   │           ├── InhabitClient.tsx   # client: Marzipano + chat overlay
│   │           └── PropertyHero.tsx     # server: SSR'd hero
│   ├── api/
│   │   └── (proxied to backend or used for Next.js route handlers)
│   └── _morph/
│       ├── render.ts               # server: resolve VisitorPrior → render plan
│       └── apply.ts                # server: apply directives to component tree
├── _components/
│   ├── ChatStream.tsx              # client: SSE consumer
│   └── DirectiveApplier.tsx        # client: apply runtime directives
├── _lib/
│   ├── kg/                         # server-only: KG client
│   ├── sense/                      # server: bridge to Edge Sense
│   └── morph/                      # shared types
└── _types/
    ├── morph.ts                    # generated from morph_rule.schema.json
    └── api.ts                      # generated from backend OpenAPI
```

## Tenant scoping in routes

The first path segment is `[tenant_slug]`. The root layout resolves the tenant once and passes `tenantId` down via a typed Context:

```tsx
// app/[tenant_slug]/layout.tsx
import { resolveTenant } from "@/_lib/tenant";
import { TenantProvider } from "@/_lib/tenant/context";
import { notFound } from "next/navigation";

export default async function TenantLayout({
  params,
  children,
}: {
  params: Promise<{ tenant_slug: string }>;
  children: React.ReactNode;
}) {
  const { tenant_slug } = await params;
  const tenant = await resolveTenant(tenant_slug);
  if (!tenant) notFound();

  return (
    <TenantProvider tenant={tenant}>
      <html lang={tenant.defaultLocale}>
        <body>{children}</body>
      </html>
    </TenantProvider>
  );
}
```

## Adaptive Renderer integration on the server

The page entrypoint resolves `VisitorPrior` (from Cloudflare Worker via headers), runs the morph rules, and applies the directives at render time:

```tsx
// app/[tenant_slug]/page.tsx
import { readVisitorPrior } from "@/_lib/sense";
import { resolveMorph } from "@/_morph/render";
import { applyDirectives } from "@/_morph/apply";
import { HomepageDefault } from "./_components/HomepageDefault";

export default async function HomePage() {
  const prior = await readVisitorPrior();           // from request headers
  const plan = await resolveMorph("homepage", prior);
  const tree = applyDirectives(<HomepageDefault />, plan);
  return tree;
}
```

`resolveMorph` calls the backend `/morph/resolve` endpoint (or runs the DSL evaluator locally if performance demands). Returns a `RenderingPlan` typed object.

`applyDirectives` is pure: it transforms the JSX tree according to the directives. It does NOT do remote calls.

## SSE consumer client component

```tsx
// app/_components/ChatStream.tsx
"use client";

import { useEffect, useReducer } from "react";
import { useTenant } from "@/_lib/tenant/context";
import { applyDirectiveClient } from "./DirectiveApplier";

type Action =
  | { type: "text"; chunk: string }
  | { type: "directive"; directive: RenderingDirective }
  | { type: "done" };

function reducer(state, action: Action) {
  switch (action.type) {
    case "text":
      return { ...state, text: state.text + action.chunk };
    case "directive":
      applyDirectiveClient(action.directive);
      return state;
    case "done":
      return { ...state, done: true };
  }
}

export function ChatStream({ conversationId }: { conversationId: string }) {
  const tenant = useTenant();
  const [state, dispatch] = useReducer(reducer, { text: "", done: false });

  useEffect(() => {
    const evt = new EventSource(
      `/api/tenants/${tenant.slug}/conversations/${conversationId}/stream`,
      { withCredentials: true }
    );

    evt.addEventListener("text", (e) =>
      dispatch({ type: "text", chunk: e.data })
    );
    evt.addEventListener("directive", (e) =>
      dispatch({ type: "directive", directive: JSON.parse(e.data) })
    );
    evt.addEventListener("done", () => {
      dispatch({ type: "done" });
      evt.close();
    });
    evt.addEventListener("error", (e) => {
      console.error("stream error", e);
      evt.close();
    });

    return () => evt.close();
  }, [conversationId, tenant.slug]);

  return <div className="prose">{state.text}</div>;
}
```

## Streaming RSC with Suspense

For data fetching during render, use Suspense boundaries so the user sees a skeleton while heavy content loads:

```tsx
// app/[tenant_slug]/properties/[slug]/page.tsx
import { Suspense } from "react";
import { PropertyHero } from "./_components/PropertyHero";
import { PropertyDetails } from "./_components/PropertyDetails";
import { PropertyDetailsSkeleton } from "./_components/PropertyDetailsSkeleton";

export default async function PropertyPage({ params }) {
  const { slug } = await params;
  // Hero loads fast (cached)
  return (
    <>
      <PropertyHero slug={slug} />
      <Suspense fallback={<PropertyDetailsSkeleton />}>
        {/* Heavy KG fetch streams in */}
        <PropertyDetails slug={slug} />
      </Suspense>
    </>
  );
}
```

## Tailwind 4 conventions

- Use the `@theme` directive in `app/globals.css` to declare design tokens.
- Tenant-aware theming: emit CSS custom properties from the tenant's brand config, override in `app/[tenant_slug]/layout.tsx` via inline `<style>` block.
- Avoid arbitrary values when a token exists. Use `text-brand-primary`, not `text-[#abc123]`.
- Component variants via `class-variance-authority` (cva) where appropriate.

```tsx
// app/_components/Button.tsx
import { cva, type VariantProps } from "class-variance-authority";

const button = cva("inline-flex items-center font-medium transition", {
  variants: {
    intent: {
      primary: "bg-brand-primary text-white hover:bg-brand-primary/90",
      secondary: "bg-transparent text-brand-primary border border-brand-primary",
      ghost: "bg-transparent text-fg",
    },
    size: {
      sm: "h-8 px-3 text-sm rounded",
      md: "h-10 px-4 text-base rounded-md",
      lg: "h-12 px-6 text-lg rounded-md",
    },
  },
  defaultVariants: { intent: "primary", size: "md" },
});

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof button>;

export function Button({ intent, size, className, ...rest }: Props) {
  return <button className={button({ intent, size, className })} {...rest} />;
}
```

## Type generation from backend

Generate frontend types from the backend OpenAPI schema. Run as part of the build:

```bash
# scripts/generate-types.sh
openapi-typescript http://localhost:8000/openapi.json --output app/_types/api.ts
```

Generate morph types from the DSL JSON Schema:

```bash
json-schema-to-typescript core/dsl/morph_rule.schema.json -o app/_types/morph.ts
```

Commit generated types. Re-generate in CI; fail build if drift detected.

## Spatial (Three.js + Marzipano) client components

These are explicitly client-only:

```tsx
// app/[tenant_slug]/properties/[slug]/_components/InhabitClient.tsx
"use client";

import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useEffect, useRef } from "react";
import { ViewportStateBus } from "@/_lib/spatial/viewport";

export function InhabitClient({ glbUrl, propertyId, tenantSlug }: Props) {
  const bus = useRef(new ViewportStateBus(propertyId, tenantSlug));

  useEffect(() => {
    bus.current.connect();
    return () => bus.current.disconnect();
  }, []);

  return (
    <Canvas camera={{ position: [0, 1.6, 5], fov: 70 }}>
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} />
      <PropertyModel glbUrl={glbUrl} onViewportChange={(s) => bus.current.publish(s)} />
      <OrbitControls />
    </Canvas>
  );
}
```

For Marzipano (360° only), wrap in a client component too. Lazy-load via dynamic import to keep initial bundle small:

```tsx
import dynamic from "next/dynamic";
const MarzipanoViewer = dynamic(() => import("./MarzipanoViewer"), { ssr: false });
```

## Forbidden patterns

- **Client-side data fetching with useEffect when server fetching would work.** Use server components.
- **Importing server-only modules in client components.** `import "server-only"` directive on critical modules to fail loud.
- **Logging request data including PII.** Reference by ID only.
- **Inline scripts that interpolate server data.** XSS risk. Use `Script` tag with `dangerouslySetInnerHTML` only with sanitized JSON.
- **`getServerSideProps` patterns from Pages Router.** This is App Router. No `getServerSideProps`, no `getStaticProps`.
- **Manual `next/dynamic({ ssr: false })` everywhere "to be safe".** This kills RSC benefits. Use it only when there's a real SSR incompatibility.

## Performance budgets (frontend)

- LCP (Largest Contentful Paint): < 2.0s on 4G.
- INP (Interaction to Next Paint): < 200ms p95.
- CLS (Cumulative Layout Shift): < 0.05.
- First load JS bundle: < 200kb.
- Per-route JS: < 80kb additional.

Test with `next build` + lighthouse + Chrome DevTools Performance Insights. Lighthouse CI in pipeline.

## Testing

- Component tests with Vitest + React Testing Library for client components.
- Server component tests via Playwright (full render in browser).
- E2E happy path with Playwright for the critical visitor journeys (per Pack: at least 5 E2E tests).
- Snapshot tests for Tailwind class outputs when refactoring component classes.

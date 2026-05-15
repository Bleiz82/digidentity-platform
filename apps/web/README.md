# digidentity-web

Next.js 15 frontend for the DigIdentity Living Site platform.

## Setup

```bash
pnpm install
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000).

## Phase 2 — Frontend foundations

### Architecture

- **EventSource** (native browser API) for SSE streaming from the backend.
- **zod** for runtime validation of every SSE directive payload received.
- **Shared types** (`src/types/api.ts`) mirror the backend Phase 1 SSE contract exactly.
- **SSE client** (`src/lib/sse-client.ts`) wraps EventSource with typed callbacks and
  clean teardown. Tenant resolution uses `?tenant_id=<uuid>` query string (EventSource
  does not support custom headers).

### Key files

| File | Purpose |
|---|---|
| `src/types/api.ts` | `Directive` union types + zod `directiveSchema` |
| `src/lib/sse-client.ts` | `createConversationStream()` — typed EventSource wrapper |
| `src/lib/sse-client.test.ts` | Vitest unit tests for SSE parser |

### Running tests

```bash
pnpm test
```

### Building

```bash
pnpm build
```

---

**TODO (STEP 7b):** UI conversazionale — chat view, message bubbles, stream rendering,
conversation state management. Depends on `createConversationStream` from this step.

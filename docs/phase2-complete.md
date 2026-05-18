# Phase 2 — COMPLETED 2026-05-18

**Status**: COMPLETE  
**Duration**: 2026-05-15 → 2026-05-18  
**Test coverage**: 127 backend + 24 frontend = **151 total**  
**Commits in scope**: 13 (c5b90de → 3acc94d)

---

## Engine implementati

### 1. Conversational Renderer — BIBLE §6.3

| Item | Detail |
|------|--------|
| Backend | `apps/api/src/digidentity_api/api/conversations.py` |
| Frontend hook | `apps/web/src/lib/use-conversation-stream.ts` |
| SSE client | `apps/web/src/lib/sse-client.ts` |
| Demo UI | `apps/web/src/app/demo/page.tsx` |
| Tests (backend) | 11 SSE streaming tests |
| Tests (frontend) | 5 (sse-client + use-conversation-stream) |
| BIBLE ref | §6.3, ADR-002 |

SSE endpoint `GET /api/v1/conversations/{id}/stream` with tenant resolution via header or query string, ping keepalive, Accept negotiation (406 for JSON-only clients), LLMRouter circuit-breaker fallback chain.

---

### 2. Adaptive Renderer — BIBLE §6.2

Delivered in three sub-steps:

#### 2a. Decision Engine (step-9)

| Item | Detail |
|------|--------|
| Engine | `apps/api/src/digidentity_api/engines/adaptive_renderer/` |
| Loader | `loader.py` — validates morph_rules YAML vs JSON Schema, per-pack cache |
| Evaluator | `evaluator.py` — resolves signals, evaluates conditions (match_all/match_any, 8 operators) |
| Decision Engine | `decision_engine.py` — priority sort, conflict resolution, directive cap |
| API endpoint | `apps/api/src/digidentity_api/api/rendering.py` — `POST /api/v1/rendering/decide` |
| DSL schema | `core/dsl/morph_rule.schema.json` — draft 2020-12, 11 primitives |
| Lint tool | `tools/lint-pack/lint_pack.py` |
| Tests (backend) | 21 tests |
| BIBLE ref | §6.2, §5 |

#### 2b. Frontend Consumer (step-9b)

| Item | Detail |
|------|--------|
| Types | `apps/web/src/types/rendering.ts` — Zod schemas + VisitorPriorInput |
| API client | `apps/web/src/lib/rendering-client.ts` |
| Hook | `apps/web/src/hooks/useAdaptiveRender.ts` |
| Components | `AdaptiveSection.tsx`, `DirectiveDebugPanel.tsx` |
| Demo page | `apps/web/src/app/demo/adaptive/page.tsx` |
| Tests (frontend) | 8 tests |
| BIBLE ref | §6.2 |

#### 2c. Visitor Sense v0 (step-9c)

| Item | Detail |
|------|--------|
| Rules | `apps/web/src/lib/sense/rules.ts` — parseUtm, parseReferrer, parseDevice, inferPersona |
| Types | `apps/web/src/lib/sense/types.ts` |
| Cookie client | `apps/web/src/lib/sense/client.ts` |
| Hook | `apps/web/src/hooks/useVisitorPrior.ts` |
| Edge middleware | `apps/web/src/middleware.ts` — sets `dg_visitor_prior` cookie on `/demo/*` |
| Tests (frontend) | 11 tests |
| BIBLE ref | §6.1 |

---

### 3. Agent Orchestrator — BIBLE §6.4

| Item | Detail |
|------|--------|
| Provider | `apps/api/src/digidentity_api/engines/agent/providers/anthropic_provider.py` |
| Tool registry | `apps/api/src/digidentity_api/engines/agent/tools/registry.py` — 3 tools |
| Tool schemas | `apps/api/src/digidentity_api/engines/agent/tools/schemas.py` |
| Agent loop | `apps/api/src/digidentity_api/engines/agent/loop.py` |
| Config | `apps/api/src/digidentity_api/config.py` — ANTHROPIC_API_KEY, ANTHROPIC_MODEL, AGENT_MAX_ITERATIONS |
| Tests (backend) | 11 tests (mock provider, no real API calls) |
| BIBLE ref | §6.4, ADR-004 |

Three built-in tools: `kg_search`, `render_highlight`, `lead_update_score`. Max 5 iterations, 30s timeout. Falls back to `MockAnthropicProvider` when `ANTHROPIC_API_KEY` absent (back-compat). Conversations endpoint routes through `AgentLoop` when key is set.

---

### 4. Qualify — BIBLE §6.5

| Item | Detail |
|------|--------|
| Scorecard | `packs/real-estate-luxury/scoring/lead_scorecard.yaml` — 10 signals, persona modifiers |
| Schema | `core/dsl/scorecard.schema.json` — draft 2020-12 |
| Loader | `apps/api/src/digidentity_api/engines/qualify/loader.py` |
| Scorer | `apps/api/src/digidentity_api/engines/qualify/scorer.py` — LeadScorer.compute() |
| Persistence | `apps/api/src/digidentity_api/engines/qualify/persistence.py` — upsert_lead (one-per-session) |
| API | `apps/api/src/digidentity_api/api/leads.py` — GET + POST `/api/v1/leads/{visitor_session_id}` |
| Tests (backend) | 13 tests |
| BIBLE ref | §6.5, §7.3 |

---

### 5. Supporting Infrastructure (step-8a/8b/8c)

| Item | Detail |
|------|--------|
| DB schema v3 | Migration 003: `conversations`, `conversation_turns`, `visitor_sessions`, `leads` |
| Pydantic schemas | `schemas/visitor.py`, `schemas/rendering.py`, `schemas/lead.py` |
| DSL morph schema | `core/dsl/morph_rule.schema.json` |
| BIBLE ref | §7.1, §7.3, §7.4 |

---

## Commit timeline Phase 2

| Hash | Date | Description |
|------|------|-------------|
| `c5b90de` | 2026-05-15 | fix(phase2): enable CORS + frontend direct backend calls [step-7b.2] |
| `923b285` | 2026-05-15 | feat(phase2): backend accepts tenant_id via query string [step-7b.1] |
| `1d799c9` | 2026-05-15 | feat(phase2): conversational UI + streaming hook [step-7b] |
| `2d61296` | 2026-05-15 | fix(phase2): align frontend SSE schema to real backend contract [step-7b.3] |
| `c1909db` | 2026-05-15 | fix(phase2): make SSE timestamp field optional [step-7b.4] |
| `c5935f1` | 2026-05-18 | feat(phase2): db schema v3 — conversations, turns, visitor_sessions, leads [step-8a] |
| `0636eb6` | 2026-05-18 | feat(phase2): pydantic schemas v3 — VisitorPrior, RenderingDirective, LeadScore [step-8b] |
| `8c7a98d` | 2026-05-18 | feat(phase2): DSL morph rules — JSON Schema + lint-pack tool [step-8c] |
| `bae6926` | 2026-05-18 | feat(phase2): adaptive renderer decision engine v1 [step-9] |
| `65713b6` | 2026-05-18 | feat(phase2): frontend adaptive renderer consumer [step-9b] |
| `e922665` | 2026-05-18 | feat(phase2): visitor sense v0 deterministic [step-9c] |
| `d76c198` | 2026-05-18 | feat(phase2): agent orchestrator + anthropic + tool calling [step-10] |
| `3acc94d` | 2026-05-18 | feat(phase2): qualify lead scoring engine [step-11] |

---

## Test coverage finale

| Layer | Suite | Count |
|-------|-------|-------|
| Backend | SSE streaming | 11 |
| Backend | Adaptive Renderer (decision engine + lint) | 21 |
| Backend | Agent Loop | 11 |
| Backend | Qualify | 13 |
| Backend | Other (health, CORS, KG, tenant isolation, etc.) | 71 |
| **Backend total** | | **127** |
| Frontend | Rendering (useAdaptiveRender, AdaptiveSection, DirectiveDebugPanel) | 8 |
| Frontend | Sense (parseUtm, parseReferrer, parseDevice, inferPersona) | 11 |
| Frontend | SSE client + useConversationStream | 5 |
| **Frontend total** | | **24** |
| **Grand total** | | **151** |

---

## Known minor inconsistencies (resolve in Phase 3)

### 1. Persona terminology mismatch
Visitor Sense (`rules.ts`) uses IDs: `international_investor`, `family_relocating`, `luxury_retiree`, `holiday_seeker`, `browsing`.  
Qualify scorecard (`lead_scorecard.yaml`) uses `persona_modifiers` with the same IDs — these are aligned.  
**However**: the original scope mentioned `luxury_investor` and `business_traveler` which do not exist in the codebase. Confirm final canonical persona ontology and document in `packs/real-estate-luxury/personas.yaml` as the single source of truth.

### 2. `_REPO_ROOT` hardcoded via `parents[N]`
`decision_engine.py`, `loop.py`, `loader.py` (adaptive + qualify) all use `Path(__file__).resolve().parents[N]` to find the repo root. This is fragile if the package is installed in a non-standard location.  
**Fix**: add `REPO_ROOT: Path` to `config.py` (auto-detect at startup) and replace all `parents[N]` patterns.

### 3. Lead bucket thresholds
The original spec stated warm=31-60, hot=61-100. Implemented (following `schemas/lead.py` docstring and BIBLE §2.5): warm=30-69, hot≥70.  
**Decision**: keep implemented thresholds (warm≥30, hot≥70). Update any external docs that reference the 31/61 numbers.

---

## Cosa NON è stato fatto in Phase 2 (rimandato a Phase 3)

| Item | BIBLE ref | Notes |
|------|-----------|-------|
| Spatial Experience Engine | §6.6 | Inhabit / immersive content — Phase 3 |
| Static Manifestation Engine | §6.7 | SEO / static generation — Phase 3 |
| Learning Engine | §6.8 | Requires golden dataset, Phase 4 BIBLE |
| Voice channel | §6.3 | LiveKit + Deepgram + Cartesia — Phase 3 |
| GitHub Actions CI | — | lint, typecheck, pytest, eval gate |
| Golden dataset (≥20 conversations) | §6.5 | Required before eval gate can block merges |
| `prompts/system.md` reale | §6.4 | Currently hardcoded placeholder string in `loop.py` |
| Eval runner integration | CLAUDE.md §10 | `eval-runner` subagent not yet wired to CI |

---

## Phase 3 preview

Ordered by commercial value (BIBLE §0 priority principle):

### STEP 12 — GitHub Actions CI + eval gate (highest leverage)
Wire `ruff`, `mypy`, `biome`, `pytest`, `pnpm test` + pack eval gate into CI. Blocks merge on regression. Required before any external demo or client handoff.

### STEP 13 — `prompts/system.md` + golden dataset 20 conversations
Write the real system prompt for the real-estate-luxury agent (persona-aware, tool-aware, lead-scoring-aware). Produce 20 golden conversation fixtures and run `eval-runner` to establish baseline `eval-reports/baseline.json`.

### STEP 14 — Spatial Experience Engine v1 (Inhabit)
Implement `engines/spatial/` — property immersive page rendering, 360-photo metadata integration, dwell-time tracking signals feeding back into lead scoring. Highest visible client impact after core chat + morph.

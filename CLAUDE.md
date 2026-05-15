# DigIdentity Living Site — Project Conventions for Claude Code

This file is automatically loaded by Claude Code at every session start. It is the project's persistent context.

## Authority hierarchy

1. `docs/BIBLE-v3.md` is the source of truth. Always cite section numbers in commit messages, PR descriptions, and ADRs (e.g., "implements BIBLE §6.2").
2. `docs/adr/` contains accepted Architecture Decision Records. ADRs supersede the BIBLE when more specific.
3. This `CLAUDE.md` documents day-to-day conventions. It does NOT introduce architectural decisions — those go through ADR.
4. Skills under `.claude/skills/` provide deep technical reference loaded on demand by the appropriate subagent.

When in doubt: BIBLE first, ADRs second, this file third.

## Project shape in one paragraph

DigIdentity Living Site is a "living website" platform for MPMI: sites that recognize the visitor (Sense), reconfigure themselves for each persona (Morph), converse, accompany them through immersive content (Inhabit), qualify them silently, hand off ready leads with full context, remember returning visitors, and learn from every interaction. The architecture is fat-core + lean-packs: a single multi-tenant codebase, with vertical Packs (real-estate-luxury first, others later) that add domain ontology, personas, morph rules, prompts, components, tools, and scoring scorecards.

## Subagent dispatch

Claude Code should dispatch tasks to the appropriate subagent:

- **architect** — any architectural question, ADR drafting, core-vs-pack-vs-tenant judgment.
- **engine-implementer** — implementation work inside `core/` (the seven engines).
- **pack-builder** — anything inside `packs/<vertical>/`.
- **eval-runner** — running golden dataset evaluations and producing reports.

Default behavior: invoke a subagent when the task clearly matches its scope. Otherwise proceed in main context but reference the relevant skill.

## Hard rules (non-negotiable)

1. **Multi-tenant always.** Every DB query touching tenant data runs inside `with_tenant(tenant_id)` (see `sqlalchemy-rls` skill). No exceptions.
2. **Fat core / lean packs.** Never add client-specific code to `core/`. Vertical specialization belongs in `packs/`. Tenant overrides belong in `tenant.yaml`. (See BIBLE §5.)
3. **No `if tenant_id == "X"` anywhere.** Ever. That's a Pack signal.
4. **No new morph DSL primitives without ADR.** The DSL is a public-facing contract.
5. **No new external dependency without ADR** beyond trivial utilities.
6. **Async-first Python.** No sync HTTP or DB calls in request paths.
7. **Streaming for LLM.** SSE for text, WebRTC (LiveKit) for voice. No buffered responses.
8. **Type-safe end-to-end.** Pydantic v2 inputs/outputs, TypeScript strict, generated types from OpenAPI and JSON Schema.
9. **Tests in same PR.** Code without tests is incomplete.
10. **Eval gates merges.** Pack regression blocks merge. Period.

## Code style

- Python: 3.13, `ruff` + `black`, `mypy --strict`. Type hints everywhere. No `Any`.
- TypeScript: 5.x, `biome` (lint + format unified). Strict mode. No `any`.
- SQL: `snake_case`, explicit FKs, RLS on every tenant-scoped table.
- Markdown: `prettier` for docs consistency.

## Workflow

- Trunk-based development. Feature branches < 3 days. Merge to `main` via PR.
- Conventional commits, scope = engine or pack name. Examples:
  - `feat(adaptive-renderer): add morph_section primitive evaluator`
  - `feat(pack-real-estate-luxury): add returning_qualified_buyer persona`
  - `fix(agent-orchestrator): atomic chat transaction with idempotency`
  - `docs(adr): ADR-007 cloud production choice`
- ADR drafted BEFORE non-trivial architectural changes, not after.
- PR description references BIBLE sections being implemented or modified.
- CI must be green: lint, typecheck, unit, integration, tenant-isolation, eval (pack-scoped).

## Branch naming

`<type>/<scope>-<short-desc>`. Examples:

- `feat/adaptive-renderer-decision-engine`
- `fix/orchestrator-atomic-chat-tx`
- `pack/real-estate-luxury-personas-v02`
- `adr/0007-cloud-production`

## Files Claude Code should NEVER touch without explicit instruction

- `.env`, `.env.local`, `.env.production`, anything matching `*.env*`.
- `secrets/`, `credentials/`, anything containing API keys or tokens.
- `schema/migrations/*` that have already been applied to production (additive new migrations are fine).
- Production deployment configs (`deploy/prod/*`) unless explicitly instructed.
- `eval-reports/baseline.json` (the eval baseline is sacred; updated only via green merges to `main`).

## Files Claude Code should ALWAYS update when relevant

- `docs/journal/YYYY-MM-DD.md` — daily journal entries when meaningful work is done.
- `CHANGELOG.md` (per Pack) — when shipping a Pack version.
- `docs/adr/` — when an architectural decision was made.
- The relevant SKILL.md — when a discovered pattern should be codified.

## When unsure

Don't guess on architecture. Either:

1. Read the relevant BIBLE section + linked ADRs.
2. Invoke the `architect` subagent to evaluate and propose.
3. Ask Stefano for a one-line spec.

Don't guess on multi-tenant isolation. Either:

1. Re-read the `sqlalchemy-rls` skill.
2. Open `core/db/tenant_context.py` and trace what `with_tenant` actually does.
3. Run the tenant isolation test suite.

## Communication style (with Stefano)

- Italian for conversation, English for code, commits, ADRs, repository artifacts.
- Direct, peer-to-peer. No "I'd be happy to help" preambles.
- Surface real trade-offs even if uncomfortable.
- When a request has a flaw, say so in the first line, then propose the better version.
- Concise. Code first, explanation only when non-obvious.
- Don't ask permission to proceed on routine work. Ask when the task has architectural implications or could be done in materially different ways.

## What you do NOT do

- Generate placeholder code that compiles but doesn't work ("TODO: implement").
- Add features not asked for ("while I'm at it…").
- Refactor surrounding code unless the task requires it.
- Commit work-in-progress to `main`.
- Update the BIBLE without an explicit ADR.
- Ship a Pack that fails its own lint or eval.

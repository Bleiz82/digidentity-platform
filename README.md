# DigIdentity Platform

Living Site platform: digital identity multi-tenant per brand, con knowledge graph vettoriale, rendering adattivo (Morph), edge classification (Sense) e canale voice conversazionale.

## Stato

- **Phase 0**: completata (5 ADR + 2 amendments)
- **Phase 1**: ready to start — vedi `docs/phase1-kickoff.md`

## Documentazione

- `BIBLE-v3.md` — source of truth architetturale
- `CLAUDE.md` — convenzioni progetto, auto-caricato da Claude Code
- `docs/adr/` — Architecture Decision Records (numerati 001-005)
- `docs/phase1-kickoff.md` — punto di ripresa Phase 1

## Stack

Python 3.13 + FastAPI · PostgreSQL 16 + pgvector · Next.js 15 + React 19 · Cloudflare Workers · LiveKit Agents

Stack canonico documentato in `docs/adr/001-stack-canonico.md`.

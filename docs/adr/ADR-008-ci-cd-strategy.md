# ADR-008: CI/CD Strategy — GitHub Actions + Eval Gate

- **Status**: Accepted
- **Date**: 2026-05-18
- **Authors**: Stefano Corda
- **BIBLE refs**: §6.4, §6.5, §10
- **Supersedes**: n/a
- **Superseded by**: n/a

---

## Context

Phase 3 Scenario A++ (kickoff §10, decision D-06) requires:

1. **Cross-pack eval gate**: no pack regression must reach `main`. Every Pack ships a golden dataset; CI must run it and block merge on failure.
2. **ADR coverage**: all Architecture Decision Records must have a valid status before merging. An ADR without status (or with status `Rejected`) indicates unresolved architectural debt.
3. **Multi-job parallelism**: backend tests (DB-heavy, ~90s) and frontend tests (build-heavy, ~60s) must run concurrently to keep CI under 5 minutes on the free tier.

Currently (Phase 2) there is no CI/CD pipeline. All validation is manual and local. This is incompatible with the multi-pack, multi-contributor trajectory of Phase 3.

## Options considered

### Option A — GitHub Actions (chosen)

- Native to the repository host (GitHub)
- Free tier: 2,000 min/month for public repos (effectively unlimited for this project)
- Native service containers for Postgres — no external infra required
- `pgvector/pgvector:pg16` Docker image provides Postgres 16 + pgvector out of the box
- `astral-sh/setup-uv@v3` action is the official uv installer; `pnpm/action-setup@v4` for Node
- 5 parallel jobs: `backend-test`, `frontend-test`, `lint-packs`, `eval-real-estate-luxury`, `adr-coverage`

### Option B — Buildkite / CircleCI

- Better at large-scale pipelines; overkill for a single-repo project
- Requires external infrastructure management
- No free tier for private repos at the scale needed

### Option C — Makefile-only local CI

- Zero infra cost, but no enforcement on PRs
- Incompatible with the requirement that "eval gates merges" (CLAUDE.md §10)

## Decision

**GitHub Actions with 5 parallel jobs.**

### Job breakdown

| Job | Trigger | Postgres? | Duration (est.) |
|-----|---------|-----------|-----------------|
| `backend-test` | push + PR | yes (service container) | ~90s |
| `frontend-test` | push + PR | no | ~60s |
| `lint-packs` | push + PR | no | ~15s |
| `eval-real-estate-luxury` | push (main) only | no (mock provider) | ~60s |
| `adr-coverage` | push (main) only | no | ~5s |

`pr.yml` runs the first three jobs on every PR to main (fast feedback loop).
`ci.yml` runs all five on every push to main (full gate).

### Secrets policy

Tests run with `EMBEDDING_PROVIDER=mock` and `ANTHROPIC_API_KEY=""`. Real API keys are never required in CI. Fork PRs can run the full test suite without secrets.

### Eval gate design

Each Pack must have `apps/api/tests/test_<pack_id>_golden.py`. The eval job conditionally executes it (`if [ -f ... ]`) so new packs can be added without breaking the pipeline before their evals exist. Once the file is present, it is a hard gate.

## Consequences

- CI/CD cost: $0 (GitHub free tier, public repo)
- Estimated CI duration: ~90s wall time (parallelism)
- All PRs to `main` must pass `backend-test`, `frontend-test`, `lint-packs`
- New packs must include a golden eval file before the first merge to `main`
- ADR files without a status field will fail CI — authors must set status before merging
- Branch protection rules (require status checks, dismiss stale reviews) are configured manually in GitHub Settings after the first CI run — out of scope for this ADR

---
name: promote-to-core
description: Evaluate whether code currently in a Pack should be promoted to core. Delegates to the architect subagent. $ARGUMENTS describes the candidate (file path or feature name).
---

Delegate to the `architect` subagent.

Candidate for promotion: $ARGUMENTS

The architect will:

1. Read the candidate code/feature.
2. Search for analogous code in other Packs (criterion for promotion: 2+ Packs would benefit).
3. Evaluate whether the abstraction is mature (used as-is by multiple consumers, stable for 4+ weeks).
4. Draft an ADR proposing promotion if criteria are met, OR explain why it should stay in the Pack.
5. If promotion is approved, outline the migration steps: extract to `core/`, update imports in source Pack, document in the relevant SKILL.md.

Promotion happens only with explicit approval from Stefano after reviewing the ADR draft.

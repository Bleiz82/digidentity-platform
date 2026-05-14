---
name: new-adr
description: Scaffold a new Architecture Decision Record under docs/adr/ with sequential numbering. Use when an architectural decision needs to be documented before implementation.
---

You will create a new ADR.

1. List existing ADRs in `docs/adr/` to determine the next sequential number (zero-padded to 4 digits, e.g., `0007`).
2. Ask the user for the ADR title in 3-7 words, kebab-case.
3. Copy `docs/adr/_template.md` to `docs/adr/NNNN-<title>.md`.
4. Pre-fill:
   - Title with the next number and kebab-case title.
   - Status: `proposed`.
   - Date: today.
   - Authors: Stefano Corda (and any others mentioned).
   - BIBLE refs: ask the user which sections this ADR refines.
5. Open the file in the editor and let the user fill the body.
6. Remind: when ready, change status to `accepted` only with explicit approval. Then update the ADR index if present.

Do NOT auto-fill the body or auto-accept.

---
name: new-pack
description: Scaffold a new vertical Pack under packs/<slug>/ following the canonical layout. Use $ARGUMENTS as the pack slug.
---

You will scaffold a new Pack. Delegate to the `pack-builder` subagent.

Pack slug: $ARGUMENTS

Steps:

1. Verify the slug is kebab-case, descriptive, available (no existing `packs/<slug>/`).
2. Create the directory tree per the `pack-structure` skill (this is mandatory layout):
   - `pack.yaml` with version `0.1.0` and status `alpha`.
   - `README.md` with sections: Intent, ICP, Personas, Top Morph Use Cases, Integration Touchpoints (all placeholders, to fill).
   - `ontology/schema_extension.sql` (empty additive skeleton).
   - `ontology/entities.json` (empty array).
   - `personas/personas.yaml` (with one example persona).
   - `morph_rules/homepage.yaml` (one minimal rule + fallback).
   - `prompts/system.md` (template from `prompt-conventions` skill).
   - `prompts/tool_descriptions.md` (template).
   - `prompts/few_shots/` (empty).
   - `components/` with `index.ts`.
   - `tools/` with `__init__.py`.
   - `scoring/lead_scorecard.yaml` (template with 5 example signals).
   - `golden_dataset/conversations.jsonl` (empty file with comment header).
   - `CHANGELOG.md` (with `## [0.1.0] - <date> - Initial scaffold`).
3. Confirm structure passes `tools/lint-pack/main.py packs/<slug>` (or report what's missing).
4. Commit with message: `feat(pack-<slug>): initial scaffold`.

Do NOT fill in domain content. The pack-builder subagent will guide that step interactively after scaffold.

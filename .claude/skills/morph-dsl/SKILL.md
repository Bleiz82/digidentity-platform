---
name: morph-dsl
description: The declarative DSL for Adaptive Renderer morph rules. Use whenever authoring, modifying, validating, or debugging YAML files under packs/*/morph_rules/. Defines primitives, schema, conflict resolution, and snapshot testing.
---

# Morph DSL — Authoring Guide

The morph DSL is a declarative YAML language for expressing how a page transforms based on `VisitorPrior` (Sense output) and `RenderingDirectives` (Agent output). It is the contract between Packs (vertical-specific rules) and the Adaptive Renderer (core engine).

This skill is the source of truth for syntax. The schema is at `core/dsl/morph_rule.schema.json`. The evaluator implementation is at `core/adaptive_renderer/decision_engine/`.

## File location and naming

Morph rules live in `packs/<vertical>/morph_rules/`. One file per logical page or component group. Conventional filenames:

- `homepage.yaml`
- `<entity>_detail.yaml` (e.g., `property_detail.yaml`)
- `lead_form.yaml`
- `pricing.yaml`
- `contact.yaml`

Filename = `target_page` value in the YAML.

## Anatomy of a rule file

```yaml
version: 1
target_page: homepage
description: Morph rules for real-estate-luxury homepage
rules:
  - id: <unique-rule-id>
    priority: <integer>
    when:
      <condition-block>
    do:
      - <directive>
      - <directive>
fallback:
  - <directive>
```

`version` is the schema version (currently 1). `target_page` matches a registered page in the Pack's component map. `rules` is a list, evaluated in priority order. `fallback` runs only when no rule matched.

## Conditions: the `when` block

A `when` block contains exactly one of these top-level operators:

- `match_all`: list of conditions, all must be true (AND).
- `match_any`: list of conditions, at least one must be true (OR).
- `not`: negation of a single nested condition.

Conditions can nest. Example:

```yaml
when:
  match_all:
    - signal: persona_score.luxury_buyer
      gte: 0.6
    - match_any:
        - signal: utm.campaign
          equals_any: ["luxury-search", "lionard-paid"]
        - signal: referrer.domain
          equals_any: ["lionard.com", "sothebysrealty.com"]
    - not:
        signal: is_returning
        equals: true
```

## Signals available in conditions

Signals are extracted from `VisitorPrior` and `SenseSignals`. Stable signal namespaces:

**persona_score.<persona_id>** — float 0..1. Persona must be declared in `personas.yaml`.

**utm.\*** — `utm.source`, `utm.medium`, `utm.campaign`, `utm.content`, `utm.term`. Strings.

**referrer.\*** — `referrer.domain`, `referrer.path`, `referrer.is_search_engine` (bool), `referrer.is_social` (bool).

**geo.\*** — `geo.country` (ISO), `geo.city`, `geo.timezone`. City-level only, never finer.

**device.\*** — `device.class` (`mobile`|`tablet`|`desktop`), `device.os`, `device.browser`.

**language** — primary language from Accept-Language header, ISO 639-1.

**local_time_bucket** — one of `night`|`morning`|`afternoon`|`evening` based on visitor's local time.

**is_returning** — bool.

**prior_session.\*** — when `is_returning=true`, properties of the previous session (e.g., `prior_session.lead_score`, `prior_session.last_entity_viewed`).

**conversation.\*** — during Converse, signals emitted by the agent into the visitor session. Example: `conversation.detected_intent`.

**custom.\*** — Pack-declared custom signals from `personas.yaml` extensions.

## Operators

For numeric signals: `gte`, `gt`, `lte`, `lt`, `equals`, `between: [low, high]`.

For string signals: `equals`, `equals_any: [...]`, `matches` (regex), `matches_any: [regex1, regex2]`, `contains`, `starts_with`, `ends_with`.

For bool signals: `equals: true|false`.

For list signals (rare, e.g., `persona_score` as multiple): `contains_any`, `all_of`, `none_of`.

## Directives: the `do` block

Directives are the actions that transform the page. The 10 core primitives:

### `morph_section`
Swap a section for a different template.
```yaml
- directive: morph_section
  target: hero_section
  params:
    template: luxury_buyer_v2
```

### `highlight`
Visually elevate a specific entity (property, service, case study).
```yaml
- directive: highlight
  target: property_id_abc123
  params:
    mode: "spotlight"   # or "badge", "pulse", "first_in_grid"
```

### `inject`
Add a component to a slot.
```yaml
- directive: inject
  target: above_fold_slot
  params:
    component: ConciergeBanner
    props:
      headline: "Un consulente dedicato vi attende"
      cta_text: "Apri conversazione"
    position: prepend   # "append", "prepend", "replace"
```

### `show` / `hide`
Toggle visibility of a section by id.
```yaml
- directive: hide
  target: generic_search_form

- directive: show
  target: concierge_chat_invite
  params:
    delay_ms: 4000     # optional, default 0
```

### `reorder`
Reorder children of a container.
```yaml
- directive: reorder
  target: hero_section
  params:
    order: ["above_5m_listings", "concierge_cta", "trust_badges"]
```

### `rewrite_copy`
Swap a copy block to a named variant.
```yaml
- directive: rewrite_copy
  target: hero_headline
  params:
    variant: luxury_buyer_v2
```
Variants are defined in `packs/<name>/components/<Component>.copy.yaml`.

### `set_persona`
Forcefully set the active persona (overrides VisitorPrior).
```yaml
- directive: set_persona
  target: _self
  params:
    persona_id: returning_qualified_buyer
```
Use sparingly. Mostly for Remember state and agent-driven persona refinement.

### `trigger_agent`
Spawn an agent message proactively.
```yaml
- directive: trigger_agent
  target: _self
  params:
    persona_aware: true
    intent: greeting_returning
    delay_ms: 2500
```

### `track`
Emit a custom analytics event (does not transform DOM).
```yaml
- directive: track
  target: _self
  params:
    event_name: morph_applied_luxury_buyer
    payload:
      rule_id: luxury-buyer-prior
```

## Conflict resolution

When multiple rules match:

1. Higher `priority` wins per-directive.
2. If two rules emit conflicting directives on the same `target`, the higher-priority rule's directive is applied; the lower-priority one is logged as suppressed.
3. If two rules at the same priority emit conflicting directives, the validator rejects at deploy time. Resolution: differentiate priority or refactor.
4. Non-conflicting directives from multiple matching rules are all applied (additive).

Conflict detection: two directives are "conflicting" iff they target the same `target` AND their primitive is in the conflict matrix below.

| primitive A | primitive B | conflict? |
|---|---|---|
| show | hide | YES |
| morph_section | morph_section | YES |
| rewrite_copy | rewrite_copy | YES |
| reorder | reorder | YES |
| set_persona | set_persona | YES |
| highlight | highlight (same target) | NO (compose) |
| inject | inject (same target) | NO (compose, order by priority) |
| track | track | NO (always compose) |
| trigger_agent | trigger_agent | YES |

## Fallback block

`fallback` runs only when zero rules in the file matched. Use it sparingly: usually one directive, often `track` to monitor how often nothing matched.

```yaml
fallback:
  - directive: track
    target: _self
    params:
      event_name: morph_no_rule_matched
```

## Validation

Every morph rule file passes through the validator before merge:

```bash
python tools/validate-morph-rules.py packs/<name>/morph_rules/
```

The validator checks:

- YAML parses.
- Schema conformance (`core/dsl/morph_rule.schema.json`).
- All `target` values reference registered selectors in the Pack's component map.
- All `persona_id` references exist in `personas.yaml`.
- All `variant` references in `rewrite_copy` exist in the Component copy file.
- No conflict at same priority.
- All rule `id`s are unique within the file.

Schema validation is enforced in pre-commit hook and CI.

## Snapshot testing

Every morph rule file has a corresponding snapshot test in `packs/<name>/morph_rules/__snapshots__/`. Test inputs are fixtures of `VisitorPrior`. Outputs are the resulting `RenderingDirectives` list. Test fails if output differs from snapshot.

Run:
```bash
make snapshot-test PACK=<name>
```

Update snapshots intentionally:
```bash
make snapshot-update PACK=<name>
```

Snapshot updates require code review.

## Pack-level DSL extensions

If a Pack genuinely needs a primitive beyond the 10 core ones, declare it in `packs/<name>/dsl_extensions.yaml` along with its handler. Adding a new primitive to the core requires an ADR (this is by design).

## Authoring guidelines

- Start with 3-5 rules per page. Resist the urge to over-personalize early.
- Use `track` directive in every rule to measure which rules actually fire.
- Run snapshot tests before committing.
- When a rule has more than 5 conditions in its `when` block, refactor — likely the persona definition itself should be more specific.
- Comment intent in YAML comments, not just rule `description`. Future-you will thank you.

## Common mistakes to avoid

- Putting tenant-specific copy in a Pack rule. Tenant-specific goes in `tenant.yaml` overrides, not in the Pack.
- Using `set_persona` to "fix" a misclassification. Fix the persona definition or signals instead.
- Hidden coupling: rule A `hides` a section, rule B `injects` into the same section. Make dependencies explicit with priority.
- Forgetting to add the new variant to the Component copy file when using `rewrite_copy`.

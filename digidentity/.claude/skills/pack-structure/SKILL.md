---
name: pack-structure
description: Canonical structure and lifecycle of a DigIdentity Pack (vertical bundle). Use when creating new Packs, validating Pack integrity, or refactoring across Pack boundaries.
---

# Pack Structure — Canonical Layout

A Pack is the unit of vertical specialization. Everything domain-specific lives inside a Pack. The core stays vertical-agnostic. Packs are atomic: you ship a Pack version end-to-end, never partial.

## Directory layout (mandatory)

```
packs/<vertical-slug>/
├── pack.yaml
├── README.md
├── ontology/
│   ├── schema_extension.sql
│   └── entities.json
├── personas/
│   └── personas.yaml
├── morph_rules/
│   ├── homepage.yaml
│   ├── <entity>_detail.yaml
│   └── (one file per page/group)
├── prompts/
│   ├── system.md
│   ├── tool_descriptions.md
│   └── few_shots/
│       ├── greeting.jsonl
│       ├── qualifying.jsonl
│       └── handoff.jsonl
├── components/
│   ├── <ComponentName>.tsx
│   ├── <ComponentName>.copy.yaml
│   └── index.ts
├── tools/
│   ├── <tool_name>.py
│   └── __init__.py
├── scoring/
│   └── lead_scorecard.yaml
├── golden_dataset/
│   └── conversations.jsonl
├── dsl_extensions.yaml      # optional, only if Pack adds DSL primitives
├── MIGRATIONS.md            # required after v1.0
└── CHANGELOG.md
```

Naming convention for the Pack slug: kebab-case, descriptive, includes geographic or market specifier when relevant. Examples: `real-estate-luxury`, `real-estate-luxury-italia`, `dental-clinic-premium`, `hospitality-boutique`.

## `pack.yaml` schema

```yaml
name: real-estate-luxury
version: 0.2.1                    # semver
display_name: "Real Estate Luxury"
description: "Vertical Pack for luxury real estate agencies in Europe."
owner: stefano@digidentity.agency
status: alpha                     # alpha | beta | stable | deprecated
supported_locales: ["it-IT", "en-GB", "en-US"]
core_engine_version: ">=1.0.0,<2.0.0"
dependencies: []                  # other Packs this depends on (rare; typically empty)
entities:
  - property
  - agent
  - viewing
personas_file: personas/personas.yaml
morph_rules_dir: morph_rules/
prompts_dir: prompts/
tool_registry:
  - id: valuation.estimate
    module: tools.valuation_estimator
    class: ValuationEstimator
  - id: availability.viewing
    module: tools.viewing_availability
    class: ViewingAvailability
scoring_file: scoring/lead_scorecard.yaml
golden_dataset: golden_dataset/conversations.jsonl
```

## `personas/personas.yaml`

Each persona is a behavioral profile. Personas drive Morph rules and seed Qualify scoring.

```yaml
version: 1
personas:
  - id: luxury_buyer
    display_name: "Luxury Buyer"
    description: "High-net-worth individual actively shopping for properties above €5M"
    priority: 100                 # tiebreaker when multiple personas score similarly
    signal_weights:               # for Sense classifier (when ML model not yet trained)
      utm_campaign_luxury: 0.4
      referrer_luxury_portal: 0.3
      device_high_end: 0.1
      geo_high_wealth_region: 0.2
    scoring_seed:                 # initial weights for Qualify when this persona is active
      budget_signal: 1.5
      urgency_signal: 1.2
      authority_signal: 1.3

  - id: returning_qualified_buyer
    display_name: "Returning Qualified Buyer"
    description: "Visitor who returned with a lead_score in prior session ≥50"
    priority: 110                 # higher than first-visit luxury_buyer
    activation:
      is_returning: true
      prior_session.lead_score: { gte: 50 }
    scoring_seed:
      retention_bonus: 0.8

  - id: journalist
    display_name: "Journalist / Press"
    description: "Press visitor researching the agency or market"
    priority: 80
    signal_weights:
      referrer_press_outlet: 0.6
      utm_campaign_press: 0.4

  - id: competitor
    display_name: "Competitor Recon"
    description: "Visitor likely from a competing agency"
    priority: 70
    signal_weights:
      referrer_competitor_domain: 0.9
```

## `prompts/system.md`

The agent system prompt for this Pack. Keep under 2000 tokens initially. Structure:

```markdown
# System Prompt — <Pack Display Name>

## Role
You are the conversational presence of <tenant agency name>, a luxury real estate agency...

## Tone and language
- Italian by default, English when visitor's language is detected as English.
- Tone: refined, knowledgeable, never pushy.
- Avoid hard sales language. Never "limited time offer", never "act now".

## Domain knowledge
[Domain-specific context: market, common buyer concerns, etiquette.]

## Tool use
[Brief, tool descriptions live in tool_descriptions.md.]

## Conversation flow
- Greeting tailored to persona (use {persona_id} signal).
- Discover intent in 1-2 turns.
- Search and present 1-3 relevant properties (never overwhelm).
- Qualify gently through conversation, not forms.
- Hand off when score ≥ threshold, framing as "connecting you with the right person".

## Hard rules
- Never reveal prices unless visitor explicitly asks and persona = qualified_buyer.
- Never share contact info of agents without lead_score ≥ 50.
- Never make claims about specific properties beyond what's in the KG.
- Always cite the property by name when discussing.

## Output guidelines
- Concise. 2-4 sentences per turn unless explanation requested.
- Italian: use "voi" formal register by default, "tu" only if visitor uses it.
```

## `tools/` and `tool_descriptions.md`

Each tool is a Python class implementing the `Tool` protocol from `core.agent.tools.base`. The class is registered in `pack.yaml` `tool_registry`. Its description in `tool_descriptions.md` is what the LLM sees.

Template tool:

```python
# packs/real-estate-luxury/tools/valuation_estimator.py
from core.agent.tools.base import Tool, ToolInput, ToolOutput
from pydantic import BaseModel, Field

class ValuationInput(BaseModel):
    criteria: dict = Field(..., description="Property characteristics for estimation")

class ValuationOutput(BaseModel):
    estimated_range_eur: tuple[int, int]
    confidence: float
    notes: str

class ValuationEstimator(Tool):
    id = "valuation.estimate"
    input_schema = ValuationInput
    output_schema = ValuationOutput

    async def run(self, inp: ValuationInput, ctx) -> ValuationOutput:
        ...
```

Description in `tool_descriptions.md`:

```markdown
## valuation.estimate

**Use when**: visitor asks "how much is a villa like X worth" or "what's the price range for ...".

**Input**: criteria dict with keys like `location`, `bedrooms`, `sea_view`, `vineyard_area_ha`.

**Output**: range in EUR + confidence + notes.

**Do NOT use**: when discussing a specific property in the KG — use `kg.fetch` for that property's actual price.

**Example**:
User: "Quanto può valere una villa simile a Punta Lada?"
→ Call valuation.estimate(criteria={...}).
```

## `scoring/lead_scorecard.yaml`

Maps signals (emitted by tools and conversation events) to points. Score accumulates 0-100.

```yaml
version: 1
buckets:
  cold: { min: 0, max: 29 }
  warm: { min: 30, max: 69 }
  hot: { min: 70, max: 100 }

signals:
  - id: budget_revealed_above_5m
    points: 25
    emitted_by: ["conversation.budget_detected", "kg.search.query_filters.price.gte=5000000"]

  - id: specific_property_dwell_60s
    points: 10
    emitted_by: ["spatial.dwell_seconds.gte=60"]

  - id: viewing_request_intent
    points: 25
    emitted_by: ["conversation.intent=book_viewing"]

  - id: contact_info_provided
    points: 30
    emitted_by: ["form.contact_submitted"]

  - id: returning_visitor_prior_warm
    points: 15
    emitted_by: ["prior_session.bucket=warm"]

handoff_thresholds:
  default: hot
  per_tenant_override: true       # tenants can lower threshold to warm if desired
```

## `golden_dataset/conversations.jsonl`

One conversation per line. Format:

```json
{"id": "luxury-buyer-italian-001", "tags": ["luxury_buyer", "italian", "viewing_intent"], "input": [{"role": "user", "content": "Buongiorno, sto cercando una villa fronte mare in Costa Smeralda sotto i 15 milioni"}], "assertions": [{"type": "tool_called", "tool_id": "kg.search", "params_match": {"filters.location": "Costa Smeralda", "filters.max_price": {"lte": 15000000}}}, {"type": "response_language", "value": "it"}, {"type": "no_pushy_cta"}, {"type": "max_turns_to_property_match", "value": 2}]}
```

Assertion types are extensible. Common ones: `tool_called`, `tool_not_called`, `response_contains_entity`, `response_language`, `response_tone`, `max_turns_to_X`, `lead_score_after_conversation_gte`, `morph_directive_emitted`.

Minimum 50 conversations for shipping. Target 200 for v1.0. Add 5-10 per week from real production conversations (anonymized).

## Versioning rules

- `0.x.y`: pre-1.0, anything can break between minor versions. Be explicit in CHANGELOG.
- `1.0.0`: contract baseline. After this:
  - Patch (`1.0.x`): copy edits, prompt refinements, new few-shots, scoring tweaks within ±10%.
  - Minor (`1.x.0`): new personas, new morph rules, new tools, new components. Must be backward compatible with existing tenant configs.
  - Major (`x.0.0`): breaking schema changes, removed personas, removed tools. Requires `MIGRATIONS.md` entry and an ADR.

## Pre-flight checklist before merging a Pack PR

- [ ] `pack.yaml` parses, valid semver, owner set.
- [ ] `tools/lint-pack/main.py packs/<name>` exits 0.
- [ ] All morph YAMLs validate against schema.
- [ ] Snapshot tests pass.
- [ ] Eval passes (≥ threshold for the Pack).
- [ ] CHANGELOG updated.
- [ ] README updated if intent/ICP changed.
- [ ] `core_engine_version` constraint in pack.yaml still satisfied.

## Anti-patterns to refuse

- **Importing from another Pack.** Packs are isolated. If two Packs need the same thing, it's a core promotion candidate (ADR required).
- **Hardcoding tenant names or IDs anywhere in the Pack.** Tenant specifics belong in tenant.yaml.
- **Destructive migrations in ontology/schema_extension.sql.** Schema extensions are additive. Removals go through Pack major version + MIGRATIONS.md.
- **System prompt > 4000 tokens.** Trim. Move detail to few-shots or tool descriptions.
- **Golden dataset < 50 entries.** Don't merge.

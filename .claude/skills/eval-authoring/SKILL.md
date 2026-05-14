---
name: eval-authoring
description: How to write golden dataset entries and assertions for DigIdentity Pack evals. Used by pack-builder when creating or extending evaluation suites. Covers JSONL format, assertion types, scenario coverage strategy, and anti-patterns.
---

# Eval Authoring

Eval is what keeps DigIdentity honest across hundreds of prompt iterations. Without it, you can't tell whether you've improved or regressed. This skill defines how golden dataset entries are written.

## File and format

Golden datasets live at `packs/<vertical>/golden_dataset/conversations.jsonl`. One entry per line. Each entry is a JSON object describing an input conversation + assertions about the agent's behavior.

```json
{"id": "lux-it-greeting-001", "tags": ["luxury_buyer", "italian", "greeting"], "context": {"persona_hint": "luxury_buyer", "language": "it"}, "input": [{"role": "user", "content": "Buongiorno"}], "assertions": [{"type": "response_language", "value": "it"}, {"type": "response_tone", "value": "formal"}, {"type": "max_response_length_chars", "value": 300}, {"type": "no_pushy_cta"}]}
```

Field reference:

- `id` (string, required): unique within file, kebab-case, descriptive.
- `tags` (array of strings, optional): for filtering and reporting. Conventionally include persona, language, intent, special-case markers.
- `context` (object, optional): pre-conversation state injected before the agent runs.
- `input` (array, required): the user-side turns in the conversation. Always starts with `role: "user"`. May include prior assistant turns for multi-turn scenarios.
- `assertions` (array, required): list of assertions evaluated against the agent's response. ALL must pass for the scenario to pass.

## Context field — what you can inject

```json
"context": {
  "persona_hint": "luxury_buyer",          // forces persona for the test (no Sense classifier)
  "language": "it",                         // sets visitor language signal
  "geo": "IT-SS",                           // sets geo signal
  "is_returning": false,
  "prior_session": null,                    // or an object with prior session state
  "tenant_overrides": {                     // override tenant.yaml for this test
    "handoff_threshold": "warm"
  },
  "kg_fixture": "real-estate-luxury-base"   // load a specific seed dataset
}
```

The `kg_fixture` field references a fixture from `packs/<vertical>/golden_dataset/fixtures/`. Fixtures pre-seed the KG with deterministic data so the agent has stuff to find.

## Assertion catalog

### `response_language`
The agent's response is in the specified language.
```json
{"type": "response_language", "value": "it"}
```
Detection: simple lang-id (langdetect lib) plus heuristic checks.

### `response_tone`
Tone classification: formal, neutral, casual, salesy.
```json
{"type": "response_tone", "value": "formal"}
```
Detection: LLM judge or keyword heuristic.

### `max_response_length_chars`
Total character count of the assistant turn(s) doesn't exceed value.
```json
{"type": "max_response_length_chars", "value": 500}
```

### `min_response_length_chars`
Floor on length, for cases where one-liners are too curt.
```json
{"type": "min_response_length_chars", "value": 50}
```

### `response_contains_entity`
Response mentions a specific entity from the KG by name.
```json
{"type": "response_contains_entity", "value": "Villa Smeralda"}
```

### `response_does_not_contain`
Negative substring match.
```json
{"type": "response_does_not_contain", "value": "limited time offer"}
```

### `tool_called`
The agent called a specific tool, with optional parameter match.
```json
{"type": "tool_called", "tool_id": "kg.search", "params_match": {"entity_type": "property", "filters.max_price": {"lte": 15000000}}}
```
`params_match` supports nested dot paths and operators (`lte`, `gte`, `equals`, `equals_any`, `contains`).

### `tool_not_called`
Tool was NOT called.
```json
{"type": "tool_not_called", "tool_id": "lead.trigger_handoff"}
```

### `tool_call_count`
Number of times a tool was called.
```json
{"type": "tool_call_count", "tool_id": "kg.search", "value": {"lte": 2}}
```

### `max_turns_to_X`
Within N turns, achieve outcome X.
```json
{"type": "max_turns_to_property_match", "value": 3}
{"type": "max_turns_to_handoff", "value": 6}
```

### `directive_emitted`
Agent emitted a rendering directive.
```json
{"type": "directive_emitted", "directive_type": "highlight", "target_match": "property_id_*"}
```

### `lead_score_after`
Lead score after the conversation is in expected range.
```json
{"type": "lead_score_after", "value": {"gte": 50, "lte": 80}}
```

### `no_pushy_cta`
Shorthand for `response_does_not_contain` on a known list of pushy phrases.
```json
{"type": "no_pushy_cta"}
```
The pushy phrase list is in `core/eval/assertion_libs/no_pushy_cta.json`.

### `llm_judge`
Free-form judge with a rubric. The most flexible (and most expensive) assertion.
```json
{"type": "llm_judge", "rubric": "The response acknowledges the visitor's interest in vineyard estates and offers either a specific property match or a clarifying question. The response is polite and does not list properties they did not ask about.", "min_score": 4.0}
```
Uses Opus 4.7 as judge. Score 1-5. Threshold is the min_score.

## Coverage strategy

For each Pack, aim for these coverage axes:

**Persona coverage**: at least 5 scenarios per declared persona.

**Intent coverage**: at least 3 scenarios per canonical intent (greeting, search, qualify, book, objection, handoff, return, info-only, abandon).

**Language coverage**: parity between supported locales. If `it-IT` has 60 scenarios, `en-GB` should have at least 30.

**Edge cases**: at least 10 adversarial scenarios per Pack (rude visitor, off-topic, prompt injection attempt, demands free service, asks about competitor).

**Tool path coverage**: every tool registered in `pack.yaml` is exercised by at least 2 scenarios.

**Negative paths**: scenarios where the agent should NOT call a tool (e.g., handoff threshold not met, visitor not qualified yet).

## Hand-writing the first 50

Process:

1. Open the agency owner's real inbox / call recordings (anonymized, with permission).
2. Pick the 10 most common opening messages. Convert to scenarios.
3. Pick the 10 most common confusing or escalation moments. Convert.
4. Pick the 5 most common rude/abusive messages. Convert.
5. Pick 5 prompt injection attempts you can think of. Convert.
6. Generate 20 synthetic scenarios spanning personas not yet covered.

Don't aim for perfect assertions from day one. Even loose assertions (`response_language`, `max_response_length_chars`) prevent obvious regressions.

## Multi-turn scenarios

For multi-turn flows, alternate user/assistant turns in `input`:

```json
{
  "id": "lux-multiturn-vineyard-001",
  "input": [
    {"role": "user", "content": "Cerco una tenuta con vigneto in Toscana"},
    {"role": "assistant", "content": "Posso aiutarvi. Avete una fascia di prezzo o un'area specifica in mente?"},
    {"role": "user", "content": "Intorno ai 10 milioni, preferibilmente nel Chianti"}
  ],
  "assertions": [
    {"type": "tool_called", "tool_id": "kg.search", "params_match": {"filters.location_includes": "Chianti", "filters.max_price": {"lte": 10000000}, "filters.has_vineyard": true}},
    {"type": "response_contains_entity", "value": "Tenuta del Chianti"}
  ]
}
```

The harness re-plays the conversation: the first turn is the user message, then the assistant turn IS the ground truth (not re-generated). The harness generates only the FINAL assistant turn and asserts against that.

## Anti-patterns

- **Exact-string assertions on agent output.** Models vary. Use semantic assertions (`response_contains_entity`, `tool_called`) instead.
- **Assertions with no failure mode.** "Response should be helpful" is unverifiable. Make it concrete.
- **Tagging everything with every tag.** Tags lose meaning. Use them sparingly and consistently.
- **Scenarios that depend on production data.** Use fixtures. Production data changes.
- **Mega-scenarios with 15 turns.** Split into smaller scenarios. Long ones make failures hard to diagnose.
- **Asserting tool params with exact equality on natural language.** Use `contains` or regex.
- **No negative scenarios.** A suite where everything passes proves nothing. Include scenarios designed to make the agent refuse, escalate, or ignore.

## Maintenance discipline

- Add 5-10 scenarios per week from real production conversations (after anonymization).
- Quarterly: re-baseline. Look at the dataset, remove obsolete scenarios, add coverage gaps.
- When a customer reports a regression, write the scenario FIRST (red), then fix (green). Standard TDD applied to prompts.
- Tag scenarios that came from real bugs: `tags: ["regression-2026-Q2", ...]`. Never delete them.

## Running locally

```bash
# Eval one Pack
make eval PACK=real-estate-luxury

# Eval one scenario
make eval PACK=real-estate-luxury SCENARIO=lux-it-greeting-001

# Eval with debug output (full LLM reasoning visible)
make eval PACK=real-estate-luxury VERBOSE=1

# Compare current vs baseline
make eval-diff PACK=real-estate-luxury
```

## When eval results disagree with your gut

The dataset wins. Your gut is hindsight. If a scenario passes that "feels" worse than before, either:

1. The assertion is too loose — tighten it.
2. The scenario doesn't cover the dimension you care about — add one that does.

Never weaken assertions to make red tests pass. That defeats the purpose.

---
name: prompt-conventions
description: Conventions for authoring agent system prompts, tool descriptions, and few-shot examples in DigIdentity Packs. Optimized for Claude Sonnet 4.6 / Opus 4.7 with prompt caching and tool calling.
---

# Prompt Conventions

This skill defines how to write prompts that the DigIdentity Agent Orchestrator will load. Bad prompts produce bad agents regardless of model quality. The conventions here are tuned for Anthropic Claude (primary) with OpenAI GPT-5 fallback (secondary).

## Structural template for `prompts/system.md`

System prompts follow a fixed structure to enable prompt caching (Anthropic prompt caching keys on a stable prefix) and to make per-section debugging easier.

```markdown
# System Prompt — <Pack Display Name>

## Role
<Single paragraph. Who the agent is, what it represents, scope.>

## Identity
<Two to four sentences on tone, voice, formality register. Language defaults.>

## Domain knowledge
<Compact, factual context about the vertical. NOT a knowledge base — that's what KG search is for. This is etiquette, market norms, common visitor types.>

## Personas you may encounter
<Brief description of each persona declared in personas.yaml. One line per persona on how to adapt.>

## Tool use
<Brief guidance on when to use tools. Tool descriptions themselves live in tool_descriptions.md and are appended to context separately.>

## Conversation flow
<5-8 bullet points describing the canonical happy path: greeting → intent discovery → search/present → qualify → handoff.>

## Hard rules
<Bulleted list of non-negotiables. "Never X." "Always Y." Keep to <10 rules.>

## Tone and language rules
<Specific language do's and don'ts. Italian formal register, English equivalents, etc.>

## Output guidelines
<Length, formatting, when to use markdown, when not to. Mobile-aware defaults.>
```

## Length budgets

- System prompt: target 1500-2500 tokens. Hard ceiling 4000 tokens.
- Tool descriptions (all combined): target 1500-3000 tokens. Hard ceiling 5000.
- Few-shots in context per turn: 0-2 examples max, only when persona is novel or intent is unusual.

Why these budgets: latency. Each 1000 tokens of system context adds ~50-100 ms to TTFC depending on cache state. Aim for sub-800ms TTFC.

## Cached prefix strategy

The orchestrator sends the system prompt + tool descriptions as a CACHED PREFIX. Anything that changes per-conversation goes AFTER the cache breakpoint. To make this work:

- The system prompt MUST be deterministic for a given Pack + Tenant config. No timestamps, no random tokens.
- Tenant-specific overrides are applied via dedicated injection point at the END of system.md, marked with `<!-- TENANT_OVERRIDES -->`. The orchestrator injects tenant content there. The pre-marker portion stays cacheable.

Example footer of system.md:

```markdown
## Tenant-specific context

<!-- TENANT_OVERRIDES -->

(The line above is replaced by the orchestrator with tenant.yaml content at runtime. Leave the marker exactly as shown.)
```

## Tool descriptions format

Each tool description in `tool_descriptions.md` follows this template:

```markdown
## <tool_id>

**Purpose**: One line.

**Use when**: Bulleted list of triggering conditions in natural language.

**Do NOT use when**: Bulleted list of contraindications.

**Parameters**:
- `param1` (type, required): Description.
- `param2` (type, optional, default=X): Description.

**Returns**: What the tool gives back.

**Example**:
User: "<typical user phrasing>"
→ Call <tool_id>(param1=..., param2=...)
→ Returns: <example result>
```

The "Use when" and "Do NOT use when" are the most important parts. Models tool-call correctly when they have explicit decision triggers, not just descriptions.

## Few-shot authoring

Few-shots are stored in `prompts/few_shots/*.jsonl`. They're loaded selectively by the orchestrator based on detected persona or intent. Format:

```json
{"id": "fs-greeting-luxury-it-001", "persona": "luxury_buyer", "intent": "greeting", "language": "it", "messages": [{"role": "user", "content": "Buongiorno"}, {"role": "assistant", "content": "Buongiorno. Sono il consulente digitale di [agenzia]. Posso aiutarvi a esplorare le proprietà disponibili, o avete una domanda specifica?"}]}
```

Rules:
- Tag few-shots with persona, intent, language for retrieval.
- Keep few-shots SHORT (1-3 turns). Long ones consume budget without helping.
- Ground them in real conversations from production (anonymized) whenever possible.
- Avoid putting tool calls in few-shots unless the lesson IS the tool call decision.

## Tone and language defaults

For Italian (default for IT tenants):

- Formal register: "voi" plural even when one person. "Loro" only for very high-end formal settings.
- Never use English business jargon (CTA, conversion, lead, prospect). Use "interesse", "contatto", "richiesta".
- Avoid emojis unless tenant.yaml explicitly enables them.
- Avoid markdown formatting in chat output (no `**bold**`, no `# headers`) unless the visitor uses it first.

For English (international tenants):

- British English by default for European tenants; American for US tenants.
- Same caution on jargon.

## Anti-patterns in prompts

- **"You are an AI assistant..."** Cliché preamble. Replace with role specific to the Pack.
- **"You must be helpful, harmless, honest."** Restating model defaults. Remove.
- **Long bulleted lists in system prompt.** Models stop reading at ~30 bullets. If you need more, restructure into sections.
- **Sales-y language in prompts.** "Convert the user", "drive conversion". The model picks up this energy. Use neutral language: "assist the visitor in their search".
- **Speculative knowledge.** "If asked about competitor X, say Y." Models hallucinate around this. Use KG search instead.
- **Hardcoded property names or prices.** Always via KG fetch.
- **Negation overload.** Models follow positive instructions better than negatives. Replace "do not be pushy" with "maintain a calm, advisory tone".

## XML tags for structured guidance

For complex structured guidance INSIDE a prompt section, use XML-style tags. They improve adherence with Claude:

```markdown
## Qualifying conversation

<qualifying_signals>
Listen for these signals during conversation:
- Budget mentioned
- Timeline mentioned ("next month", "this year")
- Decision-maker indicators ("we", "my husband and I", "with my advisor")
- Specific geography
</qualifying_signals>

<qualifying_dont_do>
- Direct budget questions in first 3 turns
- Demanding contact info before any value provided
- "What's your phone number?" type questions
</qualifying_dont_do>
```

This pattern is more reliable than prose for guidance with many discrete items.

## Updating prompts: version discipline

- Patch version (1.0.x): copy edits, single-line additions. No need for ADR.
- Minor version (1.x.0): structural changes to the prompt, new sections. Run full eval before shipping.
- Major version (x.0.0): personality shift, significant scope change. Requires ADR.

Always commit prompt changes with: (a) before/after snippet in commit message, (b) eval results from `eval-runner`, (c) reason in 1-2 lines.

## Testing prompts

Before merging any prompt change:

```bash
# Run eval on the Pack
make eval PACK=<name>

# Read the regression report carefully
# Even improvements in some scenarios may regress others
```

Common pitfall: tweaking the prompt to fix one failing scenario breaks three passing ones. The golden dataset catches this. Always run full Pack eval, not just the scenario you're fixing.

## Multi-language prompts

When a Pack supports multiple languages:

- Single `system.md` with sections labeled by language, OR
- Per-language file (`system.it.md`, `system.en.md`) when divergence is significant.

The orchestrator selects based on detected visitor language. The transition between languages is signaled by the agent itself ("Switching to English. How can I help you?") rather than silently.

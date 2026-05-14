# `.claude/` — Claude Code configuration

This directory configures how Claude Code behaves on the DigIdentity Living Site repository. Everything here is committed to git (it's part of the project's operating manual). Personal-only overrides go in `~/.claude/` (your home directory), never here.

## What's here

```
.claude/
├── agents/                 # Subagents: specialized AI personas
│   ├── architect.md
│   ├── pack-builder.md
│   ├── engine-implementer.md
│   └── eval-runner.md
├── skills/                 # On-demand technical knowledge
│   ├── morph-dsl/SKILL.md
│   ├── pack-structure/SKILL.md
│   ├── prompt-conventions/SKILL.md
│   ├── python-async-conventions/SKILL.md
│   ├── sqlalchemy-rls/SKILL.md
│   ├── fastapi-streaming/SKILL.md
│   ├── typescript-rsc/SKILL.md
│   └── eval-authoring/SKILL.md
├── commands/               # Slash commands for repeatable workflows
│   ├── new-adr.md
│   ├── new-pack.md
│   ├── run-eval.md
│   ├── promote-to-core.md
│   ├── dev-up.md
│   └── tenant-test.md
├── hooks/                  # Lifecycle automation
│   ├── pre-commit-secrets.sh
│   ├── pre-merge-eval.sh
│   ├── pre-deploy-rls-check.py
│   └── post-edit-sql-format.sh
└── README.md               # this file
```

## How they relate

**CLAUDE.md** (repo root) is always loaded. It tells Claude Code the project conventions and which subagent to dispatch for which kind of task.

**Subagents** are isolated "specialists". When Claude Code identifies an architectural question, it delegates to `architect` (which loads `architect.md` as system prompt and runs in its own context). Same pattern for `pack-builder`, `engine-implementer`, `eval-runner`. Each subagent declares which skills it pre-loads.

**Skills** are deep technical references. They're loaded contextually — either pre-loaded by a subagent's `skills:` frontmatter, or auto-invoked by Claude Code when the description matches the task at hand.

**Slash commands** are user-initiated shortcuts. You type `/new-pack real-estate-luxury` to scaffold a new Pack; the command runs the canonical setup steps without you having to remember them.

**Hooks** are deterministic enforcement. They run on git/Claude Code lifecycle events (pre-commit, pre-merge, post-edit) and can block actions that violate project rules.

## Bootstrapping a fresh machine

1. Install Claude Code (latest version supporting Skills/Subagents/Plugins).
2. Clone this repo.
3. Open the repo with Claude Code from the repo root: `claude code .` (or open in IDE with Claude Code integration).
4. Claude Code auto-discovers `.claude/` and loads all subagents, skills, and commands.
5. Verify by running `/agents list` — you should see architect, pack-builder, engine-implementer, eval-runner.

Personal preferences (e.g., your favorite shell, your tone preferences) go in `~/.claude/CLAUDE.md` and `~/.claude/agents/`, not here.

## Updating this configuration

- Adding a new subagent: create the markdown file under `agents/`, restart Claude Code (or invoke via `/agents reload`).
- Adding a new skill: create the directory under `skills/` with `SKILL.md` (frontmatter `name` + `description` mandatory).
- Adding a new slash command: create `<name>.md` under `commands/`.
- Adding a hook: create the script under `hooks/`, register it in `settings.json` if applicable.

All additions should be discussed via PR like any other code change. The `architect` subagent should be consulted if the addition has structural implications.

---
name: run-eval
description: Run eval against a Pack golden dataset and report results. Delegates to the eval-runner subagent. $ARGUMENTS is the pack slug (or "all").
---

Delegate to the `eval-runner` subagent.

Pack target: $ARGUMENTS

If `$ARGUMENTS` is empty or `all`, run the full suite.

The subagent will:

1. Determine scope from git diff.
2. Run the appropriate make target (`make eval PACK=<name>` or `make eval-all`).
3. Parse `eval-reports/<timestamp>.json` and compare against baseline.
4. Output a structured report following its standard format.
5. Set exit code: 0 for PASS, 1 for REGRESSION, 0 with warning for DEGRADED.

Do not propose fixes to failing scenarios. Report only.

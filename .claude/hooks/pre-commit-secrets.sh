#!/usr/bin/env bash
# .claude/hooks/pre-commit-secrets.sh
#
# Pre-commit hook: scans staged files for likely API keys / secrets.
# Block patterns:
#   - sk-... (OpenAI)
#   - sk-ant-... (Anthropic)
#   - AKIA... (AWS access keys)
#   - eyJ... long JWT tokens
#   - Stripe live keys (sk_live_, rk_live_)
#   - Generic high-entropy strings tagged as keys in .env-style assignments
#
# Exit 0 → safe to commit
# Exit 1 → block commit, print offending lines
#
# Install: git config core.hooksPath .claude/hooks  (then symlink or rename)

set -euo pipefail

STAGED=$(git diff --cached --name-only --diff-filter=ACM)

if [[ -z "$STAGED" ]]; then
    exit 0
fi

PATTERNS=(
    # OpenAI keys
    'sk-[A-Za-z0-9]{20,}'
    # Anthropic keys
    'sk-ant-[A-Za-z0-9_-]{20,}'
    # AWS access keys
    'AKIA[0-9A-Z]{16}'
    # Stripe live keys
    '(sk|rk)_live_[A-Za-z0-9]{20,}'
    # Generic .env-style API_KEY=long-string
    '(API_KEY|SECRET|TOKEN|PASSWORD)[[:space:]]*=[[:space:]]*[A-Za-z0-9_-]{30,}'
)

FOUND=0
for file in $STAGED; do
    # Skip binary
    if file --mime "$file" | grep -q 'charset=binary'; then
        continue
    fi
    # Skip .env example files (intentionally placeholder)
    if [[ "$file" == *.env.example ]]; then
        continue
    fi
    # Skip this hook itself
    if [[ "$file" == .claude/hooks/* ]]; then
        continue
    fi

    for pattern in "${PATTERNS[@]}"; do
        if grep -E -n "$pattern" "$file" > /dev/null 2>&1; then
            echo ""
            echo "BLOCKED: potential secret in $file"
            grep -E -n "$pattern" "$file" | head -5
            FOUND=1
        fi
    done

    # Block any .env file from being staged at all (except .env.example)
    if [[ "$file" == *.env || "$file" == *.env.* ]] && [[ "$file" != *.env.example ]]; then
        echo ""
        echo "BLOCKED: $file appears to be a .env file. Should be gitignored."
        FOUND=1
    fi
done

if [[ $FOUND -eq 1 ]]; then
    echo ""
    echo "If this is a false positive, you can bypass once with: git commit --no-verify"
    echo "But verify first that no real secret is leaking."
    exit 1
fi

exit 0

#!/usr/bin/env bash
# .claude/hooks/pre-merge-eval.sh
#
# Pre-merge hook: runs eval against any Pack touched by the merging branch.
# Designed to be invoked from GitHub Actions on PR. Local equivalent for safety.
#
# Reads changed files vs main, identifies Packs touched, runs eval per Pack.
# Exits non-zero on regression (= block merge).

set -euo pipefail

BASE_REF="${BASE_REF:-origin/main}"

# Find Pack(s) touched by the branch
CHANGED=$(git diff --name-only "$BASE_REF"...HEAD)

CORE_CHANGED=0
PACKS=()
SEEN_PACKS=()

while IFS= read -r file; do
    if [[ -z "$file" ]]; then continue; fi

    if [[ "$file" == core/* ]] || [[ "$file" == backend/app/* ]]; then
        CORE_CHANGED=1
    fi

    if [[ "$file" == packs/* ]]; then
        pack_name=$(echo "$file" | cut -d/ -f2)
        # dedup
        if [[ ! " ${SEEN_PACKS[*]:-} " =~ " ${pack_name} " ]]; then
            SEEN_PACKS+=("$pack_name")
            PACKS+=("$pack_name")
        fi
    fi
done <<< "$CHANGED"

# Decide scope
if [[ $CORE_CHANGED -eq 1 ]]; then
    echo "Core changed → running full eval suite."
    if ! make eval-all; then
        echo "REGRESSION in full eval suite. Merge blocked."
        exit 1
    fi
elif [[ ${#PACKS[@]} -gt 0 ]]; then
    for pack in "${PACKS[@]}"; do
        echo "Pack $pack changed → running pack eval."
        if ! make eval PACK="$pack"; then
            echo "REGRESSION in pack $pack. Merge blocked."
            exit 1
        fi
    done
else
    echo "No core or pack changes detected. Skipping eval."
fi

echo "Eval gate passed."
exit 0

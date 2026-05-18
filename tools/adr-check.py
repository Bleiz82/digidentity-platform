#!/usr/bin/env python3
"""adr-check.py — verify all ADRs have a valid non-Rejected status.

Exit 0: all ADRs OK.
Exit 1: one or more ADRs missing status or marked Rejected.
"""

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ADR_DIR = _REPO_ROOT / "docs" / "adr"

_STATUS_RE = re.compile(r"\*{0,2}[Ss]tatus\*{0,2}\s*:?\**\s*(.+)", re.IGNORECASE)
_REJECTED_RE = re.compile(r"^rejected", re.IGNORECASE)
_SKIP = {"_template.md"}


def check_file(path: Path) -> str | None:
    """Return error string if the file fails; None if OK."""
    content = path.read_text(encoding="utf-8")
    m = _STATUS_RE.search(content)
    if not m:
        return f"{path.name}: no Status field found"
    status = m.group(1).strip().rstrip(".").rstrip("*")
    if _REJECTED_RE.match(status):
        return f"{path.name}: status is '{status}' — Rejected ADRs must be removed or superseded"
    return None


def main() -> int:
    adr_files = sorted(f for f in _ADR_DIR.glob("*.md") if f.name not in _SKIP)

    if not adr_files:
        print("No ADR files found — check docs/adr/ exists.")
        return 0

    errors: list[str] = []
    for path in adr_files:
        err = check_file(path)
        if err:
            errors.append(err)
            print(f"FAIL  {err}", file=sys.stderr)
        else:
            print(f"OK    {path.name}")

    print()
    if errors:
        print(f"{len(errors)} ADR(s) failed status check.", file=sys.stderr)
        return 1

    print(f"{len(adr_files)} ADR(s) checked — all valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

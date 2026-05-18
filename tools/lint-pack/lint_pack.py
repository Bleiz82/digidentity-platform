#!/usr/bin/env python3
"""lint_pack.py — validates morph rule YAML files against the DSL JSON Schema (BIBLE-v3 §8)."""

import argparse
import json
import sys
from pathlib import Path

import jsonschema
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = _REPO_ROOT / "core" / "dsl" / "morph_rule.schema.json"


def _load_schema() -> dict:
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def validate_file(path: Path, schema: dict) -> list[str]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{path}: {list(e.path)}: {e.message}"
        for e in sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lint morph rule YAML files against core/dsl/morph_rule.schema.json"
    )
    parser.add_argument("files", nargs="*", type=Path, metavar="FILE")
    parser.add_argument("--all", dest="all_packs", action="store_true",
                        help="Validate all packs/**/morph_rules/*.yaml")
    args = parser.parse_args(argv)

    if not args.all_packs and not args.files:
        parser.error("provide FILE(s) or --all")

    schema = _load_schema()

    files: list[Path] = (
        list(_REPO_ROOT.glob("packs/**/morph_rules/*.yaml"))
        if args.all_packs
        else args.files
    )

    if not files:
        print("No files to validate.")
        return 0

    all_errors: list[str] = []
    for path in files:
        errors = validate_file(path, schema)
        all_errors.extend(errors)
        status = "OK" if not errors else "FAIL"
        print(f"[{status}] {path}")
        for err in errors:
            print(f"  ERROR: {err}", file=sys.stderr)

    if all_errors:
        print(f"\n{len(all_errors)} error(s) found.", file=sys.stderr)
        return 1

    print(f"\n{len(files)} file(s) validated OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

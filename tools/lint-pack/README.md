# lint-pack

Validates morph rule YAML files against `core/dsl/morph_rule.schema.json` (JSON Schema draft 2020-12).

## Usage

```bash
# validate specific files
python tools/lint-pack/lint_pack.py packs/real-estate-luxury/morph_rules/homepage.yaml

# validate all packs
python tools/lint-pack/lint_pack.py --all
```

Exit code 0 = all valid. Exit code 1 = one or more errors.

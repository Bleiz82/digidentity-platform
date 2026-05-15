"""CLI entry point for the eval framework.

Usage:
    uv run python scripts/run_eval.py --set retrieval_real_estate
    uv run python scripts/run_eval.py --all
    uv run python scripts/run_eval.py --set router_correctness --calibrate

Exit codes:
    0 — all thresholds pass (or calibration mode)
    1 — at least one threshold failed
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add src to python path for imports when run directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# Add parent so `scripts.seed_real_estate` is importable from runner
sys.path.insert(0, str(Path(__file__).parent.parent))

from digidentity_api.evals.cases import load_eval_set
from digidentity_api.evals.runner import EvalRunner

EVALS_DIR = Path(__file__).parent.parent / "evals"
RESULTS_DIR = Path(__file__).parent.parent / "eval-results"


def _find_eval_files() -> list[Path]:
    """Return all .yaml files in the evals directory."""
    return sorted(EVALS_DIR.glob("*.yaml"))


def _find_eval_file(set_name: str) -> Path | None:
    """Find a YAML file by set name (filename stem)."""
    # Try exact match first
    candidate = EVALS_DIR / f"{set_name}.yaml"
    if candidate.exists():
        return candidate
    # Try case-insensitive
    for f in EVALS_DIR.glob("*.yaml"):
        if f.stem.lower() == set_name.lower():
            return f
    return None


def _write_result(result_dict: dict, set_name: str) -> Path:
    """Write result JSON to eval-results directory."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_name = set_name.replace(" ", "_").replace("/", "_")
    output_path = RESULTS_DIR / f"{timestamp}_{safe_name}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result_dict, f, indent=2, default=str)
    return output_path


async def _run_single(
    yaml_path: Path,
    db_url: str | None,
    force_calibrate: bool,
) -> tuple[bool, str]:
    """Run a single eval set. Returns (passed, markdown_report)."""
    eval_set = load_eval_set(yaml_path)

    if force_calibrate:
        # Override calibration_mode
        from dataclasses import replace
        eval_set = replace(eval_set, calibration_mode=True)

    runner = EvalRunner()
    result = await runner.run_set(eval_set, db_url=db_url)

    # Write JSON result
    output_path = _write_result(result.to_dict(), yaml_path.stem)
    print(f"Result written to: {output_path}", flush=True)

    # Print markdown to stdout
    report = result.to_markdown()
    print(report, flush=True)
    print("", flush=True)

    return result.passed, report


async def main() -> int:
    parser = argparse.ArgumentParser(description="DigIdentity eval runner")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--set", metavar="SET_NAME", help="Run a specific eval set by name")
    group.add_argument("--all", action="store_true", help="Run all eval sets in evals/")
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Force calibration mode (thresholds logged but not enforced)",
    )
    parser.add_argument(
        "--db-url",
        metavar="URL",
        default=os.environ.get("DATABASE_URL"),
        help="Postgres URL for retrieval evals (overrides testcontainers)",
    )
    args = parser.parse_args()

    db_url: str | None = args.db_url
    force_calibrate: bool = args.calibrate

    if args.all:
        yaml_files = _find_eval_files()
        if not yaml_files:
            print(f"No .yaml files found in {EVALS_DIR}", file=sys.stderr)
            return 1
    else:
        yaml_file = _find_eval_file(args.set)
        if yaml_file is None:
            print(f"Eval set not found: {args.set}", file=sys.stderr)
            print(f"Available: {[f.stem for f in _find_eval_files()]}", file=sys.stderr)
            return 1
        yaml_files = [yaml_file]

    overall_passed = True
    for yaml_path in yaml_files:
        print(f"\nRunning eval: {yaml_path.stem}", flush=True)
        print("=" * 60, flush=True)
        passed, _ = await _run_single(yaml_path, db_url, force_calibrate)
        if not passed:
            overall_passed = False

    if overall_passed:
        print("\nAll evals PASSED (or in calibration mode).", flush=True)
        return 0
    else:
        print("\nSome evals FAILED. See reports above.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

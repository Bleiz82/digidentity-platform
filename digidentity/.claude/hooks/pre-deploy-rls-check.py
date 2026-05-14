#!/usr/bin/env python3
"""
.claude/hooks/pre-deploy-rls-check.py

Static check: every FastAPI route handler under tenant-scoped paths must use
the `with_tenant(...)` context manager. If a handler queries the DB without
entering the tenant context, this hook fails and blocks deploy.

Heuristic but high-signal. The principle: if a function under routes/ has an
`async def` whose body references session methods (`session.execute`,
`session.scalar`, etc.) without `with_tenant`, it's suspicious.

Usage:
    python .claude/hooks/pre-deploy-rls-check.py backend/app/routes/

Exit codes:
    0 → all routes look correctly tenant-scoped
    1 → at least one route is suspect
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


SUSPECT_CALLS = {
    "session.execute",
    "session.scalar",
    "session.scalars",
    "session.get",
    "db.execute",
    "db.scalar",
    "db.scalars",
}


def _attr_path(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return f"{_attr_path(node.value)}.{node.attr}"
    if isinstance(node, ast.Name):
        return node.id
    return "<unknown>"


def _has_with_tenant(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.AsyncWith):
            for item in child.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Call) and _attr_path(ctx.func).endswith("with_tenant"):
                    return True
    return False


def _has_db_query(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            path = _attr_path(child.func)
            for suspect in SUSPECT_CALLS:
                if path.endswith(suspect):
                    return True
    return False


def _is_route_handler(func: ast.AsyncFunctionDef) -> bool:
    for dec in func.decorator_list:
        path = _attr_path(dec if not isinstance(dec, ast.Call) else dec.func)
        if any(method in path for method in ("router.get", "router.post", "router.put", "router.delete", "router.patch", "app.get", "app.post", "app.put", "app.delete", "app.patch")):
            return True
    return False


def scan_file(path: Path) -> list[str]:
    issues: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        return [f"{path}: syntax error {e}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and _is_route_handler(node):
            if _has_db_query(node) and not _has_with_tenant(node):
                issues.append(
                    f"{path}:{node.lineno}: handler `{node.name}` performs DB queries without `with_tenant(...)` — RLS at risk."
                )
    return issues


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: pre-deploy-rls-check.py <path-to-routes-dir>")
        return 2

    base = Path(argv[1])
    if not base.exists():
        print(f"Path not found: {base}")
        return 2

    files = list(base.rglob("*.py"))
    all_issues: list[str] = []
    for f in files:
        all_issues.extend(scan_file(f))

    if all_issues:
        print("RLS hook found suspect route handlers:\n")
        for issue in all_issues:
            print(f"  {issue}")
        print(
            "\nIf a flagged handler is a legitimate exception (admin route, non-tenant data), "
            "annotate it with a comment `# rls-exempt: <reason>` on the route decorator line, "
            "and exclude from this check via .clauderlsignore."
        )
        return 1

    print(f"RLS check passed: {len(files)} files scanned, 0 issues.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

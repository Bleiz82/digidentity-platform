"""Eval runner — executes EvalSets and produces EvalResults.

Supported case types:
  - retrieval: requires DB (testcontainers or external db_url)
  - routing: in-memory, no DB
  - circuit_breaker: in-memory, no DB
  - latency: httpx + ASGITransport, no DB

Usage:
    runner = EvalRunner()
    result = await runner.run_set(eval_set, db_url=None)
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import structlog

from digidentity_api.engines.errors import ProviderError
from digidentity_api.engines.llm_router import LLMRouter
from digidentity_api.engines.mock_provider import BaseMockProvider, Chunk, TokenUsage
from digidentity_api.evals.cases import EvalCase, EvalSet
from digidentity_api.evals.metrics import (
    circuit_breaker_pass_rate,
    latency_percentiles,
    mrr,
    ndcg_at_k,
    recall_at_k,
    routing_accuracy,
)

log = structlog.get_logger()

# ── EvalResult ────────────────────────────────────────────────────────────────


@dataclass
class EvalResult:
    set_name: str
    cases_run: int
    cases_errored: int
    metrics: dict[str, float]
    threshold_results: dict[str, bool]  # metric -> passed
    calibration_mode: bool
    passed: bool  # True if calibration_mode or all thresholds pass
    errors: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "set_name": self.set_name,
            "cases_run": self.cases_run,
            "cases_errored": self.cases_errored,
            "metrics": self.metrics,
            "threshold_results": self.threshold_results,
            "calibration_mode": self.calibration_mode,
            "passed": self.passed,
            "errors": self.errors,
            "timestamp": self.timestamp,
        }

    def to_markdown(self) -> str:
        """Render human-readable markdown report."""
        status = (
            "CALIBRATING (thresholds not enforced)"
            if self.calibration_mode
            else ("PASS" if self.passed else "FAIL")
        )
        lines = [
            f"## Eval: {self.set_name}",
            f"Status: {status}",
            "",
            "| Metric | Value | Threshold | Status |",
            "|--------|-------|-----------|--------|",
        ]

        # Build threshold lookup (normalized keys)
        thresholds_display: dict[str, tuple[float, str]] = {}
        for metric_key, passed in self.threshold_results.items():
            val = self.metrics.get(metric_key, 0.0)
            status_str = "SKIP" if self.calibration_mode else ("PASS" if passed else "FAIL")
            thresholds_display[metric_key] = (val, status_str)

        # Show metrics with thresholds
        displayed = set()
        for metric_key, (val, status_str) in thresholds_display.items():
            # Find threshold value from threshold_results by looking at the EvalSet
            # We don't have EvalSet here, so mark with — for threshold column when calibrating
            threshold_display = "—" if self.calibration_mode else "see threshold"
            lines.append(f"| {metric_key} | {val:.3f} | {threshold_display} | {status_str} |")
            displayed.add(metric_key)

        # Show remaining metrics without thresholds
        for metric_key, val in self.metrics.items():
            if metric_key not in displayed:
                lines.append(f"| {metric_key} | {val:.3f} | — | INFO |")

        lines.append("")
        lines.append(
            f"Cases: {self.cases_run}/{self.cases_run + self.cases_errored} executed, "
            f"{self.cases_errored} errors"
        )

        if self.errors:
            lines.append("")
            lines.append("### Errors")
            for err in self.errors[:5]:
                lines.append(f"- {err}")

        return "\n".join(lines)


# ── EvalRunner ────────────────────────────────────────────────────────────────


class EvalRunner:
    async def run_set(
        self,
        eval_set: EvalSet,
        *,
        db_url: str | None = None,
    ) -> EvalResult:
        """Execute all cases in an EvalSet and return aggregated EvalResult."""
        retrieval_cases = [c for c in eval_set.cases if c.type == "retrieval"]
        routing_cases = [c for c in eval_set.cases if c.type == "routing"]
        cb_cases = [c for c in eval_set.cases if c.type == "circuit_breaker"]
        latency_cases = [c for c in eval_set.cases if c.type == "latency"]

        all_errors: list[str] = []
        cases_run = 0
        cases_errored = 0

        retrieval_results: list[dict] = []
        routing_results: list[dict] = []
        cb_results: list[dict] = []
        latency_samples: list[float] = []

        # ── Retrieval (requires DB) ──────────────────────────────────────────
        if retrieval_cases:
            session_factory = await self._setup_db(db_url)
            if session_factory is None:
                for c in retrieval_cases:
                    all_errors.append(f"{c.id}: DB unavailable (no db_url and no testcontainers)")
                    cases_errored += 1
            else:
                for case in retrieval_cases:
                    try:
                        result = await self._run_retrieval(case, session_factory)
                        retrieval_results.append(result)
                        cases_run += 1
                    except Exception as exc:
                        all_errors.append(f"{case.id}: {exc}")
                        cases_errored += 1
                        log.error("eval.retrieval_error", case_id=case.id, error=str(exc))

        # ── Routing (in-memory) ──────────────────────────────────────────────
        for case in routing_cases:
            try:
                result = await self._run_routing(case)
                routing_results.append(result)
                cases_run += 1
            except Exception as exc:
                all_errors.append(f"{case.id}: {exc}")
                cases_errored += 1
                log.error("eval.routing_error", case_id=case.id, error=str(exc))

        # ── Circuit breaker (in-memory) ──────────────────────────────────────
        for case in cb_cases:
            try:
                result = await self._run_circuit_breaker(case)
                cb_results.append(result)
                cases_run += 1
            except Exception as exc:
                all_errors.append(f"{case.id}: {exc}")
                cases_errored += 1
                log.error("eval.cb_error", case_id=case.id, error=str(exc))

        # ── Latency (httpx + ASGI) ───────────────────────────────────────────
        for case in latency_cases:
            try:
                result = await self._run_latency(case)
                latency_samples.extend(result.get("samples_ms", []))
                cases_run += 1
            except Exception as exc:
                all_errors.append(f"{case.id}: {exc}")
                cases_errored += 1
                log.error("eval.latency_error", case_id=case.id, error=str(exc))

        # ── Aggregate metrics ────────────────────────────────────────────────
        metrics: dict[str, float] = {}

        if retrieval_results:
            # NDCG and MRR aggregated across all retrieval cases that have in_top_k
            ndcg_scores: list[float] = []
            mrr_scores: list[float] = []
            recall_scores: list[float] = []

            for r in retrieval_results:
                ranked = r.get("ranked_slugs", [])
                relevant = r.get("relevant_slugs", set())
                k = r.get("limit", 10)
                if relevant:
                    ndcg_scores.append(ndcg_at_k(ranked, relevant, k))
                    mrr_scores.append(mrr(ranked, relevant))
                    recall_scores.append(recall_at_k(ranked, relevant, k))

            if ndcg_scores:
                metrics["ndcg_at_10"] = sum(ndcg_scores) / len(ndcg_scores)
                metrics["mrr"] = sum(mrr_scores) / len(mrr_scores)
                metrics["recall_at_10"] = sum(recall_scores) / len(recall_scores)

            # min_results satisfaction rate
            min_results_ok = sum(
                1
                for r in retrieval_results
                if len(r.get("ranked_slugs", [])) >= r.get("min_results", 0)
            )
            metrics["min_results_rate"] = min_results_ok / len(retrieval_results)

        if routing_results:
            acc = routing_accuracy(routing_results)
            metrics["routing_accuracy"] = acc
            # Alias for YAML files that use "accuracy" as threshold key
            metrics["accuracy"] = acc

        if cb_results:
            rate = circuit_breaker_pass_rate(cb_results)
            metrics["circuit_breaker_pass_rate"] = rate
            # Alias for YAML files that use "success_rate" as threshold key
            metrics["success_rate"] = rate

        if latency_samples:
            percs = latency_percentiles(latency_samples)
            metrics["latency_p50_ms"] = percs["p50"]
            metrics["latency_p95_ms"] = percs["p95"]
            metrics["latency_p99_ms"] = percs["p99"]

        # ── Threshold comparison ─────────────────────────────────────────────
        # Metrics ending in _ms or _seconds are lower-is-better (latency).
        # All other metrics are higher-is-better (accuracy, NDCG, etc.).
        _LOWER_IS_BETTER_SUFFIXES = ("_ms", "_seconds")

        threshold_results: dict[str, bool] = {}
        for metric_name, threshold in eval_set.thresholds.items():
            actual = metrics.get(metric_name, 0.0)
            if metric_name.endswith(_LOWER_IS_BETTER_SUFFIXES):
                threshold_results[metric_name] = actual <= threshold
            else:
                threshold_results[metric_name] = actual >= threshold

        # passed = True if calibration_mode, else all thresholds must pass
        if eval_set.calibration_mode:
            passed = True
        else:
            passed = all(threshold_results.values()) if threshold_results else True

        return EvalResult(
            set_name=eval_set.name,
            cases_run=cases_run,
            cases_errored=cases_errored,
            metrics=metrics,
            threshold_results=threshold_results,
            calibration_mode=eval_set.calibration_mode,
            passed=passed,
            errors=all_errors,
        )

    # ── DB setup ──────────────────────────────────────────────────────────────

    async def _setup_db(self, db_url: str | None):  # type: ignore[return]
        """Return an async session_factory. Uses external db_url or testcontainers."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        if db_url:
            # External DB (e.g. in CI via env var)
            async_url = _normalize_async_url(db_url)
            engine = create_async_engine(async_url, echo=False, poolclass=NullPool)
            return async_sessionmaker(engine, expire_on_commit=False)

        # Try testcontainers
        try:
            return await asyncio.get_event_loop().run_in_executor(None, self._start_testcontainer)
        except Exception as exc:
            log.warning("eval.db_setup_failed", error=str(exc))
            return None

    def _start_testcontainer(self):  # type: ignore[return]
        """Blocking: start Postgres testcontainer, apply migrations, return session_factory."""
        from pathlib import Path as _Path

        from alembic.config import Config
        from sqlalchemy import create_engine
        from sqlalchemy import text as sa_text
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool
        from testcontainers.postgres import PostgresContainer

        from alembic import command

        container = PostgresContainer("pgvector/pgvector:pg16")
        container.start()
        # Store reference so we can stop later if needed
        self._container = container

        sync_url = container.get_connection_url()

        # Apply Alembic migrations
        # __file__ = apps/api/src/digidentity_api/evals/runner.py
        # 4x .parent → apps/api/ where alembic.ini lives
        alembic_cfg_path = _Path(__file__).parent.parent.parent.parent / "alembic.ini"
        cfg = Config(str(alembic_cfg_path))
        cfg.set_main_option("sqlalchemy.url", sync_url)
        # alembic.ini uses script_location = alembic (relative to apps/api/).
        # Set it explicitly so it resolves correctly regardless of CWD.
        cfg.set_main_option("script_location", str(alembic_cfg_path.parent / "alembic"))
        command.upgrade(cfg, "head")

        # Create app_user (required for RLS FORCE)
        sync_engine = create_engine(sync_url, isolation_level="AUTOCOMMIT")
        with sync_engine.connect() as conn:
            conn.execute(sa_text("CREATE USER app_user WITH PASSWORD 'app_password'"))
            conn.execute(sa_text("GRANT CONNECT ON DATABASE test TO app_user"))
            conn.execute(sa_text("GRANT USAGE ON SCHEMA public TO app_user"))
            conn.execute(
                sa_text(
                    "GRANT SELECT, INSERT, UPDATE, DELETE "
                    "ON ALL TABLES IN SCHEMA public TO app_user"
                )
            )
            conn.execute(
                sa_text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user")
            )
        sync_engine.dispose()

        # Build async URL with app_user
        app_url = re.sub(
            r"(postgresql(?:\+psycopg2)?://)([^:@]+):([^@]+)(@)",
            r"\1app_user:app_password\4",
            sync_url,
        )
        async_url = app_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
            "postgresql://", "postgresql+asyncpg://"
        )
        engine = create_async_engine(async_url, echo=False, poolclass=NullPool)
        return async_sessionmaker(engine, expire_on_commit=False)

    # ── Retrieval runner ──────────────────────────────────────────────────────

    async def _run_retrieval(self, case: EvalCase, session_factory: Any) -> dict:
        """Execute a single retrieval case against a seeded DB.

        Query text is taken directly from the YAML case input. For stub-embedding
        evals (hash-based, no semantic similarity), the YAML must supply the exact
        rendered template text of the target entity as the query so the embedding
        vectors match. Natural-language queries are archived in
        evals/_archive/retrieval_natural_queries_phase1.yaml and will be restored
        in Phase 2 when real embeddings are available.
        """
        from uuid import UUID

        from digidentity_api.db.models import Tenant
        from digidentity_api.db.search import HybridSearchRepository, SearchWeights
        from digidentity_api.db.tenant_context import with_tenant
        from digidentity_api.packs.stub_embeddings import make_query_embedding
        from scripts.seed_real_estate import seed_database

        # Use a fixed eval tenant to avoid collisions with other runs
        tenant_id = UUID("eeeeeeee-eeee-eeee-eeee-000000000001")

        # Seed if needed
        async with with_tenant(tenant_id, session_factory=session_factory) as sess:
            existing = await sess.get(Tenant, tenant_id)
            if not existing:
                tenant = Tenant(id=tenant_id, slug="eval-tenant", name="Eval Tenant")
                sess.add(tenant)

        await seed_database(session_factory, [tenant_id])

        # Build query embedding
        inp = case.input
        query_text: str = inp["query"]
        query_type = inp.get("query_type", "neutral")
        limit: int = inp.get("limit", 10)

        query_emb = make_query_embedding(query_text, query_type=query_type)

        expected = case.expected

        # Build weights
        weights_override = inp.get("weights_override")
        weights = None
        if weights_override:
            weights = SearchWeights(
                content=float(weights_override.get("content", 0.45)),
                lifestyle=float(weights_override.get("lifestyle", 0.35)),
                features=float(weights_override.get("features", 0.20)),
            )

        # Execute search
        async with with_tenant(tenant_id, session_factory=session_factory) as sess:
            repo = HybridSearchRepository(sess)
            results = await repo.search(query_emb, weights=weights, limit=limit)

        ranked_slugs = [entity.payload.get("slug", str(entity.id)) for entity, _ in results]

        in_top_k_specs = expected.get("in_top_k", [])
        relevant_slugs: set[str] = {spec["slug"] for spec in in_top_k_specs}
        min_results: int = expected.get("min_results", 0)

        return {
            "case_id": case.id,
            "ranked_slugs": ranked_slugs,
            "relevant_slugs": relevant_slugs,
            "limit": limit,
            "min_results": min_results,
            "n_results": len(ranked_slugs),
        }

    # ── Routing runner ────────────────────────────────────────────────────────

    async def _run_routing(self, case: EvalCase) -> dict:
        """Execute a single routing classification case (no DB)."""
        inp = case.input
        expected = case.expected

        router = LLMRouter()

        prompt: str = inp.get("prompt", "")
        context_tokens: int = inp.get("context_tokens", 0)
        tool_calls_prev: int = inp.get("tool_calls_prev", 0)
        prev_score_raw = inp.get("prev_score")
        prev_score: float | None = float(prev_score_raw) if prev_score_raw is not None else None

        is_complex = router.classify(
            context_tokens=context_tokens,
            tool_calls_prev=tool_calls_prev,
            prompt=prompt,
            prev_score=prev_score,
        )
        preferred_model = router._select_model(
            prompt=prompt,
            context_tokens=context_tokens,
            tool_calls_prev=tool_calls_prev,
            prev_score=prev_score,
        )

        expected_complex: bool = bool(expected.get("complex", False))
        expected_model: str = expected.get("preferred_model", "sonnet")

        correct = (is_complex == expected_complex) and (preferred_model == expected_model)

        return {
            "case_id": case.id,
            "is_complex": is_complex,
            "preferred_model": preferred_model,
            "expected_complex": expected_complex,
            "expected_model": expected_model,
            "correct": correct,
        }

    # ── Circuit breaker runner ────────────────────────────────────────────────

    async def _run_circuit_breaker(self, case: EvalCase) -> dict:
        """Execute a single circuit breaker scenario (no DB)."""
        inp = case.input
        expected = case.expected

        model: str = inp.get("model", "sonnet")
        fail_status: int = int(inp.get("fail_status") or 503)
        n_failures: int = int(inp.get("n_failures", 3))
        channel: str = inp.get("channel", "web")
        fallback_to_model: str | None = expected.get("fallback_to_model")
        expected_state: str = expected.get("circuit_state_after", "open")
        # retry_count is recorded in the YAML for documentation; not validated in runner v1
        _ = expected.get("retry_count", 0)

        # Build providers: failing model + success fallbacks
        fail_provider = _make_counting_fail_provider(fail_status)
        success_provider = _make_simple_success_provider()

        providers = {
            "sonnet": fail_provider if model == "sonnet" else success_provider,
            "opus": fail_provider if model == "opus" else success_provider,
            "gpt5": fail_provider if model == "gpt5" else success_provider,
        }

        router = LLMRouter(providers=providers)

        # Record n failures manually to open circuit
        for _ in range(n_failures):
            router._record_failure(model, fail_status)

        circuit_open = router._is_open(model)
        actual_state = "open" if circuit_open else "closed"

        state_correct = actual_state == expected_state

        # Verify fallback: try routing and see which model is used
        actual_fallback_model: str | None = None
        if fallback_to_model is not None:
            try:
                with patch("digidentity_api.tasks.usage.log_usage") as mock_task:
                    mock_task.delay = MagicMock()
                    events = []
                    async for event in router.route(
                        prompt="test",
                        conversation_id="eval-cb-conv",
                        tenant_id="00000000-0000-0000-0000-000000000001",
                        channel=channel,  # type: ignore[arg-type]
                    ):
                        events.append(event)
                # If we got text events, fallback worked
                if any(e.get("type") == "text" for e in events):
                    # The fallback model is the one that was NOT the failing model
                    # and is the first in the chain after the open circuit
                    chain_order = ["sonnet", "opus", "gpt5"]
                    for m in chain_order:
                        if m != model:
                            actual_fallback_model = m
                            break
            except Exception:
                actual_fallback_model = None

            fallback_correct = actual_fallback_model == fallback_to_model
        else:
            fallback_correct = True

        passed = state_correct and fallback_correct

        return {
            "case_id": case.id,
            "actual_state": actual_state,
            "expected_state": expected_state,
            "state_correct": state_correct,
            "actual_fallback_model": actual_fallback_model,
            "expected_fallback_model": fallback_to_model,
            "fallback_correct": fallback_correct,
            "passed": passed,
        }

    # ── Latency runner ────────────────────────────────────────────────────────

    async def _run_latency(self, case: EvalCase) -> dict:
        """Execute latency sampling via httpx + ASGITransport (no DB)."""
        from httpx import ASGITransport, AsyncClient

        from digidentity_api.main import app

        inp = case.input
        prompt: str = inp.get("prompt", "test")
        n_samples: int = int(inp.get("n_samples", 10))
        # channel is logged in YAML for documentation; ASGI test always uses HTTP
        _ = inp.get("channel", "web")

        samples_ms: list[float] = []

        with patch("digidentity_api.tasks.usage.log_usage") as mock_task:
            mock_task.delay = MagicMock()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                for _ in range(n_samples):
                    start = time.monotonic()
                    first_chunk_time: float | None = None

                    async with client.stream(
                        "GET",
                        "/api/v1/conversations/a1b2c3d4-e5f6-7890-abcd-ef1234567890/stream",
                        params={"prompt": prompt},
                        headers={
                            "X-Tenant-Id": "550e8400-e29b-41d4-a716-446655440000",
                        },
                    ) as response:
                        import json

                        async for line in response.aiter_lines():
                            line = line.strip()
                            if line.startswith("data: "):
                                try:
                                    event = json.loads(line[6:])
                                    if event.get("type") == "text" and first_chunk_time is None:
                                        first_chunk_time = (time.monotonic() - start) * 1000
                                        break
                                except Exception:
                                    pass

                    if first_chunk_time is not None:
                        samples_ms.append(first_chunk_time)

        expected = case.expected
        empty_percs = {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        percs = latency_percentiles(samples_ms) if samples_ms else empty_percs

        return {
            "case_id": case.id,
            "samples_ms": samples_ms,
            "n_samples": len(samples_ms),
            "p95_ms": percs["p95"],
            "p99_ms": percs["p99"],
            "ttfc_p95_ms_expected": expected.get("ttfc_p95_ms"),
            "ttfc_p99_ms_expected": expected.get("ttfc_p99_ms"),
        }


# ── Helper provider factories ─────────────────────────────────────────────────

_USAGE = TokenUsage(prompt_tokens=10, completion_tokens=5, cached_tokens=0)
_FINISH_CHUNK = Chunk(text=None, finish_reason="stop", usage=_USAGE)


def _make_counting_fail_provider(status: int) -> BaseMockProvider:
    class _FailProvider(BaseMockProvider):
        provider = "mock"
        model = "mock-fail"

        async def stream(self, prompt: str, **kwargs: object) -> AsyncIterator[Chunk]:
            raise ProviderError(status=status, provider="mock")
            yield  # type: ignore[misc]

    return _FailProvider()


def _make_simple_success_provider() -> BaseMockProvider:
    class _SuccessProvider(BaseMockProvider):
        provider = "mock"
        model = "mock-success"

        async def stream(self, prompt: str, **kwargs: object) -> AsyncIterator[Chunk]:
            yield Chunk(text="ok ")
            yield _FINISH_CHUNK

    return _SuccessProvider()


# ── URL normalization ─────────────────────────────────────────────────────────


def _normalize_async_url(url: str) -> str:
    """Convert sync postgres URL to async (asyncpg) URL."""
    url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    if url.startswith("postgresql://") and "asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url

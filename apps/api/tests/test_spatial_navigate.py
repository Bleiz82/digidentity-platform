"""Tests for spatial_navigate tool — BIBLE §6.6 Spatial Experience.

Covers: registry dispatch, directive shape, schema validation,
        tool list membership, async execute dispatch.
"""

from __future__ import annotations

import pytest

from digidentity_api.engines.agent.tools.registry import ToolRegistry
from digidentity_api.engines.agent.tools.schemas import ALL_TOOLS, SPATIAL_NAVIGATE
from digidentity_api.schemas.rendering import RenderingDirective


TENANT = "00000000-0000-0000-0000-000000000001"


# ── 1. Schema ─────────────────────────────────────────────────────────────────


def test_spatial_navigate_schema_registered():
    """SPATIAL_NAVIGATE schema is included in ALL_TOOLS."""
    names = [t["name"] for t in ALL_TOOLS]
    assert "spatial_navigate" in names


def test_spatial_navigate_schema_has_enum():
    """Schema restricts scene_id to three valid scene identifiers."""
    props = SPATIAL_NAVIGATE["input_schema"]["properties"]
    enum = props["scene_id"]["enum"]
    assert set(enum) == {"villa-entrance", "master-suite", "infinity-pool"}


def test_spatial_navigate_schema_required_fields():
    """scene_id and reason are both required inputs."""
    required = set(SPATIAL_NAVIGATE["input_schema"]["required"])
    assert required == {"scene_id", "reason"}


# ── 2. Registry — direct method ───────────────────────────────────────────────


def test_spatial_navigate_returns_directive():
    """spatial_navigate() returns an emitted=True dict with the directive."""
    registry = ToolRegistry(tenant_id=TENANT)
    result = registry.spatial_navigate(
        scene_id="infinity-pool",
        reason="visitor asked about pool",
    )
    assert result["emitted"] is True
    assert result["scene_id"] == "infinity-pool"
    directive = result["directive"]
    assert directive["type"] == "spatial_navigate"
    assert directive["target"] == "infinity-pool"
    assert directive["params"]["target_scene_id"] == "infinity-pool"
    assert directive["params"]["transition"] == "fade"


def test_spatial_navigate_directive_priority_200():
    """Spatial navigate directives have priority 200 (above render_highlight)."""
    registry = ToolRegistry(tenant_id=TENANT)
    result = registry.spatial_navigate(scene_id="master-suite", reason="r")
    assert result["directive"]["priority"] == 200


def test_spatial_navigate_directive_is_valid_rendering_directive():
    """Directive shape passes Pydantic RenderingDirective validation."""
    registry = ToolRegistry(tenant_id=TENANT)
    result = registry.spatial_navigate(scene_id="villa-entrance", reason="test")
    directive = RenderingDirective.model_validate(result["directive"])
    assert directive.type == "spatial_navigate"
    assert directive.target == "villa-entrance"


# ── 3. Registry — dispatch via execute() ─────────────────────────────────────


@pytest.mark.asyncio
async def test_spatial_navigate_execute_dispatch():
    """execute() routes 'spatial_navigate' to the correct method."""
    registry = ToolRegistry(tenant_id=TENANT)
    result = await registry.execute(
        "spatial_navigate",
        {"scene_id": "master-suite", "reason": "bedroom query"},
    )
    assert result["scene_id"] == "master-suite"
    assert result["directive"]["type"] == "spatial_navigate"


@pytest.mark.asyncio
async def test_spatial_navigate_execute_unknown_tool_raises():
    """execute() raises ValueError for unrecognised tool names."""
    registry = ToolRegistry(tenant_id=TENANT)
    with pytest.raises(ValueError, match="Unknown tool"):
        await registry.execute("fly_to_moon", {})

"""RenderingDirective — BIBLE-v3 §7.2."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DirectiveType = Literal[
    "morph_section",
    "highlight",
    "inject",
    "set_persona",
    "show",
    "hide",
    "reorder",
    "rewrite_copy",
    "spatial_navigate",
]


class RenderingDirective(BaseModel):
    """Istruzione emessa dall'agente e applicata dall'Adaptive Renderer — BIBLE §7.2.

    target: selettore CSS o entity_id.
    reason: obbligatorio per tracciabilità audit (BIBLE §6.2 Decision Engine).
    """

    type: DirectiveType
    target: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=100, ge=0, le=1000)
    reason: str = Field(..., min_length=1, max_length=500)

    model_config = ConfigDict(frozen=False)

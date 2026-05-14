from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, Undefined


class _SilentUndefined(Undefined):
    """Undefined silenzioso: variabili mancanti diventano stringa vuota."""

    def __str__(self) -> str:
        return ""

    def __iter__(self):  # type: ignore[override]
        return iter([])

    def __bool__(self) -> bool:
        return False


def render_template(
    template_path: Path,
    context: dict[str, Any],
) -> str:
    """Renderizza un template Jinja2 con il contesto dato."""
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        undefined=StrictUndefined,
        autoescape=False,
    )
    template = env.get_template(template_path.name)
    return template.render(**context).strip()


def render_pack_templates(
    pack_root: Path,
    entity_payload: dict[str, Any],
) -> dict[str, str]:
    """
    Renderizza i 3 template del Pack (content, lifestyle, features).
    Restituisce un dict con le 3 stringhe pronte per l'embedding.
    """
    results: dict[str, str] = {}
    for tmpl_name in ["content_template", "lifestyle_template", "features_template"]:
        tmpl_path = pack_root / "templates" / f"{tmpl_name}.j2"
        if tmpl_path.exists():
            try:
                results[tmpl_name] = render_template(tmpl_path, entity_payload)
            except Exception:
                # Fallback su variabili assenti: usa SilentUndefined
                env = Environment(
                    loader=FileSystemLoader(str(tmpl_path.parent)),
                    undefined=_SilentUndefined,
                    autoescape=False,
                )
                template = env.get_template(tmpl_path.name)
                results[tmpl_name] = template.render(**entity_payload).strip()
        else:
            results[tmpl_name] = ""
    return results

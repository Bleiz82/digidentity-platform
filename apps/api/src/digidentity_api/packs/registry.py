from pathlib import Path
from typing import Any

import yaml


class PackRegistry:
    def __init__(self) -> None:
        self._packs: dict[str, dict[str, Any]] = {}

    def load_from_disk(self, packs_root: Path) -> None:
        for pack_yaml in packs_root.glob("*/pack.yaml"):
            with pack_yaml.open() as f:
                data = yaml.safe_load(f)
            pack_id = data.get("id") or pack_yaml.parent.name
            self._packs[pack_id] = data

    def get(self, pack_id: str) -> dict[str, Any] | None:
        return self._packs.get(pack_id)

    def get_search_weights(self, pack_id: str, query_type: str = "mixed") -> dict[str, float]:
        pack = self._packs.get(pack_id)
        if not pack:
            return {"content": 0.45, "lifestyle": 0.35, "features": 0.20}
        weights = pack.get("search", {}).get("weights", {})
        return weights.get(query_type) or weights.get("default") or {
            "content": 0.45,
            "lifestyle": 0.35,
            "features": 0.20,
        }

    @property
    def pack_ids(self) -> list[str]:
        return list(self._packs.keys())


# Singleton globale — inizializzato al boot app
_registry: PackRegistry | None = None


def get_registry() -> PackRegistry:
    global _registry
    if _registry is None:
        _registry = PackRegistry()
    return _registry


def init_registry(packs_root: Path) -> PackRegistry:
    global _registry
    _registry = PackRegistry()
    _registry.load_from_disk(packs_root)
    return _registry

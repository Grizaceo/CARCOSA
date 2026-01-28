from __future__ import annotations


def normalize_monster_id(monster_id: str) -> str:
    """Normaliza IDs de monstruos removiendo el prefijo MONSTER: si existe."""
    if monster_id.startswith("MONSTER:"):
        return monster_id.split(":", 1)[1]
    return monster_id


__all__ = ["normalize_monster_id"]

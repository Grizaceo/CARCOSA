from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

@dataclass
class RoleDefinition:
    """Definición de un rol de personaje."""
    role_id: str
    name: str
    sanity_max: int
    sanity_min: int = -5
    key_slots: int = 1
    object_slots: int = 2
    starting_items: List[str] = field(default_factory=list)
    ability_id: str = ""  # ID de la habilidad especial
    ability_description: str = ""


# ==============================================================================
# CATÁLOGO DE ROLES CANÓNICOS
# ==============================================================================

ROLE_CATALOG = {
    "HEALER": RoleDefinition(
        role_id="HEALER",
        name="Sanador",
        sanity_max=4,
        key_slots=1,
        object_slots=2,
        ability_id="HEAL_OTHERS",
        ability_description="Sacrificar 1 cordura → +2 cordura a OTROS + ILUMINADO o SANIDAD (1 acción)"
    ),
    
    "TANK": RoleDefinition(
        role_id="TANK",
        name="Tanque",
        sanity_max=7,
        key_slots=1,
        object_slots=3,
        ability_id="PROTECT_ALLY",
        ability_description="Puede recibir daño en lugar de aliados en mismo nodo. +1 escudo al inicio de ronda."
    ),
    
    "HIGH_ROLLER": RoleDefinition(
        role_id="HIGH_ROLLER",
        name="Apostador",
        sanity_max=5,
        key_slots=2,
        object_slots=2,
        ability_id="DOUBLE_ROLL",
        ability_description="Puede lanzar doble d6 y sumar (1x turno, gratis, post-primer d6)"
    ),
    
    "SCOUT": RoleDefinition(
        role_id="SCOUT",
        name="Explorador",
        sanity_max=3,
        key_slots=1,
        object_slots=1,
        ability_id="FREE_MOVE",
        ability_description="+1 movimiento adicional gratis. Escalera: si d6+cordura < 3 → STUN"
    ),
    
    "BRAWLER": RoleDefinition(
        role_id="BRAWLER",
        name="Luchador",
        sanity_max=3,
        key_slots=1,
        object_slots=2,
        starting_items=["BLUNT"],
        ability_id="BLUNT_REACTION",
        ability_description="Contundente sin acción. Puede reaccionar contra monstruos que lo atacan"
    ),
    
    "PSYCHIC": RoleDefinition(
        role_id="PSYCHIC",
        name="Psíquico",
        sanity_max=4,
        key_slots=1,
        object_slots=2,
        ability_id="PEEK_REORDER",
        ability_description="Al entrar a habitación: ver 2 cartas top, reordenar. Fondo: monstruo=-2, otro=-1"
    ),
}

ROLE_INVENTORY_LIMITS = {
    role_id: (role.key_slots, role.object_slots)
    for role_id, role in ROLE_CATALOG.items()
}
ROLE_INVENTORY_LIMITS["DEFAULT"] = (1, 2)

__all__ = [
    "RoleDefinition",
    "ROLE_CATALOG",
    "ROLE_INVENTORY_LIMITS",
]

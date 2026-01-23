"""
Sistema de Roles - CARCOSA

Define los 6 roles de personaje con sus stats y habilidades únicas.

ROLES CANÓNICOS (2026-01-22):
=============================
| Rol         | Cord.Max | Llaves | Objetos | Habilidad                           |
|-------------|:--------:|:------:|:-------:|-------------------------------------|
| HEALER      |    4     |   1    |    2    | Cura otros +2, elige estado        |
| TANK        |    7     |   1    |    3    | Bloquea meditación de otros         |
| HIGH_ROLLER |    5     |   2    |    2    | Doble d6 sumado                     |
| SCOUT       |    3     |   1    |    1    | +1 mov gratis, penalidad escaleras |
| BRAWLER     |    3     |   1    |    2    | Contundente gratis + reacción      |
| PSYCHIC     |    4     |   1    |    2    | Ver/reordenar 2 cartas al entrar   |

Todos los roles tienen cordura mínima = -5
"""
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from engine.types import PlayerId


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
        ability_id="BLOCK_MEDITATION",
        ability_description="OTROS no pueden meditar en su habitación"
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


def get_role(role_id: str) -> Optional[RoleDefinition]:
    """Obtiene la definición de un rol."""
    return ROLE_CATALOG.get(role_id)


def get_sanity_max(role_id: str) -> int:
    """Obtiene la cordura máxima de un rol."""
    role = get_role(role_id)
    return role.sanity_max if role else 5  # Default: 5


def get_key_slots(role_id: str) -> int:
    """Obtiene los slots de llaves de un rol."""
    role = get_role(role_id)
    return role.key_slots if role else 1


def get_object_slots(role_id: str) -> int:
    """Obtiene los slots de objetos de un rol."""
    role = get_role(role_id)
    return role.object_slots if role else 2


def get_starting_items(role_id: str) -> List[str]:
    """Obtiene los objetos iniciales de un rol."""
    role = get_role(role_id)
    return role.starting_items.copy() if role else []


def has_ability(role_id: str, ability_id: str) -> bool:
    """Verifica si un rol tiene una habilidad específica."""
    role = get_role(role_id)
    return role.ability_id == ability_id if role else False


# ==============================================================================
# FUNCIONES DE HABILIDAD DE ROL
# ==============================================================================

def can_use_healer_ability(player, target_players: list) -> bool:
    """
    Verifica si el Healer puede usar su habilidad.
    Requiere: cordura >= 1, al menos 1 otro jugador.
    """
    if not has_ability(getattr(player, "role_id", ""), "HEAL_OTHERS"):
        return False
    return player.sanity >= 1 and len(target_players) > 0


def can_use_double_roll(player, used_this_turn: bool) -> bool:
    """
    Verifica si el High Roller puede usar doble d6.
    Solo 1 vez por turno.
    """
    if not has_ability(getattr(player, "role_id", ""), "DOUBLE_ROLL"):
        return False
    return not used_this_turn


def blocks_meditation(blocker_player, meditator_player) -> bool:
    """
    Verifica si el Tank bloquea la meditación de otro jugador.
    Tank bloquea si está en la misma habitación.
    """
    if not has_ability(getattr(blocker_player, "role_id", ""), "BLOCK_MEDITATION"):
        return False
    if blocker_player.player_id == meditator_player.player_id:
        return False  # Tank puede meditar donde quiera
    return blocker_player.room == meditator_player.room


def get_scout_actions(player, base_actions: int) -> int:
    """
    Obtiene las acciones del Scout (base + 1 movimiento gratis).
    El movimiento gratis es ADICIONAL.
    """
    if has_ability(getattr(player, "role_id", ""), "FREE_MOVE"):
        return base_actions + 1
    return base_actions


def should_stun_scout_on_stairs(player, roll: int) -> bool:
    """
    Verifica si el Scout queda stuneado por usar escaleras.
    STUN si d6 + cordura < 3.
    """
    if not has_ability(getattr(player, "role_id", ""), "FREE_MOVE"):
        return False
    total = roll + player.sanity
    return total < 3


def can_brawler_react(player, has_blunt: bool) -> bool:
    """
    Verifica si el Brawler puede reaccionar.
    Requiere tener contundente.
    """
    if not has_ability(getattr(player, "role_id", ""), "BLUNT_REACTION"):
        return False
    return has_blunt


def brawler_blunt_free(player) -> bool:
    """
    Verifica si el jugador puede usar contundente sin coste de acción.
    """
    return has_ability(getattr(player, "role_id", ""), "BLUNT_REACTION")

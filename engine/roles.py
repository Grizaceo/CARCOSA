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
from typing import List, Optional
from engine.catalogs.roles import ROLE_CATALOG, RoleDefinition

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

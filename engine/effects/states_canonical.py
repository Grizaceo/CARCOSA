"""
ESTADOS CANÓNICOS - CARCOSA

Documentación centralizada de los 10 estados canónicos del juego.
Actualizado: 2026-01-21 conforme a aclaraciones canónicas del usuario.

CATEGORÍAS DE ESTADOS:
======================

1. ESTADOS CON CARTA PROPIA (en mazo de eventos):
   - Estas cartas se roban del mazo y aplican directamente el estado
   - Duración: 2 rondas, carta descartada al expirar
   - MALDITO, SANIDAD, ENVENENADO, PARANOIA

2. ESTADOS POR EFECTOS (no tienen carta propia):
   - Se aplican como resultado de otras mecánicas
   - VANIDAD, ILUMINADO, STUN, TRAPPED, MOVIMIENTO_BLOQUEADO, ACCION_REDUCIDA
"""

from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class CanonicalStateType(Enum):
    """Tipo de origen del estado."""
    CARD = "CARD"      # Tiene carta propia en mazo de eventos
    EFFECT = "EFFECT"  # Aplicado por efecto de otra mecánica


@dataclass
class CanonicalStateDefinition:
    """Definición canónica de un estado."""
    state_id: str
    name: str
    origin_type: CanonicalStateType
    origin_description: str
    default_duration: Optional[int]  # None = permanente hasta remoción, -1 = contextual
    effect_description: str
    permanent_effect: bool = False   # True si el efecto persiste tras expirar


# ==============================================================================
# CATÁLOGO DE ESTADOS CANÓNICOS
# ==============================================================================

CANONICAL_STATES = {
    # =========================================================================
    # ESTADOS CON CARTA PROPIA (en mazo de eventos) - Duración: 2 rondas
    # =========================================================================
    
    "MALDITO": CanonicalStateDefinition(
        state_id="MALDITO",
        name="Maldito",
        origin_type=CanonicalStateType.CARD,
        origin_description="Carta de evento en mazo",
        default_duration=2,  # 2 rondas
        effect_description=(
            "Otros jugadores en el mismo piso pierden 1 de cordura al final de ronda."
        )
    ),
    
    "SANIDAD": CanonicalStateDefinition(
        state_id="SANIDAD",
        name="Sanidad",
        origin_type=CanonicalStateType.CARD,
        origin_description="Carta de evento en mazo",
        default_duration=2,  # 2 rondas
        effect_description=(
            "Recupera 1 de cordura al final de CADA turno (propio y ajenos). "
            "Puede descartarse GRATIS para eliminar TODOS los estados (positivos y negativos)."
        )
    ),
    
    "ENVENENADO": CanonicalStateDefinition(
        state_id="ENVENENADO",
        name="Envenenado",
        origin_type=CanonicalStateType.CARD,
        origin_description="Carta de evento en mazo",
        default_duration=2,  # 2 turnos
        effect_description=(
            "Pierde 1 de cordura MÁXIMA al final de cada ronda mientras esté activo. "
            "⚠️ La reducción de máximo es PERMANENTE incluso tras expirar el estado."
        ),
        permanent_effect=True  # Marca que el efecto es permanente
    ),
    
    "PARANOIA": CanonicalStateDefinition(
        state_id="PARANOIA",
        name="Paranoia",
        origin_type=CanonicalStateType.CARD,
        origin_description="Carta de evento en mazo",
        default_duration=2,  # 2 rondas
        effect_description=(
            "No puede estar en misma habitación que otra Pobre Alma. "
            "Bloquea movimiento hacia habitaciones Y PASILLO ocupados por otros jugadores."
        )
    ),
    
    # =========================================================================
    # ESTADOS POR EFECTOS (no tienen carta propia)
    # =========================================================================
    
    "VANIDAD": CanonicalStateDefinition(
        state_id="VANIDAD",
        name="Vanidad",
        origin_type=CanonicalStateType.EFFECT,
        origin_description="Salón de Belleza (cada segunda activación)",
        default_duration=2,  # 2 turnos
        effect_description=(
            "Pierde 1 de cordura adicional por CADA instancia de pérdida de cordura. "
            "No puede activar el Salón de Belleza mientras tenga este estado."
        )
    ),
    
    "ILUMINADO": CanonicalStateDefinition(
        state_id="ILUMINADO",
        name="Iluminado",
        origin_type=CanonicalStateType.EFFECT,
        origin_description="Capilla u otro efecto",
        default_duration=2,  # 2 turnos desde activación
        effect_description="Puede tomar 1 acción adicional (3 total en lugar de 2)."
    ),
    
    "STUN": CanonicalStateDefinition(
        state_id="STUN",
        name="Aturdido",
        origin_type=CanonicalStateType.EFFECT,
        origin_description="Contundente, liberación de trap",
        default_duration=2,  # Contundente = 2 turnos, liberación = 1 turno
        effect_description=(
            "Monstruo no puede actuar. "
            "Rey de Amarillo es INMUNE. Reina Helada PUEDE ser stuneada."
        )
    ),
    
    "TRAPPED": CanonicalStateDefinition(
        state_id="TRAPPED",
        name="Atrapado",
        origin_type=CanonicalStateType.EFFECT,
        origin_description="Araña, Viejo del Saco",
        default_duration=3,  # 3 turnos
        effect_description=(
            "Jugador atrapado, no puede actuar. Cada turno intenta escape: d6+cordura >= 3. "
            "Si FALLA, NO puede actuar ese turno. Al liberarse, monstruo fuente queda STUN 1 turno. "
            "Activa mecánica de contoneo."
        )
    ),
    
    "MOVIMIENTO_BLOQUEADO": CanonicalStateDefinition(
        state_id="MOVIMIENTO_BLOQUEADO",
        name="Movimiento Bloqueado",
        origin_type=CanonicalStateType.EFFECT,
        origin_description="Reina Helada (turno de entrada)",
        default_duration=1,  # Solo 1 turno
        effect_description=(
            "No puede usar acciones de movimiento. "
            "Puede usar 2 acciones de otro tipo (buscar, meditar, activar habitación, etc.). "
            "Solo afecta a jugadores presentes cuando la Reina entra en juego."
        )
    ),
    
    "ACCION_REDUCIDA": CanonicalStateDefinition(
        state_id="ACCION_REDUCIDA",
        name="Acción Reducida",
        origin_type=CanonicalStateType.EFFECT,
        origin_description="Reina Helada (turnos posteriores)",
        default_duration=-1,  # Contextual: mientras Reina esté en el piso
        effect_description="Jugadores en piso de Reina Helada solo tienen 1 acción disponible."
    ),
}


# ==============================================================================
# FUNCIONES HELPER
# ==============================================================================

def get_state_definition(state_id: str) -> Optional[CanonicalStateDefinition]:
    """Obtiene la definición canónica de un estado."""
    normalized = normalize_state_id(state_id)
    return CANONICAL_STATES.get(normalized)


def is_card_state(state_id: str) -> bool:
    """Retorna True si el estado tiene carta propia en el mazo."""
    state_def = get_state_definition(state_id)
    return state_def.origin_type == CanonicalStateType.CARD if state_def else False


def is_effect_state(state_id: str) -> bool:
    """Retorna True si el estado se aplica por efecto de otra mecánica."""
    state_def = get_state_definition(state_id)
    return state_def.origin_type == CanonicalStateType.EFFECT if state_def else False


def get_default_duration(state_id: str) -> Optional[int]:
    """Obtiene la duración por defecto del estado (None = permanente)."""
    state_def = get_state_definition(state_id)
    return state_def.default_duration if state_def else None


def has_permanent_effect(state_id: str) -> bool:
    """Retorna True si el estado tiene efectos permanentes tras expirar (ej: ENVENENADO)."""
    state_def = get_state_definition(state_id)
    return state_def.permanent_effect if state_def else False


# IDs de estados para uso rápido
CARD_STATES = {"MALDITO", "SANIDAD", "ENVENENADO", "PARANOIA"}
EFFECT_STATES = {"VANIDAD", "ILUMINADO", "STUN", "TRAPPED", "MOVIMIENTO_BLOQUEADO", "ACCION_REDUCIDA"}
ALL_STATES = CARD_STATES | EFFECT_STATES

# Aliases para compatibilidad con código existente
STATE_ALIASES = {
    "ILLUMINATED": "ILUMINADO",
    "TRAPPED_SPIDER": "TRAPPED",
    "TRAPPED_SACK": "TRAPPED",
    "SANGRADO": "ENVENENADO",
    "POISONED": "ENVENENADO",
    "CURSED": "MALDITO",
    "SANITY": "SANIDAD",
    "PARANOID": "PARANOIA",
    "VANITY": "VANIDAD",
    "MOVEMENT_BLOCKED": "MOVIMIENTO_BLOQUEADO",
    "REDUCED_ACTION": "ACCION_REDUCIDA",
}

# Mapa inverso: dado un ID canónico, lista todos los aliases que apuntan a él
REVERSE_ALIASES = {}
for alias, canonical in STATE_ALIASES.items():
    if canonical not in REVERSE_ALIASES:
        REVERSE_ALIASES[canonical] = set()
    REVERSE_ALIASES[canonical].add(alias)


def normalize_state_id(state_id: str) -> str:
    """Normaliza un ID de estado a su forma canónica."""
    return STATE_ALIASES.get(state_id, state_id)


def get_all_ids_for_state(state_id: str) -> set:
    """
    Obtiene todos los IDs posibles para un estado (canónico + aliases).
    Útil para buscar un estado independiente de cómo fue almacenado.
    """
    normalized = normalize_state_id(state_id)
    ids = {normalized, state_id}
    # Agregar todos los aliases que apuntan a este ID canónico
    if normalized in REVERSE_ALIASES:
        ids.update(REVERSE_ALIASES[normalized])
    return ids


# ==============================================================================
# FUNCIONES DE APLICACIÓN DE ESTADOS
# ==============================================================================

def has_status(player, state_id: str) -> bool:
    """
    Verifica si un jugador tiene un estado específico.
    Acepta IDs canónicos o aliases. Busca por todas las formas posibles.
    """
    valid_ids = get_all_ids_for_state(state_id)
    return any(st.status_id in valid_ids for st in player.statuses)


def get_status(player, state_id: str):
    """
    Obtiene la instancia de estado de un jugador.
    Retorna None si no tiene el estado.
    """
    valid_ids = get_all_ids_for_state(state_id)
    for st in player.statuses:
        if st.status_id in valid_ids:
            return st
    return None


def apply_status(player, state_id: str, duration: Optional[int] = None, metadata: dict = None):
    """
    Aplica un estado a un jugador.
    
    Args:
        player: PlayerState
        state_id: ID del estado (canónico o alias)
        duration: Duración en rondas (None = usar default del catálogo)
        metadata: Datos adicionales (ej. monster_id para TRAPPED)
    """
    from engine.state import StatusInstance
    
    normalized = normalize_state_id(state_id)
    
    # Obtener duración por defecto si no se especifica
    if duration is None:
        duration = get_default_duration(normalized)
        if duration is None:
            duration = -1  # Permanente
    
    # Crear instancia con metadata si se proporciona
    status_instance = StatusInstance(
        status_id=normalized,
        remaining_rounds=duration,
        metadata=metadata or {}
    )
    
    player.statuses.append(status_instance)


def remove_status(player, state_id: str) -> bool:
    """
    Remueve un estado de un jugador.
    Acepta IDs canónicos o aliases.
    Retorna True si el estado existía.
    """
    normalized = normalize_state_id(state_id)
    original_len = len(player.statuses)
    player.statuses = [
        st for st in player.statuses 
        if st.status_id != normalized and st.status_id != state_id
    ]
    return len(player.statuses) < original_len


def remove_all_statuses(player) -> List[str]:
    """
    Remueve TODOS los estados de un jugador.
    Retorna lista de IDs de estados removidos.
    Usado por SANIDAD al descartarse.
    """
    removed = [st.status_id for st in player.statuses]
    player.statuses = []
    return removed


def get_status_remaining(player, state_id: str) -> Optional[int]:
    """
    Obtiene las rondas restantes de un estado.
    Retorna None si no tiene el estado.
    """
    status = get_status(player, state_id)
    return status.remaining_rounds if status else None


def decrement_status_durations(player) -> List[str]:
    """
    Decrementa la duración de todos los estados del jugador.
    Remueve estados que llegan a 0.
    Retorna lista de estados removidos.
    
    Nota: Estados con remaining_rounds <= 0 son permanentes y no se decrementan.
    """
    removed = []
    remaining = []
    
    for st in player.statuses:
        if st.remaining_rounds > 0:
            st.remaining_rounds -= 1
            if st.remaining_rounds <= 0:
                removed.append(st.status_id)
            else:
                remaining.append(st)
        else:
            # Estados permanentes (remaining_rounds <= 0) no se decrementan
            remaining.append(st)
    
    player.statuses = remaining
    return removed


# ==============================================================================
# FUNCIONES DE RESTRICCIÓN DE ACCIONES
# ==============================================================================

def blocks_movement(player) -> bool:
    """Retorna True si el jugador tiene un estado que bloquea movimiento."""
    return has_status(player, "TRAPPED") or has_status(player, "MOVIMIENTO_BLOQUEADO")


def blocks_all_actions(player) -> bool:
    """Retorna True si el jugador tiene un estado que bloquea todas las acciones."""
    return has_status(player, "TRAPPED")


def get_available_actions(player, base_actions: int = 2) -> int:
    """
    Calcula las acciones disponibles considerando estados.
    
    Args:
        player: PlayerState
        base_actions: Acciones base (default 2)
    
    Returns:
        Número de acciones disponibles
    """
    actions = base_actions
    
    # ILUMINADO: +1 acción
    if has_status(player, "ILUMINADO"):
        actions += 1
    
    # ACCION_REDUCIDA: fuerza a 1 acción
    if has_status(player, "ACCION_REDUCIDA"):
        actions = 1
    
    # STUN: 0 acciones
    if has_status(player, "STUN"):
        actions = 0

    # TRAPPED: 0 acciones (a menos que escape)
    if has_status(player, "TRAPPED"):
        actions = 0
    
    return actions


def can_use_special_room(player, room_id: str) -> bool:
    """
    Verifica si un jugador puede usar una habitación especial.
    
    Args:
        player: PlayerState
        room_id: ID de la habitación
    
    Returns:
        True si puede usar la habitación
    """
    # VANIDAD bloquea uso del Salón de Belleza
    if room_id == "SALON_BELLEZA" and has_status(player, "VANIDAD"):
        return False
    
    return True

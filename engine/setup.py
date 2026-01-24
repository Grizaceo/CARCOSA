"""
CORRECCIÓN A: Sistema centralizado de setup de habitaciones especiales.

Implementa el setup canónico del juego físico:
- 3 habitaciones especiales elegidas al azar del pool
- 1 por piso (F1, F2, F3)
- Ubicadas con D4 en R1-R4 (nunca pasillos)
- Boca abajo hasta primera entrada

Referencia: V0_3_Fidelity_Notes_Complement.md sección A
"""

from typing import Dict, List
from engine.state import GameState, RoomState, RoomId, DeckState, BoxState
from engine.rng import RNG


def validate_special_rooms_invariants(state: GameState) -> None:
    """
    CORRECCIÓN A: Valida invariantes de habitaciones especiales (fail-fast).

    Invariantes verificados:
    1. Exactamente 3 habitaciones especiales en total
    2. Exactamente 1 por piso (F1, F2, F3)
    3. Ninguna en pasillos (solo R1-R4)

    Args:
        state: GameState a validar

    Raises:
        ValueError: Si algún invariante falla
    """
    # Invariante 1: Validar exactamente 3 especiales en total
    total_specials = sum(
        1 for room in state.rooms.values()
        if room.special_card_id is not None
    )
    if total_specials != 3:
        raise ValueError(
            f"INVARIANTE FAIL: Debe haber exactamente 3 habitaciones especiales, "
            f"encontradas {total_specials}"
        )

    # Invariante 2: Validar exactamente 1 por piso
    for floor in [1, 2, 3]:
        specials_in_floor = sum(
            1 for room_id, room in state.rooms.items()
            if room.special_card_id is not None
            and str(room_id).startswith(f"F{floor}_")
        )
        if specials_in_floor != 1:
            raise ValueError(
                f"INVARIANTE FAIL: Piso {floor} debe tener exactamente 1 habitación especial, "
                f"encontradas {specials_in_floor}"
            )

    # Invariante 3: Validar que ninguna está en pasillo
    for room_id, room in state.rooms.items():
        if room.special_card_id is not None:
            if "_P" in str(room_id):  # Pasillo
                raise ValueError(
                    f"INVARIANTE FAIL: Habitación especial no puede estar en pasillo: {room_id}"
                )
            # Verificar que está en R1-R4
            if not any(f"_R{i}" in str(room_id) for i in [1, 2, 3, 4]):
                raise ValueError(
                    f"INVARIANTE FAIL: Habitación especial debe estar en R1-R4: {room_id}"
                )


# Pool canónico de habitaciones especiales (juego físico) - 7 tipos
# Actualizado 2026-01-21 conforme a Carcosa_Libro_Tecnico_CANON.md
SPECIAL_ROOMS_POOL = [
    "TABERNA",           # FREE - Recuperación de cordura
    "MOTEMEY",           # FREE - Compra: -2 cordura, ofrece 2 cartas
    "ARMERIA",           # FREE - Adquisición de equipo
    "PUERTAS_AMARILLO",  # PAID - Transporte entre pisos
    "CAMARA_LETAL",      # PAID - 1 acción por jugador participante
    "SALON_BELLEZA",     # PAID - Aplica estado Vanidad
    "MONASTERIO_LOCURA", # PAID - Mecánica especial
]

# Costos de acción canónicos (2026-01-21)
# FREE = No consume acción del jugador
# PAID = Consume 1 acción del jugador
FREE_SPECIAL_ROOMS = {"TABERNA", "MOTEMEY", "ARMERIA"}
PAID_SPECIAL_ROOMS = {"PUERTAS_AMARILLO", "CAMARA_LETAL", "SALON_BELLEZA", "MONASTERIO_LOCURA"}

# Aliases para compatibilidad hacia atrás (nombres legacy → canónicos)
ROOM_TYPE_ALIASES = {
    "PUERTAS": "PUERTAS_AMARILLO",
    "ARMERY": "ARMERIA",
    "PEEK": "TABERNA",  # PEEK era nombre de código para TABERNA
}


def normalize_room_type(room_type: str) -> str:
    """Normaliza un tipo de habitación a su nombre canónico."""
    return ROOM_TYPE_ALIASES.get(room_type, room_type)


def is_free_special_room(room_type: str) -> bool:
    """Retorna True si la habitación especial NO consume acción."""
    normalized = normalize_room_type(room_type)
    return normalized in FREE_SPECIAL_ROOMS


def is_paid_special_room(room_type: str) -> bool:
    """Retorna True si la habitación especial SÍ consume acción."""
    normalized = normalize_room_type(room_type)
    return normalized in PAID_SPECIAL_ROOMS


def setup_special_rooms(state: GameState, rng: RNG) -> None:
    """
    Configura las habitaciones especiales según reglas físicas.

    ALGORITMO:
    1. Elegir 3 tipos distintos del pool (sin repetición)
    2. Asignar uno a cada piso (F1, F2, F3)
    3. Por cada piso: lanzar D4 para determinar R1-R4
    4. Setear special_card_id en RoomState correspondiente

    INVARIANTES (fail-fast):
    - Exactamente 3 habitaciones especiales en total
    - Exactamente 1 por piso
    - Nunca en pasillos (solo R1-R4)

    Args:
        state: GameState a configurar
        rng: Generador de números aleatorios con seed

    Raises:
        ValueError: Si los invariantes no se cumplen
    """
    # Paso 1: Seleccionar 3 tipos distintos al azar
    selected_types = rng.sample(SPECIAL_ROOMS_POOL, k=3)

    # Paso 2: Shuffle para asignación aleatoria a pisos
    rng.shuffle(selected_types)

    # Mapeo de ubicaciones: {tipo: {piso: room_id}}
    special_locations = {}

    # Paso 3: Asignar ubicaciones con D4
    for i, floor_num in enumerate([1, 2, 3]):
        special_type = selected_types[i]

        # Lanzar D4: 1→R1, 2→R2, 3→R3, 4→R4
        d4_roll = rng.randint(1, 4)
        room_id = RoomId(f"F{floor_num}_R{d4_roll}")

        # Guardar ubicación
        if special_type not in special_locations:
            special_locations[special_type] = {}
        special_locations[special_type][floor_num] = d4_roll

        # Setear en RoomState
        if room_id not in state.rooms:
            # Crear room si no existe
            state.rooms[room_id] = RoomState(
                room_id=room_id,
                deck=DeckState(cards=[]),
                revealed=0
            )

        room_state = state.rooms[room_id]
        room_state.special_card_id = special_type
        room_state.special_revealed = False
        room_state.special_destroyed = False
        room_state.special_activation_count = 0

    # Guardar metadata en flags para referencia
    state.flags["SPECIAL_ROOMS_SELECTED"] = selected_types
    state.flags["SPECIAL_ROOM_LOCATIONS"] = special_locations

    # Invariante 1: Validar exactamente 3 especiales en total
    total_specials = sum(
        1 for room in state.rooms.values()
        if room.special_card_id is not None
    )
    if total_specials != 3:
        raise ValueError(
            f"INVARIANTE FAIL: Debe haber exactamente 3 habitaciones especiales, "
            f"encontradas {total_specials}"
        )

    # Invariante 2: Validar exactamente 1 por piso
    for floor in [1, 2, 3]:
        specials_in_floor = sum(
            1 for room_id, room in state.rooms.items()
            if room.special_card_id is not None
            and room_id.startswith(f"F{floor}_")
        )
        if specials_in_floor != 1:
            raise ValueError(
                f"INVARIANTE FAIL: Piso {floor} debe tener exactamente 1 habitación especial, "
                f"encontradas {specials_in_floor}"
            )

    # Invariante 3: Validar que ninguna está en pasillo
    for room_id, room in state.rooms.items():
        if room.special_card_id is not None:
            if "_P" in str(room_id):  # Pasillo
                raise ValueError(
                    f"INVARIANTE FAIL: Habitación especial no puede estar en pasillo: {room_id}"
                )
            # Verificar que está en R1-R4
            if not any(f"_R{i}" in str(room_id) for i in [1, 2, 3, 4]):
                raise ValueError(
                    f"INVARIANTE FAIL: Habitación especial debe estar en R1-R4: {room_id}"
                )


def setup_motemey_deck(state: GameState, rng: RNG) -> None:
    """
    Configura el mazo de Motemey según el Canon.

    Composición (13 cartas total):
    - 3x Brújula (COMPASS)
    - 3x Vial (VIAL)
    - 2x Contundente (BLUNT)
    - 4x Tesoros (TREASURE_RING, TREASURE_STAIRS, TREASURE_SCROLL, TREASURE_PENDANT)
    - 1x Llave (KEY)
    - 1x Cuento (TALE_random)

    Referencia: Canon Implementation Plan
    """
    cards = []
    
    # 3x COMPASS
    cards.extend(["COMPASS"] * 3)
    
    # 3x VIAL
    cards.extend(["VIAL"] * 3)
    
    # 2x BLUNT
    cards.extend(["BLUNT"] * 2)
    
    # 4x TESOROS
    treasures = ["TREASURE_RING", "TREASURE_STAIRS", "TREASURE_SCROLL", "TREASURE_PENDANT"]
    cards.extend(treasures)
    
    # 1x KEY
    cards.append("KEY")
    
    # 1x TALE (Randomly selected from the 4 tales)
    tales = ["TALE_REPAIRER", "TALE_MASK", "TALE_DRAGON", "TALE_SIGN"]
    # Seleccionamos uno consistente para toda la partida (o un set)
    # Por ahora 1 random tale.
    selected_tale = rng.choice(tales)
    cards.append(selected_tale)
    
    # Mezclar
    rng.shuffle(cards)
    
    # Asignar a state
    state.motemey_deck = DeckState(cards=cards)
    state.motemey_deck.top = 0

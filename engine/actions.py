from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class ActionType(str, Enum):
    MOVE = "MOVE"
    SEARCH = "SEARCH"
    MEDITATE = "MEDITATE"
    END_TURN = "END_TURN"

    # Punto de decisión del Rey al final de ronda:
    # Incluye elección de manifestación (floor o d4) y el efecto d6 (1..6).
    KING_ENDROUND = "KING_ENDROUND"

    # Mechanic specific actions
    SACRIFICE = "SACRIFICE"
    ESCAPE_TRAPPED = "ESCAPE_TRAPPED"
    
    # B2: Motemey
    USE_MOTEMEY_SELL = "USE_MOTEMEY_SELL"
    USE_MOTEMEY_BUY = "USE_MOTEMEY_BUY"  # DEPRECATED: usar BUY_START + BUY_CHOOSE
    # CORRECCIÓN D: Sistema de elección de 2 pasos
    USE_MOTEMEY_BUY_START = "USE_MOTEMEY_BUY_START"     # Paso 1: cobra cordura, muestra 2 cartas
    USE_MOTEMEY_BUY_CHOOSE = "USE_MOTEMEY_BUY_CHOOSE"   # Paso 2: elige carta (index 0 o 1)
    
    # B4: Yellow Doors
    USE_YELLOW_DOORS = "USE_YELLOW_DOORS"
    
    # B5: Taberna
    USE_TABERNA_ROOMS = "USE_TABERNA_ROOMS"
    
    # B6: Armory
    USE_ARMORY_DROP = "USE_ARMORY_DROP"
    USE_ARMORY_TAKE = "USE_ARMORY_TAKE"

    # B3: Cámara Letal
    USE_CAMARA_LETAL_RITUAL = "USE_CAMARA_LETAL_RITUAL"



@dataclass(frozen=True)
class Action:
    actor: str
    type: ActionType
    data: Dict[str, Any] = field(default_factory=dict)

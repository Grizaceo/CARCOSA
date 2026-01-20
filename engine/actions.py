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
    USE_MOTEMEY_BUY = "USE_MOTEMEY_BUY"
    
    # B4: Yellow Doors
    USE_YELLOW_DOORS = "USE_YELLOW_DOORS"
    
    # B5: Peek
    USE_PEEK_ROOMS = "USE_PEEK_ROOMS"
    
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

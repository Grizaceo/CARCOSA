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


@dataclass(frozen=True)
class Action:
    actor: str
    type: ActionType
    data: Dict[str, Any] = field(default_factory=dict)

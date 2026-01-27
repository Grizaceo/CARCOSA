from __future__ import annotations

from typing import Optional

from engine.actions import ActionType


def consume_action_cost(action_type: ActionType, cost_override: Optional[int] = None) -> int:
    if cost_override is not None:
        return cost_override

    free_action_types = {
        ActionType.USE_MOTEMEY_BUY,
        ActionType.USE_MOTEMEY_SELL,
        ActionType.USE_MOTEMEY_BUY_START,
        ActionType.USE_MOTEMEY_BUY_CHOOSE,
        ActionType.USE_TABERNA_ROOMS,
        ActionType.USE_ARMORY_DROP,
        ActionType.USE_ARMORY_TAKE,
        ActionType.DISCARD_SANIDAD,
        ActionType.PEEK_ROOM_DECK,
        ActionType.SKIP_PEEK,
    }

    if action_type in free_action_types:
        return 0

    paid_action_types = {
        ActionType.MOVE,
        ActionType.SEARCH,
        ActionType.MEDITATE,
        ActionType.SACRIFICE,
        ActionType.ESCAPE_TRAPPED,
        ActionType.USE_YELLOW_DOORS,
        ActionType.USE_HEALER_HEAL,
        ActionType.USE_BLUNT,
        ActionType.USE_PORTABLE_STAIRS,
        ActionType.USE_CAMARA_LETAL_RITUAL,
        ActionType.USE_CAPILLA,
        ActionType.USE_SALON_BELLEZA,
    }

    if action_type in paid_action_types:
        return 1

    return 0

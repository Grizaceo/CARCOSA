from __future__ import annotations

from typing import Callable, Dict, Optional

from engine.board import floor_of
from engine.rng import RNG
from engine.state import GameState, MonsterState
from engine.systems.sanity import apply_sanity_loss
from engine.types import PlayerId, RoomId

OmenHandler = Callable[[GameState, PlayerId, str, RoomId, bool, Optional[RNG]], bool]

# Registry for omen handlers (resolved by omen_id)
OMEN_HANDLERS: Dict[str, OmenHandler] = {}


def register_omen(omen_id: str) -> Callable[[OmenHandler], OmenHandler]:
    def decorator(fn: OmenHandler) -> OmenHandler:
        OMEN_HANDLERS[omen_id] = fn
        return fn

    return decorator


def get_omen_handler(omen_id: str) -> OmenHandler | None:
    return OMEN_HANDLERS.get(omen_id)


def _spawn_monster(state: GameState, monster_id: str, room: RoomId) -> None:
    from engine.systems.monsters import on_monster_enters_room

    state.monsters.append(MonsterState(monster_id=monster_id, room=room))
    on_monster_enters_room(state, room)


from engine.effects.event_utils import add_status

@register_omen("ARAÑA")
def _omen_spider(state: GameState, pid: PlayerId, omen_id: str, spawn_pos: RoomId, check_passed: bool, rng: Optional[RNG]) -> bool:
    # check_passed (True) = High Roll (Meaning: "Baby" or Minor effect?)
    # check_passed (False) = Low Roll (Meaning: "Big" or Major effect?)
    
    # CANON: "Presagio Araña: canon dice 'pierdes el turno' y araña bebé 'solo stunea 1 turno'"
    # Interpreting: 
    #   Big Spider (Failure): Spawns + Player loses turn.
    #   Baby Spider (Success): Spawns + Player Stunned 1 turn.
    
    if check_passed:
        # Baby Spider case (Success/High Roll)
        _spawn_monster(state, "MONSTER:BABY_SPIDER", spawn_pos)
        add_status(state.players[pid], "STUN", duration=1)
    else:
        # Big Spider case (Failure/Low Roll)
        exists = any("SPIDER" in m.monster_id or "ARAÑA" in m.monster_id for m in state.monsters)
        if not exists:
            _spawn_monster(state, "MONSTER:SPIDER", spawn_pos)
        
        # Player loses turn
        state.flags[f"SKIP_TURN_{pid}"] = True

    return True


@register_omen("DUENDE")
def _omen_goblin(state: GameState, pid: PlayerId, omen_id: str, spawn_pos: RoomId, check_passed: bool, rng: Optional[RNG]) -> bool:
    # Preserved existing logic but using check_passed as is_early
    if check_passed:
        exists = any("DUENDE" in m.monster_id for m in state.monsters)
        if not exists:
            _spawn_monster(state, "MONSTER:DUENDE", spawn_pos)
    else:
        p = state.players[pid]
        if p.objects:
            p.objects.pop()
    return True


@register_omen("REINA_HELADA")
def _omen_ice_queen(state: GameState, pid: PlayerId, omen_id: str, spawn_pos: RoomId, check_passed: bool, rng: Optional[RNG]) -> bool:
    # check_passed (True) -> Low Threat -> Servant?
    # check_passed (False) -> High Threat -> Queen?
    
    # CANON: Servant appears in hallway.
    
    if check_passed: # Assume True is "Late/Servant"? Or False is Queen? 
        # Existing code: is_early (True) -> Queen. False -> Servant.
        # Check: usually Early = Weak? No, Early = Queen is rare. 
        # Let's assume check_passed (True/Good) = Servant (Weaker). check_passed (False/Bad) = Queen.
        # Wait, if Queen is Unique...
        
        # Let's stick to Code equivalence: check_passed ~= is_early?
        # Previous code: is_early (True) -> Queen. 
        # Usually Omens start weak. Maybe "Early" means "First time"? Logic was count < 2.
        # 1st time: Queen. 2nd time: Servant.
        # If we use D6+Sanity, High Roll (Good) -> Servant. Low Roll (Bad) -> Queen.
        
        corridor = RoomId(f"F{floor_of(spawn_pos)}_P")
        _spawn_monster(state, "MONSTER:ICE_SERVANT", corridor)
        
    else:
        exists = any("REINA_HELADA" in m.monster_id for m in state.monsters)
        if not exists:
            corridor = RoomId(f"F{floor_of(spawn_pos)}_P")
            _spawn_monster(state, "MONSTER:REINA_HELADA", corridor)
            
    return True


@register_omen("TUE_TUE")
def _omen_tue_tue(state: GameState, pid: PlayerId, omen_id: str, spawn_pos: RoomId, check_passed: bool, rng: Optional[RNG]) -> bool:
    # CANON: "2+ cordura vuelve a 0 y 0-1 cuenta como aparición"
    # Interpreting: Check Sanity directly.
    
    p = state.players[pid]
    if p.sanity >= 2:
        p.sanity = 0
    else:
        # 0-1 Counts as appearance -> Spawn Monster
        _spawn_monster(state, "MONSTER:TUE_TUE", spawn_pos)
        
    # Remove global counter usage? Or keep for tracking?
    # Canon rule seems state-less (based on sanity), so tracking not needed for decision.
    state.tue_tue_revelations += 1 # Keep purely for stats
    
    return True

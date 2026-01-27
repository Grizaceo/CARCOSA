
import pytest
from engine.state import MonsterState
from engine.state_factory import make_game_state
from engine.types import PlayerId, RoomId
from engine.config import Config
from engine.rng import RNG
from engine.transition import _resolve_card_minimal, _move_monsters

def make_movement_state():
    rooms = {}
    # Create simple F1 map
    for i in range(1, 5):
        rooms[f"F1_R{i}"] = {}
    rooms["F1_P"] = {}

    # F2 for teleports
    for i in range(1, 5):
        rooms[f"F2_R{i}"] = {}
    rooms["F2_P"] = {}

    players = {
        "P1": {"room": "F1_R2", "sanity": 5, "objects": ["SWORD"]},
    }
    s = make_game_state(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        turn_order=["P1"],
        remaining_actions={"P1": 2},
        turn_pos=0,
    )
    s.flags = {}
    return s

def test_spider_hunt_logic():
    s = make_movement_state()
    # P1 at F1_R2
    # Spider at F1_R1
    # Canon map: R1 <-> R2 (Direct neighbor) and R1 <-> P.
    # Dist(R1, R2) = 1.
    s.monsters.append(MonsterState(monster_id="SPIDER_1", room=RoomId("F1_R1")))
    
    _move_monsters(s, Config())
    
    # Should move to R2 (Target)
    spider = s.monsters[0]
    assert spider.room == RoomId("F1_R2"), "Spider should hunt directly to player in R2"

def test_queen_static_logic():
    s = make_movement_state()
    # Queen at F1_R1. Player at F1_R2.
    s.monsters.append(MonsterState(monster_id="REINA_HELADA", room=RoomId("F1_R1")))
    
    _move_monsters(s, Config())
    
    queen = s.monsters[0]
    assert queen.room == RoomId("F1_R1"), "Queen should NOT move"

def test_goblin_spawn_steal_teleport():
    s = make_movement_state()
    p1 = s.players[PlayerId("P1")]
    p1.room = RoomId("F1_R1")
    p1.objects = ["A", "B"]
    
    # Resolve Goblin Spawn
    # Needs RNG for floor choice
    class MockRNG(RNG):
        def choice(self, seq):
            # force choice 2
            if 2 in seq: return 2
            return seq[0]
            
    _resolve_card_minimal(s, PlayerId("P1"), "MONSTER:GOBLIN_1", Config(), MockRNG(0))
    
    # 1. Steal
    assert p1.objects == [], "Goblin should steal all objects"
    assert s.flags.get("GOBLIN_HAS_LOOT_GOBLIN_1") is True
    
    # 2. Teleport to F2_R1 (Same room R1, diff floor)
    goblin = s.monsters[0]
    assert goblin.room == RoomId("F2_R1"), f"Goblin should teleport to F2_R1, got {goblin.room}"

def test_goblin_flee_logic():
    s = make_movement_state()
    # P1 at F1_R2
    # Goblin at F1_R1, WITH LOOT
    s.monsters.append(MonsterState(monster_id="GOBLIN_1", room=RoomId("F1_R1")))
    s.flags["GOBLIN_HAS_LOOT_GOBLIN_1"] = True
    
    # Move
    # Neighbors(R1) = [P, R2].
    # Dist(P, P1@R2) = 1 (P connects to R2).
    # Dist(R2, P1@R2) = 0.
    # Max dist is P (1). 
    # So Goblin should flee to Corridor F1_P.
    _move_monsters(s, Config())
    
    goblin = s.monsters[0]
    assert goblin.room == RoomId("F1_P"), "Goblin with loot should flee towards max distance (Corridor)"

def test_sack_spawn_trap_teleport_carry():
    s = make_movement_state()
    p1 = s.players[PlayerId("P1")]
    p1.room = RoomId("F1_R1")
    
    class MockRNG(RNG):
         def choice(self, seq):
            if not seq: return None
            return seq[0]

    _resolve_card_minimal(s, PlayerId("P1"), "MONSTER:SACK_1", Config(), MockRNG(0))
    
    # 1. Trapped
    assert any(st.status_id == "TRAPPED" for st in p1.statuses), "Player should be TRAPPED"
    assert s.flags.get("SACK_HAS_VICTIM_SACK_1") is True
    
    # 2. Teleport BOTH to NEAREST Empty Room
    # Start: F1_R1.
    sack = s.monsters[0]
    
    from engine.board import floor_of
    assert floor_of(sack.room) == 1, f"Sack Man should stay on F1 (nearest empty), got {sack.room}"
    assert sack.room != RoomId("F1_R1"), "Sack Man must move from spawn room"
    
    assert p1.room == sack.room, f"Player should be carried to {sack.room} with Sack Man"

def test_monster_destruction_armory():
    s = make_movement_state()
    # Set R2 as Armory
    r2 = s.rooms[RoomId("F1_R2")]
    r2.special_card_id = "ARMERY"
    r2.special_revealed = True
    r2.special_destroyed = False
    s.armory_storage[RoomId("F1_R2")] = ["ITEM"]
    
    # Monster Spawns/Moves into R2
    # Simulate via on_enter directly to test destruction
    from engine.transition import _on_monster_enters_room
    _on_monster_enters_room(s, RoomId("F1_R2"))
    
    assert r2.special_destroyed is True, "Armory should be destroyed"
    assert s.armory_storage[RoomId("F1_R2")] == [], "Armory storage should be emptied"
    assert s.flags.get("ARMORY_DESTROYED_F1_R2") is True

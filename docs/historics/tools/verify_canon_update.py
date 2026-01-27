from engine.setup import setup_canonical_deck
from engine.state import GameState, DeckState, RoomState
from engine.rng import RNG
from engine.types import RoomId
from sim.runner import run_episode
from engine.config import Config
import os
import json

def test_tue_tue_absence():
    print("Verifying Tue-Tue absence from physical deck...")
    s = GameState(round=1, players={}, rooms={})
    # Mock rooms for setup
    for f in range(1, 4):
        for r in range(1, 5):
            rid = RoomId(f"F{f}_R{r}")
            s.rooms[rid] = RoomId(rid) # Just keys needed? No, setup needs objects
            s.rooms[rid] = RoomState(room_id=rid, deck=DeckState(cards=[]))
            
    setup_canonical_deck(s, RNG(1))
    
    tue_tue_count = 0
    for room in s.rooms.values():
        for card in room.deck.cards:
            if "MONSTER:TUE_TUE" in str(card):
                tue_tue_count += 1
                
    if tue_tue_count == 0:
        print("PASS: Tue-Tue removed from physical decks.")
    else:
        print(f"FAIL: Found {tue_tue_count} Tue-Tue cards physically!")
        exit(1)

def test_replay_logging():
    print("Verifying Replay Logging (full_state)...")
    out_file = "verify_replay.jsonl"
    if os.path.exists(out_file):
        os.remove(out_file)
        
    run_episode(max_steps=5, seed=42, out_path=out_file, cfg=Config())
    
    with open(out_file, "r") as f:
        line = f.readline()
        data = json.loads(line)
        
    if "full_state" in data:
        print("PASS: full_state found in log.")
        # Optional: check internal structure
        if "players" in data["full_state"] and "rooms" in data["full_state"]:
             print("PASS: full_state structure looks valid.")
        else:
             print("FAIL: full_state missing valid structure.")
             exit(1)
    else:
        print("FAIL: full_state NOT found in log.")
        exit(1)

if __name__ == "__main__":
    test_tue_tue_absence()
    test_replay_logging()


import pytest
from sim.runner import make_smoke_state
from engine.config import Config
from engine.board import is_corridor

def test_canonical_deck_composition():
    """Verifica que el mazo canónico se distribuya correctamente."""
    cfg = Config(KEYS_TOTAL=5)
    state = make_smoke_state(seed=42, cfg=cfg)
    
    # Recolectar todas las cartas de las 12 habitaciones
    all_cards = []
    for rid, room in state.rooms.items():
        if not is_corridor(rid):
            all_cards.extend([str(c) for c in room.deck.cards])
            
    total_count = len(all_cards)
    print(f"Total cards found: {total_count}")
    
    # Conteos esperados
    counts = {}
    for c in all_cards:
        base_name = c.split(":")[1] if ":" in c else c
        if c.startswith("EVENT:"):
            key = f"EVENT:{base_name}"
        elif c.startswith("MONSTER:"):
            key = f"MONSTER:{base_name}"
        elif c.startswith("OBJECT:"):
            key = f"OBJECT:{base_name}"
        elif c.startswith("STATE:"):
            key = f"STATE:{base_name}"
        else:
            key = c
        counts[key] = counts.get(key, 0) + 1
        
    print("Counts:", counts)
    
    # 1. Total (104 aprox)
    # 48 Eventos + 14 Estados + 24 Objetos + 7 Monstruos + 5 Keys + 1 Book + 3 Tales + 2 Treasures = 104
    assert total_count == 104, f"Se esperaban 104 cartas, encontradas {total_count}"
    
    # 2. Llaves
    assert counts.get("KEY", 0) == 5
    
    # 3. Monstruos
    assert counts.get("MONSTER:ARAÑA", 0) == 1
    assert counts.get("MONSTER:WORM", 0) == 0
    assert counts.get("MONSTER:TUE_TUE", 0) == 3
    
    # 4. Objetos
    assert counts.get("OBJECT:COMPASS", 0) == 8
    
    # 5. Estados
    assert counts.get("STATE:MALDITO", 0) == 5

if __name__ == "__main__":
    test_canonical_deck_composition()


from engine.state import GameState, PlayerState
from engine.transition import _resolve_card_minimal
from engine.types import PlayerId, CardId
from engine.config import Config
from engine.board import corridor_id

def test_omen_tue_tue_spawns_token():
    """
    Reproduce el bug donde OMEN:TUE_TUE spawna una ficha de monstruo
    en lugar de aplicar el efecto volátil.
    """
    p1 = PlayerState(player_id=PlayerId("P1"), sanity=6, room=corridor_id(1))
    s = GameState(round=1, players={PlayerId("P1"): p1})
    cfg = Config()

    # Simular carta "OMEN:TUE_TUE"
    # Se espera que OMEN:TUE_TUE aplique la regla general de Omens (spawn si es early)
    # Lo cual es INCORRECTO para el Tue Tue según canon.
    
    _resolve_card_minimal(s, PlayerId("P1"), CardId("OMEN:TUE_TUE"), cfg)
    
    # Verificamos si spawneó monstruo (comportamiento actual buggy)
    monsters = [m for m in s.monsters if "TUE_TUE" in m.monster_id]
    print(f"Monstruos Tue Tue encontrados: {len(monsters)}")
    
    if len(monsters) > 0:
        print("FAIL: El Tue Tue se invocó como ficha (bug confirmado).")
    else:
        print("SUCCESS: El Tue Tue NO se invocó como ficha.")

if __name__ == "__main__":
    test_omen_tue_tue_spawns_token()

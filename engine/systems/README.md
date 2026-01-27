# Sistemas

Mapa minimo de responsabilidades e invariantes. Mantener este archivo actualizado.

- decks.py: operaciones de mazos (top/remaining/put_bottom). Invariante: top no excede len(cards).
- rooms.py: entrada de jugador y revelado de especiales. Invariante: no muta mazos fuera de la sala destino.
- monsters.py: movimiento y spawns en tablero. Invariante: respeta cap de monstruos si aplica.
- status.py: aplica efectos end-of-round via handlers. Invariante: no muta duraciones (eso va en king.py).
- inventory.py: limites y operaciones de inventario. Invariante: slots por rol y soulbound no se descarta.
- player.py: aplica acciones de jugador. Invariante: no resuelve fase del rey.
- king.py: fase del rey y tick de estados. Invariante: no ejecuta acciones de jugador.
- stairs.py: reglas de escaleras y flags temporales. Invariante: escalera temporal solo por ronda.
- sanity.py: perdida/curacion centralizada. Invariante: aplica VANIDAD y setea last_sanity_loss_event.
- sacrifice.py: reglas de sacrificio. Invariante: actualiza object_slots_penalty y sanity max segun reglas.
- turn.py: gestion de turnos y acciones disponibles. Invariante: respeta estados que bloquean.
- victory.py: condiciones de victoria/derrota. Invariante: no muta estado salvo flags de fin.
- finalize.py: cierre de paso/round. Invariante: no muta reglas base, solo orquesta sistemas.

# CHANGELOG

## [v0.4.0] - 2026-01-24 - Canon Compliance Update

### Added
- **Canon: Motemey Deck**
    - Initialized with strict canonical composition: 3 Compass, 3 Vial, 2 Blunt, 4 Treasures, 1 Key, 1 Tale.
    - Implemented logic for "Buy" (Sanity cost, offer 2, choose 1, reject returns to bottom) and "Sell".
- **Canon: Monster Phase**
    - Added End-of-Round Monster Phase.
    - Active monsters deal 1 Sanity Damage to players in the same room.
    - **Stun Logic**: Objects (2 turns) and Escape (1 turn) correctly prevent monster actions.
- **Canon: Key Mechanics**
    - Enforced **Role-based Key Capacity** (e.g. Scout=1).
    - Keys found when inventory is full are returned to the **bottom of the room deck**.
    - Motemey Buy logic respects key limits.
- **Canon: Yellow Doors**
    - Changed from random teleport to **Targeted Teleport**.
    - Acting player chooses target.
    - Target player loses 1 Sanity.
- **Canon: Tue-Tue**
    - Implemented progressive revelation logic (-1 -> -2 -> Fixed -5 Sanity). Never spawns physically.

### Fixed
- **RNG**: Implemented robust `Chi-Squared` tests to ensure d6/d4 uniformity.
- **Sacrifice**: Implemented "Interrupt" window when hitting -5 Sanity (Must choose Sacrifice or Accept).
- **Trapped**: Duration set to 3 turns. Escape is manual (Action, d6+Sanity >= 3). Success stuns monster.
- **Armory/Special Rooms**: Infinite durability confirmed as correct design choice (removed limited use concept).
- **Initialization**: Fixed `sim/runner.py` order to ensure proper canonical setup.

### Verified
- Full Canon Audit performed against `Carcosa_Libro_Tecnico_CANON.md`.
- All major mechanics (Monsters, Items, Rooms, States) verified with new test suite `tests/test_canon_fixes_b.py` and `tests/test_canon_fix_yellow_doors.py`.

## [Unreleased]

### [2026-01-14] - New Mechanics & Rule Definitions

#### Added
- **System: Habitaciones Especiales**
  - Implementación de sistema para manejar tipos de habitaciones especiales por piso.
  - Acción genérica `USE_SPECIAL_ROOM` que despacha lógica según el tipo de habitación.
  - **Tipos de Habitaciones**:
    - **MOTEMEY**: Mecánica de recuperación/interacción específica.
    - **Cámara Letal**: Riesgo/recompensa con costo de vida/cordura.
    - **Salón de Belleza**: Modificación de apariencia/stats.
    - **Puertas**: Mecánica de transporte o bloqueo.
    - **Taberna**: Recuperación de cordura o interacción social.
    - **Armería**: Adquisición de equipo/armas.

- **Mechanic: Sacrificio**
  - Nueva opción para jugadores en estado crítico (-5 Cordura).
  - **Efecto**:
    - Previene -1 de daño a otros jugadores.
    - Retorna al jugador a 0 de Cordura.
    - **Costo**: Aplica penalización permanente (ej. -1 slot de ítems o reducción de rango negativo).

- **Mechanic: Atrapado**
  - Nuevo estado negativo para jugadores.
  - **Acción de Liberación**:
    - Costo: 1 acción.
    - Requisito: Tirada de d6 >= 3 para remover el estado.

- **Rule: Movimiento por Escaleras (d6=1)**
  - Definición formal de la regla de movimiento vertical.
  - Jugadores pueden usar escaleras como movimiento legal bajo condiciones específicas (d6=1).

### [2026-01-13] - Core Updates

#### Changed
- Actualizaciones de consistencia en reglas de movimiento y adyacencia (P0).

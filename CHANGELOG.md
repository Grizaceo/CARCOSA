# CHANGELOG

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

# ESTADO ACTUAL DEL PROYECTO (2026-01-23)

## Resumen Ejecutivo
El repositorio "CARCOSA" ha sido alineado completamente con el Canon Actualizado proporcionado. Se han resuelto todas las discrepancias críticas identificadas en el `mismatch_report_v2.md`. El motor es ahora determinista, testeable y fiel a las reglas de negocio.

## Métricas Clave
- **Tests**: 333 tests pasando (0 fallos).
- **Cobertura**: Reglas Core, Habitaciones Especiales, Roles, Tue-Tue, Motemey, Victoria/Derrota.
- **Determinismo**: RNG inyectable y seeds reproducibles.

## Funcionalidades Implementadas (Canon Updated)

### 1. Mecánicas Core
- **Acciones en -5**: Jugadores mantienen sus 2 acciones (no se reducen a 1).
- **Meditación**: +1 en habitación, **+2 en pasillo**.
- **TRAPPED**: Escape manual (d6+cordura >= 3). Fallo termina turno inmediatamente. Éxito aturde monstruo.
- **Victoria**: Todos en F2_P con >= 4 llaves.
- **Derrota**: Todos en -5 O <= 3 llaves disponibles.

### 2. Rey de Amarillo
- **Inmunidad Falso Rey**: El portador de la Corona (Falso Rey) y jugadores en su piso son **inmunes** a los efectos del d6 (1-6).
- **Rotación Intra-floor**: d6=1 rota cajas dentro del mismo piso.
- **Descarte**: d6=6 descarta objetos (salvo soulbound).

### 3. Habitaciones Especiales
- **Taberna**: 1 cordura, mirar 2 habitaciones (no pasillos). Determinista (log de peek).
- **Motemey**: Compra en 2 pasos. Carta rechazada va al fondo del mazo. Venta implementada.
- **Armería**: Almacena hasta 2 ítems (objetos o llaves).
- **Cámara Letal**: d6 determina costo (ritual). **Éxito añade la 7ª llave al pool global**.
- **Salón de Belleza**: Contador global. 3er uso aplica **VANIDAD** (+1 daño sufrido).
- **Capilla**: d6+2 sanación. Riesgo Paranoia con 1.

### 4. Monstruos y Eventos
- **Tue-Tue**:
    - Nunca spawna.
    - 1ª Rev: -1 cordura (-2 con Vanidad).
    - 2ª Rev: -2 cordura (-3 con Vanidad).
    - 3ª Rev: **Fija** cordura en -5.
- **Reina Helada**: Stun al entrar, acción reducida persistentemente.

### 5. Vanidad
- Hook centralizado `apply_sanity_loss` que aplica +1 al daño sufrido si se tiene el estado VANIDAD.

## Archivos Clave
- `engine/transition.py`: Lógica principal de reglas.
- `engine/state.py`: Definición de estado (incluyendo nuevos contadores Tue-Tue).
- `engine/legality.py`: Reglas de moviemiento y disponibilidad de acciones.
- `tests/`: Suite completa de regresión.

## Próximos Pasos Sugeridos
- Implementar UI/Frontend consumiendo este engine canonizado.
- Refinar textos de flavor en logs.

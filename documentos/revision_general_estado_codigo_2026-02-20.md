# Revisión general del estado del código (2026-02-20)

## Resumen ejecutivo
- Estado general: **funcional pero con higiene de repositorio degradada**.
- Suite en Docker: **400 tests pasan, 1 falla**.
- Riesgo principal: el árbol Git está altamente contaminado por cambios de fin de línea y archivos `:Zone.Identifier`.

## Hallazgos priorizados

### 1) [ALTO] La suite no está completamente en verde en la imagen oficial de desarrollo
- Evidencia:
  - Comando ejecutado: `docker run --rm -v ${PWD}:/app -w /app carcosa:app pytest -q`
  - Resultado: `1 failed, 400 passed in 1.06s`
  - Falla: `ModuleNotFoundError: No module named 'yaml'`.
- Referencias:
  - `tests/test_smoke_pipeline.py:24`
  - `requirements.txt:1`
  - `requirements.txt:20`
  - `Dockerfile.deps:18`
- Impacto:
  - El smoke test de pipeline falla en entorno estándar Docker, bloqueando validación E2E del flujo de experimentos.
- Recomendación:
  - Agregar `PyYAML` a `requirements.txt` (y/o `pyproject.toml`) y reconstruir `carcosa:deps`.

### 2) [ALTO] Árbol Git masivamente sucio por cambios no funcionales
- Evidencia:
  - `git status --porcelain | wc -l` -> `510`
  - `git status --porcelain` -> `239` archivos tracked modificados + `271` untracked.
  - `git diff --shortstat` -> `239 files changed, 30446 insertions(+), 30446 deletions(-)`.
  - `git diff --ignore-cr-at-eol --exit-code` -> salida `0` (no diferencias funcionales al ignorar CRLF).
- Referencias:
  - `README.md`
  - `engine/state.py`
  - `tests/test_states.py`
- Impacto:
  - Revisiones y merges muy ruidosos, alto riesgo de commits accidentales y pérdida de trazabilidad.
- Recomendación:
  - Normalizar EOL en un commit dedicado y separado de cambios funcionales.

### 3) [ALTO] Presencia masiva de metadata Windows (`:Zone.Identifier`) no ignorada correctamente
- Evidencia:
  - Untracked: `271` archivos, todos de metadata `Zone.Identifier`.
  - Patrón actual no coincide con nombres tipo `archivo.py:Zone.Identifier`.
- Referencias:
  - `.gitignore:26`
  - `.gitignore:27`
  - `.gitignore:28`
- Impacto:
  - Ruido continuo en `git status`, riesgo de errores operativos y contaminación de commits.
- Recomendación:
  - Corregir patrones de ignore para metadata ADS (`*:Zone.Identifier`) y limpiar los archivos ya generados.

### 4) [MEDIO] `.gitignore` presenta corrupción de contenido/codificación al final
- Evidencia:
  - Líneas con caracteres nulos al final del archivo (`*.mshieldv\0e\0n...`).
- Referencias:
  - `.gitignore:27`
  - `.gitignore:29`
- Impacto:
  - Comportamiento no confiable de reglas de ignore y mantenimiento más difícil.
- Recomendación:
  - Reescribir `.gitignore` limpio (UTF-8), validando reglas críticas de `venv` y metadata Windows.

### 5) [MEDIO] Configuración de packaging incompleta respecto al runtime real
- Evidencia:
  - `pyproject.toml` define `dependencies = []`, mientras el runtime real depende de `requirements.txt`/Docker.
- Referencias:
  - `pyproject.toml:10`
  - `Dockerfile.deps:18`
- Impacto:
  - Instalación vía `pip install -e .` no representa el entorno real de ejecución/pruebas.
- Recomendación:
  - Alinear dependencias en una sola fuente de verdad o documentar explícitamente el contrato de instalación.

### 6) [BAJO] README desactualizado en volumen de tests
- Evidencia:
  - README indica `Test suite (65 tests)`.
  - Ejecución real reporta `401` tests.
- Referencias:
  - `README.md:129`
- Impacto:
  - Documentación puede inducir expectativas incorrectas de cobertura/escala.
- Recomendación:
  - Actualizar conteo o evitar cifras fijas (usar descripción cualitativa).

## Señales positivas
- Arquitectura modular clara por dominios (`engine/`, `sim/`, `train/`, `tools/`, `tests/`).
- Tamaño de suite amplio: `148` archivos de test.
- Salud funcional alta: 99.75% de tests pasando (400/401).
- Verificación sintáctica OK: `python -m compileall -q engine sim train tools tests` -> `OK`.

## Métricas estructurales
```yaml
snapshot:
  fecha_revision: "2026-02-20T20:48:10-03:00"
  branch: "main"
  upstream: "origin/main"
  head: "1505490a"
  ultimo_commit: "1505490a 2026-02-02 17:23:17 -0300 pendientes problemas del venv"

repositorio:
  archivos_indexables_rg: 534
  cambios_git_totales: 510
  tracked_modificados: 239
  untracked: 271
  untracked_zone_identifier: 271

modulos:
  engine_archivos: 124
  sim_archivos: 18
  train_archivos: 16
  tools_archivos: 36
  tests_archivos: 148

tests:
  comando: "docker run --rm -v ${PWD}:/app -w /app carcosa:app pytest -q"
  resultado: "1 failed, 400 passed"
  prueba_fallida: "tests/test_smoke_pipeline.py::test_smoke_pipeline"
```

## Comandos usados (trazabilidad)
```bash
git status --short --branch
git diff --shortstat
git diff --ignore-cr-at-eol --exit-code
git status --porcelain
python -m compileall -q engine sim train tools tests
docker run --rm -v ${PWD}:/app -w /app carcosa:app pytest -q
```

## Sugerencia de plan mínimo de saneamiento
1. Corregir `.gitignore` (patrón `*:Zone.Identifier` + limpiar codificación) y eliminar metadata ADS local.
2. Separar un commit exclusivo de normalización EOL.
3. Agregar `PyYAML` a dependencias y reconstruir imagen `carcosa:deps`.
4. Re-ejecutar `pytest -q` en Docker y verificar suite 100% verde.
5. Actualizar README para reflejar estado real del proyecto.

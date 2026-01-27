#!/usr/bin/env bash
set -euo pipefail

cd ~/CARCOSA

# --- INPUT (Windows) ---
WIN_PDF="/mnt/c/Users/mirtg/Downloads/Carcosa_Libro_de_Reglas_Tecnico_v0_2.pdf"

# --- OLD DOC (to archive) ---
OLD_MD="docs/Carcosa_Libro_Tecnico_v0_1_extracted.md"
ARCHIVE_DIR="docs/archive"

# --- NEW DOCS (repo) ---
CANON_PDF="docs/Carcosa_Libro_Tecnico_CANON_LEGACY.pdf"       # legacy (historico)
RELEASES_DIR="docs/releases"
RELEASE_PDF="$RELEASES_DIR/Carcosa_Libro_Tecnico_v0_2.pdf"    # versionado (ajusta v0_2 si corresponde)

TODAY="$(date +%Y-%m-%d)"

echo "== Verificando repo =="
test -d .git || { echo "ERROR: No estas en un repo git (falta .git)"; exit 1; }

echo "== Verificando PDF origen (Windows) =="
test -f "$WIN_PDF" || { echo "ERROR: No existe el PDF en Windows: $WIN_PDF"; exit 1; }

echo "== Archivando documento viejo (si existe) =="
mkdir -p "$ARCHIVE_DIR"
if [ -f "$OLD_MD" ]; then
  ARCHIVED_MD="$ARCHIVE_DIR/$(basename "$OLD_MD" .md)_archived_${TODAY}.md"
  git mv "$OLD_MD" "$ARCHIVED_MD"
  echo "OK: Archivado $OLD_MD -> $ARCHIVED_MD"
else
  echo "WARN: No se encontro $OLD_MD (se omite archivado del MD viejo)."
fi

echo "== Copiando PDF nuevo (CANON + release) =="
mkdir -p docs
mkdir -p "$RELEASES_DIR"

cp -f "$WIN_PDF" "$CANON_PDF"
cp -f "$WIN_PDF" "$RELEASE_PDF"

echo "OK: CANON  -> $CANON_PDF"
echo "OK: RELEASE-> $RELEASE_PDF"

echo "== Actualizando docs/DOCUMENTATION_INDEX.md (si existe) =="
if [ -f "docs/DOCUMENTATION_INDEX.md" ]; then
  # Agrega/normaliza una seccion canonica (idempotente: no duplica si ya existe)
  if ! grep -q "Carcosa_Libro_Tecnico_CANON_LEGACY.pdf" docs/DOCUMENTATION_INDEX.md; then
    cat >> docs/DOCUMENTATION_INDEX.md <<EOF

## Regla canonica vigente (Libro Tecnico)
- $CANON_PDF (vigente, nombre estable)
- $RELEASE_PDF (release/versionado)

## Archivo
- $ARCHIVE_DIR/ (versiones anteriores; ver nombres con fecha)
EOF
    echo "OK: docs/DOCUMENTATION_INDEX.md actualizado."
  else
    echo "OK: docs/DOCUMENTATION_INDEX.md ya referencia el CANON (sin cambios)."
  fi
else
  echo "WARN: docs/DOCUMENTATION_INDEX.md no existe (se omite actualizacion)."
fi

echo "== Git stage =="
git add -A

echo "== Estado antes de commit =="
git status

echo "== Commit =="
git commit -m "Docs: set canonical technical rulebook PDF (CANON) and archive old v0.1 extracted"

echo
echo "Listo. Ahora ejecuta:"
echo "  git push"

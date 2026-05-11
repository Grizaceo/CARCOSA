#!/usr/bin/env bash
# run_godot.sh — Entrypoint para el cliente Godot en Docker
#
# Flujo:
#   1. Iniciar display virtual (xvfb) si no hay DISPLAY
#   2. Exportar el proyecto a PCK usando el editor + xvfb
#   3. Ejecutar el PCK exportado
#
# Variables de entorno:
#   SERVER_URL    — URL del server CARCOSA (default: http://carcosa-server:8765)
#   VNC_PASSWORD  — password para VNC (default: carcosa)
#   DISPLAY       — si está seteado, usa X11 forwarding del host

set -euo pipefail

GODOT_BIN="/opt/godot/godot"
PROJECT_DIR="/app/godot_client"
EXPORT_DIR="/app/godot_client/export"
PCK_PATH="${EXPORT_DIR}/CARCOSA.pck"
VNC_PASSWORD="${VNC_PASSWORD:-carcosa}"
SERVER_URL="${SERVER_URL:-http://carcosa-server:8765}"

# Escribir config.json con la URL del server
cat > "${PROJECT_DIR}/config.json" <<EOF
{
  "server_url": "${SERVER_URL}"
}
EOF
echo "[run_godot] Server URL: ${SERVER_URL}"

# ── Iniciar display ──────────────────────────────────────────────────────────

start_display() {
	if [[ -z "${DISPLAY:-}" ]]; then
		echo "[run_godot] Iniciando display virtual (xvfb)..."
		export DISPLAY=:99
		Xvfb :99 -screen 0 1280x720x24 >/dev/null 2>&1 &
		sleep 1
	fi
}

start_display

# ── Exportar PCK si no existe ───────────────────────────────────────────────

if [[ ! -f "${PCK_PATH}" ]]; then
	echo "[run_godot] Exportando PCK con editor + xvfb..."

	# Usar xvfb-run si está disponible, si no ya tenemos DISPLAY=:99
	xvfb-run --auto-servernum --server-args="-screen 0 1280x720x24" \
		"${GODOT_BIN}" --headless --path "${PROJECT_DIR}" \
		--export-release "Linux/X11" "${PCK_PATH}" 2>&1 || {

		echo "[run_godot] xvfb-run falló, intentando con DISPLAY existente..."
		"${GODOT_BIN}" --headless --path "${PROJECT_DIR}" \
			--export-release "Linux/X11" "${PCK_PATH}" 2>&1 || {

			echo "[run_godot] FALLÓ la exportación."
			echo "[run_godot] Necesitás abrir el proyecto en Godot Editor y configurar el preset Linux."
			echo "[run_godot] Project → Export → Add → Linux/X11"
			exit 1
		}
	}

	if [[ ! -f "${PCK_PATH}" ]]; then
		echo "[run_godot] FALLÓ: no se generó el PCK."
		exit 1
	fi
	echo "[run_godot] PCK exportado: ${PCK_PATH}"
else
	echo "[run_godot] PCK ya existe: ${PCK_PATH}"
fi

# ── Iniciar VNC para visualización ──────────────────────────────────────────

if [[ -z "${DISPLAY:-}" ]]; then
	echo "[run_godot] Iniciando VNC en puerto 5900..."
	x11vnc -display :99 -nopw -forever -shared -rfbport 5900 >/dev/null 2>&1 &
	echo "[run_godot] VNC disponible en puerto 5900"
fi

# ── Ejecutar el juego ───────────────────────────────────────────────────────

echo "[run_godot] Iniciando CARCOSA Client..."
"${GODOT_BIN}" --path "${PROJECT_DIR}" --main-pack "${PCK_PATH}"

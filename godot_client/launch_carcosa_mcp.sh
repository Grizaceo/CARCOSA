#!/bin/bash
# Launch CARCOSA Godot project with MCP Native server on port 9080
# Usage: bash launch_carcosa_mcp.sh [--headless]

GODOT_EXE="/mnt/c/Users/usuario/Desktop/_WORK_MISC/Code/Godot_v4.6.1-stable_win64.exe/Godot_v4.6.1-stable_win64.exe"
PROJECT_PATH="/home/gris/.hermes/workspace/ACTIVE/CARCOSA/godot_client"

if [ ! -f "$GODOT_EXE" ]; then
    # Try to find any Godot 4.x executable in Windows
    GODOT_EXE=$(find /mnt/c -maxdepth 5 -name "Godot_v4*" -o -name "Godot.exe" 2>/dev/null | head -1)
fi

if [ -z "$GODOT_EXE" ]; then
    echo "ERROR: No se encontró Godot executable en Windows."
    echo "Instalá Godot 4.x desde https://godotengine.org/download/windows/"
    exit 1
fi

ARGS="--editor --path \"$PROJECT_PATH\" -- --mcp-server --mcp-port=9080"

if [ "$1" = "--headless" ]; then
    ARGS="$ARGS --headless"
fi

echo "Launching CARCOSA Godot MCP on port 9080..."
echo "Executable: $GODOT_EXE"
echo "Project: $PROJECT_PATH"
echo ""

# Convert WSL path to Windows path for Godot
WIN_PROJECT=$(wslpath -w "$PROJECT_PATH" 2>/dev/null || echo "$PROJECT_PATH")
cmd.exe /c "start \"\" \"$GODOT_EXE\" --editor --path \"$WIN_PROJECT\" -- --mcp-server --mcp-port=9080"

echo "Godot MCP Native iniciado en http://localhost:9080/mcp"
echo "Para headless mode: bash launch_carcosa_mcp.sh --headless"
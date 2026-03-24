# scripts/BoardView.gd
# Muestra el estado del juego con RichTextLabel (BBCode) para colores y barras visuales.
# Requiere que el nodo hijo "Content" sea de tipo RichTextLabel con bbcode_enabled=true.
extends ScrollContainer

@onready var content: RichTextLabel = $Content

# Paleta de colores por jugador (hex sin #)
const PLAYER_COLORS: Dictionary = {
	"P1": "64b5f6",
	"P2": "81c784",
	"P3": "ffb74d",
	"P4": "f06292",
}


func update_state(state: Dictionary) -> void:
	content.text = _render(state)


func _render(state: Dictionary) -> String:
	var lines: PackedStringArray = []
	var active: String = state.get("active_actor", "")
	var players: Dictionary = state.get("players", {})
	var monsters: Array = state.get("monsters", [])

	# ── Jugadores ──────────────────────────────────────────────────────────────
	lines.append("[b]JUGADORES[/b]\n")
	for pid: String in players:
		var p: Dictionary = players[pid]
		var color: String = PLAYER_COLORS.get(pid, "ffffff")
		var san: int = p.get("sanity", 0)
		var san_max: int = max(p.get("sanity_max", 10), 1)
		var dead: bool = san <= 0

		if dead:
			lines.append("[color=#444][b]✗ %s[/b] [i](eliminado)[/i][/color]\n\n" % pid)
			continue

		# Nombre + indicador de turno activo
		if pid == active:
			lines.append("[bgcolor=#1a2e00][color=#fff176][b] ▶ %s ◀ [/b][/color][/bgcolor]\n" % pid)
		else:
			lines.append("[color=#%s][b]  %s[/b][/color]\n" % [color, pid])

		# Barra de cordura
		lines.append("  Cord: [color=#%s]%s[/color] [color=#777]%d/%d[/color]\n" % [
			color, _bar(san, san_max, color), san, san_max,
		])

		# Stats compactos
		var keys_v: int = p.get("keys", 0)
		var ks: String = "[color=#ffcc80]K:%d[/color]" % keys_v if keys_v > 0 else "[color=#444]K:0[/color]"
		var acts: int = p.get("remaining_actions", 0)
		var as_str: String = "[color=#fff176]⚡%d[/color]" % acts if acts > 0 else "[color=#444]⚡0[/color]"
		lines.append("  %s   %s   [color=#888]%s[/color]\n" % [ks, as_str, str(p.get("room", "?"))])

		# Rol
		var role_id: String = str(p.get("role_id", ""))
		if not role_id.is_empty() and role_id != "null" and role_id != "None":
			lines.append("  [color=#b39ddb]★ %s[/color]\n" % role_id)

		# Objetos
		var objects: Array = p.get("objects", [])
		if objects.size() > 0:
			lines.append("  [color=#80deea]Obj: %s[/color]\n" % "  ".join(objects))

		# Estatuses negativos
		var statuses: Array = p.get("statuses", [])
		if statuses.size() > 0:
			lines.append("  [color=#ef9a9a]⚠ %s[/color]\n" % "  ".join(statuses))

		lines.append("\n")

	# ── Monstruos ──────────────────────────────────────────────────────────────
	if monsters.size() > 0:
		lines.append("[b]MONSTRUOS[/b]\n")
		for m: Dictionary in monsters:
			lines.append("  [color=#ef5350][b]MON:%s[/b][/color]  [color=#aaa]%s[/color]  [color=#666](p%s)[/color]\n" % [
				str(m.get("id", "?")),
				str(m.get("room", "?")),
				str(m.get("floor", "?")),
			])
		lines.append("\n")

	# ── Meta ───────────────────────────────────────────────────────────────────
	lines.append("[color=#444]─────────────────────────[/color]\n")
	lines.append("Ronda [b]%d[/b]   Fase [b]%s[/b]   Rey piso [b]%d[/b]\n" % [
		state.get("round", 0),
		state.get("phase", "?"),
		state.get("king_floor", 1),
	])
	if state.get("game_over", false):
		var outcome: String = state.get("outcome", "?")
		var won: bool = "WIN" in outcome.to_upper()
		lines.append("\n[b][color=%s]★  RESULTADO: %s  ★[/color][/b]\n" % [
			"#69f0ae" if won else "#ef5350", outcome,
		])

	return "".join(lines)


func _bar(value: int, max_value: int, color: String, width: int = 12) -> String:
	if max_value <= 0:
		return "[color=#333]%s[/color]" % "─".repeat(width)
	var filled: int = clampi(int(round(float(value) / float(max_value) * width)), 0, width)
	return "[color=#%s]%s[/color][color=#2a2a2a]%s[/color]" % [
		color, "█".repeat(filled), "░".repeat(width - filled),
	]

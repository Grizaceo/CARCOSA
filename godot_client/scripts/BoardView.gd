# scripts/BoardView.gd
# Muestra el estado del juego como texto estructurado (sin gráficos todavía).
# Cuando haya sprites, reemplazar _render() con nodos visuales sin tocar el resto.
extends ScrollContainer

@onready var content: Label = $Content


func update_state(state: Dictionary) -> void:
	content.text = _render(state)


func _render(state: Dictionary) -> String:
	var lines: PackedStringArray = []
	var active: String = state.get("active_actor", "")

	# ── Jugadores ──────────────────────────────────────────────────────────────
	lines.append("══════════ JUGADORES ══════════")
	var players: Dictionary = state.get("players", {})
	for pid: String in players:
		var p: Dictionary = players[pid]
		var mark: String = " ◄ TURNO" if pid == active else ""
		var remaining: int = p.get("remaining_actions", 0)
		lines.append(
			"[%s]%s" % [pid, mark]
		)
		lines.append(
			"  Cordura: %d/%d   Llaves: %d   Acciones: %d" % [
				p.get("sanity", 0),
				p.get("sanity_max", 0),
				p.get("keys", 0),
				remaining,
			]
		)
		lines.append("  Sala: %s" % str(p.get("room", "?")))
		var objects: Array = p.get("objects", [])
		if objects.size() > 0:
			lines.append("  Objetos: " + ", ".join(objects))
		var statuses: Array = p.get("statuses", [])
		if statuses.size() > 0:
			lines.append("  Estados: " + ", ".join(statuses))
		lines.append("")

	# ── Monstruos ──────────────────────────────────────────────────────────────
	var monsters: Array = state.get("monsters", [])
	if monsters.size() > 0:
		lines.append("══════════ MONSTRUOS ══════════")
		for m: Dictionary in monsters:
			lines.append(
				"  [%s]  piso: %s   sala: %s" % [
					str(m.get("id", "?")),
					str(m.get("floor", "?")),
					str(m.get("room", "?")),
				]
			)
		lines.append("")

	# ── Meta ───────────────────────────────────────────────────────────────────
	lines.append("──────────────────────────────")
	lines.append("Ronda: %d   Fase: %s   Rey: piso %d" % [
		state.get("round", 0),
		state.get("phase", "?"),
		state.get("king_floor", 1),
	])
	if state.get("game_over", false):
		lines.append("RESULTADO: %s" % state.get("outcome", "?"))

	return "\n".join(lines)

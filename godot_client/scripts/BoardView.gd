# scripts/BoardView.gd
# Board view for CARCOSA game.
extends ScrollContainer

@onready var content: RichTextLabel = $ScrollContent/Content
@onready var board_container: VBoxContainer = $ScrollContent/BoardContainer

var room_nodes: Dictionary = {}
var RoomPanelScene = preload("res://scenes/RoomPanel.tscn")

# Player colors (hex without #)
const PLAYER_COLORS: Dictionary = {
	"P1": "64b5f6",
	"P2": "81c784",
	"P3": "ffb74d",
	"P4": "f06292",
}

const FLOORS = 3
const ROOMS_PER_FLOOR = 4

func _ready() -> void:
	for f in range(FLOORS, 0, -1):
		var floor_panel = PanelContainer.new()
		var bg_style = StyleBoxFlat.new()
		bg_style.bg_color = Color(0.1, 0.1, 0.1, 0.5)
		bg_style.corner_radius_top_left = 8
		bg_style.corner_radius_top_right = 8
		bg_style.corner_radius_bottom_left = 8
		bg_style.corner_radius_bottom_right = 8
		floor_panel.add_theme_stylebox_override("panel", bg_style)
		
		var floor_margin = MarginContainer.new()
		floor_margin.add_theme_constant_override("margin_top", 10)
		floor_margin.add_theme_constant_override("margin_bottom", 10)
		floor_margin.add_theme_constant_override("margin_left", 10)
		floor_margin.add_theme_constant_override("margin_right", 10)
		floor_panel.add_child(floor_margin)
		
		var floor_vbox = VBoxContainer.new()
		floor_vbox.add_theme_constant_override("separation", 10)
		floor_margin.add_child(floor_vbox)
		
		var floor_lbl = Label.new()
		floor_lbl.text = "PISO %d" % f
		floor_lbl.add_theme_font_size_override("font_size", 14)
		floor_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		floor_vbox.add_child(floor_lbl)
		
		var top_row = HBoxContainer.new()
		top_row.add_theme_constant_override("separation", 20)
		top_row.alignment = BoxContainer.ALIGNMENT_CENTER
		top_row.add_child(_create_room("F%d_R1" % f, "F%d_R1" % f))
		top_row.add_child(_create_room("F%d_R2" % f, "F%d_R2" % f))
		floor_vbox.add_child(top_row)
		
		var mid_row = HBoxContainer.new()
		mid_row.alignment = BoxContainer.ALIGNMENT_CENTER
		var pasillo = _create_room("F%d_P" % f, "F%d Pasillo" % f)
		mid_row.add_child(pasillo)
		floor_vbox.add_child(mid_row)
		
		var bot_row = HBoxContainer.new()
		bot_row.add_theme_constant_override("separation", 20)
		bot_row.alignment = BoxContainer.ALIGNMENT_CENTER
		bot_row.add_child(_create_room("F%d_R3" % f, "F%d_R3" % f))
		bot_row.add_child(_create_room("F%d_R4" % f, "F%d_R4" % f))
		floor_vbox.add_child(bot_row)
		
		if board_container:
			board_container.add_child(floor_panel)

func _create_room(id: String, title: String) -> Control:
	var p = RoomPanelScene.instantiate()
	p.set_room(id, title)
	room_nodes[id] = p
	return p

func update_state(state: Dictionary) -> void:
	# Clear tokens
	for room in room_nodes.values():
		room.clear_tokens()
		room.title_label.text = room.room_id
	
	# Populate players
	var players = state.get("players", {})
	var active = state.get("active_actor", "")
	for pid in players:
		var p = players[pid]
		if p.get("sanity", 0) <= 0:
			continue
		var room_id = str(p.get("room", ""))
		if room_nodes.has(room_id):
			room_nodes[room_id].add_player_token(pid, p.get("sanity", 0), pid == active)
			
	# Populate monsters
	var monsters = state.get("monsters", [])
	for m in monsters:
		var room_id = str(m.get("room", ""))
		if room_nodes.has(room_id):
			room_nodes[room_id].add_monster_token(str(m.get("id", "?")))
			
	# Populate King
	var king_floor = state.get("king_floor", 0)
	if king_floor > 0:
		var corridor_id = "F%d_P" % king_floor
		if room_nodes.has(corridor_id):
			room_nodes[corridor_id].add_king_token()
			
	# Mark stairs
	var stairs = state.get("stairs", {})
	for f_str in stairs:
		var stair_room = str(stairs[f_str])
		if room_nodes.has(stair_room):
			room_nodes[stair_room].title_label.text = room_nodes[stair_room].room_id + " [UP]"

	# Update side text info
	if content:
		content.text = _render_text(state)

func _render_text(state: Dictionary) -> String:
	var lines: PackedStringArray = []
	var active: String = state.get("active_actor", "")
	var players: Dictionary = state.get("players", {})

	lines.append("[b]ESTADO DE JUGADORES[/b]\n")
	for pid: String in players:
		var p: Dictionary = players[pid]
		var color: String = PLAYER_COLORS.get(pid, "ffffff")
		var san: int = p.get("sanity", 0)
		var san_max: int = max(p.get("sanity_max", 10), 1)
		var dead: bool = san <= 0

		if dead:
			lines.append("[color=#444][b]X %s[/b] (eliminado)[/color]\n\n" % pid)
			continue

		if pid == active:
			lines.append("[bgcolor=#1a2e00][color=#fff176][b] >> %s << [/b][/color][/bgcolor]\n" % pid)
		else:
			lines.append("[color=#%s][b]  %s[/b][/color]\n" % [color, pid])

		lines.append("  Cord: [color=#%s]%s[/color] [color=#777]%d/%d[/color]\n" % [
			color, _bar(san, san_max, color), san, san_max,
		])

		var keys_v: int = p.get("keys", 0)
		var ks: String = "[color=#ffcc80]K:%d[/color]" % keys_v if keys_v > 0 else "[color=#444]K:0[/color]"
		var acts: int = p.get("remaining_actions", 0)
		var as_str: String = "[color=#fff176]A:%d[/color]" % acts if acts > 0 else "[color=#444]A:0[/color]"
		lines.append("  %s   %s   [color=#888]%s[/color]\n" % [ks, as_str, str(p.get("room", "?"))])

		var role_id: String = str(p.get("role_id", ""))
		if not role_id.is_empty() and role_id != "null" and role_id != "None":
			lines.append("  [color=#b39ddb]* %s[/color]\n" % role_id)

		var objects: Array = p.get("objects", [])
		if objects.size() > 0:
			lines.append("  [color=#80deea]Obj: %s[/color]\n" % "  ".join(objects))

		var statuses: Array = p.get("statuses", [])
		if statuses.size() > 0:
			lines.append("  [color=#ef9a9a]! %s[/color]\n" % "  ".join(statuses))

		lines.append("\n")

	lines.append("[color=#444]----------------------[/color]\n")
	lines.append("Ronda %d  Fase %s  Rey piso %d\n" % [
		state.get("round", 0),
		state.get("phase", "?"),
		state.get("king_floor", 1),
	])
	if state.get("game_over", false):
		var outcome: String = str(state.get("outcome", "?"))
		var won: bool = "WIN" in outcome.to_upper()
		lines.append("\n[b][color=%s]*** RESULTADO: %s ***[/color][/b]\n" % [
			"#69f0ae" if won else "#ef5350", outcome,
		])

	return "".join(lines)

func _bar(value: int, max_value: int, color: String, width: int = 10) -> String:
	if max_value <= 0:
		return "[color=#333]%s[/color]" % "-".repeat(width)
	var filled: int = clampi(int(round(float(value) / float(max_value) * width)), 0, width)
	return "[color=#%s]%s[/color][color=#2a2a2a]%s[/color]" % [
		color, "#".repeat(filled), ".".repeat(width - filled),
	]

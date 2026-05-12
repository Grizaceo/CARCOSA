# scripts/RoomPanel.gd
extends PanelContainer

@onready var title_label: Label = $VBoxContainer/TitleLabel
@onready var tokens_container: HFlowContainer = $VBoxContainer/TokensContainer

var room_id: String = ""

# Colores de jugadores (hex sin #)
const PLAYER_COLORS: Dictionary = {
	"P1": "64b5f6",
	"P2": "81c784",
	"P3": "ffb74d",
	"P4": "f06292",
}

func set_room(id: String, title: String) -> void:
	room_id = id
	if title_label:
		title_label.text = title

func clear_tokens() -> void:
	if not tokens_container:
		return
	for child in tokens_container.get_children():
		child.queue_free()

func add_player_token(pid: String, sanity: int, is_active: bool) -> void:
	var lbl = Label.new()
	lbl.text = " %s:%d " % [pid, sanity]
	lbl.add_theme_font_size_override("font_size", 12)
	
	var style = StyleBoxFlat.new()
	var color_hex = PLAYER_COLORS.get(pid, "ffffff")
	style.bg_color = Color(color_hex)
	style.bg_color.a = 0.3
	style.border_width_bottom = 2
	style.border_color = Color(color_hex)
	
	if is_active:
		style.bg_color = Color("#1a2e00")
		style.border_color = Color("#fff176")
		lbl.add_theme_color_override("font_color", Color("#fff176"))
	else:
		lbl.add_theme_color_override("font_color", Color(color_hex))
		
	style.corner_radius_top_left = 4
	style.corner_radius_top_right = 4
	style.corner_radius_bottom_left = 4
	style.corner_radius_bottom_right = 4
	
	lbl.add_theme_stylebox_override("normal", style)
	tokens_container.add_child(lbl)

func add_monster_token(monster_id: String) -> void:
	var lbl = Label.new()
	lbl.text = " M "
	lbl.add_theme_font_size_override("font_size", 12)
	lbl.add_theme_color_override("font_color", Color("#ef5350"))
	
	var style = StyleBoxFlat.new()
	style.bg_color = Color("#ef5350")
	style.bg_color.a = 0.2
	style.border_width_all = 1
	style.border_color = Color("#ef5350")
	style.corner_radius_top_left = 8
	style.corner_radius_top_right = 8
	style.corner_radius_bottom_left = 8
	style.corner_radius_bottom_right = 8
	
	lbl.add_theme_stylebox_override("normal", style)
	lbl.tooltip_text = monster_id
	tokens_container.add_child(lbl)

func add_king_token() -> void:
	var lbl = Label.new()
	lbl.text = " ♚ REY "
	lbl.add_theme_font_size_override("font_size", 12)
	lbl.add_theme_color_override("font_color", Color("#ce93d8"))
	
	var style = StyleBoxFlat.new()
	style.bg_color = Color("#ce93d8")
	style.bg_color.a = 0.2
	style.border_width_all = 1
	style.border_color = Color("#ce93d8")
	
	lbl.add_theme_stylebox_override("normal", style)
	tokens_container.add_child(lbl)

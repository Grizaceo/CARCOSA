# scripts/ActionPanel.gd
# Panel de acciones legales con nombres humanizados en español, categorías y
# atajos de teclado 1-9 para selección rápida sin ratón.
extends ScrollContainer

@onready var title_label: Label = $VBox/TitleLabel
@onready var buttons_container: VBoxContainer = $VBox/ButtonsContainer

@export var player_num: int = 1

var _actor: String = ""
var _actions: Array = []

# [ label_es, symbol, categoría ]
const ACTION_LABELS: Dictionary = {
	"MOVE":                    ["Moverse",              "→",  "Movimiento"],
	"SEARCH":                  ["Buscar en sala",        "[S]", "Acción"],
	"MEDITATE":                ["Meditar (+cordura)",    "+",   "Recuperación"],
	"DISCARD_SANIDAD":         ["Descartar cordura",     "-",   "Otro"],
	"END_TURN":                ["Terminar turno",        ">>",  "Turno"],
	"KING_ENDROUND":           ["Decisión del Rey",      "♚",  "Rey"],
	"SACRIFICE":               ["Sacrificar jugador",    "⚡",  "Mecánica"],
	"ACCEPT_SACRIFICE":        ["Aceptar -5 cordura",    "!",   "Mecánica"],
	"ESCAPE_TRAPPED":          ["Escapar trampa",        "→",  "Movimiento"],
	"USE_MOTEMEY_SELL":        ["Motemey: Vender",       "◆",  "Lugar"],
	"USE_MOTEMEY_BUY_START":   ["Motemey: Comprar",      "◆",  "Lugar"],
	"USE_MOTEMEY_BUY_CHOOSE":  ["Motemey: Elegir carta", "◆",  "Lugar"],
	"USE_YELLOW_DOORS":        ["Puertas Amarillas",     "◆",  "Lugar"],
	"USE_TABERNA_ROOMS":       ["Taberna: Cuartos",      "◆",  "Lugar"],
	"USE_ARMORY_DROP":         ["Armería: Dejar arma",   "◆",  "Lugar"],
	"USE_ARMORY_TAKE":         ["Armería: Tomar arma",   "◆",  "Lugar"],
	"USE_SALON_BELLEZA":       ["Salón de Belleza",      "◆",  "Lugar"],
	"USE_CAPILLA":             ["Usar Capilla",          "◆",  "Lugar"],
	"USE_CAMARA_LETAL_RITUAL": ["Cámara Letal: Ritual",  "◆",  "Lugar"],
	"USE_ATTACH_TALE":         ["Adjuntar Cuento",       "◎",  "Libro"],
	"USE_READ_YELLOW_SIGN":    ["Leer Signo Amarillo",   "◎",  "Libro"],
	"USE_HEALER_HEAL":         ["Sanador: Curar",        "★",  "Rol"],
	"USE_BLUNT":               ["Usar Contundente",      "★",  "Rol"],
	"USE_PORTABLE_STAIRS":     ["Escalera Portátil",     "★",  "Rol"],
	"USE_OBJECT":              ["Usar Objeto",           "[O]", "Acción"],
	"PEEK_ROOM_DECK":          ["Ver deck de sala",      "[V]", "Acción"],
	"SKIP_PEEK":               ["Ignorar peek",          ">>",  "Acción"],
}

const CATEGORY_COLORS: Dictionary = {
	"Movimiento":   "64b5f6",
	"Acción":       "a5d6a7",
	"Recuperación": "80cbc4",
	"Turno":        "fff176",
	"Rey":          "ce93d8",
	"Mecánica":     "ff8a65",
	"Lugar":        "ffcc80",
	"Libro":        "b0bec5",
	"Rol":          "f48fb1",
	"Otro":         "888888",
}


func show_actions(actor: String, actions: Array) -> void:
	_actor = actor
	_actions = actions
	title_label.text = "Acciones — %s  (%d)" % [actor, actions.size()]
	_rebuild_buttons()


func show_waiting(actor: String) -> void:
	_actor = ""
	_actions = []
	title_label.text = "⏳ Turno de %s…" % actor
	_rebuild_buttons()


func clear_actions() -> void:
	_actor = ""
	_actions = []
	title_label.text = "Sin acciones"
	_rebuild_buttons()


func _rebuild_buttons() -> void:
	for child in buttons_container.get_children():
		child.queue_free()

	var last_cat := ""
	for i: int in _actions.size():
		var action: Dictionary = _actions[i]
		var type_str: String = action.get("type", "?")
		var info: Array = ACTION_LABELS.get(type_str, [type_str, "▸", "Otro"])
		var label: String = info[0]
		var symbol: String = info[1]
		var cat: String = info[2]
		var color: String = CATEGORY_COLORS.get(cat, "aaaaaa")

		# Separador y encabezado de categoría
		if cat != last_cat:
			last_cat = cat
			if buttons_container.get_child_count() > 0:
				buttons_container.add_child(HSeparator.new())
			var cat_lbl := Label.new()
			cat_lbl.text = " " + cat
			cat_lbl.add_theme_font_size_override("font_size", 10)
			cat_lbl.modulate = Color(0.55, 0.55, 0.55, 1.0)
			buttons_container.add_child(cat_lbl)

		var btn := Button.new()
		var num: String = "[%d] " % (i + 1) if i < 9 else "    "
		btn.text = "%s%s  %s  %s" % [num, symbol, label, _format_data(action.get("data", {}))]
		btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
		btn.add_theme_color_override("font_color", Color("#" + color))
		btn.pressed.connect(_on_action_pressed.bind(i))
		buttons_container.add_child(btn)


func _on_action_pressed(index: int) -> void:
	if index >= _actions.size():
		return
	var action: Dictionary = _actions[index]
	var actor := _actor
	clear_actions()
	GameClient.send_action(actor, action.get("type", ""), action.get("data", {}))


func _unhandled_input(event: InputEvent) -> void:
	if _actions.is_empty():
		return
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	var n := -1
	
	if player_num == 1:
		match event.keycode:
			KEY_1: n = 0
			KEY_2: n = 1
			KEY_3: n = 2
			KEY_4: n = 3
			KEY_5: n = 4
			KEY_6: n = 5
			KEY_7: n = 6
			KEY_8: n = 7
			KEY_9: n = 8
	elif player_num == 2:
		match event.keycode:
			KEY_U: n = 0
			KEY_I: n = 1
			KEY_O: n = 2
			KEY_J: n = 3
			KEY_K: n = 4
			KEY_L: n = 5
			KEY_M: n = 6
			# Numpad como alternativa
			KEY_KP_1: n = 0
			KEY_KP_2: n = 1
			KEY_KP_3: n = 2
			KEY_KP_4: n = 3
			KEY_KP_5: n = 4
			KEY_KP_6: n = 5
			KEY_KP_7: n = 6
			KEY_KP_8: n = 7
			KEY_KP_9: n = 8
			
	if n >= 0 and n < _actions.size():
		get_viewport().set_input_as_handled()
		_on_action_pressed(n)


func _format_data(data: Dictionary) -> String:
	if data.is_empty():
		return ""
	var parts: PackedStringArray = []
	for key: String in data:
		var key_label: String = key
		match key:
			"to":     key_label = "→"
			"target": key_label = "obj"
			"index":  key_label = "#"
			"floor":  key_label = "piso"
			"amount": key_label = "x"
		parts.append("%s %s" % [key_label, str(data[key])])
	return "[color=#666](%s)[/color]" % "  ".join(parts)

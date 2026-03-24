# scripts/ActionPanel.gd
# Muestra acciones legales como botones generados dinámicamente.
# Cuando el jugador hace click, llama a GameClient.send_action().
extends ScrollContainer

@onready var title_label: Label = $VBox/TitleLabel
@onready var buttons_container: VBoxContainer = $VBox/ButtonsContainer

var _actor: String = ""
var _actions: Array = []


func show_actions(actor: String, actions: Array) -> void:
	_actor = actor
	_actions = actions
	title_label.text = "Acciones de %s  (%d disponibles)" % [actor, actions.size()]
	_rebuild_buttons()


func clear_actions() -> void:
	_actor = ""
	_actions = []
	title_label.text = "Sin acciones disponibles"
	_rebuild_buttons()


func _rebuild_buttons() -> void:
	for child in buttons_container.get_children():
		child.queue_free()

	for i: int in _actions.size():
		var action: Dictionary = _actions[i]
		var btn := Button.new()
		btn.text = _format_action(action)
		btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
		btn.pressed.connect(_on_action_pressed.bind(i))
		buttons_container.add_child(btn)


func _on_action_pressed(index: int) -> void:
	if index >= _actions.size():
		return
	var action: Dictionary = _actions[index]
	var actor := _actor
	# Limpiar antes de enviar para evitar doble-click
	clear_actions()
	GameClient.send_action(
		actor,
		action.get("type", ""),
		action.get("data", {}),
	)


func _format_action(action: Dictionary) -> String:
	var t: String = action.get("type", "?")
	var data: Dictionary = action.get("data", {})
	if data.is_empty():
		return t
	var parts: PackedStringArray = []
	for key: String in data:
		parts.append("%s=%s" % [key, str(data[key])])
	return "%s  { %s }" % [t, "  ".join(parts)]

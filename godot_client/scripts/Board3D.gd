# Board3D.gd — Vista 3D isométrica del tablero CARCOSA
# Conecta al GameClient autoload y posiciona castillos/tokens en la grilla 3D
extends Node3D

# --- Layout constants ---
const FLOORS := 3
const ROOM_SPACING := 3.0
const FLOOR_HEIGHT := 3.5

# Room layout within a floor (XZ plane)
# R1=front-left, R2=front-right, P=center corridor, R3=back-left, R4=back-right
const ROOM_OFFSETS := {
	"R1": Vector3(-ROOM_SPACING, 0.0, ROOM_SPACING),
	"R2": Vector3(ROOM_SPACING, 0.0, ROOM_SPACING),
	"P":  Vector3(0.0, 0.0, 0.0),
	"R3": Vector3(-ROOM_SPACING, 0.0, -ROOM_SPACING),
	"R4": Vector3(ROOM_SPACING, 0.0, -ROOM_SPACING),
}

# Player colors for tokens
const PLAYER_COLORS := {
	"P1": Color(0.39, 0.71, 0.96),  # blue
	"P2": Color(0.50, 0.78, 0.52),  # green
	"P3": Color(1.0, 0.72, 0.30),   # orange
	"P4": Color(0.94, 0.38, 0.57),  # pink
}

# --- Node references ---
@onready var camera: Camera3D = $IsometricCamera
@onready var sun: DirectionalLight3D = $Sun
@onready var floors_container: Node3D = $Floors

# --- State ---
var room_nodes: Dictionary = {}  # "F1_R1" -> Node3D (room root)
var player_tokens: Dictionary = {}  # "P1" -> MeshInstance3D
var monster_tokens: Dictionary = {}  # monster_id -> MeshInstance3D
var king_token: MeshInstance3D = null
var room_scene: PackedScene = null
var _screenshot_taken: bool = false

# --- Materials ---
var _room_mat_default: StandardMaterial3D
var _room_mat_active: StandardMaterial3D

func _ready() -> void:
	# Load the castle GLB
	room_scene = load("res://assets/city_capital.glb")
	if not room_scene:
		push_error("Board3D: Could not load city_capital.glb")
		return
	
	# Create materials
	_room_mat_default = StandardMaterial3D.new()
	_room_mat_default.albedo_color = Color(0.45, 0.43, 0.40)
	_room_mat_default.roughness = 0.8
	
	_room_mat_active = StandardMaterial3D.new()
	_room_mat_active.albedo_color = Color(0.85, 0.65, 0.20)
	_room_mat_active.emission_enabled = true
	_room_mat_active.emission = Color(0.6, 0.4, 0.1)
	_room_mat_active.emission_energy_multiplier = 0.5
	_room_mat_active.roughness = 0.6
	
	_build_board()
	
	# Connect to GameClient autoload if available
	if has_node("/root/GameClient"):
		var gc = get_node("/root/GameClient")
		gc.state_updated.connect(_on_state_updated)
		if not gc.current_state.is_empty():
			_on_state_updated(gc.current_state)
		else:
			# GameClient exists but no game — start one
			_fetch_demo_state()
	else:
		# Standalone mode: fetch state directly via HTTP
		_fetch_demo_state()


func _build_board() -> void:
	for f in range(1, FLOORS + 1):
		var floor_y := (f - 1) * FLOOR_HEIGHT
		var floor_node := Node3D.new()
		floor_node.name = "Floor_%d" % f
		floors_container.add_child(floor_node)
		
		for room_id in ["R1", "R2", "P", "R3", "R4"]:
			var full_id := "F%d_%s" % [f, room_id]
			var room_inst := room_scene.instantiate()
			room_inst.name = full_id
			floor_node.add_child(room_inst)
			
			var offset: Vector3 = ROOM_OFFSETS[room_id]
			room_inst.position = Vector3(offset.x, floor_y, offset.z)
			room_inst.scale = Vector3(0.8, 0.8, 0.8)
			
			room_nodes[full_id] = room_inst
	
	# Position camera for isometric view of all 3 floors
	camera.position = Vector3(12.0, 14.0, 12.0)
	camera.rotation_degrees = Vector3(-35.264, 45.0, 0.0)
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 16.0


func _on_state_updated(state: Dictionary) -> void:
	_clear_tokens()
	
	var players: Dictionary = state.get("players", {})
	var active: String = state.get("active_actor", "")
	var monsters: Array = state.get("monsters", [])
	var king_floor: int = state.get("king_floor", 0)
	var _stairs: Dictionary = state.get("stairs", {})
	
	# Place player tokens
	for pid in players:
		var p: Dictionary = players[pid]
		if p.get("sanity", 0) <= 0:
			continue
		var room_id := str(p.get("room", ""))
		if room_nodes.has(room_id):
			var token := _create_player_token(pid, p, pid == active)
			var room_node: Node3D = room_nodes[room_id]
			room_node.add_child(token)
			token.position = Vector3(0, 1.5, 0)
			player_tokens[pid] = token
	
	# Place monster tokens
	for m in monsters:
		var room_id := str(m.get("room", ""))
		if room_nodes.has(room_id):
			var mid := str(m.get("id", "?"))
			var token := _create_monster_token(mid)
			var room_node: Node3D = room_nodes[room_id]
			room_node.add_child(token)
			token.position = Vector3(0.5, 1.5, 0.5)
			monster_tokens[mid] = token
	
	# Place king token
	if king_floor > 0:
		var corridor_id := "F%d_P" % king_floor
		if room_nodes.has(corridor_id):
			king_token = _create_king_token()
			room_nodes[corridor_id].add_child(king_token)
			king_token.position = Vector3(0, 2.0, 0)
	
	# Highlight active player's room
	_highlight_active_room(active, players)
	
	# Screenshot on first state update
	if not _screenshot_taken:
		_screenshot_taken = true
		_take_screenshot()


func _create_player_token(pid: String, p: Dictionary, is_active: bool) -> MeshInstance3D:
	var sphere := SphereMesh.new()
	sphere.radius = 0.35
	sphere.height = 0.7
	
	var mat := StandardMaterial3D.new()
	var color: Color = PLAYER_COLORS.get(pid, Color.WHITE)
	mat.albedo_color = color
	mat.emission_enabled = is_active
	mat.emission = color
	mat.emission_energy_multiplier = 0.8 if is_active else 0.0
	mat.roughness = 0.4
	
	var mesh_inst := MeshInstance3D.new()
	mesh_inst.mesh = sphere
	mesh_inst.material_override = mat
	mesh_inst.name = "Token_%s" % pid
	
	# Add a small label above
	var label := Label3D.new()
	label.text = "%s:%d" % [pid, p.get("sanity", 0)]
	label.font_size = 36
	label.position = Vector3(0, 0.6, 0)
	label.modulate = color
	mesh_inst.add_child(label)
	
	return mesh_inst


func _create_monster_token(mid: String) -> MeshInstance3D:
	var box := BoxMesh.new()
	box.size = Vector3(0.4, 0.4, 0.4)
	
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.9, 0.2, 0.2)
	mat.emission_enabled = true
	mat.emission = Color(0.5, 0.05, 0.05)
	mat.emission_energy_multiplier = 0.4
	mat.roughness = 0.5
	
	var mesh_inst := MeshInstance3D.new()
	mesh_inst.mesh = box
	mesh_inst.material_override = mat
	mesh_inst.name = "Monster_%s" % mid
	
	var label := Label3D.new()
	label.text = "M"
	label.font_size = 28
	label.position = Vector3(0, 0.4, 0)
	label.modulate = Color.RED
	mesh_inst.add_child(label)
	
	return mesh_inst


func _create_king_token() -> MeshInstance3D:
	var sphere := SphereMesh.new()
	sphere.radius = 0.5
	sphere.height = 1.0
	
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.8, 0.6, 1.0)
	mat.emission_enabled = true
	mat.emission = Color(0.5, 0.3, 0.7)
	mat.emission_energy_multiplier = 0.6
	mat.metallic = 0.3
	mat.roughness = 0.3
	
	var mesh_inst := MeshInstance3D.new()
	mesh_inst.mesh = sphere
	mesh_inst.material_override = mat
	mesh_inst.name = "King"
	
	var label := Label3D.new()
	label.text = "KING"
	label.font_size = 32
	label.position = Vector3(0, 0.8, 0)
	label.modulate = Color(0.8, 0.6, 1.0)
	mesh_inst.add_child(label)
	
	return mesh_inst


func _highlight_active_room(active: String, players: Dictionary) -> void:
	# Reset all rooms to default material
	for room_id in room_nodes:
		_apply_material_to_room(room_nodes[room_id], _room_mat_default)
	
	# Highlight the room where the active player is
	if active in players:
		var room_id := str(players[active].get("room", ""))
		if room_nodes.has(room_id):
			_apply_material_to_room(room_nodes[room_id], _room_mat_active)


func _apply_material_to_room(room_node: Node3D, mat: Material) -> void:
	# Apply material to all MeshInstance3D children
	for child in room_node.get_children():
		if child is MeshInstance3D:
			child.material_override = mat
		# Also check grandchildren (GLB hierarchy)
		for grandchild in child.get_children():
			if grandchild is MeshInstance3D:
				grandchild.material_override = mat


func _clear_tokens() -> void:
	for token in player_tokens.values():
		if is_instance_valid(token):
			token.queue_free()
	player_tokens.clear()
	
	for token in monster_tokens.values():
		if is_instance_valid(token):
			token.queue_free()
	monster_tokens.clear()
	
	if king_token and is_instance_valid(king_token):
		king_token.queue_free()
	king_token = null


func _take_screenshot() -> void:
	await get_tree().create_timer(1.0).timeout
	RenderingServer.force_draw()
	var vp := get_viewport()
	var img := vp.get_texture().get_image()
	if img and img.get_width() > 2:
		var err := img.save_png("res://assets/board3d_live.png")
		print("Board3D: Screenshot ", img.get_width(), "x", img.get_height(), " saved=", err == OK)
	else:
		print("Board3D: Viewport too small or no image")


func _fetch_demo_state() -> void:
	# Standalone: start a game via HTTP and display it
	var http := HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_demo_state_received)
	var body := JSON.stringify({"seed": 42, "players": ["P1", "P2", "P3", "P4"]})
	var headers := PackedStringArray(["Content-Type: application/json"])
	var err := http.request("http://127.0.0.1:8765/start", headers, HTTPClient.METHOD_POST, body)
	if err != OK:
		print("Board3D: Failed to start demo game")
		http.queue_free()


func _on_demo_state_received(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if code < 200 or code >= 300:
		print("Board3D: HTTP error ", code)
		return
	var json := JSON.new()
	if json.parse(body.get_string_from_utf8()) != OK:
		print("Board3D: JSON parse error")
		return
	var data: Dictionary = json.data
	var state: Dictionary = data.get("state", {})
	if not state.is_empty():
		_on_state_updated(state)
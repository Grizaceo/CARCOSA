from engine.board import canonical_room_ids, is_corridor, rotate_boxes, SUSHI_CYCLE


def test_sushi_cycle_is_bijection():
    assert len(SUSHI_CYCLE) == 12
    assert len(set(SUSHI_CYCLE.keys())) == 12
    assert len(set(SUSHI_CYCLE.values())) == 12


def test_rotate_boxes_one_step():
    box_at_room = {rid: f"box_{rid}" for rid in canonical_room_ids()}
    rotated = rotate_boxes(box_at_room)

    for src, dst in SUSHI_CYCLE.items():
        assert rotated[dst] == box_at_room[src]


def test_rotate_boxes_full_cycle_returns_to_start():
    box_at_room = {rid: f"box_{rid}" for rid in canonical_room_ids()}
    rotated = box_at_room
    for _ in range(12):
        rotated = rotate_boxes(rotated)
    assert rotated == box_at_room


def test_box_mapping_has_no_corridors():
    box_at_room = {rid: f"box_{rid}" for rid in canonical_room_ids()}
    assert all(not is_corridor(rid) for rid in box_at_room.keys())

    rotated = rotate_boxes(box_at_room)
    assert all(not is_corridor(rid) for rid in rotated.keys())

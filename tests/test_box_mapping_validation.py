import pytest

from engine.board import canonical_room_ids, corridor_id, rotate_boxes


def _full_mapping():
    return {rid: f"box_{rid}" for rid in canonical_room_ids()}


def test_rotate_boxes_rejects_incomplete_mapping():
    mapping = _full_mapping()
    mapping.pop(next(iter(mapping)))
    with pytest.raises(ValueError):
        rotate_boxes(mapping)


def test_rotate_boxes_rejects_duplicate_box_ids():
    mapping = _full_mapping()
    keys = list(mapping.keys())
    mapping[keys[1]] = mapping[keys[0]]
    with pytest.raises(ValueError):
        rotate_boxes(mapping)


def test_rotate_boxes_rejects_corridor_keys():
    mapping = _full_mapping()
    mapping[corridor_id(1)] = "box_corridor"
    with pytest.raises(ValueError):
        rotate_boxes(mapping)

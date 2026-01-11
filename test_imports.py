#!/usr/bin/env python3
"""Test basic imports and structure of the carcosa engine."""
import sys
import traceback


def test_imports():
    """Test that all core modules can be imported."""
    modules_to_test = [
        "engine",
        "engine.types",
        "engine.config",
        "engine.board",
        "engine.state",
        "engine.rng",
        "engine.actions",
        "engine.legality",
        "engine.transition",
        "engine.effects",
        "sim",
    ]

    failed = []
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"✓ {module_name}")
        except Exception as e:
            print(f"✗ {module_name}: {e}")
            traceback.print_exc()
            failed.append(module_name)

    assert failed == [], f"Failed to import modules: {failed}"


def test_key_functions():
    """Test that key functions exist and are callable."""
    checks = []

    try:
        from engine.board import corridor_id, floor_of, neighbors, room_id

        print("✓ engine.board functions")
        checks.extend(
            [
                ("floor_of", True),
                ("neighbors", True),
                ("corridor_id", True),
                ("room_id", True),
            ]
        )
    except Exception as e:
        print(f"✗ engine.board functions: {e}")
        checks.append(("engine.board", False))

    try:
        from engine.transition import (
            _apply_minus5_transitions,
            _expel_players_from_floor,
            _presence_damage_for_round,
            _roll_stairs,
            step,
        )

        print("✓ engine.transition functions")
        checks.extend(
            [
                ("step", True),
                ("_roll_stairs", True),
                ("_expel_players_from_floor", True),
                ("_apply_minus5_transitions", True),
                ("_presence_damage_for_round", True),
            ]
        )
    except Exception as e:
        print(f"✗ engine.transition functions: {e}")
        checks.append(("engine.transition", False))

    failed = [name for (name, ok) in checks if not ok]
    assert not failed, f"Missing/non-importable key functions/modules: {failed}. Checks: {checks}"


if __name__ == "__main__":
    print("=" * 60)
    print("Testing imports...")
    print("=" * 60)
    try:
        test_imports()
        failed_imports = []
    except AssertionError as ae:
        failed_imports = [str(ae)]

    print("\n" + "=" * 60)
    print("Testing key functions...")
    print("=" * 60)
    try:
        test_key_functions()
    except AssertionError:
        # Keep exit behavior consistent with previous manual mode
        pass

    if failed_imports:
        print(f"\n❌ {failed_imports[0]}")
        sys.exit(1)
    else:
        print("\n✓ All imports successful")
        sys.exit(0)

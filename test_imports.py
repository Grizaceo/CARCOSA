#!/usr/bin/env python3
"""Test basic imports and structure of the carcosa engine."""
import sys
import traceback

def test_imports():
    """Test that all core modules can be imported."""
    modules_to_test = [
        'engine',
        'engine.types',
        'engine.config',
        'engine.board',
        'engine.state',
        'engine.rng',
        'engine.actions',
        'engine.legality',
        'engine.transition',
        'engine.effects',
        'sim',
    ]
    
    failed = []
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f'✓ {module_name}')
        except Exception as e:
            print(f'✗ {module_name}: {e}')
            traceback.print_exc()
            failed.append(module_name)
    
    return failed

def test_key_functions():
    """Test that key functions exist and are callable."""
    tests = []
    
    try:
        from engine.board import floor_of, neighbors, corridor_id, room_id
        print('✓ engine.board functions')
        tests.append(('floor_of', True))
        tests.append(('neighbors', True))
        tests.append(('corridor_id', True))
        tests.append(('room_id', True))
    except Exception as e:
        print(f'✗ engine.board functions: {e}')
        tests.append(('engine.board', False))
    
    try:
        from engine.transition import step, _roll_stairs, _expel_players_from_floor, _apply_minus5_transitions, _presence_damage_for_round
        print('✓ engine.transition functions')
        tests.append(('step', True))
        tests.append(('_roll_stairs', True))
        tests.append(('_expel_players_from_floor', True))
        tests.append(('_apply_minus5_transitions', True))
        tests.append(('_presence_damage_for_round', True))
    except Exception as e:
        print(f'✗ engine.transition functions: {e}')
        tests.append(('engine.transition', False))
    
    return tests

if __name__ == '__main__':
    print('=' * 60)
    print('Testing imports...')
    print('=' * 60)
    failed_imports = test_imports()
    
    print('\n' + '=' * 60)
    print('Testing key functions...')
    print('=' * 60)
    test_key_functions()
    
    if failed_imports:
        print(f'\n❌ Failed to import {len(failed_imports)} modules')
        sys.exit(1)
    else:
        print(f'\n✓ All imports successful')
        sys.exit(0)

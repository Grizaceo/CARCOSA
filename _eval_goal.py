from sim.runner import run_episode

wins = 0
for s in range(1, 51):
    state = run_episode(seed=s, max_steps=1000, policy_name='GOAL', out_path='/dev/null')
    if state.outcome == 'WIN':
        wins += 1

print(f'GOAL win_rate: {wins}/50 = {wins/50:.1%}')

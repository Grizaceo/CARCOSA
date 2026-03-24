"""Analyze key collection stats from recent run summaries to identify bottleneck."""
import sys, json, pathlib, glob

sys.path.insert(0, '/home/gris/.openclaw/workspace/repos/CARCOSA')

runs_dir = pathlib.Path('/home/gris/.openclaw/workspace/repos/CARCOSA/runs')
summaries = sorted(runs_dir.glob('**/*_summary.json'))[-80:]  # Last 80 runs

wins = []
lose_sanity = []
lose_keys = []

for sf in summaries:
    try:
        data = json.loads(sf.read_text())
    except Exception:
        continue
    outcome = data.get('outcome', '')
    keys_hand = data.get('keys_in_hand', 0)
    keys_dest = data.get('keys_destroyed_total', 0)
    rnd = data.get('round', 0)
    sac = data.get('sacrifice', {})
    sac_opps = sac.get('opportunities', 0)
    sac_count = sac.get('sacrifice', 0)
    accept_count = sac.get('accept', 0)
    
    entry = {
        'outcome': outcome, 'round': rnd, 'keys_hand': keys_hand,
        'keys_dest': keys_dest, 'sac_opp': sac_opps, 'sac': sac_count, 'accept': accept_count
    }
    
    if 'WIN' in str(outcome):
        wins.append(entry)
    elif 'MINUS5' in str(outcome) or 'ALL' in str(outcome):
        lose_sanity.append(entry)
    elif 'KEYS' in str(outcome) or 'DESTROY' in str(outcome):
        lose_keys.append(entry)

def avg(lst, key):
    vals = [x[key] for x in lst if x[key] is not None]
    return sum(vals) / len(vals) if vals else 0

print(f"=== KEY COLLECTION ANALYSIS ({len(summaries)} recent runs) ===\n")

print(f"WINS ({len(wins)} games):")
if wins:
    print(f"  avg round: {avg(wins, 'round'):.1f}")
    print(f"  avg keys_in_hand at end: {avg(wins, 'keys_hand'):.1f}")
    print(f"  avg keys_destroyed: {avg(wins, 'keys_dest'):.1f}")
    print(f"  avg sacrifice_opps: {avg(wins, 'sac_opp'):.1f}")

print(f"\nLOSE_ALL_MINUS5 ({len(lose_sanity)} games):")
if lose_sanity:
    print(f"  avg round: {avg(lose_sanity, 'round'):.1f}")
    print(f"  avg keys_in_hand at end: {avg(lose_sanity, 'keys_hand'):.1f}")
    print(f"  avg keys_destroyed: {avg(lose_sanity, 'keys_dest'):.1f}")
    print(f"  avg sacrifice_opps: {avg(lose_sanity, 'sac_opp'):.1f}")
    dist = {}
    for e in lose_sanity:
        k = e['keys_hand']
        dist[k] = dist.get(k, 0) + 1
    print(f"  keys_in_hand distribution: {dict(sorted(dist.items()))}")

print(f"\nLOSE_KEYS_DESTROYED ({len(lose_keys)} games):")
if lose_keys:
    print(f"  avg round: {avg(lose_keys, 'round'):.1f}")
    print(f"  avg keys_in_hand at end: {avg(lose_keys, 'keys_hand'):.1f}")
    print(f"  avg keys_destroyed: {avg(lose_keys, 'keys_dest'):.1f}")
    print(f"  avg sacrifice_opps: {avg(lose_keys, 'sac_opp'):.1f}")
    dist = {}
    for e in lose_keys:
        k = e['keys_hand']
        dist[k] = dist.get(k, 0) + 1
    print(f"  keys_in_hand distribution: {dict(sorted(dist.items()))}")

print("\n=== KEY INSIGHT ===")
if lose_sanity:
    near_miss_sanity = [e for e in lose_sanity if e['keys_hand'] >= 3]
    print(f"LOSE_SANITY near-misses (3+ keys found): {len(near_miss_sanity)}/{len(lose_sanity)} = {100*len(near_miss_sanity)/max(1,len(lose_sanity)):.0f}%")
if lose_keys:
    near_miss_keys = [e for e in lose_keys if e['keys_hand'] >= 3]
    print(f"LOSE_KEYS near-misses (3+ keys in hand): {len(near_miss_keys)}/{len(lose_keys)} = {100*len(near_miss_keys)/max(1,len(lose_keys)):.0f}%")

"""Verify dataset output structure."""
import json, pathlib

base = pathlib.Path('/home/gris/.openclaw/workspace/repos/CARCOSA/datasets/test_v1')

print("Files generated:")
for f in sorted(base.iterdir()):
    print(f"  {f.name}: {f.stat().st_size:,} bytes")

print()
summary = json.loads((base / 'seed000001_summary.json').read_text())
print("Summary keys:", list(summary.keys()))
print("Steps:", summary['steps'], "| Outcome:", summary['outcome'], "| Round:", summary['round'])

lines = (base / 'seed000001.jsonl').read_text().splitlines()
print(f"\nTransitions count: {len(lines)}")
first = json.loads(lines[0])
print("Transition keys:", list(first.keys()))
if 'actor' in first:
    print("Example action:", first.get('actor'), first.get('action', {}).get('type'))

index = json.loads((base / 'dataset_index.json').read_text())
print(f"\nDataset index: {index['episodes_ok']} episodes, {index['winrate']:.1%} winrate, {index['seconds_per_episode']:.2f}s/ep")

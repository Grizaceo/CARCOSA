.PHONY: build-deps build-app build-gpu run-dev run-gpu gen-bc-data train-bc test pytest clean

build-deps:
	docker build -f Dockerfile.deps -t carcosa:deps .

build-app:
	docker build -f Dockerfile.app -t carcosa:app .

build-gpu:
	docker build -f Dockerfile.gpu -t carcosa:gpu .

run-dev:
	docker run --rm -it -v ${PWD}:/app -w /app carcosa:app python -m sim.runner --seed 1 --max-steps 400

run-gpu:
	docker run --gpus all --rm -it -v ${PWD}:/app -w /app carcosa:gpu python -m sim.runner --seed 1 --max-steps 400

gen-bc-data:
	docker run --rm -v ${PWD}:/app -w /app carcosa:app python tools/ai_ready_export.py --input runs/*.jsonl --mode bc --output data/bc_training.csv

train-bc:
	docker run --rm -v ${PWD}:/app -w /app carcosa:app python train/train_bc.py --data data/bc_training.csv --epochs 1 --batch-size 32 --device cpu --save-dir models_dev --log-dir runs/dev

test:
	docker run --rm -v ${PWD}:/app -w /app carcosa:app pytest -q

pytest:
	$(MAKE) test

clean:
	rm -rf ./.buildx-cache

# ── HALI: motor de representación 2.5D ──────────────────────────────────────
# Server de juego local (HALI queda en http://127.0.0.1:8765/static/hali/)
hali-serve:
	python3 -m uvicorn sim.game_server:app --host 127.0.0.1 --port 8765

# Build autocontenido (un solo HTML, funciona desde file://)
hali-dist:
	python3 tools/build_hali_standalone.py --replay web/hali/replays/goal_s4_win.json -o dist/hali_standalone.html

# Regenerar el replay de demo desde el simulador headless
hali-demo-replay:
	python3 -m sim.runner --policy GOAL --seed 4 --max-steps 1500 --out runs/hali_demo/seed4.jsonl
	python3 tools/distill_replay.py runs/hali_demo/seed4.jsonl -o web/hali/replays/goal_s4_win.json

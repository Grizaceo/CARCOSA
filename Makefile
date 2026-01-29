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

param(
    [string]$Action = "help"
)

switch ($Action) {
    "build-deps" { docker build -f Dockerfile.deps -t carcosa:deps . }
    "build-app"  { docker build -f Dockerfile.app -t carcosa:app . }
    "build-gpu"  { docker build -f Dockerfile.gpu -t carcosa:gpu . }
    "run-dev"    { docker run --rm -it -v ${PWD}:/app -w /app carcosa:app python -m sim.runner --seed 1 --max-steps 400 }
    "gen-bc"     { docker run --rm -v ${PWD}:/app -w /app carcosa:app python tools/ai_ready_export.py --input runs/*.jsonl --mode bc --output data/bc_training.csv }
    "train-bc"   { docker run --rm -v ${PWD}:/app -w /app carcosa:app python train/train_bc.py --data data/bc_training.csv --epochs 1 --batch-size 32 --device cpu --save-dir models_dev --log-dir runs/dev }
    "help"       { Write-Output "Usage: .\run.ps1 <action> ; actions: build-deps, build-app, build-gpu, run-dev, gen-bc, train-bc" }
    default       { Write-Output "Unknown action. Run .\run.ps1 help" }
}

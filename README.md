
# Cognitive Agent Network (Hybrid PoC)

Minimal reproducible prototype for the AGI‑2025 paper.

```bash
# local run with configuration file
python runner.py --config config_a.json --logdir logs
```

## Docker
```bash
# Build Docker image
docker build -t can_poc .

# Run the simulation
docker run --rm can_poc

# Run tests
docker run --rm can_poc test
```

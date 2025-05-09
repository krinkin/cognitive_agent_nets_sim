
# Cognitive Agent Network (Hybrid PoC)

Minimal reproducible prototype for the AGI‑2025 paper.

```bash
# local run (3 sessions, 30 s each)
python runner.py --sessions 3 --duration 30 --logdir logs
```

## Docker
```bash
docker build -t can_poc .
docker run --rm can_poc
```

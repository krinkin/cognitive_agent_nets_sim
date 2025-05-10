# runner.py  ────────────────────────────────────────────────────────────────
import argparse, asyncio, json, os, time
from agents import (
    GeneratorAgent,
    CheckerAgent,
    StrategistAgent,
    SyntheticHumanAgent,
)

# ────────────────────────── Buffered logger ────────────────────────────── #
def make_logger(session: str, logdir: str, batch: int = 500):
    os.makedirs(logdir, exist_ok=True)
    path = os.path.join(logdir, f"{session}.jsonl")
    fh   = open(path, "w", buffering=1024 * 1024)       # 1 MiB buffer

    buf, closed = [], False

    def flush():
        if buf:
            fh.writelines(buf)
            buf.clear()

    def log(event: str, **data):
        nonlocal closed
        if closed:               # файл уже закрыт → игнорируем запись
            return
        buf.append(
            json.dumps(
                {"t": time.time(),
                 "event": event,
                 "session": session,
                 **data}
            ) + "\n"
        )
        if len(buf) >= batch:
            flush()

    def close():
        nonlocal closed
        if not closed:
            flush()
            fh.close()
            closed = True

    return log, close, path

# ───────────────────────────── One session ─────────────────────────────── #
async def run_once(config: dict, name: str, logdir: str, include_human: bool):
    duration              = config["duration"]
    log, close, log_path  = make_logger(name, logdir)
    log("start")                               # точка старта сессии

    done_event            = asyncio.Event()
    agents                = []

    # ── Broadcaster ──
    def broadcast(msg: str):
        log("msg", text=msg)
        for ag in agents:
            ag.inbox.put_nowait(msg)

    # ── Generator ──
    g = config["generator"]
    agents.append(
        GeneratorAgent(
            preferred_digit=g["preferred_digit"],
            force_semantic=g["force_semantic"],
            buffer_size=g["buffer_size"],
            name="G",
            broadcast=broadcast,
            done_event=done_event,
        )
    )

    # ── Checker ──
    agents.append(
        CheckerAgent(name="C", broadcast=broadcast, done_event=done_event)
    )

    # ── Strategist ──
    s = config["strategist"]
    agents.append(
        StrategistAgent(
            threshold=s["threshold"],
            include_human=include_human,
            human_interval=s["human_interval"],
            top_k=s["top_k"],
            name="S",
            broadcast=broadcast,
            done_event=done_event,
        )
    )

    # ── Synthetic Human (only in Hybrid) ──
    if include_human:
        h = config["synthetic_human"]
        agents.append(
            SyntheticHumanAgent(
                lifetime=h["lifetime"],
                name="H",
                broadcast=broadcast,
                done_event=done_event,
            )
        )

    tasks = [asyncio.create_task(a.run()) for a in agents]

    # ── Run until success or timeout ──
    try:
        await asyncio.wait_for(done_event.wait(), timeout=duration)
    except asyncio.TimeoutError:
        pass
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        close()                                  # flush + close журнал

    return log_path

# ───────────────────────────── Aggregation ─────────────────────────────── #
def analyse(paths):
    succ, deltas, bytes_total = 0, [], []
    for p in paths:
        t0 = None
        with open(p) as f:
            for line in f:
                ev = json.loads(line)
                if ev["event"] == "start":
                    t0 = ev["t"]
                elif ev["event"] == "msg":
                    txt = ev["text"]
                    if txt.startswith("CONFIRM") and t0 is not None:
                        succ += 1
                        deltas.append(ev["t"] - t0)
                    bytes_total.append(len(txt))

    S = succ / len(paths)
    T = None if not deltas else sum(deltas) / len(deltas)
    B = sum(bytes_total) / len(paths)
    return S, T, B

# ────────────────────────────── CLI driver ─────────────────────────────── #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="JSON config file")
    ap.add_argument("--logdir", required=True, help="Directory for logs")
    args = ap.parse_args()

    with open(args.config) as f:
        cfg = json.load(f)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Baseline (без человека)
    paths_a = [
        loop.run_until_complete(
            run_once(cfg, f"baseline_{i}", args.logdir, include_human=False)
        )
        for i in range(cfg["sessions"])
    ]

    # Hybrid (с Synthetic-Human)
    paths_b = [
        loop.run_until_complete(
            run_once(cfg, f"hybrid_{i}", args.logdir, include_human=True)
        )
        for i in range(cfg["sessions"])
    ]

    Sa, Ta, Ba = analyse(paths_a)
    Sb, Tb, Bb = analyse(paths_b)

    print(f"Baseline  success: {Sa:.3f}")
    print(f"Hybrid    success: {Sb:.3f}")
    print(f"Baseline  T_succ : {Ta}")
    print(f"Hybrid    T_succ : {Tb}")
    print(f"Baseline  bytes  : {Ba}")
    print(f"Hybrid    bytes  : {Bb}")

if __name__ == "__main__":
    main()
# ───────────────────────────────────────────────────────────────────────────

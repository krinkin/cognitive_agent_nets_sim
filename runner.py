# runner.py  ────────────────────────────────────────────────────────────────
import argparse, asyncio, json, os, time, datetime
from tqdm import tqdm
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
    start_time = time.time()
    pbar = tqdm(total=duration, desc=f"Simulation {name}", unit="sec", leave=False)
    try:
        # We'll update progress bar every 0.1 seconds
        while not done_event.is_set() and (time.time() - start_time) < duration:
            await asyncio.sleep(0.1)
            elapsed = min(time.time() - start_time, duration)
            pbar.n = elapsed
            pbar.refresh()
            if done_event.is_set():
                pbar.n = duration
                pbar.refresh()
                break
    finally:
        pbar.close()
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

    start_time = datetime.datetime.now()
    config_name = os.path.basename(args.config).replace(".json", "")
    print(f"\nStarting simulation with config '{config_name}' at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    with open(args.config) as f:
        cfg = json.load(f)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Ensure sessions is defined in the config
    if "sessions" not in cfg:
        print("Warning: 'sessions' not defined in config, defaulting to 3")
        cfg["sessions"] = 3

    # Baseline (без человека)
    print("Running baseline simulations...")
    paths_a = []
    for i in tqdm(range(cfg["sessions"]), desc="Baseline", unit="session"):
        path = loop.run_until_complete(
            run_once(cfg, f"baseline_{i}", args.logdir, include_human=False)
        )
        paths_a.append(path)

    # Hybrid (с Synthetic-Human)
    print("Running hybrid simulations...")
    paths_b = []
    for i in tqdm(range(cfg["sessions"]), desc="Hybrid", unit="session"):
        path = loop.run_until_complete(
            run_once(cfg, f"hybrid_{i}", args.logdir, include_human=True)
        )
        paths_b.append(path)

    Sa, Ta, Ba = analyse(paths_a)
    Sb, Tb, Bb = analyse(paths_b)

    end_time = datetime.datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    print("\n" + "="*50)
    print(f"SIMULATION RESULTS (completed in {elapsed:.1f} seconds)")
    print("="*50)
    print(f"{'Metric':<15} | {'Baseline':<14} | {'Hybrid':<14}")
    print("-"*50)
    print(f"{'Success Rate':<15} | {Sa:.3f}{' '*10} | {Sb:.3f}{' '*10}")
    ta_str = f"{Ta:.2f} sec" if Ta is not None else "N/A"
    tb_str = f"{Tb:.2f} sec" if Tb is not None else "N/A"
    print(f"{'Time to Success':<15} | {ta_str:<14} | {tb_str:<14}")
    print(f"{'Bytes Exchanged':<15} | {Ba:.1f}{' '*10} | {Bb:.1f}{' '*10}")
    print("="*50)

if __name__ == "__main__":
    main()
# ───────────────────────────────────────────────────────────────────────────

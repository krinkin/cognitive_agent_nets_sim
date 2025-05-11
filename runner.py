# runner.py  ────────────────────────────────────────────────────────────────
import argparse, asyncio, json, os, time, datetime, multiprocessing, signal
from multiprocessing import Pool
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
        if closed:               # file is already closed → ignore write
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

# Initialize worker process to ignore keyboard interrupts
def init_worker():
    """Initialize worker process by making it ignore SIGINT signal."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)

# ───────────────────────────── One session ─────────────────────────────── #
async def run_once(config: dict, name: str, logdir: str, include_human: bool):
    duration              = config["duration"]
    log, close, log_path  = make_logger(name, logdir)
    log("start")                               # session start point

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
            pbar.n = round(elapsed, 2)  # Round to 2 decimal places for cleaner display
            pbar.refresh()
            if done_event.is_set():
                pbar.n = round(duration, 2)
                pbar.refresh()
                break
    finally:
        pbar.close()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        close()                                  # flush + close the log

    return log_path

# ────────────────── Run single simulation in a process ────────────────── #
def run_simulation(params):
    """
    Run a single simulation in a separate process.
    This function is called by the multiprocessing pool.
    """
    config, session_name, logdir, include_human = params

    # Create a new event loop for this process
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Run the simulation and return the log path
    log_path = loop.run_until_complete(
        run_once(config, session_name, logdir, include_human)
    )

    # Close the loop and return the log path
    loop.close()
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

# ─────────────────────── Run complete simulation set ─────────────────────── #
def run_simulations(config, logdir, parallel=False, processes=None):
    """
    Run a complete set of simulations (baseline and hybrid) with given config.
    Returns paths to logs for baseline and hybrid runs.
    
    Args:
        config: Configuration dictionary
        logdir: Directory to store logs
        parallel: Whether to run simulations in parallel
        processes: Number of processes to use (None = auto)
        
    Returns:
        (baseline_paths, hybrid_paths): Tuple of log paths
    """
    # Ensure sessions is defined in the config
    if "sessions" not in config:
        print("Warning: 'sessions' not defined in config, defaulting to 3")
        config["sessions"] = 3
    
    # Set up CPU count for parallel processing
    num_processes = processes if processes else multiprocessing.cpu_count()
    if parallel:
        print(f"Running simulations in parallel using {num_processes} processes")
    else:
        print("Running simulations in sequence (use --parallel for faster execution)")

    # Prepare parameters for baseline simulations
    baseline_params = [
        (config, f"baseline_{i}", logdir, False) 
        for i in range(config["sessions"])
    ]
    
    # Prepare parameters for hybrid simulations
    hybrid_params = [
        (config, f"hybrid_{i}", logdir, True) 
        for i in range(config["sessions"])
    ]

    # Run simulations
    if parallel:
        # Run in parallel using multiprocessing with proper SIGINT handling
        with Pool(processes=num_processes, initializer=init_worker) as pool:
            # Baseline (without human)
            print("Running baseline simulations...")
            paths_a = list(tqdm(
                pool.imap(run_simulation, baseline_params),
                total=config["sessions"],
                desc="Baseline",
                unit="session"
            ))
            
            # Hybrid (with Synthetic-Human)
            print("Running hybrid simulations...")
            paths_b = list(tqdm(
                pool.imap(run_simulation, hybrid_params),
                total=config["sessions"],
                desc="Hybrid",
                unit="session"
            ))
    else:
        # Run sequentially using a single event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Baseline (without human)
            print("Running baseline simulations...")
            paths_a = []
            for i in tqdm(range(config["sessions"]), desc="Baseline", unit="session"):
                path = loop.run_until_complete(
                    run_once(config, f"baseline_{i}", logdir, include_human=False)
                )
                paths_a.append(path)

            # Hybrid (with Synthetic-Human)
            print("Running hybrid simulations...")
            paths_b = []
            for i in tqdm(range(config["sessions"]), desc="Hybrid", unit="session"):
                path = loop.run_until_complete(
                    run_once(config, f"hybrid_{i}", logdir, include_human=True)
                )
                paths_b.append(path)
        finally:
            # Ensure the event loop is properly closed
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
            
    return paths_a, paths_b

# ─────────────────────── Display simulation results ────────────────────── #
def display_results(baseline_paths, hybrid_paths, start_time=None):
    """
    Analyze and display simulation results.
    
    Args:
        baseline_paths: Paths to baseline simulation logs
        hybrid_paths: Paths to hybrid simulation logs
        start_time: Optional start time for elapsed time calculation
    
    Returns:
        (Sa, Ta, Ba, Sb, Tb, Bb): Tuple of metrics
    """
    Sa, Ta, Ba = analyse(baseline_paths)
    Sb, Tb, Bb = analyse(hybrid_paths)
    
    # Calculate elapsed time if start_time provided
    elapsed = None
    if start_time:
        end_time = datetime.datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        elapsed_str = f" (completed in {elapsed:.1f} seconds)"
    else:
        elapsed_str = ""
    
    print("\n" + "="*50)
    print(f"SIMULATION RESULTS{elapsed_str}")
    print("="*50)
    print(f"{'Metric':<15} | {'Baseline':<14} | {'Hybrid':<14}")
    print("-"*50)
    print(f"{'Success Rate':<15} | {Sa:.3f}{' '*10} | {Sb:.3f}{' '*10}")
    ta_str = f"{Ta:.2f} sec" if Ta is not None else "N/A"
    tb_str = f"{Tb:.2f} sec" if Tb is not None else "N/A"
    print(f"{'Time to Success':<15} | {ta_str:<14} | {tb_str:<14}")
    print(f"{'Bytes Exchanged':<15} | {Ba:.1f}{' '*10} | {Bb:.1f}{' '*10}")
    print("="*50)
    
    return Sa, Ta, Ba, Sb, Tb, Bb

# ────────────────────────────── CLI driver ─────────────────────────────── #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="JSON config file")
    ap.add_argument("--logdir", required=True, help="Directory for logs")
    ap.add_argument("--parallel", action="store_true", help="Run simulations in parallel")
    ap.add_argument("--processes", type=int, default=None, 
                   help="Number of parallel processes (default: CPU count)")
    args = ap.parse_args()

    start_time = datetime.datetime.now()
    config_name = os.path.basename(args.config).replace(".json", "")
    print(f"\nStarting simulation with config '{config_name}' at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    with open(args.config) as f:
        cfg = json.load(f)

    # Run simulations
    baseline_paths, hybrid_paths = run_simulations(
        cfg, 
        args.logdir, 
        parallel=args.parallel, 
        processes=args.processes
    )
    
    # Display results
    display_results(baseline_paths, hybrid_paths, start_time)

if __name__ == "__main__":
    main()
# ───────────────────────────────────────────────────────────────────────────
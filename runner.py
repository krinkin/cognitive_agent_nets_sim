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
    mode = "Hybrid" if include_human else "Baseline"
    sim_id = name.split('_')[-1] if '_' in name else name

    pbar = tqdm(
        total=duration,
        desc=f"{mode} {sim_id}",
        unit="sec",
        leave=False,
        bar_format="{desc}: {percentage:3.1f}%|{bar}| {n:.1f}/{total:.1f}s [{elapsed}<{remaining}]"
    )

    success = False
    try:
        # We'll update progress bar every 0.1 seconds
        while not done_event.is_set() and (time.time() - start_time) < duration:
            await asyncio.sleep(0.1)
            elapsed = min(time.time() - start_time, duration)
            pbar.n = elapsed

            # Check if we've succeeded (done_event is set)
            if done_event.is_set():
                success = True
                pbar.set_postfix({"status": "✓ Success"})
                pbar.n = elapsed  # Show actual completion time
                pbar.refresh()
                break

            pbar.set_postfix({"status": "Running"})
            pbar.refresh()
    finally:
        if not success and pbar.n >= duration - 0.1:
            pbar.set_postfix({"status": "⚠ Timeout"})
            # Log timeout event with actual duration elapsed
            log("session_end", status="timeout", duration_actual=pbar.n)

        pbar.close()

        # Send EXIT message to all agents for graceful shutdown
        broadcast("EXIT")

        # Give agents a moment to process the EXIT message
        await asyncio.sleep(0.1)

        # Then cancel any remaining tasks
        for t in tasks:
            if not t.done():
                t.cancel()

        # Then wait for all tasks to complete with return_exceptions=True
        # to properly handle CancelledError exceptions
        await asyncio.gather(*tasks, return_exceptions=True)

        # Make sure all tasks are truly done
        for t in tasks:
            if not t.done():
                try:
                    # Set a timeout to prevent hanging if a task won't terminate
                    await asyncio.wait_for(t, timeout=0.5)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass

        # Now it's safe to close the log
        close()  # flush + close the log

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
def analyse(paths, config_duration):
    succ, deltas, bytes_total = 0, [], []
    session_durations = []
    p_rates_per_session = []
    c_rates_per_session = []
    r_can_per_session = []
    
    # Constants for RCAN calculation
    k = 1.0
    epsilon = 1e-6
    
    for p in paths:
        t0 = None
        session_successful = False
        session_duration_actual = config_duration  # Default duration if timeout
        session_bytes = []
        
        with open(p) as f:
            for line in f:
                ev = json.loads(line)
                if ev["event"] == "start":
                    t0 = ev["t"]
                elif ev["event"] == "msg":
                    txt = ev["text"]
                    if txt.startswith("CONFIRM") and t0 is not None:
                        succ += 1
                        session_successful = True
                        session_duration_actual = ev["t"] - t0
                        deltas.append(session_duration_actual)
                    session_bytes.append(len(txt))
                elif ev["event"] == "session_end" and ev.get("status") == "timeout" and t0 is not None:
                    session_duration_actual = ev["duration_actual"]
        
        # Store session duration
        session_durations.append(session_duration_actual)
        
        # Calculate P_rate (Progress Rate) for this session
        if session_successful:
            p_rate = 1.0 / session_duration_actual
        else:
            p_rate = 0.0
        p_rates_per_session.append(p_rate)
        
        # Calculate C_rate (Communication Cost Rate) for this session
        total_bytes = sum(session_bytes)
        bytes_total.append(total_bytes)
        c_rate = total_bytes / session_duration_actual if session_duration_actual > 0 else float('inf')
        c_rates_per_session.append(c_rate)
        
        # Calculate RCAN for this session
        r_can = k * (p_rate / (c_rate + epsilon))
        r_can_per_session.append(r_can)
    
    # Calculate average metrics
    S = succ / len(paths) if len(paths) > 0 else 0
    T = None if not deltas else sum(deltas) / len(deltas)
    B = sum(bytes_total) / len(paths) if len(paths) > 0 else 0
    
    # Calculate average P_rate, C_rate, and RCAN
    avg_P_rate = sum(p_rates_per_session) / len(paths) if len(paths) > 0 else 0
    avg_C_rate = sum(c_rates_per_session) / len(paths) if len(paths) > 0 else 0
    avg_R_CAN = sum(r_can_per_session) / len(paths) if len(paths) > 0 else 0
    
    return S, T, B, avg_P_rate, avg_C_rate, avg_R_CAN

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
                unit="session",
                bar_format="{desc}: {percentage:3.1f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
            ))

            # Hybrid (with Synthetic-Human)
            print("Running hybrid simulations...")
            paths_b = list(tqdm(
                pool.imap(run_simulation, hybrid_params),
                total=config["sessions"],
                desc="Hybrid",
                unit="session",
                bar_format="{desc}: {percentage:3.1f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
            ))
    else:
        # Run sequentially using a single event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Baseline (without human)
            print("Running baseline simulations...")
            paths_a = []
            for i in tqdm(range(config["sessions"]),
                       desc="Baseline",
                       unit="session",
                       bar_format="{desc}: {percentage:3.1f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"):
                path = loop.run_until_complete(
                    run_once(config, f"baseline_{i}", logdir, include_human=False)
                )
                paths_a.append(path)

            # Hybrid (with Synthetic-Human)
            print("Running hybrid simulations...")
            paths_b = []
            for i in tqdm(range(config["sessions"]),
                       desc="Hybrid",
                       unit="session",
                       bar_format="{desc}: {percentage:3.1f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"):
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
def display_results(baseline_paths, hybrid_paths, config_duration, start_time=None):
    """
    Analyze and display simulation results.
    
    Args:
        baseline_paths: Paths to baseline simulation logs
        hybrid_paths: Paths to hybrid simulation logs
        config_duration: Duration from configuration for timeout calculations
        start_time: Optional start time for elapsed time calculation
    
    Returns:
        (Sa, Ta, Ba, baseline_P_rate, baseline_C_rate, baseline_R_CAN, 
         Sb, Tb, Bb, hybrid_P_rate, hybrid_C_rate, hybrid_R_CAN): Tuple of all metrics
    """
    Sa, Ta, Ba, baseline_P_rate, baseline_C_rate, baseline_R_CAN = analyse(baseline_paths, config_duration)
    Sb, Tb, Bb, hybrid_P_rate, hybrid_C_rate, hybrid_R_CAN = analyse(hybrid_paths, config_duration)
    
    # Calculate elapsed time if start_time provided
    elapsed = None
    if start_time:
        end_time = datetime.datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        elapsed_str = f" (completed in {elapsed:.1f} seconds)"
    else:
        elapsed_str = ""
    
    print("\n" + "="*60)
    print(f"SIMULATION RESULTS{elapsed_str}")
    print("="*60)
    print(f"{'Metric':<20} | {'Baseline':<18} | {'Hybrid':<18}")
    print("-"*60)
    print(f"{'Success Rate (S)':<20} | {Sa:.3f}{' '*14} | {Sb:.3f}{' '*14}")
    ta_str = f"{Ta:.2f} sec" if Ta is not None else "N/A"
    tb_str = f"{Tb:.2f} sec" if Tb is not None else "N/A"
    print(f"{'Time to Success (T)':<20} | {ta_str:<18} | {tb_str:<18}")
    print(f"{'Bytes Exchanged (B)':<20} | {Ba:.1f}{' '*14} | {Bb:.1f}{' '*14}")
    print(f"{'Progress Rate (P̊)':<20} | {baseline_P_rate:.6f}{' '*8} | {hybrid_P_rate:.6f}{' '*8}")
    print(f"{'Comm Cost Rate (C̊)':<20} | {baseline_C_rate:.2f}{' '*14} | {hybrid_C_rate:.2f}{' '*14}")
    print(f"{'Resonance (R_CAN)':<20} | {baseline_R_CAN:.6f}{' '*8} | {hybrid_R_CAN:.6f}{' '*8}")
    print("="*60)
    
    return (Sa, Ta, Ba, baseline_P_rate, baseline_C_rate, baseline_R_CAN,
            Sb, Tb, Bb, hybrid_P_rate, hybrid_C_rate, hybrid_R_CAN)

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
    display_results(baseline_paths, hybrid_paths, cfg["duration"], start_time)

if __name__ == "__main__":
    main()
# ───────────────────────────────────────────────────────────────────────────
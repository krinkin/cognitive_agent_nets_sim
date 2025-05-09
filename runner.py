import asyncio
import json
import os
import time
import argparse
from pathlib import Path

from agents import GeneratorAgent, CheckerAgent, StrategistAgent
from synthetic_human import SyntheticHuman
from constraints import sample_constraints


# ---------------------------------------------------------------------
def load_config(path):
    return json.load(open(path)) if Path(path).exists() else {}


def make_logger(session, logdir):
    os.makedirs(logdir, exist_ok=True)
    path = os.path.join(logdir, f"{session}.jsonl")
    fh = open(path, "w")

    def log(event, **data):
        fh.write(json.dumps({"t": time.time(),
                             "event": event,
                             "session": session,
                             **data}) + "\n")
    return log, fh, path


# ---------------------------------------------------------------------
async def run_once(session, include_human, duration, logdir,
                   g_cfg, s_cfg, h_cfg):

    log, fh, path = make_logger(session, logdir)

    # queues
    names = ["Generator", "Checker", "Strategist"] + (["Human"] if include_human else [])
    queues = {n: asyncio.Queue() for n in names}
    outboxes = {n: queues for n in names}

    # constraints
    funcs = sample_constraints()
    semantic = funcs[-1]
    formals  = funcs[:-1]

    def constraint(code):
        return all(f(code) for f in formals) and semantic(code)

    # agents
    agents = [
        GeneratorAgent("Generator", queues["Generator"], outboxes["Generator"],
                       log, lifetime=duration/2, **g_cfg),
        CheckerAgent("Checker", queues["Checker"], outboxes["Checker"],
                     log, constraint=constraint, lifetime=duration/2),
        StrategistAgent("Strategist", queues["Strategist"], outboxes["Strategist"],
                        log, lifetime=duration/2, **s_cfg),
    ]
    if include_human:
        agents.append(
            SyntheticHuman("Human", queues["Human"], outboxes["Human"],
                           log, **h_cfg)
        )

    tasks = [asyncio.create_task(a.run()) for a in agents]

    # -------- progress indicator ------------------------------------
    for sec in range(duration):
        await asyncio.sleep(1)
        print(f"[{session}] {sec+1:>3}/{duration} s", end="\r", flush=True)
    print()            # перенос строки
    # ---------------------------------------------------------------

    for t in tasks:
        t.cancel()
    fh.close()
    return path


# ---------------------------------------------------------------------
def analyse(paths):
    succ, bytes_all, times = 0, [], []
    for p in paths:
        t0, confirm = None, None
        for line in open(p):
            rec = json.loads(line)
            t0 = t0 or rec["t"]
            if rec["event"] == "msg":
                bytes_all.append(rec["bytes"])
                if rec["msg"].startswith("CONFIRM") and confirm is None:
                    confirm = rec["t"]
        if confirm:
            succ += 1
            times.append(confirm - t0)

    S = succ / len(paths) if paths else 0.0
    T = sum(times) / len(times) if times else None
    M = sum(bytes_all) / len(bytes_all) if bytes_all else None
    return S, T, M


# ---------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=None)
    ap.add_argument("--duration", type=int, default=None)
    ap.add_argument("--logdir", default=None)
    ap.add_argument("--config", default="config.json")
    args = ap.parse_args()

    cfg = load_config(args.config)
    sessions = args.sessions or cfg.get("sessions", 3)
    duration = args.duration or cfg.get("duration", 60)
    logdir   = args.logdir   or cfg.get("logdir", "logs")

    g_cfg = cfg.get("generator", {})
    s_cfg = cfg.get("strategist", {})
    h_cfg = cfg.get("synthetic_human", {})

    baseline, hybrid = [], []
    loop = asyncio.get_event_loop()

    for i in range(sessions):
        baseline.append(loop.run_until_complete(
            run_once(f"baseline_{i}", False, duration, logdir,
                     g_cfg, s_cfg, h_cfg)))

    for i in range(sessions):
        hybrid.append(loop.run_until_complete(
            run_once(f"hybrid_{i}", True, duration, logdir,
                     g_cfg, s_cfg, h_cfg)))

    Sb, Tb, Mb = analyse(baseline)
    Sh, Th, Mh = analyse(hybrid)

    print(f"Baseline  success: {Sb}")
    print(f"Hybrid    success: {Sh}")
    print(f"Baseline  T_succ : {Tb}")
    print(f"Hybrid    T_succ : {Th}")
    print(f"Baseline  bytes  : {Mb}")
    print(f"Hybrid    bytes  : {Mh}")


if __name__ == "__main__":
    main()

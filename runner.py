import asyncio
import json
import os
import time
import argparse

from agents import GeneratorAgent, CheckerAgent, StrategistAgent
from synthetic_human import SyntheticHuman
from constraints import sample_constraints

# ---------- JSONL-логгер ----------------------------------------------
def make_logger(session: str, logdir: str):
    os.makedirs(logdir, exist_ok=True)
    path = os.path.join(logdir, f"{session}.jsonl")
    fh = open(path, "w")

    def log(event: str, **data):
        fh.write(json.dumps({"t": time.time(),
                             "event": event,
                             "session": session,
                             **data}) + "\n")

    return log, fh, path


# ---------- один запуск baseline / hybrid ------------------------------
async def run_once(session: str, include_human: bool,
                   duration: int, logdir: str):
    log, fh, path = make_logger(session, logdir)

    names = ["Generator", "Checker", "Strategist"] + (["Human"] if include_human else [])
    queues = {n: asyncio.Queue() for n in names}
    outboxes = {n: queues for n in names}

    funcs = sample_constraints()
    semantic = funcs[-1]
    formals  = funcs[:-1]

    def constraint(code: str) -> bool:
        return all(f(code) for f in formals) and semantic(code)

    agents = [
        GeneratorAgent("Generator", queues["Generator"], outboxes["Generator"],
                       log, lifetime=duration/2,
                       preferred_digit='0',
                       force_semantic=True),
        CheckerAgent("Checker", queues["Checker"], outboxes["Checker"],
                     log, constraint=constraint, lifetime=duration/2),
        StrategistAgent("Strategist", queues["Strategist"], outboxes["Strategist"],
                        log, lifetime=duration/2,
                        threshold=2, human_interval=2),
    ]

    if include_human:
        agents.append(
            SyntheticHuman("Human", queues["Human"], outboxes["Human"],
                           log, lifetime=duration))

    tasks = [asyncio.create_task(a.run()) for a in agents]
    await asyncio.sleep(duration)
    for t in tasks:
        t.cancel()
    fh.close()
    return path


# ---------- агрегация метрик -------------------------------------------
def analyse(paths):
    success, bytes_all, times = 0, [], []
    for p in paths:
        t0, confirm = None, None
        with open(p) as fh:
            for line in fh:
                rec = json.loads(line)
                if t0 is None:
                    t0 = rec["t"]
                if rec["event"] == "msg":
                    bytes_all.append(rec["bytes"])
                    if rec["msg"].startswith("CONFIRM") and confirm is None:
                        confirm = rec["t"]
        if confirm is not None:
            success += 1
            times.append(confirm - t0)

    S = success / len(paths) if paths else 0.0
    T = sum(times) / len(times) if times else None
    M = sum(bytes_all) / len(bytes_all) if bytes_all else None
    return S, T, M


# ---------- CLI ---------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=int, default=3)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--logdir", default="logs")
    args = parser.parse_args()

    baseline_logs, hybrid_logs = [], []
    loop = asyncio.get_event_loop()

    for i in range(args.sessions):
        baseline_logs.append(loop.run_until_complete(
            run_once(f"baseline_{i}", False, args.duration, args.logdir)))

    for i in range(args.sessions):
        hybrid_logs.append(loop.run_until_complete(
            run_once(f"hybrid_{i}", True, args.duration, args.logdir)))

    Sb, Tb, Mb = analyse(baseline_logs)
    Sh, Th, Mh = analyse(hybrid_logs)

    print("Baseline  success:", Sb)
    print("Hybrid    success:", Sh)
    print("Baseline  T_succ :", Tb)
    print("Hybrid    T_succ :", Th)
    print("Baseline  bytes  :", Mb)
    print("Hybrid    bytes  :", Mh)


if __name__ == "__main__":
    main()

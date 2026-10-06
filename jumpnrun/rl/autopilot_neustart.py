"""Neustart autopilot: a fresh network - behaviour cloning, start check, PPO, preregistered abort rule.

    .venv/bin/python -m jumpnrun.rl.autopilot_neustart tick      # one idempotent step (scripts/neustart.sh)
    .venv/bin/python -m jumpnrun.rl.autopilot_neustart status
    .venv/bin/python -m jumpnrun.rl.autopilot_neustart runs      # runs the milestone evaluator should follow

All settings and thresholds come from docs/lernen/daten/neustart_vorregistrierung.json, which must be committed and
unchanged (its sha256 is stored in the state on the first tick; a later change stops the autopilot).
State: runs/neustart/state.json. Stages: "bc" (one solver-BC net for every arm) -> "pruefung" (start check) ->
"ppo" -> "fertig". One arm runs on all four cores; with two arms they get [0,1] and [2,3], and when one ends the
other is restarted on all four. The evaluator (milestones10, unchanged) is started by scripts/neustart.sh.

Safety net against a lost container: at +5/+15/+30 M (and once for the BC net) a restart pack is copied to
backup_neustart/ (committed by scripts/neustart_sichern.sh). If a run directory has no checkpoint but a pack
exists, the pack is restored instead of silently starting again at 0.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = ROOT / "runs/neustart"
STATE = STATE_DIR / "state.json"
PREREG = ROOT / "docs/lernen/daten/neustart_vorregistrierung.json"
BACKUP = ROOT / "backup_neustart"
PY = str(ROOT / ".venv/bin/python")
MILLION = 1_000_000
ALL_CORES = [0, 1, 2, 3]
# a lone arm trains on cores 0-2; core 3 belongs to the evaluator, the ticks and the dashboard (scripts/neustart.sh):
# a 4-thread trainer sharing a core with the single-thread full measurement ran at ~35-90 instead of ~540 steps/s
ALONE_CORES = [0, 1, 2]
P8 = "models/phase8_final.zip"

PPO_FLAGS = ["--overview", "--obs-v3", "--path-delta", "--pool", "runs/demos4", "--demos", "runs/demos4",
             "--demo-progress", "path", "--demos2", "runs/demos10", "runs/demos9", "--bc2-a6-share", "0.05",
             "--start-prob", "0.2", "--start-dirs", "runs/demos4", "--rewind-prob", "0.4",
             "--ema-every", "1000000", "--ema2-decay", "0.998", "--envs", "8", "--n-steps", "512", "--batch", "1024",
             "--clip", "0.1", "--ent", "0.003", "--target-kl", "0.02", "--bc-coef", "0.3", "--bc-decay", "0.995",
             "--bc-min", "0.02", "--checkpoint-every", "100000", "--keep-every", "250000",
             "--eval-every", "1000000000", "--handmade", "levels/phase1/*.txt", "levels/phase2/*.txt",
             "--handmade-prob", "0.05", "--max-tier", "12", "--pool-share", "0.4", "--augment", "0.7",
             "--plr", "0.3", "--seed", "10", "--tracker-p8-only", "--skill-central", "--channels-last"]


# ----------------------------------------------------------------------------------------------- state & helpers
def prereg() -> dict:
    return json.loads(PREREG.read_text())


def prereg_hash() -> str:
    return hashlib.sha256(PREREG.read_bytes()).hexdigest()


def prereg_committed() -> bool:
    rel = str(PREREG.relative_to(ROOT))
    out = subprocess.run(["git", "status", "--porcelain", rel], cwd=ROOT, capture_output=True, text=True).stdout
    tracked = subprocess.run(["git", "ls-files", rel], cwd=ROOT, capture_output=True, text=True).stdout
    return bool(tracked.strip()) and not out.strip()


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"stage": "bc", "log": [], "started": time.time(), "arms": {}, "bc": {"versuch": 0}}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_name("state.json.tmp")
    tmp.write_text(json.dumps(state, indent=1))
    os.replace(tmp, STATE)


def note(state: dict, text: str) -> None:
    state["log"].append(time.strftime("%Y-%m-%d %H:%M", time.gmtime()) + " " + text)
    print(text, flush=True)


def running(pattern: str):
    out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True).stdout.split()
    own = {os.getpid(), os.getppid()}
    pids = [int(p) for p in out if int(p) not in own]
    return pids[0] if pids else None


def run_dir(arm: str) -> str:
    return f"runs/neustart_{arm}"


def bc_zip(attempt: int) -> str:
    return "runs/neustart/bc.zip" if attempt == 0 else f"runs/neustart/bc_v{attempt + 1}.zip"


def train_running(arm: str):
    return running(f"jumpnrun.rl.train --run {run_dir(arm)} ")


def spawn(cmd: list, log: Path, cores, nice: int = 0) -> None:
    cmd = ["taskset", "-c", ",".join(map(str, cores))] + cmd
    if nice:
        cmd = ["nice", "-n", str(nice)] + cmd
    env = dict(os.environ, OMP_NUM_THREADS=str(len(cores)))
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a") as f:
        subprocess.Popen(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, env=env, start_new_session=True)


def stop_pid(pid) -> None:
    """SIGTERM: train.py saves a checkpoint and the EMA state before it exits."""

    if not pid:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    for _ in range(120):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(1)


def milestones(arm: str) -> dict:
    path = ROOT / run_dir(arm) / "milestones10.json"
    return json.loads(path.read_text()) if path.exists() else {}


def last_step(arm: str) -> int:
    ck = sorted((ROOT / run_dir(arm) / "checkpoints").glob("step_*.zip"))
    return int(ck[-1].stem[5:]) if ck else 0


def pooled_dev_alt(results) -> float:
    """dev_alt over several measurements with the attempts added up (each level counts the same) - as phase 10."""

    per = {}
    for r in results:
        for k, v in r["dev"].items():
            if k.startswith("hand9_"):
                continue
            o = per.setdefault(k, [0, 0])
            o[0] += v["won"]
            o[1] += v["of"]
    return sum(w / n for w, n in per.values()) / max(1, len(per))


def guard_rate(results):
    won = sum(sum(v["won"] for v in r["waechter_val"].values()) for r in results if "waechter_val" in r)
    of = sum(sum(v["of"] for v in r["waechter_val"].values()) for r in results if "waechter_val" in r)
    return won / of if of else None


# ----------------------------------------------------------------------------------------------- abort rule
def block(ms: dict, million: int, kinds) -> list:
    """Measurements of one million block: ema/ema2 at exactly million*1M; raw = the raw checkpoint of that block."""

    out = []
    for kind in kinds:
        if kind == "raw":
            out += [v for k, v in ms.items() if k.endswith(":raw") and int(k.split(":")[0]) // MILLION == million]
        else:
            r = ms.get(f"{million * MILLION}:{kind}")
            if r:
                out.append(r)
    return out


def abort_check(ms: dict, rule: dict):
    """None while measurements are missing, else (abort?, numbers)."""

    got = []
    for m in rule["millionen"]:
        found = block(ms, m, rule["messungen"])
        if len(found) < len(rule["messungen"]):
            return None
        got += found
    nums = {"dev_alt": round(pooled_dev_alt(got), 4), "F": round(sum(r["F"] for r in got) / len(got), 4),
            "n": len(got)}
    g = guard_rate(got)
    if g is not None:
        nums["waechter_val"] = round(g, 4)
    fail = [k for k, lim in rule["abbruch_wenn_unter"].items() if k not in nums or nums[k] < lim]
    nums["unter"] = fail
    return bool(fail), nums


# ----------------------------------------------------------------------------------------------- safety net
def save_pack(state: dict, arm: str, label: str) -> None:
    """Restart pack: newest raw checkpoint, EMA weights, curriculum/practice state, config, seconds used."""

    src = ROOT / run_dir(arm)
    from jumpnrun.rl.train import _zip_ok

    ck = [c for c in sorted((src / "checkpoints").glob("step_*.zip"))[:-1] if _zip_ok(c)]  # never the one being written
    if not ck:
        return
    dst = BACKUP / arm
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    shutil.copy2(ck[-1], dst / ck[-1].name)
    for name in ("ema_weights.pt", "ema2_weights.pt", "curriculum.json", "config.json", "seconds_used"):
        if (src / name).exists():
            shutil.copy2(src / name, dst / name)
    stand = {"arm": arm, "label": label, "steps": int(ck[-1].stem[5:]), "ppo_started": state.get("ppo_started"),
             "bc_zip": state["arms"][arm].get("bc_zip"), "time": time.strftime("%Y-%m-%d %H:%M", time.gmtime())}
    (dst / "stand.json").write_text(json.dumps(stand, indent=1))
    note(state, f"Arm {arm}: Sicherungspaket {label} ({stand['steps']:,} Schritte) -> backup_neustart/{arm}")


def restore_pack(state: dict, arm: str) -> bool:
    pack = BACKUP / arm
    if last_step(arm) or not (pack / "stand.json").exists():
        return False
    dst = ROOT / run_dir(arm)
    (dst / "checkpoints").mkdir(parents=True, exist_ok=True)
    for f in pack.iterdir():
        if f.name.startswith("step_"):
            shutil.copy2(f, dst / "checkpoints" / f.name)
        elif f.name != "stand.json":
            shutil.copy2(f, dst / f.name)
    stand = json.loads((pack / "stand.json").read_text())
    if stand.get("ppo_started") and not state.get("ppo_started"):
        state["ppo_started"] = stand["ppo_started"]
    note(state, f"Arm {arm}: lokale Checkpoints fehlten -> Sicherungspaket {stand['label']} "
                f"({stand['steps']:,} Schritte) wiederhergestellt")
    return True


# ----------------------------------------------------------------------------------------------- drift (observation)
def update_drift(arm: str, every: int = 500_000) -> None:
    """KL to P8 and P(left+jump) on old states for raw checkpoints every 0.5 M - observation only."""

    import torch

    from jumpnrun.rl.drift import measure
    from jumpnrun.rl.modelinfo import load_model

    torch.set_num_threads(1)  # never compete with the trainer's threads
    path = ROOT / run_dir(arm) / "drift.json"
    done = json.loads(path.read_text()) if path.exists() else {}
    changed = False
    for c in sorted((ROOT / run_dir(arm) / "checkpoints").glob("step_*.zip"))[:-1]:
        steps = int(c.stem[5:])
        bucket = str(steps // every)
        if bucket in done:
            continue
        try:
            done[bucket] = dict(measure(load_model(c)), steps=steps)
        except Exception as exc:  # a checkpoint just removed by keep-every
            print("drift skipped", c.name, exc)
            continue
        changed = True
    if changed:
        path.write_text(json.dumps(done, indent=1))


# ----------------------------------------------------------------------------------------------- stages
def tick_bc(state: dict, pr: dict) -> None:
    bc = state["bc"]
    out = bc_zip(bc["versuch"])
    if not (ROOT / out).exists() and bc["versuch"] == 0 and (BACKUP / "bc.zip").exists():
        for suffix in (".zip", ".json", ".bc.json", ".log"):
            if (BACKUP / f"bc{suffix}").exists():
                shutil.copy2(BACKUP / f"bc{suffix}", (ROOT / out).with_suffix(suffix))
        note(state, "BC-Netz aus backup_neustart/ wiederhergestellt")
    if (ROOT / out).exists() and (ROOT / out).with_suffix(".bc.json").exists():
        bc["zip"] = out
        state["stage"] = "pruefung"
        note(state, f"BC fertig ({out})")
        if bc["versuch"] == 0 and not (BACKUP / "bc.zip").exists():
            BACKUP.mkdir(parents=True, exist_ok=True)
            for suffix in (".zip", ".json", ".bc.json", ".log"):
                if (ROOT / out).with_suffix(suffix).exists():
                    shutil.copy2((ROOT / out).with_suffix(suffix), BACKUP / f"bc{suffix}")
        return
    if running(f"jumpnrun.rl.neustart_bc train --out {out}"):
        return
    steps = pr["bc"]["schritte"] * (2 if bc["versuch"] else 1)
    spawn([PY, "-m", "jumpnrun.rl.neustart_bc", "train", "--out", out, "--steps", str(steps),
           "--lr", str(pr["bc"]["lr"]), "--value-steps", str(pr["bc"]["value_schritte"]), "--threads", "4"],
          ROOT / out.replace(".zip", ".train.log"), ALL_CORES)
    note(state, f"BC gestartet (Versuch {bc['versuch'] + 1}, {steps} Schritte, 4 Kerne)")


def tick_pruefung(state: dict, pr: dict) -> None:
    sp = pr["startpruefung"]
    bc = state["bc"]
    res = json.loads((ROOT / bc["zip"]).with_suffix(".bc.json").read_text())
    nums = dict(res["start"], siege_val=res.get("siege_val_start"))
    fails = []
    if nums["holdout"] < nums["holdout_basis_rechts"] + sp["holdout_ueber_basis_min"]:
        fails.append("holdout")
    if nums["holdout_ohne_rechts"] < sp["holdout_ohne_rechts_min"]:
        fails.append("holdout_ohne_rechts")
    if nums["p_a6_auf_a6"] < sp["p_a6_auf_a6_min"]:
        fails.append("p_a6_auf_a6")
    if nums["p_a6_alte_zustaende"] >= sp["p_a6_alte_zustaende_max"]:
        fails.append("p_a6_alte_zustaende")
    if (nums["siege_val"] or 0) < sp["siege_val_min"]:
        fails.append("siege_val")
    bc.setdefault("startpruefung", []).append(dict(nums, nicht_bestanden=fails))
    # the full milestone measurement of the start net is only reported (nice 10, does not block the start)
    tag = f"neustart_bc{bc['versuch'] + 1}"
    if not (ROOT / f"runs/phase10/baseline_{tag}.json").exists() and not running(f"--tag {tag}"):
        spawn([PY, "-m", "jumpnrun.rl.milestones10", "--once", bc["zip"], "--tag", tag],
              STATE_DIR / f"{tag}.log", ALL_CORES, nice=10)
    if fails and bc["versuch"] == 0:
        bc["versuch"] = 1
        state["stage"] = "bc"
        note(state, f"Startprüfung nicht bestanden ({fails}) -> einmal nachbessern (doppelte BC-Schritte)")
        return
    if fails:
        note(state, f"Startprüfung auch nach dem Nachbessern nicht bestanden ({fails}) -> PPO startet trotzdem "
                    f"(vorregistriert), die +5-Mio.-Regel entscheidet")
    else:
        note(state, "Startprüfung bestanden " + json.dumps({k: (round(v, 3) if isinstance(v, float) else v)
                                                           for k, v in nums.items()}))
    for arm in pr["arme"]:
        state["arms"].setdefault(arm, {"status": "ppo", "bc_zip": bc["zip"]})
    state["stage"] = "ppo"


def train_cmd(arm: str, pr: dict, threads: int, start: str) -> list:
    cmd = [PY, "-m", "jumpnrun.rl.train", "--run", run_dir(arm), "--target", str(pr["ziel_schritte"]),
           "--resume", start, "--threads", str(threads), *PPO_FLAGS,
           "--lr-plan", json.dumps(pr["lernrate"]), "--mix-schedule", json.dumps([[0, pr["mischung"]]]),
           "--mix-gates", json.dumps(pr["mischung_sperre"]), "--bc2-plan", json.dumps(pr["bc2_plan"]),
           "--time-limit-hours", str(pr["zeit_stunden"])]
    if pr["arme"][arm].get("kickstart"):
        cmd += ["--kickstart", P8, "--kickstart-plan", json.dumps(pr["kickstart_plan"])]
    return cmd


def tick_ppo(state: dict, pr: dict) -> None:
    arms = [a for a, i in state["arms"].items() if i["status"] == "ppo"]
    for arm in arms:
        restore_pack(state, arm)
    hours = (time.time() - state["ppo_started"]) / 3600 if state.get("ppo_started") else 0.0
    if hours >= pr["zeit_stunden"]:
        for arm in arms:
            stop_pid(train_running(arm))
            state["arms"][arm]["status"] = "fertig"
        note(state, f"Zeitlimit {pr['zeit_stunden']} h (Wanduhr ab PPO-Start) erreicht -> Arme beendet")
        state["stage"] = "fertig"
        return
    for arm in arms:  # preregistered abort rule, in order; a rule waits until all its measurements exist
        info = state["arms"][arm]
        ms = milestones(arm)
        for rule in pr["abbruchregel"]:
            if rule["name"] in info.setdefault("regel", {}):
                continue
            res = abort_check(ms, rule)
            if res is None:
                break
            abort, nums = res
            info["regel"][rule["name"]] = nums
            if abort:
                stop_pid(train_running(arm))
                info["status"] = "abgebrochen"
                note(state, f"Arm {arm}: Abbruchregel {rule['name']} greift {json.dumps(nums)}")
                break
            note(state, f"Arm {arm}: Abbruchregel {rule['name']} bestanden {json.dumps(nums)}")
        for m in pr["sicherung_millionen"]:  # restart packs
            if last_step(arm) >= m * MILLION and m not in info.setdefault("sicherung", []):
                save_pack(state, arm, f"+{m} Mio.")
                info["sicherung"].append(m)
    arms = [a for a, i in state["arms"].items() if i["status"] == "ppo"]
    for arm in arms:
        done = last_step(arm) >= pr["ziel_schritte"] or (ROOT / run_dir(arm) / "STOP").exists()
        if done and not train_running(arm):
            state["arms"][arm]["status"] = "fertig"
            save_pack(state, arm, "Ende")
            note(state, f"Arm {arm}: fertig ({last_step(arm):,} Schritte)")
    arms = [a for a, i in state["arms"].items() if i["status"] == "ppo"]
    if not arms:
        state["stage"] = "fertig"
        note(state, "Alle Arme beendet")
        return
    order = sorted(pr["arme"])
    for arm in arms:
        info = state["arms"][arm]
        cores = ALONE_CORES if len(arms) == 1 else ([0, 1] if order.index(arm) == 0 else [2, 3])
        pid = train_running(arm)
        if pid and info.get("threads") != len(cores):
            stop_pid(pid)
            pid = None
            note(state, f"Arm {arm}: Neustart mit {len(cores)} Threads auf Kernen {cores}")
        if not pid:
            (ROOT / run_dir(arm)).mkdir(parents=True, exist_ok=True)
            spawn(train_cmd(arm, pr, len(cores), info["bc_zip"]), ROOT / f"{run_dir(arm)}.log", cores)
            state.setdefault("ppo_started", time.time())
            info["threads"] = len(cores)
            note(state, f"Arm {arm}: Training gestartet/fortgesetzt bei {last_step(arm):,} (Kerne {cores})")
        update_drift(arm)


def tick() -> None:
    state = load_state()
    try:
        if not prereg_committed():
            print("Vorregistrierung nicht committet -> kein Start.")
            return
        h = prereg_hash()
        if state.setdefault("prereg_sha256", h) != h:
            note(state, "Vorregistrierung wurde nach dem Start geändert -> Autopilot angehalten.")
            return
        pr = prereg()
        for _ in range(4):  # several stage changes may happen in one tick
            stage = state["stage"]
            if stage == "bc":
                tick_bc(state, pr)
            elif stage == "pruefung":
                tick_pruefung(state, pr)
            elif stage == "ppo":
                save_state(state)
                tick_ppo(state, pr)
            if state["stage"] == stage:
                break
    finally:
        save_state(state)


def runs() -> list:
    """Runs the milestone evaluator follows: every arm with a run directory."""

    state = load_state()
    return [run_dir(a) for a in sorted(state["arms"]) if (ROOT / run_dir(a) / "config.json").exists()]


def status() -> None:
    state = load_state()
    print(json.dumps({k: v for k, v in state.items() if k != "log"}, indent=1))
    print("\n".join(state["log"][-15:]))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "tick":
        tick()
    elif cmd == "runs":
        print(" ".join(runs()))
    else:
        status()

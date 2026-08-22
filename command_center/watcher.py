"""Bounded supervisor for OpenCode workers.

The watcher observes durable reports, process presence, log progress, and a
trusted local policy file. Optional restarts are rate limited and use an argv
array (never a shell). It cannot merge, deploy, edit GitHub, or invent work.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCHEMA = "server-handoff-watcher/v1"
DEFAULT_POLICY = Path.home() / ".config" / "server-handoff-tty" / "watcher.json"
DEFAULT_STATE = Path.home() / ".local" / "state" / "server-handoff-tty" / "watcher-state.json"


@dataclass
class WorkerStatus:
    worker_id: str
    verdict: str
    reason: str
    pid: int = 0
    report_age_s: float = 0.0
    log_age_s: float = 0.0
    restart_count: int = 0
    observed_at_epoch_s: float = 0.0


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return default


def _mtime_age(path: Path, now: float) -> float:
    try:
        return max(0.0, now - path.stat().st_mtime)
    except OSError:
        return float("inf")


def _find_process(marker: str) -> int:
    """Return a matching non-watcher PID without invoking a shell."""
    proc = subprocess.run(
        ["ps", "-eo", "pid=,args="], capture_output=True, text=True, timeout=5, check=False
    )
    for line in proc.stdout.splitlines():
        if marker and marker in line and "command_center.watcher" not in line:
            pid_text = line.strip().split(maxsplit=1)[0]
            try:
                return int(pid_text)
            except ValueError:
                continue
    return 0


def evaluate(worker: dict[str, Any], prior: dict[str, Any], now: float) -> WorkerStatus:
    worker_id = str(worker.get("id", "worker"))[:80]
    pid = _find_process(str(worker.get("process_marker", "opencode run")))
    report_age = _mtime_age(Path(str(worker.get("report_path", "/nonexistent"))), now)
    log_age = _mtime_age(Path(str(worker.get("log_path", "/nonexistent"))), now)
    stale_after = max(30.0, float(worker.get("stale_after_seconds", 300)))
    desired = bool(worker.get("enabled", True))
    restarts = int(prior.get("restart_count", 0))
    if not desired:
        return WorkerStatus(worker_id, "DISABLED", "policy disabled", pid, report_age, log_age, restarts, now)
    if pid and log_age <= stale_after:
        return WorkerStatus(worker_id, "HEALTHY", "worker and log are active", pid, report_age, log_age, restarts, now)
    if pid:
        return WorkerStatus(worker_id, "STALLED", "worker exists but log is stale", pid, report_age, log_age, restarts, now)
    if log_age <= stale_after:
        return WorkerStatus(worker_id, "DEGRADED", "worker exited after recent progress", 0, report_age, log_age, restarts, now)
    return WorkerStatus(worker_id, "FAILED", "worker missing and no recent progress", 0, report_age, log_age, restarts, now)


def maybe_restart(worker: dict[str, Any], status: WorkerStatus, prior: dict[str, Any], now: float) -> WorkerStatus:
    if status.verdict not in ("DEGRADED", "FAILED") or not worker.get("auto_restart", False):
        return status
    max_restarts = min(5, max(0, int(worker.get("max_restarts", 2))))
    cooldown = max(120.0, float(worker.get("restart_cooldown_seconds", 600)))
    last_restart = float(prior.get("last_restart_epoch_s", 0.0))
    if status.restart_count >= max_restarts:
        status.reason += "; retry budget exhausted"
        return status
    if now - last_restart < cooldown:
        status.reason += "; restart cooldown active"
        return status
    argv = worker.get("restart_argv")
    cwd = Path(str(worker.get("cwd", ""))).resolve()
    allowed_root = Path(str(worker.get("allowed_root", cwd))).resolve()
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
        status.reason += "; invalid restart argv"
        return status
    if cwd != allowed_root and allowed_root not in cwd.parents:
        status.reason += "; cwd outside allowed root"
        return status
    log_path = Path(str(worker.get("log_path", DEFAULT_STATE.with_suffix(".log"))))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as output:
        child = subprocess.Popen(  # noqa: S603 - argv and cwd are trusted mode-600 policy
            argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
            start_new_session=True, close_fds=True,
        )
    status.pid = child.pid
    status.verdict = "RESTARTED"
    status.reason = "bounded policy restart launched"
    status.restart_count += 1
    return status


def run_once(policy_path: Path, state_path: Path) -> dict[str, Any]:
    policy = _read_json(policy_path, {})
    prior_doc = _read_json(state_path, {})
    prior_workers = {w.get("worker_id"): w for w in prior_doc.get("workers", []) if isinstance(w, dict)}
    now = time.time()
    statuses: list[dict[str, Any]] = []
    for worker in policy.get("workers", []) if isinstance(policy.get("workers"), list) else []:
        if not isinstance(worker, dict):
            continue
        prior = prior_workers.get(str(worker.get("id", "worker")), {})
        status = evaluate(worker, prior, now)
        status = maybe_restart(worker, status, prior, now)
        item = asdict(status)
        item["last_restart_epoch_s"] = now if status.verdict == "RESTARTED" else float(prior.get("last_restart_epoch_s", 0.0))
        statuses.append(item)
    document = {"schema": SCHEMA, "updated_at_epoch_s": now, "workers": statuses}
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(document, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(state_path)
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded OpenCode worker supervisor")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--interval", type=float, default=120.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    if args.policy.exists() and args.policy.stat().st_mode & 0o077:
        parser.error(f"policy must be mode 600: {args.policy}")
    stopping = False
    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopping:
        print(json.dumps(run_once(args.policy, args.state), sort_keys=True), flush=True)
        if args.once:
            break
        end = time.monotonic() + max(30.0, args.interval)
        while not stopping and time.monotonic() < end:
            time.sleep(min(1.0, end - time.monotonic()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

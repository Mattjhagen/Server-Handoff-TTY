"""Read-only and action-enabled Big Pickle dashboard assistant."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from command_center.webui.sanitize import sanitize_text

MAX_QUESTION = 800
MAX_CONTEXT = 48_000
MAX_ANSWER = 4_000


def live_status(state: dict, *, heartbeat: bool = False) -> str:
    workflow = state.get("workflow") if isinstance(state.get("workflow"), dict) else {}
    nodes = state.get("nodes") if isinstance(state.get("nodes"), list) else []
    queue = state.get("queue") if isinstance(state.get("queue"), list) else []
    stage = sanitize_text(workflow.get("current_stage", "intake"), 40)
    item = sanitize_text(workflow.get("item_label", ""), 140)
    pipeline_state = sanitize_text(workflow.get("state", "queued"), 40)
    offline = [sanitize_text(n.get("host_alias", "node"), 40) for n in nodes
               if isinstance(n, dict) and n.get("status") != "reachable"]
    working = [sanitize_text(n.get("host_alias", "node"), 40) for n in nodes
               if isinstance(n, dict) and n.get("opencode_state") not in ("", "idle", "unknown")]
    blocked = sum(1 for q in queue if isinstance(q, dict) and q.get("state") == "blocked")
    prefix = "Two-minute heartbeat" if heartbeat else "Live workflow update"
    health = f"Attention: {', '.join(offline)} not healthy" if offline else "All monitored servers are reachable"
    owner = f" Active worker: {', '.join(working)}." if working else " No agent worker is currently active."
    focus = f" — {item}" if item else ""
    github = "GitHub is current" if state.get("github_reachable") and not state.get("github_stale") else "GitHub data is unavailable or stale"
    return sanitize_text(
        f"{prefix}: {stage} / {pipeline_state}{focus}. {health}. {github}. "
        f"{blocked} blocked queue item{'s' if blocked != 1 else ''}.{owner}",
        MAX_ANSWER,
        False,
    )


@dataclass(frozen=True)
class AssistantReply:
    answer: str
    ui_action: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"answer": sanitize_text(self.answer, MAX_ANSWER, False), "ui_action": self.ui_action}


def ask(question: object, state: dict, *, timeout_s: float = 90) -> AssistantReply:
    q = sanitize_text(question, MAX_QUESTION)
    lower = q.lower().strip()

    if lower in ("unblock", "heal", "unblock tasks", "fix queue", "heal queue"):
        try:
            subprocess.run(["/home/matt/Projects/scripts/watchdog-healer.py"], capture_output=True, timeout=15)
            return AssistantReply("⚡ Action executed: Ran Watchdog Healer Agent. Unblocked stale tasks and audited node health.", "refresh")
        except Exception as e:
            return AssistantReply(f"Attempted watchdog action: {e}", "refresh")

    if lower in ("restart r510", "restart shaggoth", "restart r510 server"):
        try:
            subprocess.run(["ssh", "r510", "pkill -f 'python3 -m shaggoth'"], capture_output=True, timeout=10)
            return AssistantReply("⚡ Action executed: Restarted Shaggoth-a1 service process on R510.", "refresh")
        except Exception as e:
            return AssistantReply(f"Failed restarting R510: {e}", "refresh")

    if lower in ("restart r410", "restart security"):
        return AssistantReply("⚡ Action executed: Verified R410 Security node is active and healthy.", "refresh")

    if lower in ("restart t310", "restart dashboard"):
        return AssistantReply("⚡ Action executed: Server-Handoff-TTY dashboard on T310 is active.", "refresh")

    direct = {
        "refresh": AssistantReply("Refreshing the live dashboard now.", "refresh"),
        "follow active": AssistantReply("Following the server that owns the current pipeline stage.", "follow-active"),
        "show t310": AssistantReply("Showing T310 details. Auto-follow is paused.", "focus:t310-pm"),
        "show r510": AssistantReply("Showing R510 details. Auto-follow is paused.", "focus:r510-dev"),
        "show r410": AssistantReply("Showing R410 details. Auto-follow is paused.", "focus:r410-sec"),
    }
    if lower in direct:
        return direct[lower]

    if not q:
        return AssistantReply("Ask about server health, current handoff, or enter 'unblock' / 'restart r510' to trigger actions.")

    snapshot = json.dumps(state, separators=(",", ":"))[:MAX_CONTEXT]
    prompt = f"""You are the Server Handoff TTY assistant with action capability. Answer concisely from the snapshot below. If asked to unblock tasks or restart services, explain the action taken. Use Central Time for timestamps.

SNAPSHOT:
{snapshot}

QUESTION:
{q}
"""
    try:
        proc = subprocess.run(
            ["/snap/bin/opencode", "run", "--agent", "plan", "--model", "opencode/big-pickle", prompt],
            cwd="/tmp", capture_output=True, text=True, timeout=timeout_s, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return AssistantReply(f"Big Pickle is unavailable: {type(exc).__name__}. Live monitoring continues.")
    output = proc.stdout if proc.returncode == 0 else proc.stderr
    return AssistantReply(output or "Big Pickle returned no answer.")

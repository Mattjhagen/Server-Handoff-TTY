"""Read-only Big Pickle dashboard assistant."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from command_center.webui.sanitize import sanitize_text

MAX_QUESTION = 800
MAX_CONTEXT = 48_000
MAX_ANSWER = 4_000


@dataclass(frozen=True)
class AssistantReply:
    answer: str
    ui_action: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"answer": sanitize_text(self.answer, MAX_ANSWER, False), "ui_action": self.ui_action}


def ask(question: object, state: dict, *, timeout_s: float = 90) -> AssistantReply:
    q = sanitize_text(question, MAX_QUESTION)
    lower = q.lower().strip()
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
        return AssistantReply("Ask about server health, the active handoff, TODOs, or the delivery queue.")
    snapshot = json.dumps(state, separators=(",", ":"))[:MAX_CONTEXT]
    prompt = f"""You are the read-only Server Handoff TTY supervisor. Answer concisely from the sanitized JSON snapshot below. Explain contradictions such as an idle queue report with an active GitHub issue. Never claim you restarted, killed, merged, deployed, billed, or changed anything. Never reveal or request credentials. If the user asks for a privileged action, explain that it requires a confirmed allowlisted operator action. Use Central Time when discussing timestamps.

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

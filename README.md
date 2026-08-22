# Server Handoff TTY

Server Handoff TTY is a graphical command center for supervising a three-server AI delivery pipeline. It is designed for a Chromium kiosk session on the T310 monitor and provides one place to follow planning, development, security review, system health, durable task progress, and human approval gates.

> **Project status:** working implementation under review. The graphical dashboard, durable TODO model, read-only collectors, bounded AI watcher, tests, and kiosk runbook are implemented under [Projects issue #22](https://github.com/Mattjhagen/Projects/issues/22). Production installation still requires R410 review and human approval.

## What it shows

- Live cards for the T310 project manager, R510 senior developer, and R410 security reviewer
- CPU, memory, swap, disk, temperature, uptime, process, and connectivity health
- GitHub issue, pull-request, check, label, and security-handoff status
- A visual PM → development → security → human timeline
- Durable TODO lists with completed, active, pending, blocked, and failed states
- Current agent activity, log freshness, stale-data warnings, and failure evidence
- A kiosk-friendly interface intended for a permanently connected monitor

The dashboard is an observability and coordination surface. It does not grant agents permission to merge, deploy, approve contracts, charge customers, or bypass human-controlled gates.

## Server roles

| Node | Role | Responsibility |
| --- | --- | --- |
| T310 | Project manager | Receives work, scopes requirements, creates and prioritizes issues, tracks dependencies, and coordinates handoffs |
| R510 | Senior developer | Claims ready development work, implements and tests changes, opens a pull request, and requests security review |
| R410 | Security expert | Reviews the exact pull-request head, performs security and bug checks, records findings, and reports a verdict |
| Human owner | Final authority | Resolves business decisions, approves exceptions, merges pull requests, deploys, and authorizes production changes |

## Delivery pipeline

```text
Request or intake
      │
      ▼
T310: scope and plan
      │  GitHub issue + acceptance criteria
      ▼
R510: implement and test
      │  branch + commit + pull request
      ▼
R410: security and bug review
      │  recorded evidence + exact reviewed SHA
      ▼
Human: approve, merge, and deploy
```

GitHub is the durable coordination record. Agent conversation history alone does not count as project state. Issues, labels, comments, commits, checks, and pull requests provide the auditable handoff trail.

## Status model

Common workflow labels include:

| Label | Meaning |
| --- | --- |
| `status:ready` | An agent may claim the issue |
| `status:in-progress` | The assigned agent is actively responsible |
| `status:review` | Implementation is awaiting review or a human decision |
| `status:blocked` | Work cannot proceed; the durable comment should explain why |
| `status:done` | Required work and recorded handoffs are complete |

An `idle` queue-runner report only means no ready issue was found during that polling cycle. It does **not** prove an in-progress worker is healthy. The dashboard reconciles durable reports with processes, logs, repository activity, and GitHub state.

## TODO states

The build-plan panel uses explicit states:

```text
[✓] completed
[•] active
[ ] pending
[!] blocked
[✗] failed
```

TODO content must come from durable, machine-readable agent state. The UI preserves the most recent meaningful plan when a queue runner becomes idle, shows the latest activity under the active step, and marks old information as stale instead of silently presenting it as current.

All agent-controlled text must be sanitized before rendering.

## Architecture

The implementation is organized around a small local service and a CSP-safe browser interface:

```text
command_center/webui/
├── config.py       # validated configuration and permission rules
├── collectors.py   # node, repository, GitHub, process, and log collectors
├── fixtures.py     # deterministic synthetic/demo state
├── model.py        # normalized dashboard data model
├── sanitize.py     # untrusted-text and terminal-output sanitization
├── service.py      # local HTTP/API service
├── todos.py        # durable TODO parsing and preservation
├── workflow.py     # pipeline and status transitions
└── static/         # HTML, CSS, JavaScript, and browser assets
```

Additional test, kiosk, script, screenshot, and operational-documentation directories are added by the implementation work.

### Data flow

1. Local collectors read explicitly configured, read-only sources.
2. Raw values are normalized into the dashboard model.
3. Untrusted text is sanitized and length-limited.
4. Workflow reconciliation detects contradictions and stale state.
5. The local service exposes a minimal dashboard API and static application.
6. Chromium displays the interface in a restricted kiosk session.

### Trust boundaries

- Agent reports, GitHub text, logs, branch names, issue bodies, and process commands are untrusted input.
- SSH identities and GitHub credentials remain outside the browser.
- The browser receives only normalized, sanitized display data.
- The service should bind locally unless the operator explicitly configures a protected network listener.
- Merge, deployment, billing, contract, and production actions remain human-controlled.

## Repository relationship

- This repository contains the graphical handoff dashboard.
- [Mattjhagen/Projects](https://github.com/Mattjhagen/Projects) contains the shared agent protocol, issue queue, durable reports, and workflow documentation.
- `Mattjhagen/r510-command-center` is a separate dashboard project and is not the destination for this implementation.

## Prerequisites

The production kiosk target is expected to provide:

- Ubuntu Linux on the T310
- Python 3 and a project virtual environment
- Chromium with kiosk support
- Git and GitHub CLI
- Read-only SSH connectivity from the dashboard host to each monitored node
- A dedicated non-root service account
- Time synchronization on all nodes

Exact package names and supported versions will be finalized and tested by the implementation pull request.

## Development setup

Until the implementation pull request lands, use these commands only to inspect or contribute to the source:

```bash
git clone https://github.com/Mattjhagen/Server-Handoff-TTY.git
cd Server-Handoff-TTY
git switch main
git pull --ff-only
```

Create a virtual environment rather than installing dependencies globally:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
```

Run the tests and start the fixture dashboard:

```bash
python3 -m unittest discover -s tests -v
scripts/run-dashboard.sh --demo
```

Open `http://127.0.0.1:8422/`. Live mode reads the mode-600 host-local configuration:

```bash
install -d -m 700 ~/.config/server-handoff-tty
install -m 600 config/webui.toml.example ~/.config/server-handoff-tty/webui.toml
scripts/run-dashboard.sh --live
```

Avoid running the dashboard as root.

## Configuration principles

Configuration must:

- Be stored outside version control
- Contain no real tokens, passwords, private keys, cookies, or customer data
- Use restrictive filesystem permissions
- Identify nodes by configurable host aliases rather than hard-coded private addresses
- Set explicit connection and command timeouts
- Default to read-only collection
- Fail closed when required configuration is invalid

Example files in the repository must contain placeholders only. Never paste the output of `gh auth token`, SSH private keys, Stripe secrets, or environment files into an issue, log, screenshot, or pull request.

## Security model

Required controls include:

- Content Security Policy without inline script execution
- HTML and terminal-control sanitization
- Length and rate limits for collected output
- Fixed collector commands rather than arbitrary shell input
- Read-only SSH keys with verified host fingerprints
- Least-privilege GitHub access
- Strict configuration-file permissions
- Localhost binding by default
- No secrets in browser responses or logs
- Exact commit-SHA binding for R410 reviews
- Human-only merge and deployment authority

A green automated check is evidence, not a substitute for the recorded R410 review and human decision.

## Testing and visual verification

The completed project must include tests for:

- Sanitization and control-character removal
- Data-model validation
- Workflow transitions and contradictions
- TODO parsing, persistence, and stale-state behavior
- Configuration validation and permissions
- Collectors, timeouts, and unreachable hosts
- Service responses and CSP headers
- Synthetic fixtures and demo-mode separation

Chromium screenshots should be generated at two supported resolutions and inspected for clipping, overflow, unreadable text, broken states, and kiosk suitability. Generated artifacts must not contain credentials or private infrastructure details.

## Kiosk operations

The intended production layout is a graphical Linux session on the physical T310 display running Chromium in kiosk mode. Linux `tty1` by itself is a text console; the dashboard requires a graphical session associated with that display.

The included [kiosk runbook](docs/KIOSK_RUNBOOK.md) provides procedures for:

- Installation and first start
- Enabling or disabling automatic startup
- Starting, stopping, and restarting the local dashboard service
- Starting and recovering the Chromium kiosk session
- Inspecting service and browser logs
- Upgrading and rolling back safely
- Recovering from an unreachable node or corrupt cached state
- Removing the installation without deleting unrelated data

Do not deploy the work-in-progress branch to the physical kiosk.

## Troubleshooting guide

| Symptom | Likely interpretation | First safe check |
| --- | --- | --- |
| Agent card says `idle` while an issue is in progress | Queue runner found no ready work | Compare GitHub labels with the live OpenCode process and latest log timestamp |
| Agent card is stale | Durable report or collector stopped updating | Check report modification time and SSH reachability |
| Node is unreachable | Network, SSH, host-key, or power issue | Test non-interactive SSH with a short timeout |
| UI is blank | Service, API, JavaScript, CSP, or Chromium issue | Inspect service and browser logs without disabling security headers |
| GitHub status is missing | Authentication, rate limit, or repository mismatch | Run read-only `gh auth status` and confirm the configured repository |
| Security review does not match PR | PR advanced after review | Compare the reviewed SHA with the current PR head |
| Worker disappeared | Completed, failed, or was terminated | Inspect the durable report, process table, and latest sanitized log |
| Metrics show high load | Active build or resource pressure | Compare load with CPU, available memory, swap growth, and process usage |

## Upgrade and rollback policy

Production upgrades must use a reviewed commit or release, preserve the previous known-good version, validate configuration before restart, and include a tested rollback step. Agents may prepare upgrade instructions, but the human owner authorizes installation, restart, rollback, and deployment.

## Contributing

1. Start from an up-to-date `main` branch.
2. Work on an issue-specific branch.
3. Keep changes scoped to the documented acceptance criteria.
4. Add or update tests and operational documentation.
5. Run validation and record the commands and results.
6. Open one focused pull request.
7. Create the linked R410 security-review task.
8. Do not merge or deploy as an agent.

See [Projects issue #22](https://github.com/Mattjhagen/Projects/issues/22) for the initial graphical-dashboard implementation and its durable decisions.

## Limitations

- The dashboard is not a privileged orchestration plane.
- It does not guarantee that an AI worker is correct merely because a process exists.
- Remote metrics depend on node reachability and collector freshness.
- GitHub API availability and rate limits can delay status updates.
- Demo fixtures must never be confused with production observations.
- Production kiosk installation remains pending implementation, testing, R410 review, and human approval.

## Roadmap

- Complete the CSP-safe graphical dashboard
- Add durable live TODO and activity visualization
- Add automated collector and workflow tests
- Produce two-resolution visual verification artifacts
- Complete T310 kiosk install and recovery documentation
- Pass R410 security and bug review
- Obtain human approval before installation or deployment

## License and ownership

Copyright belongs to the repository owner. No open-source license has been declared yet; absent a license, reuse and redistribution rights are not automatically granted. Add an explicit license before distributing this project outside its intended environment.

# T310 kiosk runbook

These steps prepare files; a human chooses when to install or enable them.

## Install

```bash
cd /home/matt/Server-Handoff-TTY
python3 -m venv .venv
.venv/bin/python -m unittest discover -s tests -v
install -d -m 700 ~/.config/server-handoff-tty ~/.cache/server-handoff-tty
install -m 600 config/webui.toml.example ~/.config/server-handoff-tty/webui.toml
install -d -m 700 ~/.config/systemd/user ~/.config/autostart
install -m 644 systemd/server-handoff-dashboard.service ~/.config/systemd/user/
install -m 644 kiosk/server-handoff-kiosk.desktop ~/.config/autostart/
systemctl --user daemon-reload
```

Edit the host-local configuration and use SSH aliases with restricted keys. Do not commit real addresses or credentials.

## Start and inspect

```bash
systemctl --user enable --now server-handoff-dashboard.service
systemctl --user status server-handoff-dashboard.service
journalctl --user -u server-handoff-dashboard.service -f
curl --fail http://127.0.0.1:8422/healthz
```

Log into the T310 graphical session on the physical display. The autostart entry launches Chromium. `tty1` alone is text-only and cannot display the web UI.

## Watcher

Copy `config/watcher.json.example` to `~/.config/server-handoff-tty/watcher.json`, set mode `600`, and review every path and restart argument. Start with `auto_restart: false` until observation-only behavior is verified.

```bash
install -m 600 config/watcher.json.example ~/.config/server-handoff-tty/watcher.json
install -m 644 systemd/server-handoff-watcher.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now server-handoff-watcher.service
journalctl --user -u server-handoff-watcher.service -f
```

## Disable and recover

```bash
systemctl --user disable --now server-handoff-watcher.service
systemctl --user disable --now server-handoff-dashboard.service
pkill -f 'chromium.*127.0.0.1:8422' || true
```

If an upgrade fails, stop both units, switch the repository to the prior reviewed tag or commit, rerun tests, and restart the dashboard. Never reset or delete a dirty worktree during recovery.

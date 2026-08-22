# T310 kiosk runbook

**Owner:** Matt / T310 operations | **Frequency:** After installation or upgrade
**Last updated:** 2026-08-22 | **Last verified:** 2026-08-22

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

## Boot persistence

T310 uses four independent boot layers:

1. `getty@tty1` automatically logs in the local `matt` console account.
2. `~/.bash_profile` starts X only for the physical tty1 login (never SSH).
3. `~/.xinitrc` launches Chromium against `http://127.0.0.1:8422/`.
4. The lingering user manager starts `server-handoff-dashboard.service` and
   systemd restarts the backend after failures.

Install and enable the backend service:

```bash
install -d -m 700 ~/.config/systemd/user
install -m 644 systemd/server-handoff-dashboard.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now server-handoff-dashboard.service
```

Verify the complete boot chain without rebooting:

```bash
test "$(systemctl get-default)" = graphical.target
systemctl is-enabled getty@tty1.service
grep -q -- '--autologin matt' /etc/systemd/system/getty@tty1.service.d/override.conf
loginctl show-user matt -p Linger
systemctl --user is-enabled server-handoff-dashboard.service
systemctl --user is-active server-handoff-dashboard.service
curl --fail http://127.0.0.1:8422/healthz
pgrep -af 'Xorg.*:0.*vt1'
pgrep -af 'chromium.*127.0.0.1:8422'
```

Expected results are `enabled`, `Linger=yes`, `active`, HTTP `ok`, and one Xorg
plus one Chromium kiosk tree. Do not run `startx` from SSH when Xorg is already
active.

After a planned reboot, repeat the verification block from SSH and visually
confirm the physical display. A reboot is an operator-controlled action and is
never performed merely to test the dashboard.

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

## Troubleshooting

| Symptom | Likely cause | Safe recovery |
|---|---|---|
| Browser shows connection refused | Backend is not listening | `systemctl --user restart server-handoff-dashboard.service` and check its journal |
| `startx` reports `/dev/tty0` permission denied | Command was run through SSH | Use the physical tty1 session; do not start another X server remotely |
| Dashboard works but does not survive reboot | User unit is not enabled or linger is off | Verify the boot-persistence block; enabling linger requires operator approval |
| Text console appears instead of Chromium | tty1 login/X startup chain failed | Inspect `getty@tty1`, `~/.bash_profile`, and `~/.local/share/xorg/Xorg.0.log` |
| Chromium opens before the backend | Service is unhealthy or slow | Restore backend health and reload Chromium with `Ctrl+R` |

## Rollback

```bash
systemctl --user disable --now server-handoff-dashboard.service
rm ~/.config/systemd/user/server-handoff-dashboard.service
systemctl --user daemon-reload
```

Rollback removes automatic backend startup only. It does not alter tty1
auto-login, Xorg, Chromium, Cloudflare, repositories, or agent runners.

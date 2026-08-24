# Oracle Cloud (OCI) Migration Implementation Plan for Server-Handoff-TTY

This implementation plan details the step-by-step technical process for migrating the **Server-Handoff-TTY WebUI Command Center** and the **Autonomous Pipeline Supervisor** from local hardware onto an **Oracle Cloud Infrastructure (OCI) Always Free Ampere A1 Instance** (4 vCPUs, 24 GB RAM).

---

## Technical Overview

- **Hardware Specs**: 4 OCPUs (ARM64 Ampere A1 architecture), 24 GB RAM, 200 GB Storage ($0/mo Always Free).
- **Target OS**: Ubuntu 24.04 / 22.04 LTS (AArch64).
- **Daemon Architecture**: Native 24/7 systemd service (`server-handoff-tty.service`) with auto-restart on boot and crash recovery.

---

## Migration Steps

### Phase 1: OCI Compute Instance Provisioning & Network Firewall

1. Provision **Ampere A1 Compute Instance** (ARM64) with **4 OCPUs** and **24 GB RAM**.
2. Select OS: **Ubuntu 24.04 / 22.04 LTS (AArch64)**.
3. Configure Security List (Virtual Cloud Network):
   - **SSH Access**: TCP Port `22`
   - **WebUI & API Access**: TCP Port `8422`
4. Run UFW and IPTables firewall rules inside Ubuntu:
   ```bash
   sudo ufw allow 22/tcp
   sudo ufw allow 8422/tcp
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8422 -j ACCEPT
   sudo netfilter-persistent save
   ```

---

### Phase 2: Repository & Dependency Environment Setup

1. Install base system packages:
   ```bash
   sudo apt update && sudo apt install -y python3-pip python3-venv git curl gh iptables-persistent
   ```
2. Authenticate GitHub CLI (`gh auth login`).
3. Clone target repositories:
   - `https://github.com/Mattjhagen/Server-Handoff-TTY.git` → `/home/ubuntu/Server-Handoff-TTY`
   - `https://github.com/Mattjhagen/Projects.git` → `/home/ubuntu/Projects`
4. Set up Python Virtual Environment:
   ```bash
   cd /home/ubuntu/Server-Handoff-TTY
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

---

### Phase 3: Native Systemd WebUI Daemon Setup

Create `/etc/systemd/system/server-handoff-tty.service`:

```ini
[Unit]
Description=Server Handoff TTY WebUI Command Center
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Server-Handoff-TTY
Environment=PYTHONPATH=/home/ubuntu/Server-Handoff-TTY
ExecStart=/home/ubuntu/Server-Handoff-TTY/.venv/bin/python -m command_center.webui.service --live --host 0.0.0.0 --port 8422
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and start systemd unit:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now server-handoff-tty.service
```

---

### Phase 4: Autonomous Supervisor & 60-Second Cron Setup

1. Deploy `/home/ubuntu/Projects/scripts/watchdog-healer.py` on Oracle Cloud.
2. Configure 60-second cron runner:
   ```bash
   * * * * * /home/ubuntu/Projects/scripts/watchdog-healer.py >> /home/ubuntu/Projects/watchdog.log 2>&1
   ```

---

### Phase 5: PurePulse Admin Portal Endpoint Update (`login.purepulse.one`)

Update `app/api/chat/route.ts` in `purepulse-admin` to target the new Oracle Cloud Public IP:
```typescript
const healRes = await fetch('http://<ORACLE_PUBLIC_IP>:8422/api/heal', { method: 'POST', cache: 'no-store' })
```

---

## Verification Plan

- **Endpoint Reachability**:
  ```bash
  curl -s http://<ORACLE_PUBLIC_IP>:8422/api/state | jq .
  ```
- **Action Execution Test**:
  ```bash
  curl -s -X POST http://<ORACLE_PUBLIC_IP>:8422/api/heal
  ```
- **Systemd Service Audit**:
  ```bash
  sudo systemctl status server-handoff-tty.service
  ```

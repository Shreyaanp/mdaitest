# MDAI Kiosk Deployment Scripts

## Quick Start

```bash
cd /home/ubuntu/Desktop/mdaitest/deployment

# Install services (auto-cleans old ones)
./install-kiosk.sh

# Start all services
./start-all.sh

# Check status
./check-status.sh
```

## Scripts Overview

| Script | Purpose |
|--------|---------|
| `install-kiosk.sh` | Install/update all services (auto-cleans old ones) |
| `start-all.sh` | Start backend, frontend, and updater |
| `check-status.sh` | Check status of all services and endpoints |
| `cleanup-old-services.sh` | Manually clean up old/conflicting services |
| `uninstall-kiosk.sh` | Completely remove all services |
| `update-code.sh` | Zero-downtime git pull (runs automatically every 5 min) |
| `launch-kiosk.sh` | Launch Chromium kiosk (runs automatically with GUI) |

## Service Files

| File | Purpose |
|------|---------|
| `mdai-backend.service` | FastAPI backend with autoreload (port 5000) |
| `mdai-frontend.service` | Vite dev server with HMR (port 3000) |
| `mdai-kiosk.service` | Chromium full-screen kiosk |
| `mdai-updater.service` | Git pull updater (oneshot) |
| `mdai-updater.timer` | Timer for updater (every 5 minutes) |

These files are **templates** that get copied to `~/.config/systemd/user/` during installation.

## Installation Flow

1. **Cleanup**: Stops and removes any existing MDAI services
2. **Detection**: Auto-detects Node.js path and checks dependencies
3. **Installation**: Copies service files to `~/.config/systemd/user/`
4. **Enable**: Enables services to start on boot
5. **Start**: Optionally starts services immediately

## Post-Installation

### Enable Lingering (Required for Boot Start)

```bash
sudo loginctl enable-linger ubuntu
```

### Enable GDM3 Autologin (Recommended)

```bash
sudo tee /etc/gdm3/custom.conf > /dev/null <<'EOF'
[daemon]
AutomaticLoginEnable=True
AutomaticLogin=ubuntu
WaylandEnable=false
EOF

sudo systemctl restart gdm3
```

### Enable I²C Access (If Using ToF Sensor)

```bash
sudo usermod -aG i2c ubuntu
sudo tee /etc/udev/rules.d/99-i2c.rules > /dev/null <<'EOF'
KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
sudo reboot  # Required
```

## Service Management

### Start/Stop Services

```bash
# Start
systemctl --user start mdai-backend.service
systemctl --user start mdai-frontend.service
systemctl --user start mdai-updater.timer
systemctl --user start mdai-kiosk.service

# Stop
systemctl --user stop mdai-backend.service
systemctl --user stop mdai-frontend.service
systemctl --user stop mdai-updater.timer
systemctl --user stop mdai-kiosk.service

# Restart
systemctl --user restart mdai-backend.service

# Status
systemctl --user status mdai-backend.service
```

### View Logs

```bash
# Application logs
tail -f ~/Desktop/mdaitest/logs/backend.log
tail -f ~/Desktop/mdaitest/logs/frontend.log
tail -f ~/Desktop/mdaitest/logs/kiosk.log
tail -f ~/Desktop/mdaitest/logs/updater.log

# Systemd journal
journalctl --user -u mdai-backend.service -f
journalctl --user -u mdai-frontend.service -f
```

## Zero-Downtime Updates

### How It Works

1. Services start with existing code immediately on boot
2. Updater timer runs `git pull --ff-only` every 5 minutes
3. Backend: `uvicorn --reload` auto-reloads on Python changes
4. Frontend: Vite HMR updates browser instantly
5. **No service restarts, no downtime!**

### Manual Update

```bash
cd /home/ubuntu/Desktop/mdaitest
git pull --ff-only
# Services auto-reload automatically
```

### Update Dependencies

If `requirements.txt` or `package.json` change, the updater automatically:
- Runs `pip install` for backend
- Runs `npm install` for frontend

## Troubleshooting

### Services Won't Start

```bash
# Check status
systemctl --user status mdai-backend.service

# Check logs
journalctl --user -u mdai-backend.service -n 50

# Reset failed state
systemctl --user reset-failed

# Reload daemon
systemctl --user daemon-reload
```

### Services Don't Start on Boot

```bash
# Enable lingering
sudo loginctl enable-linger ubuntu

# Check lingering status
loginctl show-user ubuntu | grep Linger
```

### Chromium Won't Launch

```bash
# Check if display is available
echo $DISPLAY  # Should be :0

# Test manually
DISPLAY=:0 chromium-browser --kiosk http://localhost:3000
```

### Git Pull Fails

```bash
# Check upstream
cd /home/ubuntu/Desktop/mdaitest
git remote -v
git branch -vv

# Set upstream
git branch --set-upstream-to=origin/main main
```

## Documentation

- `../DEPLOYMENT.md` - Complete deployment guide
- `../QUICK_START.md` - 5-minute quickstart
- This file - Deployment scripts reference

## Support

Run `./check-status.sh` for a complete health check of your installation.


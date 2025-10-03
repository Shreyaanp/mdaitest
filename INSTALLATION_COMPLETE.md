# ✅ MDAI Kiosk Installation Complete!

**Date**: October 1, 2025  
**Status**: Services Installed & Configured  
**Next Step**: Start services and verify

---

## What Was Installed

### ✅ Service Files Installed

Location: `~/.config/systemd/user/`

- ✓ `mdai-backend.service` - FastAPI with autoreload (port :5000)
- ✓ `mdai-frontend.service` - Vite dev server with HMR (port :3000)
- ✓ `mdai-kiosk.service` - Chromium full-screen kiosk
- ✓ `mdai-updater.service` - Zero-downtime code updater
- ✓ `mdai-updater.timer` - Runs updates every 5 minutes

### ✅ Scripts Created

Location: `/home/ubuntu/Desktop/mdaitest/deployment/`

- ✓ `start-all.sh` - Start all services
- ✓ `check-status.sh` - Check service health
- ✓ `install-kiosk.sh` - Installer (already run)
- ✓ `uninstall-kiosk.sh` - Complete removal
- ✓ `cleanup-old-services.sh` - Manual cleanup
- ✓ `update-code.sh` - Zero-downtime updater
- ✓ `launch-kiosk.sh` - Kiosk launcher

### ✅ Old Services Cleaned Up

- Removed old `mdai-backend.service`
- Removed old `mdai-frontend.service`
- Removed old `mdai-kiosk.service`

### ✅ Documentation Created

- `DEPLOYMENT.md` - Complete deployment guide
- `QUICK_START.md` - 5-minute quickstart
- `deployment/README.md` - Scripts reference

---

## Next Steps (Run These Commands)

### 1. Start All Services

```bash
cd /home/ubuntu/Desktop/mdaitest/deployment
chmod +x *.sh  # Make all scripts executable
./start-all.sh
```

### 2. Check Status

```bash
./check-status.sh
```

### 3. Enable Lingering (For Boot Start)

```bash
sudo loginctl enable-linger ubuntu
```

### 4. Test the Kiosk

The kiosk service will start automatically when you login to the GUI. To test now:

```bash
# Make sure you're in a graphical session (DISPLAY=:0)
systemctl --user start mdai-kiosk.service
```

You should see Chromium launch in full-screen mode pointing to `http://localhost:3000`.

---

## Quick Verification

Run these commands to verify everything is working:

```bash
# Check if services are enabled
systemctl --user list-unit-files | grep mdai

# Check if services are running (after starting them)
systemctl --user list-units | grep mdai

# Test backend
curl http://localhost:5000/health
curl http://localhost:5000

# Test frontend
curl http://localhost:3000
```

---

## Architecture Overview

```
Boot
  ↓
GDM3 Autologin → Xorg :0
  ↓
Services Start:
  ├─→ Backend (FastAPI, :5000, autoreload)     [default.target]
  ├─→ Frontend (Vite, :3000, HMR)              [default.target]
  ├─→ Updater (git pull every 5 min)          [timer]
  └─→ Kiosk (Chromium full screen)            [graphical-session.target]
  ↓
Zero-downtime updates:
  - Git pull in background every 5 min
  - Backend auto-reloads on Python changes
  - Frontend HMRs on React changes
  - No service restarts needed!
```

---

## Service Startup Targets

- **Backend & Frontend**: Start with `default.target` (always running)
- **Kiosk**: Start with `graphical-session.target` (only when GUI available)
- **Updater**: Timer-based (every 5 minutes after boot)

---

## Configuration Status

### ✅ Configured

- Python virtual environment exists
- Node.js v22.20.0 detected and configured
- Frontend dependencies exist
- I²C group membership configured

### ⚠ Needs Manual Configuration

**GDM3 Autologin** (for automatic kiosk start on boot):

```bash
sudo tee /etc/gdm3/custom.conf > /dev/null <<'EOF'
[daemon]
AutomaticLoginEnable=True
AutomaticLogin=ubuntu
WaylandEnable=false
AutomaticLoginSession=gnome-xorg.desktop
DefaultSession=gnome-xorg.desktop
EOF

sudo systemctl restart gdm3

# Suppress desktop selection + GNOME tour prompts
sudo -u ubuntu /home/ubuntu/Desktop/mdaitest/scripts/configure-gdm-autologin.sh
# (Optional) Use a different session name if you ship another desktop.
# sudo -u ubuntu /home/ubuntu/Desktop/mdaitest/scripts/configure-gdm-autologin.sh ubuntu.desktop
```

**Lingering** (for services to start on boot without login):

```bash
sudo loginctl enable-linger ubuntu
```

---

## File Locations

### Service Files (Active)
```
~/.config/systemd/user/
├── mdai-backend.service
├── mdai-frontend.service
├── mdai-kiosk.service
├── mdai-updater.service
├── mdai-updater.timer
└── (symlinks in target directories)
```

### Service Templates (Source)
```
/home/ubuntu/Desktop/mdaitest/deployment/
├── mdai-backend.service
├── mdai-frontend.service
├── mdai-kiosk.service
├── mdai-updater.service
└── mdai-updater.timer
```

### Logs
```
/home/ubuntu/Desktop/mdaitest/logs/
├── backend.log
├── frontend.log
├── kiosk.log
└── updater.log
```

---

## Zero-Downtime Updates

### How It Works

1. **Services start immediately** on boot with existing code
2. **Updater runs every 5 minutes** in background
3. **Git pull --ff-only** safely fetches updates
4. **Backend auto-reloads** via uvicorn --reload
5. **Frontend HMRs** via Vite
6. **No service restarts, no downtime!**

### Manual Update

```bash
cd /home/ubuntu/Desktop/mdaitest
git pull --ff-only
# Services auto-reload automatically
```

---

## Troubleshooting

### Services Not Running?

```bash
# Start them
cd /home/ubuntu/Desktop/mdaitest/deployment
./start-all.sh

# Check status
./check-status.sh

# View logs
tail -f ~/Desktop/mdaitest/logs/backend.log
```

### Need More Help?

See the full documentation:
- `DEPLOYMENT.md` - Complete guide
- `QUICK_START.md` - Quick reference
- `deployment/README.md` - Scripts reference

---

## Summary

✅ **Installation Successful!**

All services are installed and ready to start. Run:

```bash
cd /home/ubuntu/Desktop/mdaitest/deployment
./start-all.sh
```

Then open a browser to `http://localhost:3000` or let the kiosk service launch it automatically!

🚀 Enjoy your zero-downtime, resilient RPi 5 kiosk!

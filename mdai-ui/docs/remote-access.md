# Remote Access Persistence

This document captures the steps we use on the Jetson to make NordVPN Meshnet and `x11vnc` resilient across reboots.

## NordVPN Meshnet

1. Ensure the NordVPN daemon is enabled at boot (the CLI falls back to the SysV init script if systemd D-Bus is unavailable in the current shell):

   ```bash
   systemctl enable nordvpnd 2>/dev/null || true
   service nordvpn start
   nordvpn status
   ```

2. Log in once if needed, then keep Meshnet on permanently:

   ```bash
   nordvpn login     # only if not already logged in
   nordvpn set meshnet on
   nordvpn meshnet peer list
   ```

3. Add a watchdog to auto-recover Meshnet if the daemon drops off. Drop the script below at `/usr/local/sbin/nordvpn-meshnet-ensure.sh` and make it executable:

   ```bash
   cat <<'SCRIPT' | sudo tee /usr/local/sbin/nordvpn-meshnet-ensure.sh >/dev/null
   #!/usr/bin/env bash
   set -euo pipefail

   if ! pgrep -x nordvpnd >/dev/null; then
     service nordvpn restart >/dev/null 2>&1 || service nordvpn start >/dev/null 2>&1 || true
     sleep 2
   fi

   if nordvpn status 2>/dev/null | grep -Fq "Meshnet: disabled"; then
     nordvpn set meshnet on >/dev/null 2>&1 || true
   fi
   SCRIPT

   sudo chmod 755 /usr/local/sbin/nordvpn-meshnet-ensure.sh
   ```

4. Pair the script with a systemd timer (`/etc/systemd/system/nordvpn-meshnet-ensure.timer`) so it runs every minute:

   ```ini
   [Unit]
   Description=Keep NordVPN Meshnet enabled

   [Timer]
   OnBootSec=1min
   OnUnitActiveSec=1min

   [Install]
   WantedBy=timers.target
   ```

   Create the matching service at `/etc/systemd/system/nordvpn-meshnet-ensure.service`:

   ```ini
   [Unit]
   Description=Ensure NordVPN Meshnet stays enabled

   [Service]
   Type=oneshot
   ExecStart=/usr/local/sbin/nordvpn-meshnet-ensure.sh
   ```

   Enable the timer (the command may warn about running in a chrooted shell, which is safe to ignore in this devbox environment):

   ```bash
   systemctl enable nordvpn-meshnet-ensure.timer
   systemctl start nordvpn-meshnet-ensure.timer 2>/dev/null || true
   ```

## x11vnc service

1. Ensure the control user owns a valid Xauthority file (the helper below will create one automatically if missing):

   ```bash
   cat <<'SCRIPT' | sudo tee /usr/local/sbin/x11vnc-ensure-xauth.sh >/dev/null
   #!/usr/bin/env bash
   set -euo pipefail

   XAUTH_FILE=/home/jetbot/.Xauthority

   if [ ! -f "$XAUTH_FILE" ]; then
     runuser -l jetbot -c 'touch ~/.Xauthority && xauth add :0 . $(mcookie)'
   fi

   chown jetbot:jetbot "$XAUTH_FILE"
   chmod 600 "$XAUTH_FILE"
   SCRIPT

   sudo chmod 755 /usr/local/sbin/x11vnc-ensure-xauth.sh
   ```

2. Drop the service file at `/etc/systemd/system/x11vnc.service`:

   ```ini
   [Unit]
   Description=x11vnc remote console
   After=display-manager.service network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   User=jetbot
   Environment=DISPLAY=:0
   Environment=XAUTHORITY=/home/jetbot/.Xauthority
   ExecStartPre=/usr/local/sbin/x11vnc-ensure-xauth.sh
   ExecStart=/usr/bin/x11vnc -display :0 -auth /home/jetbot/.Xauthority -forever -loop -nopw -xdamage -ncache 10 -shared -rfbport 5900
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

   Adjust `User=` if the desktop session runs under another account.

3. Enable at boot and start immediately (again, `systemctl` may warn about the chrooted shell; the enable step still lays down the symlink):

   ```bash
   systemctl enable x11vnc.service
   systemctl start x11vnc.service 2>/dev/null || runuser -l jetbot -c '/usr/bin/x11vnc -display :0 -auth /home/jetbot/.Xauthority -forever -loop -nopw -xdamage -ncache 10 -shared -rfbport 5900'
   ```

4. Confirm reachability from the laptop once Meshnet is up:

   ```bash
   nc -zv support-sutton7163.nord 22
   nc -zv support-sutton7163.nord 5900
   nordvpn meshnet peer list
   ```

With Meshnet active and `x11vnc` managed by systemd, VNC/SSH access will survive reboots and temporary link drops.

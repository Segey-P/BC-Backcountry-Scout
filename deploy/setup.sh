#!/usr/bin/env bash
# Oracle Cloud Always-Free ARM VM setup for BC Backcountry Scout.
# Run once as the ubuntu user after provisioning the VM.
# Usage: bash setup.sh
set -euo pipefail

REPO_URL="https://github.com/Segey-P/bc-backcountry-scout.git"
INSTALL_DIR="$HOME/bc-backcountry-scout"
SERVICE_NAME="bcscout"
SERVICE_FILE="$INSTALL_DIR/deploy/bcscout.service"
SYSTEMD_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

echo "=== BC Backcountry Scout — VM Setup ==="

# 1. System packages
echo "[1/7] Installing system packages…"
sudo apt-get update -qq
sudo apt-get install -y -qq python3.11 python3.11-venv python3-pip git

# 2. Clone or update repo
echo "[2/7] Cloning repository…"
if [ -d "$INSTALL_DIR/.git" ]; then
    git -C "$INSTALL_DIR" pull --ff-only
else
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# 3. Create virtual environment
echo "[3/7] Creating Python virtual environment…"
python3.11 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# 4. Ensure .env exists
echo "[4/7] Checking .env…"
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    echo ""
    echo "  *** ACTION REQUIRED ***"
    echo "  Edit $INSTALL_DIR/.env and set TELEGRAM_BOT_TOKEN before starting the service."
    echo "  Run: nano $INSTALL_DIR/.env"
    echo ""
fi

# 5. Install systemd service
echo "[5/7] Installing systemd service…"
sudo cp "$SERVICE_FILE" "$SYSTEMD_PATH"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

# 6. Set up log rotation
echo "[6/7] Configuring log rotation…"
sudo tee /etc/logrotate.d/bcscout > /dev/null <<'EOF'
/var/log/journal/bcscout.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
}
EOF

# 7. Start service (only if .env is populated)
echo "[7/7] Checking token before starting service…"
if grep -q "your-telegram-bot-token-here" "$INSTALL_DIR/.env" 2>/dev/null; then
    echo ""
    echo "  Token not set — skipping service start."
    echo "  After editing .env, run:"
    echo "    sudo systemctl start $SERVICE_NAME"
    echo "    sudo systemctl status $SERVICE_NAME"
else
    sudo systemctl start "$SERVICE_NAME"
    echo ""
    echo "  Service started. Check status:"
    echo "    sudo systemctl status $SERVICE_NAME"
    echo "    journalctl -u $SERVICE_NAME -f"
fi

echo ""
echo "=== Setup complete ==="

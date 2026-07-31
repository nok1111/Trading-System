#!/bin/bash
# Deploy script for Binance VPS Proxy
# Run on the VPS: bash deploy.sh

set -e

PROXY_DIR="/opt/binance-proxy"
PROXY_TOKEN="${PROXY_TOKEN:-}"

if [ -z "$PROXY_TOKEN" ]; then
    echo "ERROR: Set PROXY_TOKEN environment variable first."
    echo "  export PROXY_TOKEN=$(openssl rand -hex 32)"
    echo "  Then re-run this script."
    exit 1
fi

echo "=== Binance VPS Proxy Deployment ==="

# Create directory
sudo mkdir -p "$PROXY_DIR"
sudo chown -R $(whoami) "$PROXY_DIR"

# Copy files
cp main.py "$PROXY_DIR/"
cp requirements.txt "$PROXY_DIR/"

# Create venv
cd "$PROXY_DIR"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create systemd service
cat > /etc/systemd/system/binance-proxy.service << EOF
[Unit]
Description=Binance VPS Proxy
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$PROXY_DIR
Environment=PROXY_TOKEN=$PROXY_TOKEN
ExecStart=$PROXY_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 9100
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable binance-proxy
sudo systemctl restart binance-proxy

echo ""
echo "=== Deployment complete ==="
echo "Proxy running on port 9100"
echo "Health check: curl http://localhost:9100/health"
echo ""
echo "IMPORTANT: Open port 9100 in your firewall:"
echo "  sudo ufw allow 9100/tcp"
echo ""
echo "PROXY_TOKEN (save this, needed by client):"
echo "  $PROXY_TOKEN"

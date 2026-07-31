"""Deploy script: SSH into VPS and run deployment commands."""
import paramiko
import sys
import time

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"
REPO_PATH = "/opt/trading-system"

def run_remote(ssh, cmd, timeout=120):
    """Run a command on the remote server and print output."""
    print(f"\n{'='*60}")
    print(f">>> {cmd}")
    print(f"{'='*60}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(f"[stderr] {err}")
    print(f"[exit code: {exit_code}]")
    return exit_code, out, err

def main():
    print(f"Connecting to {USER}@{HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    print("Connected!\n")

    # Step 1: Check current state
    run_remote(ssh, "uname -a")
    run_remote(ssh, "which python3 && python3 --version")
    run_remote(ssh, "which docker && docker --version 2>/dev/null || echo 'no docker'")
    run_remote(ssh, "which git && git --version")

    # Step 2: Check repo exists
    code, out, _ = run_remote(ssh, f"ls -la {REPO_PATH}/.git 2>/dev/null && echo 'REPO_EXISTS' || echo 'NO_REPO'")
    repo_exists = "REPO_EXISTS" in out

    if not repo_exists:
        print(f"\nRepo not found at {REPO_PATH}. Cloning...")
        run_remote(ssh, f"git clone https://github.com/nok1111/Trading-System.git {REPO_PATH}")
    else:
        print(f"\nRepo found at {REPO_PATH}. Pulling latest...")

    # Step 3: Git pull
    run_remote(ssh, f"cd {REPO_PATH} && git fetch origin main")
    code, out, err = run_remote(ssh, f"cd {REPO_PATH} && git pull origin main 2>&1")

    # Check if trading-client is a subdirectory
    code, out, _ = run_remote(ssh, f"ls {REPO_PATH}/trading-client/proxy/main.py 2>/dev/null && echo 'PROXY_EXISTS' || echo 'NO_PROXY'")
    if "PROXY_EXISTS" not in out:
        # Maybe the repo structure is different, check
        code, out, _ = run_remote(ssh, f"ls {REPO_PATH}/proxy/main.py 2>/dev/null && echo 'PROXY_EXISTS' || echo 'NO_PROXY'")
        if "PROXY_EXISTS" in out:
            client_path = REPO_PATH
        else:
            code, out, _ = run_remote(ssh, f"find {REPO_PATH} -name 'main.py' -path '*/proxy/*' 2>/dev/null | head -5")
            print(f"Searching for proxy/main.py: {out}")
            client_path = REPO_PATH
    else:
        client_path = f"{REPO_PATH}/trading-client"

    print(f"\nClient path: {client_path}")

    # Step 4: Deploy the proxy
    print("\n\n========== DEPLOYING PROXY ==========")
    proxy_path = f"{client_path}/proxy"

    # Generate a token
    code, out, _ = run_remote(ssh, "openssl rand -hex 32")
    proxy_token = out.strip()
    print(f"\nGenerated PROXY_TOKEN: {proxy_token}")

    # Install proxy dependencies
    run_remote(ssh, f"cd {proxy_path} && python3 -m venv /opt/binance-proxy-venv && /opt/binance-proxy-venv/bin/pip install -r requirements.txt 2>&1")

    # Create systemd service
    service_content = f"""[Unit]
Description=Binance VPS Proxy
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={proxy_path}
Environment=PROXY_TOKEN={proxy_token}
ExecStart=/opt/binance-proxy-venv/bin/uvicorn main:app --host 0.0.0.0 --port 9100
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    run_remote(ssh, f"cat > /etc/systemd/system/binance-proxy.service << 'SERVICEEOF'\n{service_content}\nSERVICEOF")

    # Reload and start
    run_remote(ssh, "systemctl daemon-reload")
    run_remote(ssh, "systemctl enable binance-proxy")
    run_remote(ssh, "systemctl restart binance-proxy")
    time.sleep(2)

    # Check proxy health
    run_remote(ssh, "curl -s http://localhost:9100/health || echo 'PROXY NOT RESPONDING'")

    # Open firewall
    run_remote(ssh, "ufw allow 9100/tcp 2>/dev/null || iptables -I INPUT -p tcp --dport 9100 -j ACCEPT 2>/dev/null || echo 'firewall: no action needed'")

    # Step 5: Restart trading-client (docker)
    print("\n\n========== RESTARTING TRADING CLIENT ==========")
    code, out, _ = run_remote(ssh, f"ls {client_path}/docker-compose.yml 2>/dev/null && echo 'HAS_DOCKER' || echo 'NO_DOCKER'")
    if "HAS_DOCKER" in out:
        run_remote(ssh, f"cd {client_path} && docker-compose down 2>&1")
        run_remote(ssh, f"cd {client_path} && docker-compose build 2>&1", timeout=300)
        run_remote(ssh, f"cd {client_path} && docker-compose up -d 2>&1")
        time.sleep(3)
        run_remote(ssh, "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'")
    else:
        print("No docker-compose found. Checking if trading-client runs as systemd service...")
        run_remote(ssh, "systemctl list-units --type=service | grep -i 'trading\|client\|uvicorn' || echo 'no trading service found'")
        run_remote(ssh, "ps aux | grep uvicorn | grep -v grep")

    # Step 6: Restart auth server
    print("\n\n========== RESTARTING AUTH SERVER ==========")
    # Check if auth-server is a systemd service
    code, out, _ = run_remote(ssh, "systemctl list-units --type=service | grep -i 'auth\|ai-server' || echo 'no auth service'")
    if "no auth service" in out:
        # Maybe docker
        code, out, _ = run_remote(ssh, "docker ps --format '{{.Names}}' | grep -i 'auth\|ai-server' || echo 'no auth docker'")
        if "no auth docker" not in out:
            run_remote(ssh, "docker restart $(docker ps --format '{{.Names}}' | grep -i 'auth\|ai-server')")
        else:
            # Check what's running on port 8000
            run_remote(ssh, "ss -tlnp | grep 8000 || echo 'nothing on port 8000'")
    else:
        run_remote(ssh, "systemctl restart auth-server 2>/dev/null || systemctl restart ai-server 2>/dev/null || echo 'could not restart auth'")

    # Step 7: Final verification
    print("\n\n========== FINAL VERIFICATION ==========")
    time.sleep(3)
    run_remote(ssh, "curl -s http://localhost:8000/health 2>/dev/null || echo 'AUTH SERVER NOT RESPONDING'")
    run_remote(ssh, "curl -s http://localhost:8080/health 2>/dev/null || echo 'TRADING CLIENT NOT RESPONDING'")
    run_remote(ssh, "curl -s http://localhost:9100/health 2>/dev/null || echo 'PROXY NOT RESPONDING'")

    # Save the token for the user
    print(f"\n\n{'='*60}")
    print(f"PROXY TOKEN (save this for the Electron app):")
    print(f"  {proxy_token}")
    print(f"{'='*60}")

    ssh.close()
    print("\nDone!")

if __name__ == "__main__":
    main()

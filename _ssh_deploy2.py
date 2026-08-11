import paramiko
import sys
import secrets
import string
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('76.13.180.80', username='root', password='6yfRBK?t;9+u/eQd', timeout=15)

def run_cmd(cmd, timeout=60):
    print(f'>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if out:
        sys.stdout.buffer.write(out.encode('utf-8', errors='replace'))
        sys.stdout.buffer.write(b'\n')
    if err:
        sys.stdout.buffer.write(b'STDERR: ')
        sys.stdout.buffer.write(err.encode('utf-8', errors='replace'))
        sys.stdout.buffer.write(b'\n')
    sys.stdout.buffer.write(f'[exit: {exit_code}]\n'.encode())
    sys.stdout.buffer.write(b'\n')
    sys.stdout.buffer.flush()
    return exit_code

# Generate secure secrets
jwt_secret = secrets.token_urlsafe(48)
hmac_secret = secrets.token_urlsafe(48)
print(f"Generated JWT_SECRET (len={len(jwt_secret)})")
print(f"Generated HMAC_SECRET (len={len(hmac_secret)})")
print()

# STEP 1: Pull latest code (includes build_strategy fix)
print("=" * 60)
print("STEP 1: Pull latest code")
print("=" * 60)
run_cmd('cd /opt/trading-system && git pull origin main', timeout=60)
run_cmd('cd /opt/trading-system && git log --oneline -3')

# STEP 2: Update .env files with real secrets
# Use a Python script on the server to safely update .env files
print("=" * 60)
print("STEP 2: Update .env files with secure secrets")
print("=" * 60)

update_script = f'''
import os, re, sys

JWT_SECRET = "{jwt_secret}"
HMAC_SECRET = "{hmac_secret}"
CORS_ORIGINS = "https://alvora.app,https://www.alvora.app,http://localhost:5173,http://localhost:1420,http://localhost:8080"

def update_env_file(path, updates):
    if not os.path.exists(path):
        print(f"  {{path}} does not exist, skipping")
        return
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    found = {{}}
    new_lines = []
    for line in lines:
        for key, val in updates.items():
            if line.startswith(f"{{key}}="):
                new_lines.append(f"{{key}}={{val}}\\n")
                found[key] = True
                break
        else:
            new_lines.append(line)
    for key, val in updates.items():
        if key not in found:
            new_lines.append(f"{{key}}={{val}}\\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(f"  Updated {{path}}: {{list(updates.keys())}}")

# Auth server
update_env_file("/opt/trading-system/auth-server/.env", {{
    "JWT_SECRET": JWT_SECRET,
    "CORS_ORIGINS": CORS_ORIGINS,
}})

# AI server
update_env_file("/opt/trading-system/ai-server/.env", {{
    "HMAC_SECRET": HMAC_SECRET,
    "JWT_SECRET": JWT_SECRET,
}})

# Trading client (needs JWT_SECRET for validation if any)
update_env_file("/opt/trading-system/trading-client/.env", {{
    "JWT_SECRET": JWT_SECRET,
}})

print("Done updating .env files")
'''

# Write the script to server and run it
run_cmd(f'cd /tmp && cat > _update_envs.py << \'PYEOF\'\n{update_script}\nPYEOF\npython3 _update_envs.py')

# Verify the updates (mask values)
print("=" * 60)
print("STEP 3: Verify .env updates")
print("=" * 60)
run_cmd('grep -E "^(JWT_SECRET|CORS_ORIGINS)" /opt/trading-system/auth-server/.env | sed -E "s/=(.{8}).*/=\\1.../" ')
run_cmd('grep -E "^(HMAC_SECRET|JWT_SECRET)" /opt/trading-system/ai-server/.env | sed -E "s/=(.{8}).*/=\\1.../" ')
run_cmd('grep -E "^JWT_SECRET" /opt/trading-system/trading-client/.env | sed -E "s/=(.{8}).*/=\\1.../" ')

# STEP 4: Restart services
print("=" * 60)
print("STEP 4: Restart auth-server")
print("=" * 60)
run_cmd('systemctl restart auth-server.service', timeout=15)
time.sleep(4)
run_cmd('systemctl is-active auth-server.service')
run_cmd('journalctl -u auth-server.service --no-pager -n 8 --since "30 seconds ago" 2>/dev/null || true')

print("=" * 60)
print("STEP 5: Restart ai-server")
print("=" * 60)
run_cmd('systemctl restart ai-server.service', timeout=15)
time.sleep(4)
run_cmd('systemctl is-active ai-server.service')
run_cmd('journalctl -u ai-server.service --no-pager -n 8 --since "30 seconds ago" 2>/dev/null || true')

print("=" * 60)
print("STEP 6: Restart trading-system")
print("=" * 60)
run_cmd('systemctl restart trading-system.service', timeout=15)
time.sleep(5)
run_cmd('systemctl is-active trading-system.service')
run_cmd('journalctl -u trading-system.service --no-pager -n 12 --since "30 seconds ago" 2>/dev/null || true')

# STEP 5: Final status
print("=" * 60)
print("STEP 7: Final status check")
print("=" * 60)
run_cmd('systemctl list-units --type=service --state=running | grep -iE "trading|auth|ai|omniroute|postgres"')
run_cmd('curl -s -o /dev/null -w "trading-system(8080): %{http_code}\\n" http://localhost:8080/ 2>/dev/null || echo "trading-system: no response"')
run_cmd('curl -s -o /dev/null -w "auth-server(8000): %{http_code}\\n" http://localhost:8000/health 2>/dev/null || echo "auth-server: no response"')
run_cmd('curl -s -o /dev/null -w "ai-server(8001): %{http_code}\\n" http://localhost:8001/ 2>/dev/null || echo "ai-server: no response"')

# Cleanup
run_cmd('rm -f /tmp/_update_envs.py')

ssh.close()
print("\nDeploy complete!")

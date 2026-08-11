import paramiko
import sys
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

# Update CORS_ORIGINS in ai-server .env
print("=" * 60)
print("STEP 1: Update CORS_ORIGINS in ai-server .env")
print("=" * 60)
update_cmd = '''python3 -c "
import os
path = '/opt/trading-system/ai-server/.env'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
new_lines = []
found = False
for line in lines:
    if line.startswith('CORS_ORIGINS='):
        new_lines.append('CORS_ORIGINS=https://alvora.app,https://www.alvora.app,http://localhost:5173,http://localhost:1420,http://localhost:8080\\n')
        found = True
    else:
        new_lines.append(line)
if not found:
    new_lines.append('CORS_ORIGINS=https://alvora.app,https://www.alvora.app,http://localhost:5173,http://localhost:1420,http://localhost:8080\\n')
with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('Updated CORS_ORIGINS in ai-server .env')
"'''
run_cmd(update_cmd)

# Verify
run_cmd('grep "^CORS_ORIGINS" /opt/trading-system/ai-server/.env | sed -E "s/=(.{20}).*/=\\1.../"')

# Restart ai-server
print("=" * 60)
print("STEP 2: Restart ai-server")
print("=" * 60)
run_cmd('systemctl restart ai-server.service', timeout=15)
time.sleep(5)
run_cmd('systemctl is-active ai-server.service')
run_cmd('journalctl -u ai-server.service --no-pager -n 10 --since "30 seconds ago" 2>/dev/null || true')

# Final check all services
print("=" * 60)
print("STEP 3: Final status of all services")
print("=" * 60)
run_cmd('systemctl list-units --type=service --state=running | grep -iE "trading|auth|ai|omniroute|postgres"')
run_cmd('curl -s -o /dev/null -w "trading-system(8080): %{http_code}\\n" http://localhost:8080/ 2>/dev/null || echo "trading-system: no response"')
run_cmd('curl -s -o /dev/null -w "auth-server(8000): %{http_code}\\n" http://localhost:8000/health 2>/dev/null || echo "auth-server: no response"')
run_cmd('curl -s -o /dev/null -w "ai-server(8001): %{http_code}\\n" http://localhost:8001/ 2>/dev/null || echo "ai-server: no response"')

ssh.close()
print("\nDone!")

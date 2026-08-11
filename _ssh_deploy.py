import paramiko
import sys
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('76.13.180.80', username='root', password='6yfRBK?t;9+u/eQd', timeout=15)

def run_cmd(cmd, timeout=60):
    print(f'>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    exit_code = stdout.channel.recv_exit_status()
    if out:
        print(out.strip())
    if err:
        print(f'STDERR: {err.strip()}')
    print(f'[exit: {exit_code}]')
    print()
    return exit_code

# 1. Check for local changes before pulling
print("=" * 60)
print("STEP 1: Check server git status")
print("=" * 60)
run_cmd('cd /opt/trading-system && git status --short')
run_cmd('cd /opt/trading-system && git stash list')

# 2. Pull latest code
print("=" * 60)
print("STEP 2: Pull latest code from GitHub")
print("=" * 60)
run_cmd('cd /opt/trading-system && git pull origin main', timeout=60)

# 3. Verify new commits
print("=" * 60)
print("STEP 3: Verify new code")
print("=" * 60)
run_cmd('cd /opt/trading-system && git log --oneline -5')

# 4. Check if new dependencies needed
print("=" * 60)
print("STEP 4: Check dependencies")
print("=" * 60)
# trading-client
run_cmd('cd /opt/trading-system && /opt/trading-system/venv/bin/pip install -r requirements.txt --quiet 2>&1 | tail -3', timeout=120)
# auth-server
run_cmd('cd /opt/trading-system/auth-server && /opt/trading-system/auth-server/.venv/bin/pip install -r requirements.txt --quiet 2>&1 | tail -3', timeout=120)
# ai-server
run_cmd('cd /opt/trading-system/ai-server && /opt/trading-system/ai-server/.venv/bin/pip install -r requirements.txt --quiet 2>&1 | tail -3', timeout=120)

# 5. Create new database tables (for HmacNonce)
print("=" * 60)
print("STEP 5: Database - create new tables")
print("=" * 60)
run_cmd('cd /opt/trading-system/ai-server && /opt/trading-system/ai-server/.venv/bin/python -c "from app.database.base import Base, engine; Base.metadata.create_all(engine); print(\'Tables created\')"', timeout=30)

ssh.close()
print("Pre-deploy checks complete. Ready for service restart.")

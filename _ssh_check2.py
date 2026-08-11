import paramiko
import sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('76.13.180.80', username='root', password='6yfRBK?t;9+u/eQd', timeout=15)

commands = [
    'cd /opt/trading-system && git remote -v && git branch && git log --oneline -3',
    'cd /opt/trading-system && git status --short | head -20',
    'systemctl cat trading-system.service 2>/dev/null | head -20',
    'systemctl cat auth-server.service 2>/dev/null | head -20',
    'systemctl cat ai-server.service 2>/dev/null | head -20',
    'cd /opt/trading-system && cat .env 2>/dev/null | grep -iE "DATABASE_URL|APP_ENV|TRADING_MODE" | head -5',
]

for cmd in commands:
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    print(f'=== {cmd} ===')
    if out:
        print(out.strip())
    if err:
        print(f'STDERR: {err.strip()}')
    print()

ssh.close()
print("Done")

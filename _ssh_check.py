import paramiko
import sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect('76.13.180.80', username='root', password='6yfRBK?t;9+u/eQd', timeout=15)
except Exception as e:
    print(f"Connection failed: {e}")
    sys.exit(1)

commands = [
    'hostname',
    'uname -a',
    'ls /root/',
    'ls /opt/',
    'ls /home/',
    'docker ps 2>/dev/null || echo "no docker"',
    'systemctl list-units --type=service --state=running 2>/dev/null | grep -iE "trading|auth|ai|uvicorn|gunicorn|nginx" || echo "no matching services"',
    'find / -maxdepth 3 -name "*.py" -path "*/trading*" 2>/dev/null | head -5',
    'find / -maxdepth 3 -name "*.py" -path "*/auth*" 2>/dev/null | head -5',
    'find / -maxdepth 3 -name "*.py" -path "*/ai-server*" 2>/dev/null | head -5',
    'ps aux | grep -iE "uvicorn|gunicorn|python" | grep -v grep',
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

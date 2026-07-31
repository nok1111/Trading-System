import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

cmd = """cd /opt/trading-system && source venv/bin/activate && python3 -c "
import sys
print('Python path:', sys.path[:5])
import os
print('CWD:', os.getcwd())
# Check what app modules exist
try:
    import app
    print('app location:', app.__file__)
except:
    print('app not found as module')

# List database models
models_dir = os.path.join(os.path.dirname(app.__file__), 'database', 'models')
if os.path.isdir(models_dir):
    print('Models:', os.listdir(models_dir))
"
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
out = stdout.read().decode().strip()
err = stderr.read().decode().strip()
if out:
    print(out)
if err:
    print(f"STDERR: {err}")
ssh.close()

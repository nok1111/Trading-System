import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

# Read the script content
with open("check_via_api2.py", "r") as f:
    script_content = f.read()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

sftp = ssh.open_sftp()
with sftp.file("/tmp/check_keys.py", "w") as f:
    f.write(script_content)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("cd /opt/trading-system && source venv/bin/activate && python3 /tmp/check_keys.py", timeout=30)
out = stdout.read().decode().strip()
err = stderr.read().decode().strip()
if out:
    print(out)
if err:
    print(f"STDERR: {err}")
ssh.close()

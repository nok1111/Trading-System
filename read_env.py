"""Read .env from VPS."""
import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

stdin, stdout, stderr = ssh.exec_command("cat /opt/trading-system/.env", timeout=15)
print(stdout.read().decode())

ssh.close()

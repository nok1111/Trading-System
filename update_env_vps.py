"""Update .env on VPS to use PostgreSQL."""
import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

NEW_DB_URL = "postgresql+psycopg2://trading_app:Tr4d1ngApp2026!@localhost:5432/trading_system"

commands = [
    # Backup current .env
    "cp /opt/trading-system/.env /opt/trading-system/.env.bak",
    # Replace DATABASE_URL line
    f"""sed -i 's|^DATABASE_URL=.*|DATABASE_URL={NEW_DB_URL}|' /opt/trading-system/.env""",
    # Verify
    "grep DATABASE_URL /opt/trading-system/.env",
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

for cmd in commands:
    print(f"\n>>> {cmd[:80]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")

ssh.close()
print("\nDone!")

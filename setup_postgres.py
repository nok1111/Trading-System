"""Install and configure PostgreSQL on the VPS."""
import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

DB_NAME = "trading_system"
DB_USER = "trading_app"
DB_PASS = "Tr4d1ngApp2026!"

commands = [
    # Check if PostgreSQL is already installed
    "which psql && psql --version || echo 'NOT_INSTALLED'",
    # Install PostgreSQL
    "apt-get update -qq && apt-get install -y -qq postgresql postgresql-contrib 2>&1 | tail -5",
    # Start and enable PostgreSQL
    "systemctl start postgresql && systemctl enable postgresql",
    "systemctl is-active postgresql",
    # Create database and user
    f"""sudo -u postgres psql -c "CREATE USER {DB_USER} WITH PASSWORD '{DB_PASS}';" 2>/dev/null || echo 'User may already exist'""",
    f"""sudo -u postgres psql -c "CREATE DATABASE {DB_NAME} OWNER {DB_USER};" 2>/dev/null || echo 'DB may already exist'""",
    f"""sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE {DB_NAME} TO {DB_USER};" 2>/dev/null || true""",
    f"""sudo -u postgres psql -c "ALTER USER {DB_USER} WITH SUPERUSER;" 2>/dev/null || true""",
    # Configure pg_hba.conf for local connections with password
    """PG_HBA=$(find /etc/postgresql -name pg_hba.conf 2>/dev/null | head -1) && echo "Found: $PG_HBA" && sed -i 's/local   all             all                                     peer/local   all             all                                     md5/' "$PG_HBA" && sed -i 's/host    all             all             127.0.0.1\\/32            scram-sha-256/host    all             all             127.0.0.1\\/32            md5/' "$PG_HBA" && systemctl restart postgresql""",
    # Test connection
    f"""PGPASSWORD={DB_PASS} psql -U {DB_USER} -d {DB_NAME} -c "SELECT version();" 2>&1""",
    # Show current DATABASE_URL in .env
    "grep DATABASE_URL /opt/trading-system/trading-client/.env 2>/dev/null || echo 'No .env found'",
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

for cmd in commands:
    print(f"\n>>> {cmd[:80]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")

ssh.close()
print("\nDone!")

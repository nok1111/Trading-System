"""Fix PostgreSQL sequences after SQLite migration — sync auto-increment with max ID."""
import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

# SQL to fix all sequences
FIX_SQL = """
DO $$
DECLARE
    r RECORD;
    max_id BIGINT;
    seq_name TEXT;
BEGIN
    FOR r IN
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND column_name = 'id'
        AND data_type = 'integer'
    LOOP
        seq_name := r.table_name || '_id_seq';
        EXECUTE format('SELECT COALESCE(MAX(id), 0) FROM %I', r.table_name) INTO max_id;
        IF max_id > 0 THEN
            EXECUTE format('SELECT setval(%L, %s)', seq_name, max_id);
            RAISE NOTICE 'Fixed %: set to %', seq_name, max_id;
        END IF;
    END LOOP;
END $$;
"""

commands = [
    # Pull latest code
    "cd /opt/trading-system && git pull origin main",
    # Fix sequences
    f"PGPASSWORD=Tr4d1ngApp2026! psql -U trading_app -d trading_system -c \"{FIX_SQL}\" 2>&1",
    # Restart service
    "systemctl restart trading-system",
    "sleep 3",
    "systemctl is-active trading-system",
    "curl -s http://localhost:8080/health",
    # Check for errors in logs after restart
    "journalctl -u trading-system --no-pager -n 30 2>&1 | grep -i 'error\\|fail\\|traceback' | tail -10",
    # Test news fetcher (trigger scheduler run)
    "curl -s http://localhost:8080/api/intelligence/scheduler/status -H 'Authorization: Bearer dummy' 2>&1 | head -5",
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

for cmd in commands:
    print(f"\n>>> {cmd[:100]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")

ssh.close()
print("\nDone!")

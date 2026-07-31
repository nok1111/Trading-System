"""Fix PostgreSQL sequences — write SQL to file on VPS then execute."""
import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

SQL_CONTENT = """DO $$
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

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

# Write SQL file to VPS
sftp = ssh.open_sftp()
with sftp.file("/tmp/fix_sequences.sql", "w") as f:
    f.write(SQL_CONTENT)
sftp.close()

commands = [
    # Execute SQL file
    "PGPASSWORD=Tr4d1ngApp2026! psql -U trading_app -d trading_system -f /tmp/fix_sequences.sql 2>&1",
    # Verify: check current sequence value for intelligence_news
    "PGPASSWORD=Tr4d1ngApp2026! psql -U trading_app -d trading_system -c \"SELECT last_value FROM intelligence_news_id_seq;\" 2>&1",
    # Restart service
    "systemctl restart trading-system",
    "sleep 5",
    "systemctl is-active trading-system",
    "curl -s http://localhost:8080/health",
    # Check for errors after restart
    "journalctl -u trading-system --no-pager -n 30 2>&1 | grep -i 'error\\|fail\\|traceback' | tail -10",
    # Wait for news fetcher to run and check
    "sleep 10",
    "journalctl -u trading-system --no-pager -n 20 2>&1 | grep -i 'news\\|cleanup' | tail -10",
]

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

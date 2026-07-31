"""Comprehensive verification of Fase 1-3 on VPS."""
import paramiko
import json

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

# ============================================================
# 1. Service health
# ============================================================
print("=" * 70)
print("1. SERVICE HEALTH")
print("=" * 70)
for port, name in [(8080, "trading-system"), (9100, "binance-proxy"), (8000, "auth-server")]:
    cmd = f"curl -s http://localhost:{port}/health"
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    out = stdout.read().decode().strip()
    print(f"  [{name}] port {port}: {out}")

# ============================================================
# 2. PostgreSQL table counts
# ============================================================
print("\n" + "=" * 70)
print("2. POSTGRESQL TABLE ROW COUNTS")
print("=" * 70)
cmd = """PGPASSWORD=Tr4d1ngApp2026! psql -U trading_app -d trading_system -t -c "
SELECT relname, n_live_tup 
FROM pg_stat_user_tables 
ORDER BY relname;" 2>&1"""
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
print(stdout.read().decode().strip())

# ============================================================
# 3. Check user_id columns exist on all 9 migrated tables
# ============================================================
print("\n" + "=" * 70)
print("3. USER_ID COLUMN VERIFICATION")
print("=" * 70)
cmd = """PGPASSWORD=Tr4d1ngApp2026! psql -U trading_app -d trading_system -t -c "
SELECT table_name, column_name 
FROM information_schema.columns 
WHERE column_name = 'user_id' 
AND table_schema = 'public'
ORDER BY table_name;" 2>&1"""
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
print(stdout.read().decode().strip())

# ============================================================
# 4. Check .env DATABASE_URL
# ============================================================
print("\n" + "=" * 70)
print("4. ENV CONFIGURATION")
print("=" * 70)
cmd = "grep DATABASE_URL /opt/trading-system/.env"
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
print(stdout.read().decode().strip())

# ============================================================
# 5. Check backup exists
# ============================================================
print("\n" + "=" * 70)
print("5. BACKUP VERIFICATION")
print("=" * 70)
cmd = "ls -lh /opt/backups/postgresql/ 2>&1"
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
print(stdout.read().decode().strip())

cmd = "crontab -l | grep pg_backup"
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
print(f"  Cron: {stdout.read().decode().strip()}")

# ============================================================
# 6. Check recent service logs for errors
# ============================================================
print("\n" + "=" * 70)
print("6. RECENT SERVICE LOGS (last 30 lines, errors/warnings)")
print("=" * 70)
cmd = "journalctl -u trading-system --no-pager -n 100 2>&1 | grep -i 'error\\|warning\\|fail\\|traceback' | tail -15"
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
out = stdout.read().decode().strip()
if out:
    print(out)
else:
    print("  No errors/warnings found in recent logs")

# ============================================================
# 7. Check intelligence scheduler status
# ============================================================
print("\n" + "=" * 70)
print("7. INTELLIGENCE SCHEDULER STATUS")
print("=" * 70)
cmd = "curl -s http://localhost:8080/api/intelligence/scheduler/status"
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
out = stdout.read().decode().strip()
try:
    data = json.loads(out)
    for k, v in data.items():
        print(f"  {k}: {v}")
except Exception:
    print(f"  {out}")

# ============================================================
# 8. Check cleanup ran
# ============================================================
print("\n" + "=" * 70)
print("8. CLEANUP LOG CHECK")
print("=" * 70)
cmd = "journalctl -u trading-system --no-pager -n 200 2>&1 | grep -i 'cleanup' | tail -10"
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
out = stdout.read().decode().strip()
if out:
    print(out)
else:
    print("  No cleanup logs yet (runs every 24h)")

# ============================================================
# 9. PostgreSQL connection pool health
# ============================================================
print("\n" + "=" * 70)
print("9. POSTGRESQL CONNECTION STATS")
print("=" * 70)
cmd = """PGPASSWORD=Tr4d1ngApp2026! psql -U trading_app -d trading_system -t -c "
SELECT state, count(*) FROM pg_stat_activity WHERE datname='trading_system' GROUP BY state;" 2>&1"""
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
print(stdout.read().decode().strip())

# ============================================================
# 10. Disk usage
# ============================================================
print("\n" + "=" * 70)
print("10. DISK USAGE")
print("=" * 70)
cmd = "df -h / | tail -1"
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
print(f"  {stdout.read().decode().strip()}")

cmd = "du -sh /opt/backups/postgresql/ 2>/dev/null"
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
print(f"  Backups: {stdout.read().decode().strip()}")

ssh.close()
print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)

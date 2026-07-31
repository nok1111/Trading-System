"""Set up backup cron and verify Fase 3 tables on VPS."""
import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

commands = [
    # Make backup script executable
    "chmod +x /opt/trading-system/trading-client/scripts/pg_backup.sh",
    # Add cron job for daily backup at 3am
    "(crontab -l 2>/dev/null | grep -v pg_backup; echo '0 3 * * * /opt/trading-system/trading-client/scripts/pg_backup.sh >> /var/log/pg_backup.log 2>&1') | crontab -",
    # Verify cron
    "crontab -l | grep pg_backup",
    # Run first backup manually
    "/opt/trading-system/trading-client/scripts/pg_backup.sh 2>&1",
    # Check new tables
    "PGPASSWORD=Tr4d1ngApp2026! psql -U trading_app -d trading_system -c \"SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN ('user_preferences','watchlists');\" 2>&1",
    # Full table list
    "PGPASSWORD=Tr4d1ngApp2026! psql -U trading_app -d trading_system -c '\\dt' 2>&1",
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

for cmd in commands:
    print(f"\n>>> {cmd[:80]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")

ssh.close()
print("\nDone!")

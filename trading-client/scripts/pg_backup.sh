#!/bin/bash
# PostgreSQL backup script for trading_system database
# Usage: Add to crontab: 0 3 * * * /opt/trading-system/scripts/pg_backup.sh
# Keeps last 7 daily backups

set -e

BACKUP_DIR="/opt/backups/postgresql"
DB_NAME="trading_system"
DB_USER="trading_app"
DB_PASS="Tr4d1ngApp2026!"
RETENTION_DAYS=7

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# Create compressed backup
echo "Creating backup: ${BACKUP_FILE}"
PGPASSWORD="${DB_PASS}" pg_dump -U "${DB_USER}" -d "${DB_NAME}" | gzip > "${BACKUP_FILE}"

# Verify backup
if [ -s "${BACKUP_FILE}" ]; then
    echo "Backup OK: $(du -h ${BACKUP_FILE} | cut -f1)"
else
    echo "ERROR: Backup file is empty!"
    exit 1
fi

# Delete old backups
echo "Cleaning backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "${DB_NAME}_*.sql.gz" -mtime +${RETENTION_DAYS} -delete

# List remaining backups
echo "Current backups:"
ls -lh "${BACKUP_DIR}"/${DB_NAME}_*.sql.gz 2>/dev/null | tail -10

echo "Done!"

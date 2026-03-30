#!/bin/bash
# Backup assistant data and vault to a timestamped archive.
# Run manually or add to cron: 0 2 * * * /opt/assistant/scripts/backup.sh

set -e

BACKUP_DIR="/opt/assistant/backups"
DATE=$(date +%Y-%m-%d_%H%M)
ARCHIVE="$BACKUP_DIR/backup_$DATE.tar.gz"

mkdir -p "$BACKUP_DIR"

tar -czf "$ARCHIVE" \
  /opt/assistant/data/assistant.db \
  /opt/assistant/vault/

echo "Backup saved: $ARCHIVE"

# Keep only the last 14 backups
ls -t "$BACKUP_DIR"/backup_*.tar.gz | tail -n +15 | xargs -r rm --

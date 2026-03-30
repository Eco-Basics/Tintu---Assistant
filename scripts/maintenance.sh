#!/bin/bash
# Routine maintenance: vacuum SQLite, clean old logs.

set -e

echo "=== Vacuuming database ==="
sqlite3 /opt/assistant/data/assistant.db "VACUUM;"

echo "=== Removing log files older than 30 days ==="
find /opt/assistant/data/logs/ -name "*.log*" -mtime +30 -delete

echo "=== Done ==="

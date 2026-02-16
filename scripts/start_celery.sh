#!/usr/bin/env bash
# Celery launcher — started by server.py on backend boot.
# Manages worker + beat as child processes with PID tracking.

set -e

PIDFILE_WORKER="/tmp/celery_worker.pid"
PIDFILE_BEAT="/tmp/celery_beat.pid"
LOGDIR="/var/log/supervisor"
APP_DIR="/app"

cd "$APP_DIR"
export DJANGO_SETTINGS_MODULE=TelegramBot.settings
export PATH="/root/.venv/bin:$PATH"

# Source .env
set -a
[ -f /app/.env ] && source /app/.env
set +a

# Kill stale processes
for pf in "$PIDFILE_WORKER" "$PIDFILE_BEAT"; do
    if [ -f "$pf" ]; then
        old_pid=$(cat "$pf")
        kill "$old_pid" 2>/dev/null || true
        rm -f "$pf"
    fi
done
pkill -f "celery -A TelegramBot" 2>/dev/null || true
sleep 1

# Start worker
celery -A TelegramBot worker \
    --loglevel=info \
    --concurrency=2 \
    --pidfile="$PIDFILE_WORKER" \
    >> "$LOGDIR/celery_worker.out.log" 2>&1 &
echo $! > "$PIDFILE_WORKER"
echo "[celery_launcher] Worker started (PID $(cat $PIDFILE_WORKER))"

# Start beat
celery -A TelegramBot beat \
    --loglevel=info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler \
    --pidfile="$PIDFILE_BEAT" \
    >> "$LOGDIR/celery_beat.out.log" 2>&1 &
echo $! > "$PIDFILE_BEAT"
echo "[celery_launcher] Beat started (PID $(cat $PIDFILE_BEAT))"

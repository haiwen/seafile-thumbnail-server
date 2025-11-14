#!/bin/bash

# log function
function log() {
    local time=$(date +"%F %T")
    local level=${2:-INFO}
    echo "$time $1 "
    echo "[thumbnail-server] [$time] [$level] $1 " &>> /opt/seafile/logs/init.log
}

# check nginx
while [ 1 ]; do
    process_num=$(ps -ef | grep "/usr/sbin/nginx" | grep -v "grep" | wc -l)
    if [ $process_num -eq 0 ]; then
        log "Waiting Nginx"
        sleep 0.2
    else
        log "Nginx ready"
        break
    fi
done

env > /opt/dockerenv

# logrotate
chmod 0644 /scripts/logrotate-conf/logrotate-cron
/usr/bin/crontab /scripts/logrotate-conf/logrotate-cron

# non-root
if [[ "${NON_ROOT}" == "true" ]]; then
    # Paths must match thumbnail-runit.sh exports and main.py
    THUMBNAIL_ROOT="/opt/seafile/seahub-data/thumbnail"
    LOG_DIR="/shared/seafile/logs"
    THUMBNAIL_LOG="$LOG_DIR/thumbnail.log"
    THUMBNAIL_SERVER_LOG="$LOG_DIR/thumbnail-server.log"
    INIT_MARKER="/shared/seafile/.thumbnail-nonroot-initialized"

    # Use sentinel file to avoid expensive chown on every container restart
    if [[ ! -f "$INIT_MARKER" ]]; then
        log "First run: Creating user seafile (8000:8000) and setting permissions"
        groupadd --gid 8000 seafile 2>/dev/null || true
        useradd --home-dir /home/seafile --create-home --uid 8000 --gid 8000 --shell /bin/sh --skel /dev/null seafile 2>/dev/null || true

        chown -R seafile:seafile /opt/seafile/

        if [[ -d "$THUMBNAIL_ROOT" ]]; then
            log "Changing ownership of thumbnail directory"
            chown -R seafile:seafile "$THUMBNAIL_ROOT" 2>&1 | grep -v "Operation not permitted" || true
        fi

        if [[ -f "$THUMBNAIL_LOG" ]]; then
            chown seafile:seafile "$THUMBNAIL_LOG" 2>&1 | grep -v "Operation not permitted" || true
        fi
        if [[ -f "$THUMBNAIL_SERVER_LOG" ]]; then
            chown seafile:seafile "$THUMBNAIL_SERVER_LOG" 2>&1 | grep -v "Operation not permitted" || true
        fi

        su seafile -c "touch $INIT_MARKER" 2>/dev/null || true
    else
        log "NON_ROOT already initialized, skipping ownership changes"
        # Ensure user exists (container might be recreated)
        groupadd --gid 8000 seafile 2>/dev/null || true
        useradd --home-dir /home/seafile --create-home --uid 8000 --gid 8000 --shell /bin/sh --skel /dev/null seafile 2>/dev/null || true
    fi

    if [[ -d /shared/seafile ]]; then
        if ! su seafile -c "touch /shared/seafile/.write_test 2>/dev/null && rm /shared/seafile/.write_test 2>/dev/null"; then
            log "ERROR: seafile user cannot write to /shared/seafile/" ERROR
            log "On the host, run: chown -R 8000:8000 /path/to/seafile-data/" ERROR
            exit 1
        fi
    fi
fi

# autorun
# Thumbnail-server is now managed by runit (no manual start needed)

wait

sleep 1


#
log "This is a idle script (infinite loop) to keep container running."

function cleanup() {
    kill -s SIGTERM $!
    exit 0
}

trap cleanup SIGINT SIGTERM

while [ 1 ]; do
    sleep 60 &
    wait $!
done

#!/bin/bash

export SRC_DIR=/opt/seafile/
export LD_LIBRARY_PATH=/opt/seafile/seafile/lib/
export PYTHONPATH=/opt/seafile/seafile/lib/python3/site-packages/:/usr/lib/python3.12/dist-packages:/usr/lib/python3.12/site-packages:/usr/local/lib/python3.12/dist-packages:/usr/local/lib/python3.12/site-packages
export PATH=/opt/seafile/seafile/bin/:$PATH

export SEAFILE_CONF_DIR=/opt/seafile/seafile-data
export SEAFILE_CENTRAL_CONF_DIR=/opt/seafile/conf
export CONF_DIR=/opt/seafile/conf
export LOG_DIR=/opt/seafile/logs
export THUMBNAIL_ROOT=/opt/seafile/seahub-data/thumbnail

export INNER_SEAHUB_SERVICE_URL=${INNER_SEAHUB_SERVICE_URL}
export URL_PREFIX=${URL_PREFIX:-/}
export JWT_PRIVATE_KEY=${JWT_PRIVATE_KEY}
export SEAFILE_MYSQL_DB_CCNET_DB_NAME=${SEAFILE_MYSQL_DB_CCNET_DB_NAME:-ccnet_db}
export SEAFILE_MYSQL_DB_SEAFILE_DB_NAME=${SEAFILE_MYSQL_DB_SEAFILE_DB_NAME:-seafile_db}
export SEAFILE_MYSQL_DB_SEAHUB_DB_NAME=${SEAFILE_MYSQL_DB_SEAHUB_DB_NAME:-seahub_db}
export SITE_ROOT=${SITE_ROOT:-/}


# log function
function log() {
    local time=$(date +"%F %T")
    echo "[$time] $1 "
}

# check process number
# $1 : process name
function check_process() {
    if [ -z $1 ]; then
        log "Input parameter is empty."
        return 0
    fi

    process_num=$(ps -ef | grep "$1" | grep -v "grep" | wc -l)
    echo $process_num
}

# monitor
function monitor_seafile() {
    process_name="seaf-server"
    check_num=$(check_process $process_name)
    if [ $check_num -eq 0 ]; then
        log "Start $process_name"
        seaf-server -F /opt/seafile/conf -d /opt/seafile/seafile-data -l /opt/seafile/logs/seafile.log -L /opt/seafile -P /opt/seafile/pids/seafile.pid - &
        sleep 0.2
    fi
}

function monitor_seafile_thumbnail() {
    process_name="uvicorn"
    check_num=$(check_process $process_name)
    if [ $check_num -eq 0 ]; then
        log "Start $process_name"
        pkill -9 -f multiprocessing
        sleep 0.2
        cd /opt/seafile/thumbnail-server/
        /usr/local/bin/uvicorn main:app --host 127.0.0.1 --port 8088 --workers 4 --access-log --proxy-headers &>> /opt/seafile/logs/thumbnail-server.log &
        sleep 0.2
    fi
}


log "Start Monitor"

while [ 1 ]; do
    monitor_seafile
    monitor_seafile_thumbnail

    sleep 30
done

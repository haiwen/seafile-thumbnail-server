#!/bin/bash

export SRC_DIR=/opt/seafile/
export LD_LIBRARY_PATH=/opt/seafile/seafile/lib/
export PYTHONPATH=/opt/seafile/seafile/lib/python3/site-packages/:/usr/lib/python3.12/dist-packages:/usr/lib/python3.12/site-packages:/usr/local/lib/python3.12/dist-packages:/usr/local/lib/python3.12/site-packages
export PATH=/opt/seafile/seafile/bin/:$PATH

export SEAFILE_DATA_DIR=/opt/seafile/seafile-data
export SEAFILE_CENTRAL_CONF_DIR=/opt/seafile/conf
export CONF_DIR=/opt/seafile/conf
export LOG_DIR=/opt/seafile/logs
export THUMBNAIL_ROOT=/opt/seafile/seahub-data/thumbnail

export INNER_SEAHUB_SERVICE_URL=${INNER_SEAHUB_SERVICE_URL}
export JWT_PRIVATE_KEY=${JWT_PRIVATE_KEY}
export SEAFILE_MYSQL_DB_CCNET_DB_NAME=${SEAFILE_MYSQL_DB_CCNET_DB_NAME:-ccnet_db}
export SEAFILE_MYSQL_DB_SEAFILE_DB_NAME=${SEAFILE_MYSQL_DB_SEAFILE_DB_NAME:-seafile_db}
export SEAFILE_MYSQL_DB_SEAHUB_DB_NAME=${SEAFILE_MYSQL_DB_SEAHUB_DB_NAME:-seahub_db}
export SITE_ROOT=${SITE_ROOT:-/}
export NON_ROOT=${NON_ROOT:-false}
export SEAFILE_LOG_TO_STDOUT=${SEAFILE_LOG_TO_STDOUT:-false}
export ENABLE_MULTI_STORAGE=${ENABLE_MULTI_STORAGE:-}

export REDIS_HOST=${REDIS_HOST:-redis}
export REDIS_PORT=${REDIS_PORT:-6379}
export REDIS_PASSWORD=${REDIS_PASSWORD:-}

# log function
function log() {
    local time=$(date +"%F %T")
    local level=${2:-INFO}
    echo "[thumbnail-server] [$time] [$level] $1 "
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

function monitor_seafile_thumbnail() {
    process_name="main.py"
    check_num=$(check_process $process_name)
    if [ $check_num -eq 0 ]; then
        log "Start $process_name"
        cd /opt/seafile/thumbnail-server/
        if [[ "${SEAFILE_LOG_TO_STDOUT}" == "true" ]]; then
            if [[ "${NON_ROOT}" == "true" ]]; then
                su seafile -c "/usr/bin/python3 main.py &"
            else
                /usr/bin/python3 main.py &
            fi
        else
            if [[ "${NON_ROOT}" == "true" ]]; then
                su seafile -c "/usr/bin/python3 main.py &>> /opt/seafile/logs/thumbnail-server.log &"
            else
                /usr/bin/python3 main.py &>> /opt/seafile/logs/thumbnail-server.log &
            fi
        fi
        sleep 0.2
    fi
}


log "Start Monitor"

while [ 1 ]; do
    monitor_seafile_thumbnail

    sleep 30
done

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
export JWT_PRIVATE_KEY=${JWT_PRIVATE_KEY}
export SEAFILE_MYSQL_DB_CCNET_DB_NAME=${SEAFILE_MYSQL_DB_CCNET_DB_NAME:-ccnet_db}
export SEAFILE_MYSQL_DB_SEAFILE_DB_NAME=${SEAFILE_MYSQL_DB_SEAFILE_DB_NAME:-seafile_db}
export SEAFILE_MYSQL_DB_SEAHUB_DB_NAME=${SEAFILE_MYSQL_DB_SEAHUB_DB_NAME:-seahub_db}
export SITE_ROOT=${SITE_ROOT:-/}
export NON_ROOT=${NON_ROOT:-false}
export SEAFILE_LOG_TO_STDOUT=${SEAFILE_LOG_TO_STDOUT:-false}


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

# Remove temp files left over by a previous main.py process.
#
# main.py can be terminated without running its cleanup code: it calls
# os._exit(1) when the memory limit is reached, and a container restart or
# kill has the same effect.  The temp files created by the thumbnail tasks
# (see seafile_thumbnail/thumbnail.py) are then never removed, so they
# accumulate in the temp directory forever.
#
# This runs right before main.py is started, so no thumbnail task can be
# using these files at that moment.
function cleanup_thumbnail_temp_files() {
    local tmp_dir=${TMPDIR:-/tmp}

    find "$tmp_dir" -maxdepth 1 -type f -regextype posix-extended \
        \( -regex '.*/[0-9a-f]{8,40}\.(png|pdf|mp4|xmind)' \
           -o -regex '.*/tmp[A-Za-z0-9_]{8}\.pdf' \) \
        -delete 2>/dev/null

    return 0
}


function monitor_seafile_thumbnail() {
    process_name="main.py"
    check_num=$(check_process $process_name)
    if [ $check_num -eq 0 ]; then
        log "Start $process_name"
        cleanup_thumbnail_temp_files
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

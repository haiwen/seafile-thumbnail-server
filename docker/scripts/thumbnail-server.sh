#!/bin/bash

function stop_server() {
    pkill -9 -f seaf-server
    pkill -9 -f main.py

    pkill -9 -f monitor

    rm -f /opt/seafile/pids/*.pid
}

function set_env() {
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
}

function run_python_wth_env() {
    set_env
    python3 ${*:2}
}

function start_server() {

    stop_server
    sleep 0.5

    set_env

    seaf-server -F /opt/seafile/conf -d /opt/seafile/seafile-data -l /opt/seafile/logs/seafile.log -L /opt/seafile -P /opt/seafile/pids/seafile.pid - &
    sleep 0.2

    cd /opt/seafile/thumbnail-server/
    /usr/bin/python3 main.py &>> /opt/seafile/logs/thumbnail-server.log &
    sleep 0.2

    /scripts/monitor.sh &>> /opt/seafile/logs/monitor.log &

    echo "thumbnail-server started"
    echo

}


case $1 in
"start")
    start_server
    ;;
"python-env")
    run_python_wth_env "$@"
    ;;
"stop")
    stop_server
    ;;
*)
    start_server
    ;;
esac

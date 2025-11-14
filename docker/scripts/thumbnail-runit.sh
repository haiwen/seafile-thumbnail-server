#!/bin/bash

# Wait for nginx to be ready (backward compatibility)
while [ 1 ]; do
    process_num=$(ps -ef | grep "/usr/sbin/nginx" | grep -v "grep" | wc -l)
    if [ $process_num -eq 0 ]; then
        sleep 0.2
    else
        break
    fi
done

# Set environment variables (from monitor.sh)
export SRC_DIR=/opt/seafile/
export LD_LIBRARY_PATH=/opt/seafile/seafile/lib/
export PYTHONPATH=/opt/seafile/seafile/lib/python3/site-packages/:/usr/lib/python3.12/dist-packages:/usr/lib/python3.12/site-packages:/usr/local/lib/python3.12/dist-packages:/usr/local/lib/python3.12/site-packages
export PATH=/opt/seafile/seafile/bin/:$PATH
export SEAFILE_CONF_DIR=/opt/seafile/seafile-data
export SEAFILE_CENTRAL_CONF_DIR=/opt/seafile/conf
export CONF_DIR=/opt/seafile/conf
# Paths must match enterpoint.sh for NON_ROOT chown
export LOG_DIR=/opt/seafile/logs
export THUMBNAIL_ROOT=/opt/seafile/seahub-data/thumbnail

export INNER_SEAHUB_SERVICE_URL=${INNER_SEAHUB_SERVICE_URL}
export JWT_PRIVATE_KEY=${JWT_PRIVATE_KEY}
export SEAFILE_MYSQL_DB_CCNET_DB_NAME=${SEAFILE_MYSQL_DB_CCNET_DB_NAME:-ccnet_db}
export SEAFILE_MYSQL_DB_SEAFILE_DB_NAME=${SEAFILE_MYSQL_DB_SEAFILE_DB_NAME:-seafile_db}
export SEAFILE_MYSQL_DB_SEAHUB_DB_NAME=${SEAFILE_MYSQL_DB_SEAHUB_DB_NAME:-seahub_db}
export SITE_ROOT=${SITE_ROOT:-/}

cd /opt/seafile/thumbnail-server/

# Startup message to STDOUT (captured by docker logs)
echo "Starting Seafile Thumbnail"

# Wait for seafile user to be created when NON_ROOT mode is enabled
if [[ "${NON_ROOT}" == "true" ]]; then
    echo "Waiting for seafile user to be created..."
    while ! id seafile &>/dev/null; do
        sleep 0.1
    done
    echo "seafile user ready"
fi

# Use setuser if NON_ROOT, otherwise run directly (backward compatible)
# Use exec for proper signal forwarding
# Redirect to log file instead of stdout (like monitor.sh does)
if [[ "${NON_ROOT}" == "true" ]]; then
    exec /sbin/setuser seafile /usr/bin/python3 main.py &>> /opt/seafile/logs/thumbnail-server.log
else
    exec /usr/bin/python3 main.py &>> /opt/seafile/logs/thumbnail-server.log
fi

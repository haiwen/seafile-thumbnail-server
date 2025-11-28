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


# non-noot
if [[ $NON_ROOT == "true" ]] ;then
    log "Create linux user seafile in container, please wait."
    groupadd --gid 8000 seafile 
    useradd --home-dir /home/seafile --create-home --uid 8000 --gid 8000 --shell /bin/sh --skel /dev/null seafile

    if [[ -e /shared/seafile/ ]]; then
        permissions=$(stat -c %a "/shared/seafile/")
        owner=$(stat -c %U "/shared/seafile/")
        if [[ $permissions != "777" && $owner != "seafile" ]]; then
            log "The permission of path seafile/ is incorrect."
            log "To use non root, change the folder permission of seafile folder in your host machine by 'chmod -R a+rwx /opt/seafile-data/seafile/' and try again later. (If you use another path, change the path in the command correspondingly). Now quit."
            exit 1
        fi
    fi

    # chown
    chown seafile:seafile /opt/seafile/
    chown -R seafile:seafile /opt/seafile/thumbnail-server/
    chown -R seafile:seafile /opt/seafile/seafile/
    chown -R seafile:seafile /opt/seafile/scripts/
    if [[ -e /opt/seafile/logs/thumbnail-server.log ]]; then
        chown seafile:seafile /opt/seafile/logs/thumbnail-server.log
    fi

fi


# autorun
log "Starting Seafile Thumbnail"

/scripts/thumbnail-server.sh start

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

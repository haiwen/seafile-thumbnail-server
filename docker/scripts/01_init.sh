#!/bin/bash

set -e

# time zone
if [[ $TIME_ZONE != "" ]]; then
    time_zone=/usr/share/zoneinfo/$TIME_ZONE
    if [[ ! -e $time_zone ]]; then
        echo "invalid time zone"
        exit 1
    else
        ln -snf $time_zone /etc/localtime
        echo "$TIME_ZONE" > /etc/timezone
    fi
fi

# check folder
if [[ ! -e /shared ]]; then
    echo 'do not find /shared path'
    exit 1
fi

if [[ ! -e /shared/seafile ]]; then
    mkdir /shared/seafile
fi

if [[ ! -e /shared/seafile/conf ]]; then
    mkdir /shared/seafile/conf
fi

if [[ ! -e /shared/seafile/conf/seafile.conf ]]; then
    touch /shared/seafile/conf/seafile.conf
fi

if [[ ! -e /shared/seafile/seahub-data && ! -e /opt/seafile/seahub-data ]]; then
    mkdir /shared/seafile/seahub-data
fi

if [[ ! -e /shared/seafile/seahub-data/thumbnail ]]; then
    mkdir /shared/seafile/seahub-data/thumbnail
fi

if [[ ! -e /shared/seafile/logs ]]; then
    mkdir /shared/seafile/logs
fi

if [[ ! -e /opt/seafile/pids ]]; then
    mkdir /opt/seafile/pids
fi

# thumbnail-server.sh
if [[ ! -e /opt/seafile/scripts ]]; then
    mkdir /opt/seafile/scripts
fi

cp /scripts/thumbnail-server.sh /opt/seafile/scripts/thumbnail-server.sh
sed -i '$a\PATH=/opt/seafile/scripts:$PATH' ~/.bashrc
chmod u+x /opt/seafile/scripts/*.sh

# main
ln -sfn /shared/seafile/* /opt/seafile

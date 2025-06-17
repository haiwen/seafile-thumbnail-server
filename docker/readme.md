# thumbnail-server-docker

1, seafile_thumbnail
2. seaserv
3. seafobj

## Deploy

1. mkdir -p /opt/seafile/shared/
2. vim /opt/seafile/docker-compose.yml
3. docker-compose up
4. vim /opt/seafile/shared/seafile/conf/*
5. vim /opt/seafile/shared/seafile/seafile-license.txt
6. docker exec -d thumbnail-server /scripts/thumbnail-server.sh

## Build

1. cp seafile_thumbnail docker/src/thumbnail-server/seafile_thumbnail
2. cp main.py docker/thumbnail-server/main.py
3. cp seafile docker/seafile (seafile folder was in seafile docker)
4. docker build -t docker.seafile.top/seafileltd/thumbnail-server:1.x.x ./

#!/bin/bash

version=$1
first_num=$(echo $version | cut -d '.' -f1)
second_num=$(echo $version | cut -d '.' -f2)

docker tag docker.seafile.top/seafileltd/thumbnail-server:${version}-testing docker.seafile.top/seafileltd/thumbnail-server:${version}
docker tag docker.seafile.top/seafileltd/thumbnail-server:${version}-testing docker.seafile.top/seafileltd/thumbnail-server:${first_num}.${second_num}-latest

docker push docker.seafile.top/seafileltd/thumbnail-server:${version}
docker push docker.seafile.top/seafileltd/thumbnail-server:${first_num}.${second_num}-latest


docker tag seafileltd/thumbnail-server:${version}-testing seafileltd/thumbnail-server:${version}
docker tag seafileltd/thumbnail-server:${version}-testing seafileltd/thumbnail-server:${first_num}.${second_num}-latest

docker push seafileltd/thumbnail-server:${version}
docker push seafileltd/thumbnail-server:${first_num}.${second_num}-latest


echo docker.seafile.top/seafileltd/thumbnail-server:${version}
echo docker.seafile.top/seafileltd/thumbnail-server:${first_num}.${second_num}-latest
echo seafileltd/thumbnail-server:${version}
echo seafileltd/thumbnail-server:${first_num}.${second_num}-latest

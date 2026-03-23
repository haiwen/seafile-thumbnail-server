#!/bin/bash

version=$1

docker build --pull --build-arg server_version=$version -t docker.seafile.top/seafileltd/thumbnail-server:${version}-arm-testing ./

docker tag docker.seafile.top/seafileltd/thumbnail-server:${version}-arm-testing seafileltd/thumbnail-server:${version}-arm-testing

docker push seafileltd/thumbnail-server:${version}-arm-testing
docker push docker.seafile.top/seafileltd/thumbnail-server:${version}-arm-testing

echo seafileltd/thumbnail-server:${version}-arm-testing
echo docker.seafile.top/seafileltd/thumbnail-server:${version}-arm-testing

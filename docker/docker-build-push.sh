#!/bin/bash

version=$1

docker build -t docker.seafile.top/seafileltd/thumbnail-server:${version}-testing ./

docker tag docker.seafile.top/seafileltd/thumbnail-server:${version}-testing seafileltd/thumbnail-server:${version}-testing

docker push seafileltd/thumbnail-server:${version}-testing
docker push docker.seafile.top/seafileltd/thumbnail-server:${version}-testing

echo seafileltd/thumbnail-server:${version}-testing
echo docker.seafile.top/seafileltd/thumbnail-server:${version}-testing

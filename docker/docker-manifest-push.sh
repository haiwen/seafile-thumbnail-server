#!/bin/bash

version=$1
first_num=$(echo $version | cut -d '.' -f1)
second_num=$(echo $version | cut -d '.' -f2)

docker manifest rm seafileltd/thumbnail-server:${first_num}.${second_num}-latest

docker manifest create seafileltd/thumbnail-server:${first_num}.${second_num}-latest seafileltd/thumbnail-server:${version}-testing seafileltd/thumbnail-server:${version}-arm-testing

docker manifest push seafileltd/thumbnail-server:${first_num}.${second_num}-latest



docker manifest rm seafileltd/thumbnail-server:${version}

docker manifest create seafileltd/thumbnail-server:${version} seafileltd/thumbnail-server:${version}-testing seafileltd/thumbnail-server:${version}-arm-testing

docker manifest push seafileltd/thumbnail-server:${version}



docker manifest rm docker.seafile.top/seafileltd/thumbnail-server:${first_num}.${second_num}-latest

docker manifest create docker.seafile.top/seafileltd/thumbnail-server:${first_num}.${second_num}-latest docker.seafile.top/seafileltd/thumbnail-server:${version}-testing docker.seafile.top/seafileltd/thumbnail-server:${version}-arm-testing

docker manifest push docker.seafile.top/seafileltd/thumbnail-server:${first_num}.${second_num}-latest



docker manifest rm docker.seafile.top/seafileltd/thumbnail-server:${version}

docker manifest create docker.seafile.top/seafileltd/thumbnail-server:${version} docker.seafile.top/seafileltd/thumbnail-server:${version}-testing docker.seafile.top/seafileltd/thumbnail-server:${version}-arm-testing

docker manifest push docker.seafile.top/seafileltd/thumbnail-server:${version}



echo seafileltd/thumbnail-server:${first_num}.${second_num}-latest
echo seafileltd/thumbnail-server:${version}
echo docker.seafile.top/seafileltd/thumbnail-server:${first_num}.${second_num}-latest
echo docker.seafile.top/seafileltd/thumbnail-server:${version}

#!/bin/bash

version=$1

docker build -t docker.seafile.top/seafileltd/thumbnail-server:${version} ./

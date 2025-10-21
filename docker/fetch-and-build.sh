#!/bin/bash

git pull

cd thumbnail-server/
cp -r /opt/seafile-thumbnail-server/seafile_thumbnail .
cp /opt/seafile-thumbnail-server/app.py .
cp /opt/seafile-thumbnail-server/main.py .
cp /opt/seafile-thumbnail-server/requirements.txt .

cd ../seafobj
git pull

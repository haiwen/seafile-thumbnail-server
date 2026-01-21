FROM ubuntu:24.04
# seafileltd/thumbnail-server:13.x.x

# https://github.com/phusion/baseimage-docker
COPY base_scripts /bd_build
RUN /bd_build/prepare.sh && \
    /bd_build/system_services.sh && \
    /bd_build/utilities.sh && \
    /bd_build/cleanup.sh
ENV DEBIAN_FRONTEND="teletype" \
    LANG="en_US.UTF-8" \
    LANGUAGE="en_US:en" \
    LC_ALL="en_US.UTF-8"


RUN apt-get update --fix-missing && apt upgrade -y

## Dev related libs
RUN export DEBIAN_FRONTEND=noninteractive && apt-get install -y tzdata \
    nginx gcc libz-dev libmemcached-dev \
    procps net-tools curl vim poppler-utils ffmpeg \
    libjemalloc2

# set python3 global
RUN apt-get install -y python3 python3-pip python3-setuptools && \
    rm /usr/lib/python3.12/EXTERNALLY-MANAGED && \
    rm -f /usr/bin/python && ln -s /usr/bin/python3 /usr/bin/python

# thumbnail-server
RUN mkdir -p /opt/seafile 
WORKDIR /opt/seafile
COPY thumbnail-server /opt/seafile/thumbnail-server
COPY seafobj/requirements.txt /opt/seafile/thumbnail-server/seafobj-requirements.txt
COPY seafobj/seafobj /opt/seafile/seafile/lib/python3/site-packages/seafobj
COPY seafobj/objwrapper /opt/seafile/seafile/lib/python3/site-packages/objwrapper

RUN pip3 install --no-cache-dir -r /opt/seafile/thumbnail-server/requirements.txt && \
    pip3 install --no-cache-dir -r /opt/seafile/thumbnail-server/seafobj-requirements.txt && \ 
    pip3 install --no-cache-dir chardet pymysql sqlalchemy redis pylibmc oss2 lxml

# scripts
COPY scripts /scripts

RUN mkdir -p /etc/service/nginx && \
	rm -f /etc/nginx/sites-enabled/* /etc/nginx/conf.d/* && \
	mv /scripts/nginx.conf /etc/nginx/nginx.conf && \
	mv /scripts/nginx.sh /etc/service/nginx/run && \
    mv /scripts/default /etc/nginx/sites-enabled/default

# my_init
RUN rm -rf /etc/my_init.d/*
COPY scripts/01_init.sh /etc/my_init.d/01_init.sh
RUN chmod +x /etc/my_init.d/01_init.sh \
	/scripts/*.sh

CMD ["/sbin/my_init", "--", "/scripts/enterpoint.sh"]

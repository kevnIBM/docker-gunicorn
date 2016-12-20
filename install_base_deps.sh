#!/bin/bash

set -eo pipefail

echo "Installing dependencies for building:"
echo "    nginx ${NGINX_VERSION}"
echo "    python ${PYTHON_VERSION}"
echo "    gunicorn ${GUNICORN_VERSION}"
echo "    supervisor ${SUPERVISOR_VERSION}"
echo ""
apt-get update

apt-get install -y --no-install-recommends \
	ca-certificates \
	gcc \
	libpcre3-dev \
	libexpat1-dev \
	libffi-dev \
	libssl-dev \
	locales \
	make \
	vim \
	wget \


# Supervisord doesn't currently support running under python3,
# so we'll install python2.7 just for that if using 3.x for our app.
case ${PYTHON_VERSION} in
    3.*)
        apt-get install -y --no-install-recommends python2.7
	;;
esac

rm -r /var/lib/apt/lists/*

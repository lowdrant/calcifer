#!/usr/bin/env bash
scriptdir="$(dirname "($realpath "$0")")"

# PyGObject req
sudo apt install  -y --install-recommends libglib2.0-dev \
libgirepository1.0-dev python3-cairo-dev libcairo2-dev

# Python Reqs
pip3 install -r "$scriptdir/requirements.txt"

# TODO: edit rc.local
# TODO: put symlink in bin
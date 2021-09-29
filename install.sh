#!/usr/bin/env bash
set -o errexit
scriptdir="$(dirname "$(realpath "$0")")"

# Install PyGame dependencies
# https://stackoverflow.com/questions/57672568/sdl2-on-raspberry-pi-without-x
sudo apt build-dep -y libsdl2
sudo apt install -y libdrm-dev libgbm-dev
wget 'https://www.libsdl.org/release/SDL2-2.0.10.tar.gz' -O ~/sdl.tar.gz
mkdir -p ~/sdl-src && tar -xvf ~/sdl.tar.gz --strip-components 1 -C ~/sdl-src && rm ~/sdl.tar.gz
cd ~/sdl-src
./configure --enable-video-kmsdrm
make -j4 && sudo make install
rm -rf ~/sdl-src

# Python Reqs
cd "$scriptdir"
pip3 install -r "$scriptdir/requirements.txt" --no-cache-dir

# TODO: edit rc.local
# TODO: put symlink in bin

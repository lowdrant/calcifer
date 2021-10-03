#!/usr/bin/env bash
set -o errexit


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
sudo apt install -y libsdl2-mixer-2.0-0 libsdl2-image-2.0-0 libsdl2-2.0-0

#!/usr/bin/env bash
scriptdir="$(dirname "$(realpath "$0")")"

# Python Reqs
cd "$scriptdir"
pip3 install -r "$scriptdir/requirements.txt" --no-cache-dir

# Check for libsdl2 for pygame
installpygamedeps=false
dpkg -s libsdl2-mixer-2.0-0 &>/dev/null || installpygamedeps=true
if [ "$installpygamedeps" = true ]
then
    echo 'Missing libsdl2-mixer-2.0-0; Installing pygame dependencies...'
    "$scriptdir/install-pygame-deps.sh"
else
    echo "PyGame dependencies already installed"
fi

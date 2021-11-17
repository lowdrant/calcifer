#!/usr/bin/env bash
#
# Provides CLI to configure SystemD to run calcifer.py at boot with
# appropriate configuration parameters.
#
#   usage: configure the calcifer.service daemon to calcifer.py at boot [-h] [SECTION]
#
#   optional arguments:
#          -h, --help  show this help message and exit
#          SECTION     specify config file section, defaults to CALCIHATTER
#
# https://www.cyberciti.biz/faq/linux-unix-run-commands-when-you-log-out/
# https://roboticsbackend.com/make-a-raspberry-pi-3-program-start-on-boot/
# https://www.shellhacks.com/systemd-service-file-example/

set -o nounset
set -o pipefail
set -o errexit
scriptdir="$(dirname "$(realpath "$0")")"

# Print help dialog
if [ $# -gt 0 ] && ([ $1 = "-h" ] || [ $1 = "--help" ])
then
    printf "usage: configure the calcifer.service daemon to calcifer.py at boot [-h] [SECTION]\n\n"
    printf "optional arguments:\n"
    printf "       -h, --help  show this help message and exit\n"
    printf "       SECTION     specify config file section, defaults to CALCIHATTER\n"
    exit 0
fi

# Prep service options
# use --run instead of --bg because systemd wants script to not exit
base="/usr/bin/python3 \""$scriptdir/"calcifer.py\" --section=${1:-CALCIHATTER} --loglevel=DEBUG"
servicetext="[Unit]
Description=Calcifer talking fireplace daemon. https://github.com/lowdrant/calcifer
After=multi-user.target

[Service]
ExecStart=$base --run
ExecStop=$base --stop
User=pi

[Install]
WantedBy=multi-user.target"

# Configure systemd to run service
fnservice="/lib/systemd/system/calcifer.service"
sudo touch "$fnservice"
sudo echo "$servicetext" > "$fnservice"
sudo systemctl daemon-reload
sudo systemctl enable calcifer.service

#!/usr/bin/env bash
#
# Configure calcifer.py to run at boot.
#
#  configures calcifer as system service
#
# https://www.cyberciti.biz/faq/linux-unix-run-commands-when-you-log-out/
# https://roboticsbackend.com/make-a-raspberry-pi-3-program-start-on-boot/
# https://www.shellhacks.com/systemd-service-file-example/

set -o nounset
set -o pipefail
scriptdir="$(dirname "$(realpath "$0")")"

# Print help dialog
if [ $# -gt 0 ] && ([ $1 = "-h" ] || [ $1 = "--help" ])
then
    printf "usage: configure calcifer.py as a service [-h] [SECTION]\n\n"
    printf "optional arguments:\n"
    printf "       -h, --help  show this help message and exit\n"
    printf "       SECTION     specify config file section, defaults to CALCIHATTER\n"
    exit 0
fi

# Prep service options
base="/usr/bin/python3 \""$scriptdir/"calcifer.py --section=${1:-CALCIHATTER}\""
servicetext="[Unit]
Description=Run Calcifer program at boot. https://github.com/lowdrant/calcifer
After=multi-user.target

[Service]
ExecStart=$base --bg &>> $scriptdir/calcifer.log
ExecStop=$base --stop
User=pi

[Install]
WantedBy=multi-user.target"

# Configure systemd to run service
fnservice="/lib/systemd/system/calcifer.service"
sudo echo "$servicetext" > "$fnservice"
sudo systemctl daemon-reload
sudo systemctl enable calcifer
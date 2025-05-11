#!/bin/bash
set -e

xvfb-run -a -f /root/.Xauthority -s "-screen 0 1920x1080x24" "$@"

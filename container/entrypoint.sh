#!/bin/bash
set -euo pipefail

# Wings supplies `bash /mnt/install/install.sh` for installation containers.
# Pass shell commands through unchanged; otherwise enter the supervised game
# runtime used by normal server containers.
case "${1:-}" in
    bash|/bin/bash|sh|/bin/sh)
        exec "$@"
        ;;
esac

cd /home/container
exec /usr/bin/python3 -B /supervise.py "$@"

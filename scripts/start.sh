#!/bin/bash
set -euo pipefail
umask 077
unset LD_PRELOAD LD_LIBRARY_PATH PYTHONPATH PYTHONHOME BASH_ENV ENV
exec /usr/bin/python3 -B "$(dirname -- "$(readlink -f -- "$0")")/runtime.py"

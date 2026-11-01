#!/bin/bash
# Local/private acceptance only. Never downloads the proprietary archive.
set -euo pipefail
cd "$(dirname -- "$(readlink -f -- "$0")")/.."
if ! docker info >/dev/null 2>&1; then
    echo 'BLOCKED: Docker daemon inaccessible; no container smoke result.' >&2
    exit 77
fi
mode=${1---image-only}
image=bf2-native-linux:local
docker build --platform linux/amd64 -t "$image" -f container/Dockerfile .
docker run --rm --entrypoint /bin/bash "$image" -ceu '
    test "$(id -u)" = 0
    test "$(uname -m)" = x86_64
    python3 --version
    readelf -d /lib/x86_64-linux-gnu/libncurses.so.5 | grep -F "[libncurses.so.5]"
    ! readelf -d /lib/x86_64-linux-gnu/libncurses.so.5 | grep -F "[libncurses.so.6]"
'
if [[ $mode == --image-only ]]; then
    echo 'PASS: image dependency check only; no server startup tested.'
    exit 0
fi
[[ $mode == --payload ]] || { echo 'Use --image-only or --payload' >&2; exit 2; }
: "${BF2_ARCHIVE:?Path to the exact privately held archive required}"
[[ ${EA_EULA_ACCEPT-} == YES && ${NONCOMMERCIAL_USE-} == YES ]] || {
    echo 'Explicit EA_EULA_ACCEPT=YES and NONCOMMERCIAL_USE=YES are required.' >&2; exit 2;
}
archive=$(readlink -f -- "$BF2_ARCHIVE")
[[ -f $archive && ! -L $BF2_ARCHIVE ]] || exit 2
volume=$(docker volume create)
name="bf2-smoke-$$"
container_id=
work=$(mktemp -d)
cleanup() {
    if [[ -n $container_id ]]; then
        docker rm -f "$container_id" >/dev/null 2>&1 || true
    fi
    docker volume rm "$volume" >/dev/null 2>&1 || true
    rm -rf -- "$work"
}
trap cleanup EXIT
python3 -B - "$work/install.sh" <<'PY'
import json,sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.loads(Path('egg-battlefield-2.json').read_text())['scripts']['installation']['script'])
PY
# Use Wings' exact command shape and the exact rendered installer in its
# declared image with no network access.
docker run --rm --network none \
    -v "$volume:/mnt/server" -v "$archive:/mnt/server/bf2-linuxded-1.5.3153.0-installer.tgz:ro" \
    -v "$work/install.sh:/mnt/install/install.sh:ro" \
    -e EA_EULA_ACCEPT -e NONCOMMERCIAL_USE "$image" bash /mnt/install/install.sh
# Wings normalizes ownership after a successful install; mirror that before
# running the server as its unprivileged per-server UID.
docker run --rm --network none --entrypoint /bin/chown \
    -v "$volume:/mnt/server" "$image" -R 1000:1000 /mnt/server/server
# Network namespace has no external routes/public ports. Preserve stdin for legacy console.
container_id=$(docker run -dit --name "$name" --network none --user 1000:1000 --cap-drop ALL --security-opt no-new-privileges \
    -v "$volume:/home/container" -e EA_EULA_ACCEPT -e NONCOMMERCIAL_USE \
    -e INTERNET=0 -e BF2HUB_ENABLED=0 "$image")
for _ in {1..12}; do
    sleep 5
    [[ $(docker inspect -f '{{.State.Running}}' "$container_id") == true ]] || {
        docker logs "$container_id"; echo 'FAIL: server exited' >&2; exit 1;
    }
done
docker exec "$container_id" /bin/bash -ceu '
    file server/bin/amd-64/bf2 | grep -F "x86-64"
    sockets=$(ss -H -lun)
    grep -Eq ":16567[[:space:]]" <<< "$sockets"
    grep -Eq ":29900[[:space:]]" <<< "$sockets"
    ! ss -H -ltn | grep -Eq ":4711[[:space:]]"
    ! grep -Eq ":5512[345][[:space:]]" <<< "$sockets"
'
docker logs "$container_id" > "$work/server.log" 2>&1
if grep -Eiq 'error while loading shared libraries|failed to load|unable to load|syntax error' "$work/server.log"; then
    echo 'FAIL: inspect private container console errors' >&2; exit 1
fi
docker stop --time 20 "$container_id" >/dev/null
[[ $(docker inspect -f '{{.State.ExitCode}}' "$container_id") != 137 ]] || {
    echo 'FAIL: server required SIGKILL' >&2; exit 1;
}
docker start "$container_id" >/dev/null
sleep 15
[[ $(docker inspect -f '{{.State.Running}}' "$container_id") == true ]]
echo 'PASS: offline 60-second survival, expected listeners, bounded stop and restart. No client join/query-response/public-listing claim.'

# Installation and source boundaries

The inspected dedicated server package has a separate EA Tools EULA restricting
use to personal noncommercial purposes and restricting copying, distribution,
modification and transfer. Owning a game or finding a public mirror does not
establish redistribution rights. Read the actual supplied EULA; this project
does not grant rights to EA/DICE, PunkBuster or BF2Hub content. See the
[distribution reference](https://www.bf-games.net/downloads/954/bf2-dedicated-server-150-linux-build-153153-8020.html).

The operator must set **both** `EA_EULA_ACCEPT=YES` and
`NONCOMMERCIAL_USE=YES`. Defaults are `NO`. The installer never runs `license.sh`,
feeds an acceptance response, accepts PunkBuster terms or patches a game binary.
It keeps the supplied EULA and readmes under `server/readmes/`. PunkBuster files
are removed from staging before installation; there is no enable option.

## Exact input

| Payload | Bytes | SHA-256 |
| --- | ---: | --- |
| `bf2-linuxded-1.5.3153.0-installer.tgz` | 330688322 | `4d849218c1725e7bd6a7e7f164e27b036248f8ded2e30340dd0722c1dfffbab6` |
| `BF2Hub-Unranked-Linux-R3.tar.gz` (optional) | 38980 | `c4b3d583741c500e930502e96c6a43a40f223868c9ca1111c70d80c7e6d2cd2b` |

Upload the first file as `/home/container/bf2-linuxded-1.5.3153.0-installer.tgz`
from the runtime/panel view. Its installer view is
`/mnt/server/bf2-linuxded-1.5.3153.0-installer.tgz`. Do not nest it in another
folder or extract it yourself. Keep the exact uploaded file for future reinstalls.
A wrong local upload fails immediately; it never triggers a silent network fallback.

Source order is fixed:

1. Exact-name regular local upload at the volume root, rejecting symlinks/hardlinks.
2. Explicit `ARCHIVE_URL`, an HTTPS URL chosen by the operator, with HTTPS-only
   redirects, no embedded credentials and a bounded download.
3. Only with `ALLOW_THIRD_PARTY_MIRROR=1`, the optional **third-party** mirror
   [static.nihlen.net](https://static.nihlen.net/bf2/server/bf2-linuxded-1.5.3153.0-installer.tgz).
   This is a community source, **not an EA origin**. Availability is not guaranteed.

Network writes also have a kernel file-size limit, including responses without a
Content-Length header. Every route uses the same fixed byte and SHA-256 pins. The code has no hash
bypass or configurable digest. Failed explicit URLs do not silently switch sources.
If a mirror is unavailable, upload the exact original file and click Reinstall.

BF2Hub is opt-in before initial installation. With `BF2HUB_ENABLED=1` and
`INTERNET=1`, use a matching optional local archive or download the exact R3
archive directly from [BF2Hub](https://www.bf2hub.com/downloads/BF2Hub-Unranked-Linux-R3.tar.gz).
That download does not follow redirects to any origin. Archive and all four
supplied file hashes are checked. Only the amd64 library, launcher and guide
are installed; the ia32 library is checked then discarded. No BF2Hub binary is
included in a repository or release.

## Staging and reinstall behavior

Allow at least 2 GiB free staging space plus the uploaded archive, and more for
custom content. Staging lives on the server volume. The exact outer archive must
contain only the named makeself script. The authenticated inner tar is inspected
for traversal, links, devices, duplicate paths and size/count limits before
`--noexec --nox11 --nochown --target` extraction. Extracted ownership is not trusted.
No installed tree is visible until verification/config validation passes and a
same-filesystem rename publishes `server/`. Temporary archives and staging are
removed on success or exception. An interrupted process may leave a private
`.bf2-install-*` directory for manual cleanup after confirming the server is stopped.

A reinstall with an existing `server/` validates and preserves it without writing
code, mods, maps, configs or saves. It is intentionally not an upgrade mechanism.
Stop the server and back up the complete volume before any explicit replacement.
For a new egg revision or adding BF2Hub to an installation that lacks it, rename
`server/` to an operator-chosen backup, install afresh, then deliberately migrate
custom content/configuration. Do not copy unverified launchers or executables.
BF2Hub can be turned off at runtime using the preserved `start_original.sh`.
The original `start.sh` is also preserved byte for byte. Empty `pb/` prevents the
vendor wrapper from creating a dangling PunkBuster symlink.

## Runtime image

```sh
docker build --platform linux/amd64 -t bf2-native-linux:local -f container/Dockerfile .
```

Build on every intended node; no registry publication is required. The base image
is pinned by digest and package installation uses a dated Debian snapshot with
signed repository metadata. HTTP snapshot transport bootstraps CA certificates;
apt signature checks remain enabled. Debian's actual
[libncurses5 package](https://packages.debian.org/bookworm/libncurses5) provides
SONAME `libncurses.so.5`, even though its package version begins with 6.4.
This is different from pointing ABI 5 at `libncurses.so.6`.

The image has not been built on the implementation worker because Docker access
is denied. The reproducible script and CI job must establish image buildability
and runtime compatibility. Runtime checks validate x86_64 ELF, all pinned native
files, `ldd` resolution and the ncurses SONAME before writing config or launching.
The image deliberately has no final Dockerfile `USER`: Wings runs the installer
as the image default root user so it can publish into a root-owned server volume,
then runs the game container as its per-server unprivileged UID. The payload smoke
tests this split by using the image default for installation and UID 1000 for the
runtime. Direct Docker operators must likewise pass an unprivileged runtime UID.
The unsupported ia32 path would additionally need the 32-bit loader and
libstdc++5; this candidate neither selects it nor claims that its dependencies work.

The server volume is an operator trust boundary. Stop the server before changing
its files. Advisory locking serializes this project's installer/runtime; it cannot
protect against a same-UID operator actively racing arbitrary filesystem changes.

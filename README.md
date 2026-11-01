# Battlefield 2 (2005) Pterodactyl/Pelican egg

**Native Linux v1.5 · PTDL_v2 · BF2Hub-compatible · Source-only**

[Latest release](https://github.com/grimreapper/pterodactyl-bf2-egg/releases/latest) ·
[Installation](docs/INSTALL.md) · [Configuration](docs/CONFIGURATION.md) ·
[Maps](docs/MAPS.md) · [Client setup](docs/CLIENT-SETUP.md) ·
[Validation](docs/VALIDATION.md)

## Overview

A source-only PTDL_v2 egg for the native Linux v1.5 dedicated server. The
repository and release contain original scripts, metadata and documentation
only. EA/DICE, PunkBuster, BF2Hub, maps and mods are not included or redistributed.
The MIT license covers this project's original work only.

**Candidate status:** source validation plus an authorized, receipt-bound
disposable Pterodactyl acceptance run are complete. Native startup, external
query/RCON, controlled restart/soak, BF2Hub public unranked listing, and a real
BF2Hub-patched client join/gameplay/rejoin passed. One initial client disconnect
had no matching server crash, OOM, restart or listener/query failure, but its
exact client message was not retained. End-to-end VOIP remains **unverified**.
See [the validation record](docs/VALIDATION.md) for the exact boundaries.

Use [egg-battlefield-2.json](egg-battlefield-2.json) with the locally built
`bf2-native-linux:local` image. This tag is an operator build target, not a
published image. The same image supplies installation tools and an amd64 runtime
with genuine `libncurses.so.5`; ia32 and ARM are deliberately unsupported.
No ncurses6 alias, binary patch, automatic updater or proprietary download occurs
when building the image or running ordinary tests.

1. Read [installation and licensing](docs/INSTALL.md), obtain the exact archive
   independently, and read its EA Tools EULA. Use is gated on explicit
   `EA_EULA_ACCEPT=YES` and `NONCOMMERCIAL_USE=YES`.
2. Build the supplied container image on an authorized test node; verify it with
   `bash scripts/container_smoke.sh --image-only`.
3. Import only into a disposable test panel/server for acceptance. Upload the
   exact archive to the server volume root, then reinstall. The installer checks
   this upload before considering an explicit HTTPS URL or the optional,
   opt-in third-party community mirror.
4. Configure allocations, server settings and [map rotation](docs/MAPS.md).
   PunkBuster is not supported. RCON, VOIP and BF2Hub are off by default.
5. Complete the [private runtime and panel acceptance checklist](docs/VALIDATION.md)
   before relying on this candidate.

[Configuration](docs/CONFIGURATION.md) · [Client setup](docs/CLIENT-SETUP.md) ·
[Discovery and ports](docs/DISCOVERY.md) · [Troubleshooting](docs/TROUBLESHOOTING.md)

```sh
python3 -B scripts/build_release.py
bash scripts/validate.sh
```

The renderer embeds exact standalone source bytes into the installer without
fetching code at install time. The release builder creates a deterministic
source-only ZIP in `dist/` with fixed timestamps/modes, checksums and an exact
public-file manifest. Tests use original synthetic fixtures. Optional private
extraction checks accept existing local archives; they do not download or execute
the game. Keep all private inputs outside this repository.

# Validation record and acceptance guide

This candidate completed an authorized isolated-panel acceptance run against
receipt-bound temporary resources. It was not promoted, published or committed
during that phase. The public repository contains original source and factual
metadata only. The quality reference informed validation scope; no game-specific
code/content was copied from another egg.

## Local matrix

Run `bash scripts/validate.sh` after `python3 -B scripts/build_release.py`.
It covers deterministic rendering, exact embedded-source bytes, PTDL_v2 field
encoding/defaults, Bash syntax, in-memory Python compilation, JSON parsing,
archive/hash/input safety, cross-UID installer/runtime locking, installer staging/preservation, map metadata
intersection, config validation/atomicity, library/preload refusal, process stop
handling, checksums, deterministic ZIP reconstruction and public scans.

The public scan checks every file against PUBLIC_FILES, including intended
untracked content, plus an exact staged-file/byte match, reachable history/ref metadata and release
contents. It refuses binary/config/log payloads, private paths, non-neutral email,
non-documentation IPs, credential patterns and unapproved URL hosts. This is a
strict automated baseline, not a promise that pattern matching can recognize all
possible personal information. Human review remains necessary before publication.
No real game fixture is in the repository; tests synthesize their own inputs.

Private extraction-only check, using already held archives outside the repository:

```sh
python3 -B scripts/check_payload.py "$BF2_ARCHIVE" --hub "$BF2HUB_ARCHIVE"
```

This snapshots and verifies exact bytes, validates the outer archive and makeself
tar, extracts with `--noexec`, verifies original native file hashes and the complete
22-map metadata intersection, rejects one-byte corruption, and optionally checks
R3 plus all four per-file hashes. It never downloads or launches either package,
runs an EULA script, or sets an acceptance variable. Temporary bytes are removed.

## Container and panel acceptance scope

The implementation worker's local Docker daemon returned permission denied, so
the local container smoke script exited **77 (blocked)**. The later authorized
disposable Pterodactyl run below closed the image, Wings install, runtime,
socket/query/RCON, BF2Hub listing, and patched-client join gates for the exact
candidate. That one run does not replace acceptance of a new build, panel,
payload, network, or configuration.

The CI `image-smoke` job builds the exact Dockerfile and checks genuine ncurses5
without a proprietary payload. CI workflow execution itself has not been observed
locally. It neither downloads a game archive nor uploads private artifacts.
To reproduce the container checks on an authorized private host, run:

```sh
bash scripts/container_smoke.sh --image-only
# Set these only after personally reading/accepting the terms:
EA_EULA_ACCEPT=YES NONCOMMERCIAL_USE=YES BF2_ARCHIVE="$BF2_ARCHIVE" \
  bash scripts/container_smoke.sh --payload
```

The payload smoke uses the exact rendered installer in its declared image, an
ephemeral volume, the image's normal entrypoint as UID 1000, no external network,
no published ports, 60-second survival, UDP game/query listener checks, absence
of default RCON/VOIP listeners, bounded stop and restart. Cleanup deletes only
resources created by that invocation. It does not establish a GameSpy protocol
response, client join, authenticated RCON or external listing. Record the image
ID/digest and results privately. A failed test is not a passing acceptance.

Before relying on a new or changed deployment, an authorized operator must:

1. Import the exact JSON into disposable Pterodactyl and Pelican eggs. Export each
   stored installer and compare raw bytes, shell syntax, variables, image, the
   JSON-encoded `files`/`startup`/`logs` fields, and the plain `^C` stop string.
   Verify stop is graceful and the panel's readiness state is accurate. The empty done
   list intentionally avoids a fabricated engine-ready phrase.
2. Install from a valid operator upload with both explicit acknowledgments, and
   test corrupt payload/missing acceptance rejection. Inspect EULA/readme retention
   and PunkBuster absence. Confirm the original launcher and amd64 ELF hashes.
3. Start privately/offline; observe actual process/library resolution and UDP
   game/query sockets, run an external GameSpy query, and observe no RCON/VOIP
   listener when disabled. Check generated settings and a controlled restart.
4. Enable RCON with a private unique password; verify its TCP allocation,
   authentication and an authenticated command. Test rejection of wrong passwords.
   Verify optional VOIP's actual socket surface separately.
5. Start a supported coop map with bots and join from a valid matching client.
   Verify custom mod/map assets and restart preservation separately.
6. On an explicitly authorized public test endpoint, verify exact BF2Hub R3,
   matching preload/library path in the process, documented outbound traffic,
   external query status `ranked = 0`, public listing and a patched-client join.
   Verify BF2Hub-off still chooses the original path. These are separate gates.
7. Preserve private evidence without publishing credentials, IPs, config dumps,
   packet captures or proprietary bytes. Run the release scan again before sharing.

## Local execution results

See the final local and authorized disposable-panel runs recorded below. Source
tests do not substitute for a real client join; that gate remains explicitly
separate.

Recorded on 2026-11-01:

| Check | Exact result |
| --- | --- |
| `bash scripts/validate.sh` | Exit 0; 74 tests, zero failures/errors/skips |
| Canonical + embedded Bash syntax, Python compilation, PTDL/JSON, defaults and renderer bytes | PASS within the 74-test matrix |
| Source checksum inventory | 32 entries verified; SHA256SUMS excludes itself |
| ZIP integrity, fixed modes, exact source contents, two consecutive release builds | PASS; byte-identical deterministic rebuilds |
| Public workspace/index/reachable-history/release scan | PASS; 33 public files |
| Workflow YAML parse | PASS |
| Exact private archive/extraction/core hashes/map intersection | PASS; 22 maps; no license script or game executed |
| One-byte archive corruption | PASS; rejected by SHA-256 gate |
| Private BF2Hub R3 archive and four per-file hashes | PASS; no BF2Hub library executed |
| Local `bash scripts/container_smoke.sh --image-only` | Exit 77: local Docker daemon inaccessible; separately covered by the authorized remote image/panel run below |

## Authorized disposable-panel results

Recorded on 2026-11-01 against a receipt-bound temporary egg and server. The
test resources were isolated from existing servers and were retained stopped
after the run.

| Check | Exact result |
| --- | --- |
| Exact temporary egg import and installer execution through Wings | PASS |
| Pinned BF2 1.5 amd64 and BF2Hub R3 files after reinstall | PASS |
| Native Conquest startup with bots disabled | PASS; `Loaded 100%`, `playing`, zero players, no crash/OOM |
| External GameSpy challenge/full status | PASS for `gpm_cq` and `gpm_coop`; expected map, mode, limits and `ranked = 0` |
| External RCON | PASS; correct credential authenticated, wrong credential rejected, `users` executed |
| Controlled panel restart and bounded soak | PASS; changed container start time, 313-second observed soak, zero container restarts/OOM |
| Coop startup with eight configured bots | PASS to `Loaded 100%`/`playing`; real patched-client gameplay passed, while individual bot AI behavior was not separately instrumented |
| Real process listeners | PASS for game/query UDP, RCON TCP and the observed integrated-VOIP UDP sockets |
| BF2Hub R3 registration/discovery | PASS; exact library mapped, master/list heartbeats observed and public unranked listing verified |
| Real patched-client public-browser join and Coop gameplay | PASS; first join ~10 minutes, immediate rejoin ~22m38s; exact first-disconnect text unavailable, with no matching server crash/OOM/restart/listener loss |
| Direct-IP-only join and end-to-end VOIP | UNVERIFIED; not claimed |
| Final disposable-server state and protected-resource comparison | PASS; stopped and retained; existing servers/eggs/allocations unchanged |

The final documentation/checksum refresh was followed by a release rebuild,
checksum verification, exact embedded-source check and scan of the staged public
candidate. No proprietary archive was downloaded during implementation. Existing
private evidence was read and temporary extraction copies were deleted. The
implementation and live-acceptance phases made no commit or remote write;
publication is a separate post-acceptance gate.

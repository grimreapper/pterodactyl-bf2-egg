# Map rotation and custom content

Use `map mode size` triples separated by semicolons. Supported mode tokens are
`gpm_cq` and `gpm_coop`; supported size tokens are `16`, `32`, `64`. Size is explicit;
the candidate does not silently substitute a size based on player slots.

The table is a factual inventory derived from the exact pinned v1.5 payload,
intersecting each `info/<map>.desc` declaration with nonempty
`GameModes/<mode>/<size>/GamePlayObjects.con` entries in that map's `server.zip`.
It is cross-checked by `scripts/check_payload.py`. No proprietary metadata text
is copied into this repository. Extra dormant sizes/modes in ZIPs are not promoted
to support. Runtime applies the same intersection to installed content rather than
assuming that every map works. This checks structure, not a successful play session.

| Map | gpm_cq sizes | gpm_coop sizes |
| --- | --- | --- |
| dalian_plant | 16, 32, 64 | 16 |
| daqing_oilfields | 16, 32, 64 | 16 |
| dragon_valley | 16, 32, 64 | 16 |
| fushe_pass | 16, 32, 64 | 16 |
| greatwall | 16, 32 | 16 |
| gulf_of_oman | 16, 32, 64 | 16 |
| highway_tampa | 16, 32, 64 | - |
| kubra_dam | 16, 32, 64 | - |
| mashtuur_city | 16, 32, 64 | - |
| midnight_sun | 16, 32, 64 | 16 |
| operation_blue_pearl | 16, 32, 64 | - |
| operation_clean_sweep | 16, 32, 64 | 16 |
| operationharvest | 16, 32, 64 | 16 |
| operationroadrage | 16, 32, 64 | 16 |
| operationsmokescreen | 16, 32 | 16 |
| road_to_jalalabad | 16, 32, 64 | 16 |
| sharqi_peninsula | 16, 32, 64 | 16 |
| songhua_stalemate | 16, 32, 64 | 16 |
| strike_at_karkand | 16, 32, 64 | 16 |
| taraba_quarry | 16, 32 | 16 |
| wake_island_2007 | 64 | - |
| zatar_wetlands | 16, 32, 64 | 16 |

Conquest example: `strike_at_karkand gpm_cq 32; wake_island_2007 gpm_cq 64`.
Coop example: `strike_at_karkand gpm_coop 16` with `BOT_COUNT=16` and
`MAX_PLAYERS=32`. Wake Island 2007 is 64-player Conquest only. Highway Tampa has
no accepted coop pair. Bot difficulty uses 10–100, and positive bot count requires
at least one coop map. Bot settings do not create navigation/cooperative data.

Upload complete, separately obtained mod trees to `server/mods/<lowercase-mod>/`
(`/mnt/server/server/mods/<lowercase-mod>/` in the installer view). Set MOD to that
directory token. Upload complete custom map trees to
`server/mods/<mod>/levels/<lowercase-map>/`. Do not add an extra nesting level.
An init.con or marker file alone is not a complete mod: retain all required server
archives, Python, objects, gameplay data and dependent assets. The egg's structural
checks are a minimum preflight, not an exhaustive content/authenticity inventory.
All loose paths must be lowercase except Python scripts; ZIP member casing is
read without modifying the archive. Symlinks/hardlinks/special files are refused.

Special Forces uses `MOD=xpack` and requires separately owned/supplied content.
A package skeleton is not proof of usable xpack maps. No Special Forces map list
or custom compatibility is invented here. Unsupported/missing metadata fails
closed; resolve it from the original mod's authoritative distribution. The egg
never downloads, patches or silently renames mods/maps. Reinstall preserves them.

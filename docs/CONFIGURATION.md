# Configuration contract

All panel defaults come from `scripts/spec.py`, which the runtime imports too.
The table below lists every setting and its actual destination. Numeric ranges
are this candidate's supported policy, not claims of undocumented engine limits.
Text fields reject controls, newlines, non-ASCII characters, quotes and backslashes
instead of assuming an unverified legacy escape grammar. Shell expansion is never
used on panel values. Explicit empty values fail except optional URL/passwords.

Generated settings and rotation live under `server/egg-config/current/` and are
passed with `+config` and `+mapList`. Vendor/operator files in
`server/mods/<mod>/settings/` are preserved and are not active overrides.
`server/admin/default.cfg` points into the same atomically switched generation.
The default admin module is selected only when RCON is enabled. Disabled RCON
also disables that module's optional autobalance/teamkill administration hooks.
A pre-existing operator `admin/default.cfg` causes a refusal; back it up explicitly
before using generated RCON settings. Do not edit generated files: edited content
is detected and preserved by refusing the next start. Keep operator configuration
in your own backups and transfer the desired values into panel variables.
Old generated generations, including stale secrets, are removed after publication.
Config files have mode 0600; settings are not printed to the console.

| Variable | Default | Destination / accepted values |
| --- | --- | --- |
| EA_EULA_ACCEPT | NO | Exact YES required at install and start |
| NONCOMMERCIAL_USE | NO | Exact YES required at install and start |
| ALLOW_THIRD_PARTY_MIRROR | 0 | 1 enables optional community mirror; 0 disables |
| ARCHIVE_URL | empty | Optional operator HTTPS input after local upload |
| BF2HUB_ENABLED | 0 | 1 selects verified R3 launcher, requires INTERNET=1; 0 selects original |
| SERVER_NAME | Battlefield 2 Server | `sv.serverName`, 1–64 printable ASCII characters |
| SERVER_PASSWORD | empty | `sv.password`; empty = public join, otherwise 12–64 characters |
| INTERNET | 0 | `sv.internet`, 1 reports online, 0 private/offline |
| SERVER_BIND_IP | 0.0.0.0 | `sv.serverIP`, local IPv4 bind address |
| SERVER_PORT (panel built-in) | primary allocation; 16567 local fallback | `sv.serverPort`, gameplay UDP; this reserved value is injected by Pterodactyl/Wings and is not an egg variable |
| QUERY_PORT | 29900 | `sv.gameSpyPort`, query UDP allocation |
| MAX_PLAYERS | 32 | `sv.maxPlayers`, 1–64 |
| MIN_PLAYERS | 1 | `sv.numPlayersNeededToStart`, 1 through MAX_PLAYERS |
| ROUNDS_PER_MAP | 3 | `sv.roundsPerMap`, 1–99 rounds |
| TICKET_RATIO | 100 | `sv.ticketRatio`, 1–1000 percent |
| TIME_LIMIT | 0 | `sv.timeLimit`, 0–1440 minutes; 0 unlimited |
| BOT_COUNT | 0 | `sv.coopBotCount`, 0–64 and at most MAX_PLAYERS; positive requires coop in rotation |
| BOT_RATIO | 50 | `sv.coopBotRatio`, 0–100 percent |
| BOT_DIFFICULTY | 50 | `sv.coopBotDifficulty`, 10 easiest through 100 hardest |
| MOD | bf2 | `+modPath mods/<token>`, lowercase letters/digits/underscores, 1–48 chars, starts alphanumeric |
| MAP_ROTATION | strike_at_karkand gpm_cq 32 | Semicolon-separated `map mode size`; see MAPS.md |
| RCON_ENABLED | 0 | 1 selects `sv.adminScript "default"`; 0 selects empty admin script |
| RCON_PORT | 4711 | `admin/default.cfg` port, TCP allocation when enabled |
| RCON_PASSWORD | empty | `admin/default.cfg` password; required when RCON enabled |
| VOIP_ENABLED | 0 | `sv.voipEnabled`, 1 enabled / 0 disabled |
| VOIP_CLIENT_PORT | 55123 | `sv.voipBFClientPort`, UDP when enabled |
| VOIP_BF_PORT | 55124 | `sv.voipBFServerPort`, UDP when enabled |
| VOIP_SERVER_PORT | 55125 | `sv.voipServerPort`, UDP when enabled |

All ports are 1024–65535 and active ports must be distinct. The panel does not
create secondary allocations just because a variable has a default; allocate
and forward each required port explicitly. RCON requires a unique 16–64 character
password from letters/digits or `._!@%+:-`. Equals signs and whitespace break the
vendor parser and are refused. Both passwords reject common placeholders and
trivial repetition. Generate your own secrets privately; never copy credentials
from documentation or put secrets in repository files.

`SERVER_PORT` is deliberately absent from the egg-variable list because it is a
[reserved panel environment name](https://github.com/pterodactyl/panel/blob/1.0-develop/app/Models/EggVariable.php).
Pterodactyl/Wings supplies the primary allocation at runtime; the 16567 fallback
exists only for the documented direct local container smoke test.

PunkBuster, global rank and global unlocks are fixed off; NAT negotiation is off.
Servers are unranked. VOIP uses the integrated server, not a remote VOIP service.
BF2Hub listing and public-browser patched-client gameplay/rejoin passed on the
disposable endpoint. Direct-IP-only join and end-to-end VOIP remain unverified.
Revalidate all accepted behavior for each new deployment.

## PTDL and stop behavior

The PTDL `files`, `startup`, and `logs` values are JSON-encoded strings. `stop` is
the ordinary plain string `^C`, allowing Wings to deliver SIGINT rather than send
a quoted console command. The supplied container supervisor forwards SIGINT/TERM
to the game's process group, cleans up descendants, and bounds escalation to TERM
then KILL. The runtime itself executes the byte-preserved vendor launcher, which
execs the amd64 server. Do not substitute an unrelated runtime image: it would
omit this process supervision and ncurses5. Panel import/readback and panel stop
behavior were accepted through an exact egg import and controlled restart on the
disposable panel. Revalidate both on each new deployment.
See [Pterodactyl's configuration converter](https://github.com/pterodactyl/panel/blob/1.0-develop/app/Services/Eggs/EggConfigurationService.php).

No startup readiness phrase is invented: `config.startup.done` is an empty list.
The preflight banner is not game readiness. The controlled restart passed, but
deployment-specific running-state behavior and an engine readiness marker must
still be revalidated during each disposable acceptance.

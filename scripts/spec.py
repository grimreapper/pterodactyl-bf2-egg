"""Public provenance facts and the single source of panel/runtime defaults."""
ARCHIVE = 'bf2-linuxded-1.5.3153.0-installer.tgz'
ARCHIVE_SIZE = 330688322
ARCHIVE_SHA256 = '4d849218c1725e7bd6a7e7f164e27b036248f8ded2e30340dd0722c1dfffbab6'
INNER = 'bf2-linuxded-1.5.3153.0-installer.sh'
INNER_SIZE = 330909895
PAYLOAD_OFFSET = 8893
MIRROR = 'https://static.nihlen.net/bf2/server/' + ARCHIVE
HUB_ARCHIVE = 'BF2Hub-Unranked-Linux-R3.tar.gz'
HUB_URL = 'https://www.bf2hub.com/downloads/' + HUB_ARCHIVE
HUB_SIZE = 38980
HUB_SHA256 = 'c4b3d583741c500e930502e96c6a43a40f223868c9ca1111c70d80c7e6d2cd2b'
BASE_HASHES = {
    'bin/amd-64/bf2': 'b60c1d055437daaad51603f2ffa7cacab71c6502cdd9c8011887e64ed19e1719',
    'bin/amd-64/libdice_py.so': '275b6fd2096fa619ffd662227846f48f1acab6cb7f3c7d86e9900a07f6272454',
    'bin/amd-64/libaidll.so': '5e801d62021950941f4d7b7b72a37f62f7f13f210d404dfb2e211b0077ffcbb8',
    'start.sh': '829010ee4dc9984d6763dcdc425dd987ba69264c3354cdd9526647977569c6a1',
    'start_original.sh': '829010ee4dc9984d6763dcdc425dd987ba69264c3354cdd9526647977569c6a1',
}
HUB_HASHES = {
    'BF2Hub-Unranked-Linux-R3.txt': 'f4c47969d2751ad8235453f270591ab7ca9e1daf3dccfb912c4de0b5348586d4',
    'start_bf2hub.sh': 'd9b9c0b594452ba6a72e08c8f80d1730216c1ede3a4804ac1055e9b113e58799',
    'bin/amd-64/libbf2hub.so': 'd8e9eff04e45eca70481d3f5d688e75b3728823c95b52a9a03b8f7046941c604',
    'bin/ia-32/libbf2hub.so': '459e7ee967667efa81480ce514aea3a94cf1d8efd14e041e6d1ccf23482565b3',
}
# name: (default, Laravel rules, operator description)
VARIABLES = {
    'EA_EULA_ACCEPT': ('NO', 'required|string|in:NO,YES', 'Set exactly YES only after reading and accepting the EA Tools EULA; no automatic acceptance.'),
    'NONCOMMERCIAL_USE': ('NO', 'required|string|in:NO,YES', 'Set exactly YES to acknowledge personal noncommercial use under the supplied license.'),
    'ALLOW_THIRD_PARTY_MIRROR': ('0', 'required|integer|in:0,1', '1 = allow the optional community HTTPS mirror after local upload and explicit URL; 0 = no mirror. Not an EA origin.'),
    'ARCHIVE_URL': ('', 'nullable|string|max:2048', 'Optional operator HTTPS source for the exact pinned archive. Local root upload takes priority. HTTPS redirects only; no embedded credentials.'),
    'BF2HUB_ENABLED': ('0', 'required|integer|in:0,1', '1 = use verified BF2Hub unranked R3; 0 = original launcher. Set before install. Requires patched clients; public listing/join unverified.'),
    'SERVER_NAME': ('Battlefield 2 Server', 'required|string|max:64', 'Server display name, 1–64 printable ASCII characters; quotes and backslashes are refused.'),
    'SERVER_PASSWORD': ('', 'nullable|string|max:64', 'Empty = public join; otherwise 12–64 printable ASCII characters without quotes/backslashes. Placeholder secrets are refused.'),
    'INTERNET': ('0', 'required|integer|in:0,1', '1 = Internet reporting; 0 = offline/private. BF2Hub requires 1. Does not configure firewall/NAT.'),
    'SERVER_BIND_IP': ('0.0.0.0', 'required|ipv4', 'Local IPv4 bind address; 0.0.0.0 listens on container interfaces. Never put an unbound public NAT address here.'),
    'QUERY_PORT': ('29900', 'required|integer|between:1024,65535', 'GameSpy query/status UDP; separate allocation required for BF2Hub reachability.'),
    'MAX_PLAYERS': ('32', 'required|integer|between:1,64', 'Player slots, 1–64 supported by this candidate. Map size is selected separately in each rotation entry.'),
    'MIN_PLAYERS': ('1', 'required|integer|between:1,64', 'Players required to start; must not exceed MAX_PLAYERS.'),
    'ROUNDS_PER_MAP': ('3', 'required|integer|between:1,99', 'Rounds before rotating, candidate policy 1–99.'),
    'TICKET_RATIO': ('100', 'required|integer|between:1,1000', 'Ticket percentage, candidate policy 1–1000 percent; higher values lengthen rounds.'),
    'TIME_LIMIT': ('0', 'required|integer|between:0,1440', 'Round limit in minutes; 0 = no limit, candidate policy up to 1440.'),
    'BOT_COUNT': ('0', 'required|integer|between:0,64', 'Coop bots, 0–64 and no greater than MAX_PLAYERS; positive count requires a gpm_coop rotation.'),
    'BOT_RATIO': ('50', 'required|integer|between:0,100', 'Coop team bot ratio in percent, 0–100.'),
    'BOT_DIFFICULTY': ('50', 'required|integer|between:10,100', 'Coop difficulty: 10 = easiest, 100 = hardest; requires cooperative map data.'),
    'MOD': ('bf2', 'required|string|max:48', 'Lowercase mod directory token: letters/digits/underscores; starts with a letter or digit. xpack/custom content must be supplied separately.'),
    'MAP_ROTATION': ('strike_at_karkand gpm_cq 32', 'required|string|max:4096', 'Semicolon-separated map mode size triples. Modes gpm_cq/gpm_coop, sizes 16/32/64; every combination must exist in installed metadata and server.zip.'),
    'RCON_ENABLED': ('0', 'required|integer|in:0,1', '1 = authenticated TCP RCON using default admin module; 0 = no admin module/listener. Restrict source IPs in your firewall.'),
    'RCON_PORT': ('4711', 'required|integer|between:1024,65535', 'Optional RCON TCP allocation; only used when RCON_ENABLED=1.'),
    'RCON_PASSWORD': ('', 'nullable|string|max:64', 'Required when RCON is enabled: 16–64 ASCII letters/digits or ._!@%+:-; no spaces or equals sign. Placeholder secrets refused.'),
    'VOIP_ENABLED': ('0', 'required|integer|in:0,1', '1 = integrated VOIP, requiring three extra UDP allocations; 0 = disabled. Listener behavior remains unverified.'),
    'VOIP_CLIENT_PORT': ('55123', 'required|integer|between:1024,65535', 'Integrated VOIP client UDP port; used only with VOIP_ENABLED=1.'),
    'VOIP_BF_PORT': ('55124', 'required|integer|between:1024,65535', 'Integrated VOIP BF server UDP port; used only with VOIP_ENABLED=1.'),
    'VOIP_SERVER_PORT': ('55125', 'required|integer|between:1024,65535', 'Integrated VOIP server UDP port; used only with VOIP_ENABLED=1.'),
}
DEFAULTS = {k: v[0] for k, v in VARIABLES.items()}
# Pterodactyl reserves SERVER_PORT and injects the primary allocation itself, so
# it must not be declared as an egg variable. The fallback exists only for direct
# local/container tests outside a panel.
BUILTIN_DEFAULTS = {'SERVER_PORT': '16567'}
RUNTIME_IMAGE = 'bf2-native-linux:local'
INSTALL_IMAGE = 'bf2-native-linux:local'

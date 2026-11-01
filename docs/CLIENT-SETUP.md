# Client setup and rollback

Use an independently obtained, valid Battlefield 2 (2005) installation patched
to v1.5. This is the original BF2 protocol, not a modern Battlefield title.
For BF2Hub discovery the client must use BF2Hub's client software/settings;
an unchanged client must not be assumed to see a BF2Hub server. Follow the current
[official BF2Hub support instructions](https://www.bf2hub.com/home/support.php).
This project neither supplies a client nor automatically modifies one.

Before installing client software, back up the game installation and profiles
privately, review BF2Hub's terms, and record the exact files/settings changed by
the selected client release. The accepted private test used the official BF2Hub
Client 1.8 installer after verifying its published SHA-1/MD5 and independently
recording SHA-256. The client was installed reversibly inside Steam AppID 24860's
existing Proton prefix, then Battlefield 2 was launched through Steam's normal
tracked path. This is acceptance evidence for that tested setup, not a promise
that future BF2Hub releases or other Wine/Proton layouts behave identically.
Retain the installer's change log and original files; rollback means restoring
those originals/settings or restoring the complete private backup. Do not apply
this server's Linux R3 preload to a Windows client.

On the server, the exact R3 additions are `start_bf2hub.sh`,
`bin/amd-64/libbf2hub.so`, and `BF2Hub-Unranked-Linux-R3.txt`.
`start.sh` and `start_original.sh` retain the original launcher bytes. Set
`BF2HUB_ENABLED=0` to select the original server path again. No binary patching
or replacement of the original game executable is performed by this project.

Use the client's in-game Connect to IP flow with `<SERVER_IP>` and `<GAME_PORT>`
for a separately tested direct connection. Do not assume command-line syntax
from another game applies to BF2. Keep server and client mod/map versions aligned.
Windows path casing can hide mistakes; Linux server loose file/directory names
must be lowercase except Python script filenames. ZIP metadata uses its supplied
case and is compared case-insensitively without rewriting archive contents.

A real BF2Hub-patched client joined through the public browser and played on the
receipt-bound Coop server. External GameSpy monitoring proved the first join,
a disconnect/rejoin, and a second continuous interval of about 22m38s. The first
disconnect's exact client message was not retained; no server crash, OOM, restart,
listener loss or matching server-log failure occurred. Direct-IP-only join was
not separately exercised, and end-to-end VOIP remains unverified.

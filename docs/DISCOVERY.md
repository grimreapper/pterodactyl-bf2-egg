# Discovery and networking

BF2Hub is an optional replacement master service for this unranked BF2 v1.5
server. Its R3 server package and correctly configured patched clients are both
needed. Installing a preload alone does not prove reporting, reachability,
public listing or client joining. An authorized disposable run verified the
loaded R3 library, outbound master/list heartbeats, external query reachability
and BF2Hub's public unranked web listing. A real BF2Hub-patched client also
joined through the public browser, played Coop, disconnected and rejoined.
Direct-IP-only join remains unverified. The original GameSpy browser must not
be presented as a working current service. Revalidate these results for each
new deployment.

The [BF2Hub server setup page](https://www.bf2hub.com/home/serversetup.php) lists
the following traffic. DNS and download HTTPS access are additional installation
or ordinary infrastructure requirements.

| Direction | Transport | Default port(s) | Purpose |
| --- | --- | --- | --- |
| Inbound | UDP | 16567 | Gameplay, SERVER_PORT |
| Inbound | UDP | 29900 | Query/status and BF2Hub reachability, QUERY_PORT |
| Outbound | UDP | 27900, 29910, 29960 | BF2Hub service traffic |
| Outbound | TCP | 80 | BF2Hub service traffic |
| Inbound, optional | TCP | 4711 | Authenticated RCON; firewall-restrict clients |
| Optional | UDP | 55123, 55124, 55125 | Integrated VOIP; separately verify direction/listeners |

These are required/documented sockets; Docker/panel mappings alone do not prove
listeners. The disposable run measured game/query UDP, authenticated RCON TCP
and two integrated-VOIP UDP listeners in the real process namespace. The
configured VOIP client port was not observed, so end-to-end VOIP remains
unverified. Re-measure on each deployment. Allocate the gameplay and query UDP
ports separately; forward both through NAT. `SERVER_BIND_IP=0.0.0.0` binds inside
the container; do not use an external address that is not present on an interface.
The parent payload uses `sv.serverPort`; BF2Hub's page calls it `sv.gameport`.
This egg follows the inspected shipped configuration's `sv.serverPort` spelling.

[BF2Hub server policy](https://www.bf2hub.com/home/serverpolicy.php) requires
unranked servers to report `ranked = 0` on the query port. This candidate fixes
global rank and unlocks off; the authorized external query returned `ranked = 0`.
Ranked hosting has a separate
[BF2Hub application process](https://www.bf2hub.com/home/admins.php); enabling
this egg's BF2Hub switch does not grant ranked status or hosting permission.

Server-side acceptance used an authorized isolated public test endpoint and
verified outbound traffic, external GameSpy status and BF2Hub's public web
listing. Public-browser patched-client join, Coop gameplay and rejoin also
passed there. Direct-IP-only join and end-to-end VOIP remain unverified; repeat
the accepted checks and resolve those remaining gates on each deployment before
making deployment-specific claims. Record evidence privately. Do not publish
addresses, accounts, captures or credentials.

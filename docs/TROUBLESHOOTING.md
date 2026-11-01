# Troubleshooting

| Symptom | Action |
| --- | --- |
| EA or noncommercial gate refuses | Read the supplied EULA; set exact YES only if you accept and meet its conditions. No bypass exists. |
| Exact size/SHA mismatch | Remove or replace the incorrect upload privately. HTML error pages and changed releases are refused; never change the pin to make them pass. |
| Download denied | Upload the exact original filename at the volume root and reinstall. Local input always wins. |
| Existing install preserved | Reinstall is validation-only; back up/rename the server directory explicitly before a fresh installation or egg-code upgrade. |
| BF2Hub enabled without files | Set it before initial installation or perform the documented backed-up fresh installation; runtime never downloads code. |
| libncurses.so.5 missing | Build/use the supplied amd64 image and run its smoke check. Never symlink libncurses.so.6. |
| Wrong architecture | Use an x86_64 node and linux/amd64 image. ARM emulation and ia32 are not supported. |
| Map/mode/size rejected | Inspect the selected installed map's .desc and server.zip. Both must confirm the pair; do not bypass validation. |
| Uppercase mod path | Normalize loose operator filenames before upload, retaining Python script casing. Resolve collisions explicitly; the egg does not rename proprietary files. |
| Operator admin/default.cfg exists | Preserve it in your private backup, then remove the conflict explicitly. The egg refuses to overwrite it. |
| Generated config edited | Save your edits privately, migrate them to panel settings, and remove the edited generated directory/link while stopped. |
| Console says preflight passed | That confirms checks before exec only, not engine readiness or listening ports. |
| Public listing missing | Verify INTERNET=1, exact R3 files, query UDP reachability, BF2Hub reporting and patched client configuration independently. |
| Panel stop does not interrupt the server | Confirm the imported `config.stop` is the plain `^C` string and verify Wings delivers SIGINT to the container supervisor. Verify actual panel stop/readback before acceptance. |
| Docker smoke exits 77 | Docker is unavailable or inaccessible. This is blocked/unverified, never a passing runtime test. |

The candidate refuses modified/missing/non-executable core files, missing
libraries, unsafe links, empty rotations, ambiguous secrets, port collisions and
unconfirmed combinations. Restore exact trusted inputs instead of suppressing a
failure. Keep diagnostic console/config files outside the public repository.

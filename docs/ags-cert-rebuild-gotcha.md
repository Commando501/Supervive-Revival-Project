# ags rebuild → TLS breaks at menu-load (re-append `root.crt` to `cacert.pem`)

**Operational gotcha. Verified live 2026-07-04.** Migrated out of the Claude memory store into the
repo on 2026-08-12.

## Symptom

You rebuild `ags` (`server/ags.exe`) and restart it to replace a previously-running build, and the
game rejects its TLS:

- `SSL certificate problem: self signed certificate in certificate chain` / `unknown CA`
  (client sends a TLS "unknown CA (560)" alert; `ags` logs `tls: bad record MAC`)
- → the `configuration/public` bootstrap query fails with
  `LogLokiPlatformQuery: Error: Invalid response received`
- → the client falls back to the real (dead) URLs and **CRASHES at menu-load**

**This is NOT a code or endpoint bug.** Do not go looking for one — the shape of the failure
(`Invalid response received`) is exactly what a missing required top-level field looks like, which
makes it very easy to misdiagnose as a handler regression.

## Why

`tlscert.EnsureCert("certs")` reuses `certs/root.crt` if present, but the game's `cacert.pem`
(`<GameRoot>/Loki/Content/Certificates/cacert.pem`) may contain a **different** old
"SUPERVIVE Revival Root CA" cert, appended by a prior `ags` run. The old running backend
(e.g. `ags-s45c`) was serving the cert that IS in the bundle; a fresh build serving a different
`certs/root.crt` is not trusted.

Compounding it: the user `Engine.ini`
(`%LOCALAPPDATA%/SUPERVIVE/Saved/Config/Windows/Engine.ini`) `[HTTP.Curl] bVerifyPeer=false`
override is also often **GONE** (UE regenerates `Engine.ini`), so peer validation is back ON.

## Fix

After building and starting a new `ags`, verify the served cert is trusted — compare

```bash
openssl x509 -in certs/root.crt -noout -fingerprint
```

against the certs already in the game's `cacert.pem`. If absent, append it (idempotent — check
first):

```bash
python -c "cac=open(CACERT,'rb').read(); root=open('certs/root.crt','rb').read(); open(CACERT,'wb').write(cac + (b'' if cac.endswith(b'\n') else b'\n') + root + b'\n')"
```

Or just re-run `configs/launch-redirect.ps1` — its cacert step restores-clean and re-appends
`certs/root.crt`. Then relaunch.

**Verified 2026-07-04:** after appending the `F0:9B…` `root.crt`, the game connected,
`LogPlatformInventory: Refreshed player inventory`, no TLS errors.

⚠ Related security item: `server/certs/server.key` was tracked into public git history, and because
the launcher appends `root.crt` to the game's general CA bundle, that key mints certs trusted by
every self-hoster. Untracked + gitignored, **not rotated**. See the root-CA note in `CLAUDE.md`.

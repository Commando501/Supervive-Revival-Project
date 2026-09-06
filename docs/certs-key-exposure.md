# The local root-CA private key is in public git history

**Status: OPEN — untracked, NOT remediated. Rotation required.**
**Found: 2026-08-10, during the .gitignore audit that unblocked the 100 MB push.**

## What

`server/certs/server.key` — an RSA private key — has been **tracked** since the
first commit (`d172bae` "Starting Point") and re-committed across five commits.
It is present in `origin/dedicated-server-stub`, and
`github.com/Commando501/Supervive-Revival-Project` is **PUBLIC**
(`gh repo view --json visibility` → `"PUBLIC"`, confirmed 2026-08-10).

Tracked alongside it, and part of the same compromised chain:
`server/certs/root.crt`, `server/certs/server.crt`.

## Why it matters more than a normal leaked key

This is not a leaf key for one host. It is the private key of **the local root
CA**, and `configs/launch-redirect.ps1` appends `certs/root.crt` to the game's
`cacert.pem` — the client's **general CA trust bundle**, not a per-host pin.

So anyone who has the repo can mint a certificate for **any hostname** that will
be trusted by **every self-hoster who ran the launcher**. The redirect works by
trusting this CA; that is the whole mechanism.

The root `.gitignore` has warned about exactly this since it was written:

> a committed root.crt/server.key would make every self-hoster … install a CA
> whose private key is public into their trust store.

The comment was right. The rule under it was `/certs/` — **root-anchored**.

## How the rule missed it

`server/cmd/ags/main.go:43` defaults the `-certs` flag to the **CWD-relative**
`"certs"`. Two launch paths, two destinations:

| path | cwd | writes to | covered by `/certs/`? |
|---|---|---|---|
| `launch-redirect.ps1` (passes an absolute `-certs`, line 220) | any | `/certs/` | yes |
| the documented "iterative server-only restarts" recipe | `server/` | `server/certs/` | **no** |

`EnsureCert()` *reuses whatever is already on disk*, so once the key landed in
`server/certs/` it was stable, kept getting re-committed, and never tripped
anything.

Fixed forward by adding `/server/certs/` (commit `fabc59a`). The original
`/certs/` rule and its comment are preserved verbatim.

⚠ Un-anchoring to a bare `certs/` was considered and **rejected**: unbounded
depth would swallow a future vendored or testdata `certs/` directory. Two
anchored rules, not one loose one.

## What untracking did and did not do

`git rm --cached` stops **future** commits. It does **not** remove the key from
history, from the pack, or from GitHub. Treat the key as **compromised**.

## Remediation

**1. Rotate (mandatory, local, ~1 min).** The key is public; nothing recovers it.

```bash
rm -rf "G:/git/Supervive Revival Project/server/certs" "G:/git/Supervive Revival Project/certs"
```

`tlscert.EnsureCert()` generates a fresh 10-year chain on the next `ags` start.

⚠ Then re-append the **new** `certs/root.crt` to the game's `cacert.pem` or TLS
fails at menu load — this is the documented `supervive-ags-cert-rebuild-gotcha`.
`launch-redirect.ps1` does it for you; a hand-started `ags` does not.

**2. Purge from history (optional, disruptive).** `git filter-repo` / BFG over
all history plus a force-push to a public repo. Note what this does *not* buy:
the key has been public for the life of the repo, so rotation is what actually
closes the exposure. A purge only reduces future discoverability, and GitHub
retains unreferenced commits reachable by SHA until asked to GC them. Rotation
first, always; purge is a separate call.

If a purge is going to happen, run it **before** any further untrack-style
commits — a later rewrite invalidates them anyway.

## Also flagged, lower severity

- `state/interactive.json` — per-account runtime state keyed by a local player
  identifier. Not a credential. Untracked in `fabc59a`.
- The 1.89 GB FK-7 log corpus was **sampled, not exhaustively scanned**, for
  credentials (`Bearer`, `access_token=`, `eyJ`, 15+ digit SteamIDs — zero hits
  in the two files checked). ⚠ **Newer logs are strictly higher-risk:** the S113
  `[Core.Log]` change makes `LogAccelByte` trace the whole backend conversation
  including full URLs and request handles. Those logs are now gitignored, but
  scan before ever committing one.

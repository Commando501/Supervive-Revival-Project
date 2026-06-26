# Next session kickoff — Milestone 3: make the menu *functional*

> Paste the block below into a new session to start. Everything above the line is
> notes; the prompt itself is the fenced block.

---

```
We're continuing the SUPERVIVE Revival Project (G:\git\Supervive Revival Project) —
reviving the shut-down game with a self-hosted zero-dep Go backend (server/, build
with & "$env:ProgramFiles\Go\bin\go.exe" build -o ags.exe ./cmd/ags). Milestones 1
(reach the menu) and 2 (populate the menu) are DONE: the client loads into a fully
rendered, broadly-alive main menu — working WebSocket lobby, friends, presence, voice,
nav, party slots, level/rank badges, Vive Points currency, Customization (local
cosmetics + emote wheel), and a working Career screen (Stats/Ranked/History).

THIS MILESTONE'S GOAL: make as many functional menu SYSTEMS/OPTIONS actually WORK as
possible — BEFORE touching gameplay. "Look alive" is done; now make things do things.
Read these first (they hold everything learned; the supervive-milestone2-status memory
also loads automatically):
- docs/findings.md — full RE journey (login→menu gate, deserialize/validity rules).
- docs/endpoints.md — every endpoint's status + the "Invalid response received"
  validity model + the session-end "backend-reachable ceiling" writeup.
- server/internal/menu/menu.go — current storefront/wallet/heroes/inventory handlers
  with the decode-probe history in comments.

THE CENTRAL CONSTRAINT (discovered last session): the menu is broadly *populated*, but
the remaining empty/placeholder content is gated on PACKED IoStore data, not the
backend. Specifically, all of these need real IDs/strings baked into
Loki/Content/Paks/*.utoc/.ucas:
- HUNTERS roster grid, STORE offers, owned cosmetics, PASSES tier detail → packed item
  & hero SKUs.
- "<MISSING STRING TABLE ENTRY>" / "ITEM NAME" / "TEXT BLOCK" placeholders → packed UI
  string tables (LogStringTable: Failed to find ST_Cosmetics_Categories, etc.).
- Hero-token count → battlepass reward-track claim state (reward SKUs; confirmed NOT a
  wallet balance).

So Milestone 3 almost certainly has TWO tracks — please scope both and recommend an
order:
  TRACK A — IoStore extraction. Stand up UE5.4 IoStore tooling (FModel / retoc /
    ZenTools / UEViewer) against Loki/Content/Paks to extract: the hero catalog +
    hero/item/cosmetic SKUs, the storefront offer/bundle definitions, and the UI string
    tables (ST_*). These real IDs are the missing inputs that unblock Hunters, Store,
    Armory ownership, and Passes. The game backup is at
    "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE".
  TRACK B — interactive backend flows. Make menu ACTIONS round-trip, not just reads:
    equipping cosmetics (POST/PUT /personalization/players/{id}/clientprofile,
    /lobbyplatforms), claiming battlepass/progression rewards
    (PUT /progression/players/{id}/mission, claim endpoints), store purchase/redeem
    orders (/storefront/orders, /storefront/steam/player/, /storefront/entitlements),
    party invites / friend requests (the /lobby WS protocol + party endpoints),
    missions, and the mailbox. Each is a request the client SENDS that currently hits
    the {} catch-all — capture it, RE the expected response, return a typed shape.

PROVEN METHOD (unchanged — it works well):
- The Go server listens HTTP :8080 (AccelByte + PostAuth via -ini: URL overrides) +
  HTTPS :443 (Theorycraft hosts via hosts-file redirect) and logs every request to
  docs/capture.log (WS frames as WS <- / WS ->).
- I (the agent) CANNOT launch the game. The user runs .\configs\launch-redirect.ps1
  (elevated; it rebuilds from source) and reports back / sends screenshots.
- Recon sources: %LOCALAPPDATA%\SUPERVIVE\Saved\Logs\Loki.log (every URL, deserialize
  error, warning; UTF — note it's UTC and OVERWRITTEN per launch, so a fresh-exit log
  can shadow the live session — cross-check docs/capture.log, the HTTP ground truth)
  and UTF-16/ASCII string scans of the shipping exe
  (Loki/Binaries/Win64/SUPERVIVE-Win64-Shipping.exe). LogPlatformStorefront /
  LogPlatformInventory are excellent readback channels for what the client parsed.

CRITICAL GOTCHAS (don't re-learn):
- List endpoints want an OBJECT wrapper with the required field present
  ({"data":[],"paging":{}}, not {} or []).
- UE's JsonObjectStringToUStruct IGNORES JSON keys that match no UPROPERTY, and ONLY
  rejects the whole doc when a key that DOES match has the wrong TYPE. So you can probe
  liberally with safe string/int/array values; send only fields whose type you're sure
  of. This is the key that unlocked the decode probes.
- "Could not find service address for service X" → add X to serviceHostnames in
  internal/loki/loki.go (service name has NO hyphen: coregame; URL path DOES: /core-game).
- The server runs elevated; my non-elevated shell can't kill it — the launch script
  handles restarts.
- Binary RE: many struct field names are deduplicated FNames (pooled), so a struct's
  contiguous cluster only shows fields UNIQUE to it. Use the decode-probe loop (send
  sentinel values, read back via logs/UI) when clustering isn't enough.

START BY: recommending whether to lead with Track A (IoStore extraction — the bigger
unlock, since it feeds Track B's content) or Track B (interactive flows that don't need
SKUs, e.g. equipping a cosmetic the client already knows locally). Then pick the single
highest-value system, RE it, implement, have the user relaunch, and iterate.
```

---

## Why this framing

- Milestone 2 hit a clean ceiling: backend can't invent packed catalog IDs/strings.
- "Functional systems before gameplay" means two distinct kinds of work — extracting the
  packed catalogs (Track A) and making menu actions round-trip (Track B) — and they
  interlock (B's content comes from A).
- The proven probe-and-relaunch loop carries straight over; the new ingredient is
  IoStore tooling.

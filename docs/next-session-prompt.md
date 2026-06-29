# Next session prompt — SUPERVIVE Revival dedicated-server stub

Paste the section below as the first message of the new session. It
bootstraps the agent fully without re-reading dozens of files.

---

We're starting a new chapter of the SUPERVIVE Revival project on branch
`claude/assetregistry-primary-assets-w7pljz`. Repo at
`G:\git\Supervive Revival Project`. The diagnostic phase for the menu data
blockers is COMPLETE. This session begins the **dedicated-server stub**
work, which is required to unblock the Missions modal (and likely Store,
Cosmetics, Hunters grid, all in-match features).

START BY (in this order):
  cd "G:\git\Supervive Revival Project"
  git status
  git log --oneline -15
  # Then read in order:
  #   docs/dedicated-server-stub.md   (★ this chapter's design notes — read first)
  #   docs/lokiassetmanager-vtable-dump.md  (the full RE diagnostic, ~2000 lines;
  #     skim to the "G1-G2 NEGATIVE" section at the end for the latest verdict)
  #   docs/trackb-notes.md  (HTTP endpoint surface; `handleCoreGamePlayer`
  #     stub commentary mentions where match-server connect info goes)
  #   docs/endpoints.md     (every endpoint + handler status)
  # Memory file [[supervive-hero-roster-blocker]] auto-loads with the
  # latest verdict.

THE CORE FINDING THIS CHAPTER ACTS ON:

The Missions modal calls `UMissionsModel.GetActiveMissionModel(fpaid)` /
`GetClaimableMissionModel(fpaid)`. Both are NATIVE methods on
UMissionsModel that iterate a TSet at `UMissionsModel+0x30` containing
`UMissionModel*` pointers. That TSet is populated ONLY by
`OnPSMissionsUpdated` (FName 0x0058FF4F), which fires from UE Network
Replication on `LokiPlayerState_Missions`.

At the menu, there is NO live `LokiPlayerState_Missions` instance
(CDO-only, confirmed via findptr on its vtable, both pre- and
post-restart). So no missions, hence empty modal.

Enriching `PUT /progression/players/{id}/mission` response with a full
MissionData payload was tested (commits `368b675` + `435b739`) and
CONFIRMED to NOT trigger UMissionModel creation — the HTTP path is
write-only. The architectural reality: missions arrive via a UE
dedicated server replicating `LokiPlayerState_Missions` to the
connected client.

THIS CHAPTER'S GOAL:

Bring up a UE5.4 dedicated server stub that the client connects to and
that replicates enough of `LokiPlayerState_Missions` for the Missions
modal to render at least 1 mission. Treat that 1-mission render as the
"hello world" smoke test; everything else (more missions, Store /
Cosmetics replication, in-match logic) follows the same path.

Per `docs/dedicated-server-stub.md`, three implementation paths exist
(Path A = full UE5.4 dedicated server, Path B = Go netcode emulator,
Path C = hybrid). Decide which is tractable based on what's available
on the user's machine.

START-OF-CHAPTER CONCRETE STEPS:

1. **Survey UE5.4 install** — does the user have UE5.4 source / editor
   installed? If yes, what path? If only the binary launcher install,
   server targets aren't directly buildable without the source. Run
   `Get-ChildItem 'C:\Program Files\Epic Games\UE_5.4' -ErrorAction SilentlyContinue`
   and similar paths. Ask the user if not found.

2. **Capture the post-matchmaking protocol** — modify
   `server/internal/interactive/interactive.go::handleCoreGamePlayer`
   to return a phantom matchInfo pointing at `127.0.0.1:7777` (or
   another test port nothing's listening on). Restart `ags`, watch
   Loki.log for what the client tries to do next when it thinks there's
   an active match. That tells us the protocol surface to implement.

   The current handler returns
   `{hasActiveMatch:false, matchInfo:null, player:null}`. The shape of
   matchInfo when populated is unknown — needs experimentation. Likely
   fields: server address, server port, session token, match ID.

3. **Decide on Path A/B/C** based on findings + scope appetite. Document
   the choice in `docs/dedicated-server-stub.md`.

KEY TECHNICAL ANCHORS (already RE'd):

UMissionsModel layout — what replication needs to fill on the client:
```
UMissionsModel
  +0x30 : TSet<UMissionModel*>  ← populate via OnPSMissionsUpdated
UMissionModel
  +0x40, +0x48 : FPrimaryAssetId PoolId — the lookup key
  +0xB8, +0xB9 : flag bytes — both must be 0 to qualify as
                   "active" / "claimable" per native impl disasm
```

Per-category pool wiring (from
`docs/exports/WBP_UI_MissionModalCategory.json`):

| Category | PoolAsset BP classes (FPrimaryAssetIds when GetPrimaryAssetIdFromClass'd) |
|---|---|
| Dailies | DA_MissionPoolDailyEasy_C, DailyChallenge_C, DailyEasy_Planbee_C, DailyChallenge_Planbee_C |
| Weekly | DA_MissionPoolWeekly_C, WeeklyChallenge_C, Weekly_Planbee_C, WeeklyChallenge_Planbee_C |
| Seasonal | DA_MissionPool_Tournament_C |
| Onboarding | DA_MissionPoolOnboardingPlanbee_C, MissionPoolOnboarding_C |
| PCBang | DA_MissionPoolDailyPCB_C, DA_MissionPoolDailyPCB_Armory_C |

For the smoke test, even 1 UMissionModel with PoolId =
`MissionPool:DA_MissionPoolDailyEasy` + flags=0 in the TSet would make
the Dailies tab render that 1 entry.

GUARDRAILS (per CLAUDE.md):

- Commit + push each meaningful step. Push needs `gh auth` or system
  git credential helper — interactive prompt fails in the Claude shell,
  so user pushes manually.
- DON'T mutate the game's running state without showing the user the
  command and the expected effect first.
- The HTTP/HTTPS redirect is already working; don't touch
  `launch-redirect.ps1` casually.
- Steam must be running before the game launches (else Auth Failure
  14005). Easy to miss.

LARGER CONTEXT REMINDER:

The user's strategic intuition that "the menu blocker is server-side"
was proven correct this session. The dedicated server stub is the next
required-but-hard milestone for the project; the user said: "The
dedicated server stub was always going to be a major requirement for
this project to work at all. I know for a fact that most of the game
will not be playable or triggerable without the dedicated server
allowing the client to do so." Treat this chapter as a multi-session
effort. The first session is mostly surveying + the matchmaking-protocol
probe; it's fine to end without ANY actual server code if the recon
clarifies what the implementation needs to be.

TOOLING ALREADY BUILT (do not duplicate):

- `tools/usmapdump` (external RPM, includes `poke` for WriteProcessMemory
  experiments and `nameid` for FName resolution — note: `nameid`'s pool
  discovery sometimes fails on fresh processes; you may need a few
  launch attempts)
- `tools/extractor` (CUE4Parse-based, includes `bpdump` for cooked-asset
  property inspection)
- `tools/inject` (manual-map DLL injector for in-process shims like
  `registration_shim.cpp`)
- FModel installed at `G:\Tools\FModel` (configured for SUPERVIVE
  GAME_UE5_4) — use for any further cooked-asset inspection where
  property names matter

If you propose to run a long shell command or modify a critical file,
state the intent in one sentence before the tool call so the user can
veto. Otherwise proceed at the same pace as prior sessions.

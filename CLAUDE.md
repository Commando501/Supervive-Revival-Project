# SUPERVIVE Revival — project rules for Claude

This is a reverse-engineering project to revive a Steam-launched UE5.4 game whose
official backends are dead. We've redirected the client to a local Go server
(`server/cmd/ags`) over hosts-file + HTTPS-with-self-signed-cert. The work spans
backend RE, IoStore extraction, native shim injection, and asset-registry patching.
Lots of dead ends. Honor the prior-work docs.

The whole front-end menu is now ONLINE: login, the ALL HUNTERS roster (+ click-to-
refresh), the STORE, COSMETICS, the full MISSIONS page (with working progress
bars), the PASSES / Hunter's Journey account pass (full 85-tier ladder), and the
AVATAR / CALLSIGN customization (render + live switching) all render live. That was
achieved with the backend feed **plus** a set of client-side native shims built on a
reusable game-thread native-call primitive (see below).

**Current frontier = the tutorial WORLD.** Getting in is solved (S107/S108): the client
loads `LVL_Tutorial`, the hero spawns, is possessed, moves, and **walks/runs with real
locomotion animation** (S108b). The whole sitting is now **hands-free** — no human at the
keyboard (see "Tutorial sittings" below). ★★ **STABILITY IS LARGELY SOLVED (S112, 2026-08-08):**
FK-7 — "the run dies within ~1–5 min" — was substantially **our own standing `.text` patch**, and the
shipped `tutorial_launch_play.dll` no longer makes one (10/10 armed windows died with it vs 2/30
without, Fisher p = 0.00000008; 16/16 survived a full 600 s hold). What is still open is *simulation*
(abilities / combat: the hero owns no ability system) and the **staging hazard** — ~25 % of launches
still die before the probe is injected, with only `gft`+`fo` resident.

## Before doing anything else

### If the user mentions hero/roster/grid/hunters/store/cosmetics/missions modal/passes/battlepass
**These are SOLVED — they render live.** Do NOT re-open the closed hypotheses.
- **Roster / store / cosmetics** — root cause was one un-set client-side
  catalog-ready sub-flag (`CatMgr+0x354`), NOT the backend, NOT enumeration, NOT
  LokiAssetManager bypass (all falsified over ~13 sessions). Fix = the native shim
  `tools/sigbypass-mod/catalog_store_fix.dll`. ★ **As of 2026-08-06 it contains NO `.text`
  patch at all** — the old self-restoring `jz`-NOP was MEASURED to be the protector-kill
  trigger (`docs/s111-bisect-jz-is-the-trigger.md`) and was dropped; the shim's existing
  **`[+0x354]` DATA poke** on the live CatalogManager is sufficient and the roster still
  renders (screenshot-verified, `docs/s111-jz-dropped-shipping.md`). It still does the
  AssetManager scan + CatalogEntry poke. Rollback: `build.ps1 -Variant jzpatch`.
  ⚠ The data poke must land BEFORE the user first opens HUNTERS — keep it early and
  continuous, or the grid can Construct-and-wait with an empty roster (S47). STORE
  tiles also need the backend to mark cosmetics `IsOwned` (`handleInventory`).
  Living log: `docs/hero-roster-attempts.md`.
- **Missions** — the full page renders client-side via the native-call primitive
  (`AsyncLoadPrimaryAssets` → `CreateMissionModelFromFinalProgress` → swap
  `ProgMgr.MissionsModel`), packaged as `tools/sigbypass-mod/missions_fix.dll`
  (`launch-redirect.ps1 -Missions`). Per-account progress served by the backend.
  Read `docs/session-59-progress-bars.txt` + `docs/missions-progression-hookup.md`.
- **PASSES / Hunter's Journey (ACCOUNT pass)** — the page renders live with its full
  85-tier ladder (S83). Two client-side root causes, NOT the backend (that route was
  exhausted over ~9 probes): (1) `CheckAccountPassChanges` (`0x5794480`, the populate's
  real caller) bailed on its tier gate `dword[PM+0x90+0xEC] == -1`; (2) the keystone —
  a **VM map-key mismatch**: it finds the view model by `P->GetPrimaryAssetId()`
  (vtbl+0x1D0) → `ToString` (`0x12F4230`) → `FindVM` (`0x57AB180`), i.e.
  **`ProgressionTrack:HuntersJourney`**, while our track keyed it bare `HuntersJourney`.
  Fix = `tools/sigbypass-mod/battlepass_adopt_fix.dll` resolves that key at runtime and
  adopts with it (BUMP its `Version` on every re-inject). Two traps: `VM.Levels`(+0xC8)
  is `TArray<UObject*>` (NOT PrimaryAssetId) and the populate `0x57DF4B0` CONSTRUCTS
  objects — **never force-call it** (that was the S82 crash); and the old note
  "P = S[+0x238]" is WRONG (S *is* `HuntersJourney_C`).
  Read `docs/session-83-passes-tier-grid-solved.txt` (its POST-SESSION CORRECTIONS block is
  load-bearing — a later 21-agent RE pass showed the grid is built by the VM
  builder's Init `0x57BB560` ahead of both gates, so the map key is the SOLE
  verified cause, and it FALSIFIED "the backend route is exhausted": the native
  ingester `0x585A570` does exist). Still open: real PROGRESS (tiers draw but
  nothing is claimed — gated on `byte[PM+0x388]`) and the SEASONAL pass (same
  byte, plus no packed `LokiDataAsset_Season`).

- **AVATAR / CALLSIGN (player-card customization)** — SOLVED end-to-end, BACKEND-ONLY,
  no shim (S85, 2026-07-21). Three causes, none the render/enum: (1) the avatar CARD
  reads `PartyMember.PersonalizationLoadout` which we never served — fix = `buildSoloParty`
  serves `personalizationLoadout` on the party member; (2) switches wrote to the WRONG
  ACCOUNT — the client's `/oauth/token` grant fell to an ad-hoc `"player"` key
  (`b70b628c…`) while the Steam login + party used `platform:steam` (`9b9d…`); fix =
  `token.LocalPlayerKey`/`LocalPlayerID` canonicalizes every unidentified-user auth path;
  (3) `UPartyModel::SetParty` (`base+0x587BE90`) gates the whole party doc on a strict
  monotonic `FParty.Version` (`cmp [PartyModel+0x568]; jge bail`) — we pinned `1`; fix =
  `store.partyVersion()` bumps on each loadout write. LATENCY (~30-57s → ~1.5s): the client
  applies the party ONLY on its `/notifications` messenger-RECONNECT resync, so we DROP that
  socket on a loadout write (`ws.Conn.Drop()` + `lobby.MarkDirty`, wired via
  `interactive.SetPartyDirtyNotifier`). The ~1s floor is the client's own reconnect backoff
  (not backend-controllable); a native shim (write member loadout + broadcast
  `OnPersonalizationLoadoutChanged` `base+0x587C699`) would reach ~0.2s but adds a PI-hooker —
  parked. ⚠ `PartyModel` exposes NO reflected `Version` UProperty (absence of a UProperty ≠
  absence of the field). ⚠ the `avId:""` presence trap: sample presence AFTER an equip.
  Read `docs/session-85-avatar-render.md`.

Before RE-touching any of these, READ the relevant doc above first — the value is
the trial-and-error history, and the corrected root causes are easy to regress on.

### Before touching anything tutorial- / FK-7- / FK-24-shaped
Read `docs/s108-fk24-instrument-corrected.md` **including its RETRACTIONS block at the
top, which governs**, then `docs/s108b-ksmactor-bisect.md`, `docs/s108-crash-triage.md`,
`docs/s108-fk7-verification-attempt.md` and `docs/s108-skeptic-review.md`. Also
`docs/s108-fk24-instrument-corrected.md` and `docs/fk7-crash-settled.md` (SUPERSEDED banner).

★★★★★ **FK-7 IS CLOSED — fixed, shipped and verified (S112, 2026-08-08).**
**Do NOT re-open it.** `docs/fk7-crash-settled.md` §0 still reads "OPEN (do NOT close)"; that verdict
was correct when written, the experiment it demanded has now been run, and the file carries a
SUPERSEDED banner at the top. Read `docs/s112-fk7-ab-results.md` first.
**What still fails on the tutorial route was SPLIT OUT as FK-31 / FK-32 — see
`docs/fk31-fk32-successors.md`.** Neither is FK-7; each has a different mechanism and window, and
pooling them under FK-7 would repeat this project's own recorded error of merging distinct
mechanisms under one label.
- **FK-31 — the staging hazard (NOW THE DOMINANT FAILURE): 22/82 launches (27 %)** die before the
  probe is injected, with only `gft`+`fo` resident; all dumped ones are `OURS/protector`. `fo`'s
  ≤8 s `.text` prologue and ≤25.5 s `.rdata` slot-285 patch are CONFOUNDED in every run ever flown.
  ⚠ `KNOLOGINVT` is **FALSIFIED — do not re-run it** (4/4 died, 0/4 map loads, fatal
  `ALokiGameMode::Login failed to Login`, p = 0.0026). Next: patch-then-immediately-restore.
- **FK-32 — the `0x0000DEAD` residual: 3/36 armed windows**, no artifact of any kind, NOT a protector
  kill. `0xDEAD` is not ours (no `TerminateProcess`/`ExitProcess` in any shim source; our own
  `Stop-Process` exits `0xFFFFFFFF`, measured). ⚠ N=2 — suggestive, not established. The exit-code
  instrument is permanent, so **harvest it, don't spend launches on it.**

★★★★★ **FK-7 detail (S112, 2026-08-08).** Final corpus: **standing `.text`
patch 10/10 armed windows DIED vs no module-image write 3/36 (8 %) — Fisher p = 0.00000007.** The
shipped `tutorial_launch_play.dll` (`.text 5151621d2154e454`, DEPLOYED) arms on **2 heap pointers**
and writes no module image; confirmed on the default recipe path, **5 of 6 armed windows survived a
full 600 s**. Rollback = `-Variant play-textpatch` (`433cf7d8f6a0770f`), which IS the measured control.
⚠ **What remains is NOT FK-7:** the **staging hazard, 22/82 launches (27 %)**, which kills the game
before the probe is injected and is untouched by this fix — it is now the dominant tutorial-route
failure. And **no shim-free tutorial run has ever been made**, so a game defect is unsupported but
not excluded.
⚠ **The residual is 3/36 and unexplained.** All three left NO artifact; the two instrumented ones
exit **`0x0000DEAD`** (a silent TerminateProcess sentinel that is NOT ours — our `Stop-Process` exits
`0xFFFFFFFF`, measured as a control). N=2, reproducible, unattributed.

★★★★ **FK-7 WAS RE-TESTED AND LARGELY ANSWERED (S112, 2026-08-07). START AT
`docs/s112-fk7-fk8-completion-review.md`, then `docs/s112-fk7-ab-results.md`; the S111 handoff below
is now history, not a plan.** Review verdict: **FK-7 substantially answered, NOT closed; FK-8 closed
and independently re-confirmed.** Three review findings that govern:
- ★ the "treatment survived by doing LESS" objection is **FALSIFIED** — identical `[PL]` init, MORE
  shim work per second, and the hero walks the SAME path in both arms (treatment reaches `x≈2841`,
  control dies partway at `x≈1379`);
- ★ **FK-8 re-confirmed DIRECTLY against ground truth** (N=11, median delta −6.2 s) — but with a
  **systematic ~6 s undercount** and **one unexplained −48.8 s outlier**, so per-death
  `SecondsSinceStart` carries occasional tens-of-seconds error. **Do not lean on narrow bands.**
- ⚠ **the camera family occurred 0 times in 41 launches, which is NOT evidence `KXFORMFIX` worked**
  (denominator is the 21 armed windows; at ~8 % P(0) ≈ 0.17).
★★★ **PHASE 3 FLOWN (2026-08-08) — the result is now overwhelming.** Matched 600 s holds, footprint
the only variable: `play-funcswap` (17,126 pointers) **0/8 died** and `play-funcswap-one` (**2**
pointers) **0/8 died**, all 16 surviving the full 600 s. Pooled across every non-`.text` arm:
**2/30 (6.7 %) vs the standing-`.text` control's 10/10 — Fisher p = 0.00000008.**
- ★★ **`build.ps1 -Variant play-funcswap-one` (`5151621d2154e454`) is the SHIPPABLE form** — it arms
  on **`swapped=2` heap pointers**, not 17,126, and RM_PLAY runs normally for 600 s. Target
  `ReceiveTickClient` was picked from a MEASURED settled-world profile (`play-funcswap-profile`,
  90 s window: 1549 hits/90 s ≈ once per frame). The old 4 s window only profiles world load, where
  every candidate reads `hits=1` and none is selectable.
- ⚠ **The footprint hypothesis is UNTESTED, not refuted** — 0/8 vs 0/8 cannot discriminate. Phase 3
  simply could not reproduce the residual; the phase-1 2/10 now looks like noise, since the LONGER
  600 s hold produced **0/16** (the opposite of a dose-response).
- ⚠⚠ **`KNOLOGINVT` FALSIFIED — do not re-run it.** Dropping `fo`'s slot-285 `.rdata` patch kills the
  route: **4/4 launches, 0/4 map loads**, fatal `ALokiGameMode::Login failed to Login` (exactly what
  the S62 source comment predicts), p = 0.0026. S62's purpose STANDS. The `.rdata`-is-caught-too
  question **cannot be tested by removal**; it needs a patch-then-immediately-restore design.
- **The staging hazard is now the largest open item on the tutorial route** (~25 % of launches die
  before the probe is injected; 6/22 in phase 3).
A pre-registered one-variable A/B on the tutorial route, **N = 10 armed windows per arm**:
**control (RM_PLAY's 600 s standing `.text` patch) died 10/10; treatment (the same shim with the
hook expressed as a heap `UFunction.Func` swap, zero module-image writes) died 2/10. Fisher's exact
p = 0.00071.** ⇒ **FK-7 is substantially OUR OWN standing `.text` patch.** Build:
`build.ps1 -Variant play-funcswap` (`badecc840bafee84`); control rebuilt from HEAD is
`433cf7d8f6a0770f`.
- ★ **The kill MODE differs, not just the rate.** Control deaths exit **`0xC0000005`** and leave the
  `runtime.dll+1` crashpad dump; the treatment death exits **`0x0000DEAD`** and leaves **nothing**.
  `0xDEAD` is NOT ours (no `TerminateProcess`/`ExitProcess` anywhere in the shim sources). ⇒ the
  project's "artifact-less death class" is **not all hangs** — some are silent kills, and holding an
  OS handle open across process exit recovers the code for free. Do this in every future harness.
- ★ **28/28 dumps this session were `OURS/protector`. ZERO game-defect dumps.** The dump that would
  be the first real FK-7 evidence still does not exist.
- ⚠ **The residual is 2/10 and is OPEN** — not a protector kill, no artifact. Leading suspect is the
  treatment's OWN footprint (it swaps 17,126 `Func` pointers); `-DKFSNAME=<name>` swaps one instead.
- ⚠⚠ **8 of 20 non-arming launches DIED DURING STAGING**, with only `gft`+`fo` resident and the probe
  never injected — before RM_PLAY's patch exists. So **"FK-7 is our PI hook" is too narrow.** `fo`'s
  ≤25.5 s `.rdata` slot-285 vtable patch is the leading suspect and is still CONFOUNDED with its own
  transient `.text` write. `KNOLOGINVT` **does not exist** (the S111 handoff cites it as if it did);
  neither did `KPLAYHOLDMS` until S112 added it (`-Variant play-hold300`).
- ⚠ **`build\tutorial_launch_play.dll` was ONE COMMIT STALE** (`513c6277c3ae88f3` vs HEAD's
  `433cf7d8f6a0770f`); `KWIREGAS` defaults to **1**, so the gap was live code, not dead. Archived as
  `build\tutorial_launch_play_a827ef9_ARCHIVED.dll`. **Rebuild `play` before any A/B against it.**
- ★ **Positive control that actually works:** `[PL] *** init complete ***` (`tutorial_launch.cpp:5190`)
  — fires ~100 %, is arm-symmetric, and catches a silent no-op in a non-`.text` arm. **Do NOT use the
  mandated 3× `play_novtguard` gate**: it fires on an ~8 % event and voids ~4 sittings in 5.
- Harness: `configs/fk7-ab-run.ps1` (one armed window) + `configs/fk7-ab-campaign.ps1` (alternates on
  ARMED WINDOWS, not launches) + `tools/crashtri/fk7_ab_analyze.py`.
- ⚠ `tools/crashtri/fk8_classify.py` dedupes UECC dumps on the constant `"UEMinidump"` → reports
  **1 distinct report for 105 directories**. Do not point it at `Saved\Crashes`.

Historical (S111): `docs/s111-FK7-HANDOFF.md`, then `docs/NEXT-SESSION-PROMPT.md`. S111 (2026-08-07) measured that a **standing `.text` write is what
makes the protector kill the process** (patch standing 11/12 vs no patch 0/5, p = 0.00097; a
*permanent* heap-**bytecode** patch is free, 0/9). And **`tutorial_launch.cpp:6511-6513` (RM_PLAY)
holds a 5-byte `.text` patch at `ProcessInternal` for 600 s** — `g_done` is never set in RM_PLAY —
which is the exact condition measured at **~88 % lethal**, standing for the entire sitting and
bracketing the whole observed FK-7 death spread (87–524 s). ⇒ **The primary hypothesis is now that
FK-7 is largely OUR OWN PI hook.** Audited: only **11** death records survive every contamination
filter, **ten of them from one 15-hour stretch**, and **all are shim-mediated** —
`log_forceopen_tutorial_url == 2` in 15/15, i.e. **no shim-free tutorial run has ever been made.**
⚠ Also: the mandated 3× `play_novtguard` control gate would declare a sitting VOID ~4 times in 5
even when everything works (the camera family is ~8 % per staged launch) — fix the control before
spending launches.

The short version, because it has already cost two sessions:
- **The FK-24 watchpoint probe was killing the game**, and its crash was recorded as a
  game crash for a whole session. Dump `166396E2` (DR mode) and `FED1F952` (page mode) are
  both **the shim self-killing**, not FK-7. Do not feed them to `crash_census.csv` analysis.
- **S107's "the watchpoint is VOID → escalate `wprobe`→`wprobe2`" was unfounded.** The DR
  watchpoint fired fine (127/128 threads armed, GameThread among them). The writer of the
  `0x01` byte at `PCM+0x420` is **still NOT named**; FK-24 is OPEN.
- **FK-7 is OPEN.** Zero reproduce-then-repair runs exist. The `play_novtguard` positive
  control is MANDATORY and a **quiet control means the sitting is VOID, not a pass**.
  Hold to **T+220–250 s, NOT T+300 s.** ⚠ **The hold survives; the "~285 s" number does NOT** (S111,
  FK-8 corpus mining). MEASURED over 114 distinct death records: one late-kill mode is **240–295 s,
  N=15, median 264 s — only 4 of 15 are ≥283 s, and 4 of 15 are asserts** (asserts are not
  anti-tamper kills). ⚠ **That band describes ONE CLASS, not the population — do NOT hold to it**
  (S111 reconciliation, `docs/s111-fk8-s110-reconciliation.md`). On the **crashpad** class, tutorial
  route, N=13 — which contains every S110 sitting — deaths run **87–524 s, median 283, and 7 of 13
  fall OUTSIDE 240–295**, four of them above it (336 / 432 / 491 / 524 s). Two of those four are not
  S110 runs, so the tail was already in FK-8's own corpus. S110's own "budget ~330 s" is likewise too
  tight. ⇒ **No `T+<n>` rule survives; use the staging-invariant anchor below and the fault family.**
  (The two sessions' clocks were cross-checked and agree to 2–3 s, so this is a real spread, not a
  clock artifact.) Worse, `SecondsSinceStart` is the **launch** clock and therefore contains the
  operator's staging schedule, which moved **+33.0 s** between the July and August batches — so any
  `T+<n>` rule silently drifts when `-InjectGapSeconds` changes. **Prefer the staging-invariant form:
  hold ≲50 s past `Load map complete …/LVL_Tutorial`.** Detect the kill by **fault family**
  (`RIP == runtime.dll base + 1`, EXECUTE, `ExceptionInformation[0]==8`), never by elapsed time.
  See `docs/fk8-crash-timing-mined.md` §2.3.
- ⚠ **`play`'s `.text` hash has moved THREE times. Current: `513c6277c3ae88f3`** (S110 `KANIMREF`).
  `7bc4df9236ead0ac` was `play` only between S109 and S110; `ae532866e15fd8ac` only between S108b and
  S109; `a67239a0d83d9300` is `play-statictest`. Docs citing any of those as "the candidate" are stale.
  ⚠ `play-strictroot` / `play-noanimref` share a 161,792-byte `.text`; historically `play` /
  `play-earlywalk` shared identical whole-file AND `.text` SIZES (which is part of why earlywalk was
  DELETED in S110) — **only the hash separates such pairs. Diff `.text`, never size.** Use
  `tools/sigbypass-mod/verify_dll.py` or the section-hash snippet in `docs/s109-dump-forensics.md` §23.
- ⚠ **`KGCROOT` was silently INERT from S106 until S109.** Its root-bit corroboration used
  `AND(native classes) & ~OR(sampled ordinary objects)` on the false premise that ordinary objects are
  never rooted; **one** rooted sample in 64 vetoed the correct bit, so nothing was ever rooted. Fixed
  (frequency test; `-DKGCROOTSTRICT=1` restores the old one). ⚠ **Fixing it did NOT stop the asset
  collection** — the run AnimSequence is still collected with a verified `flags -> 40000004` readback,
  if anything sooner. So "rooting keeps it alive" is **not established in this build**.
  See `docs/s109-dump-forensics.md` §22-§24.
- ★★★ **THE ANIMATION THREAD IS SOLVED (S110) — read `docs/s110-item-watch-gc-mechanism.md` before
  re-opening any of it.** The run anim really IS garbage-collected (full `BeginDestroyed →
  FinishDestroyed → LowLevelRename(NAME_None) → FreeUObjectIndex`, slot reissued later), so "torn down
  out of band" is ELIMINATED. **The poked RootSet bit is INERT** — a phase-locked experiment (only the
  injection phase varied) gives leads of **0.15 s / 2.9 s / 33.1 s from poke to the next GC pass, and
  the asset died at that pass every time**; in the last it sat through six clean heartbeats and died
  708 ms after the flip, so it is not a race. **Do not "fix" this by rooting harder.**
  **THE FIX = `KANIMREF` (default ON in `play`)**: park the asset in the body component's unused
  `AnimationData.AnimToPlay` UPROPERTY so the traversal reaches it — offsets resolved BY NAME, write
  readback-verified. CONFIRMED: re-marked at **two** consecutive GC passes, zero `[GCW]` lines, and
  `PlayAnimation(run/idle, loop) ok` cycling **at the default `KAUTOWALKATMS=20000`** — so
  `play-earlywalk` (which only RACED the collection) was **deleted**; `-DKAUTOWALKATMS=<ms>` still
  works for a one-off. Control arm: `play-noanimref`.
  ⚠ Also: **"Unreachable" is not a sticky bit in this build.** Reachability is an alternating flag
  rotating through bits 0/1/2, flipped population-wide each GC pass — which is what S109's unexplained
  `flags=00000004` / "bit 1 on 81% of ordinary objects" actually was, and it gives a free read-only GC
  clock (`tools/re/item_watch.py --marker`, ~61.1 s period).

### Before touching anything WebSocket- / notification- / server-push-shaped
★★★★★ **THE `/lobby` ENVELOPE — EVERY FRAME WE EVER SENT THERE WAS SILENTLY DROPPED, NOW FIXED
(S117, 2026-08-13). Read `docs/fk15-lobby-fragment-defect-20260813.md` FIRST.**
The client asks for message delimiters in its WS handshake and we never honoured them:
`X-Ab-EnvelopeStart: LbS` / `X-Ab-EnvelopeEnd: LbE` (literals `.rdata 0x8604890` / `0x86048A8`).
It stores them as the FStrings at **`lobby+0xA8` / `+0xB8`**, and `Lobby::OnMessage`'s completeness
check (**`.text 0x4b35a80`**, gating the fragment log at `0x4b0adf8`) takes the no-framing fast path
**only when BOTH are empty**. MEASURED before the fix: **14 `Raw Lobby Response` → 14
`Message fragmented` → 0 dispatches.** `Type: %s` (`0x04B0B12B`) had **never fired**.
⇒ **Our `listOfFriendsResponse` / `setUserStatusResponse` etc. were NEVER parsed**, and all five
2026-06-29 probes were buffered the same way — that is the mechanism behind FK-15's "silent
absorption", and it was on OUR side.
★ **This is also why the messenger probes worked and the `/lobby` ones did not** — the messenger
negotiates **empty** markers (`envelope=[""..""]`), so it needs no envelope. The two channels were
never comparable.
**FIX:** `ws.Conn.WriteText` wraps with the socket's own negotiated markers (a no-op on the
messenger); `WriteTextRaw` keeps the unwrapped form for probes. **Result on reconnect: dispatch
0 → 4**, four responses parsed for the first time ever.
★★★ **THE FULL 33-TYPE SWEEP THEN RAN CLEAN — 33/33 RECEIVED, PARSED AND ROUTED**
(`docs/fk15-sweep-33-types-20260813.md`). Dispatch 5 → 38; **0** parse errors, **0** deserialize
failures, and `Message fragmented` did NOT grow. ⇒ **the `/lobby` receive channel is fully
functional for the first time in this project's history.**
⚠⚠ **CORRECTED same day — do NOT read this as "33/33 reached a bound handler case."** That claim
rested on the absence of `Error; Detected of type notif but no specific handler case assigned`,
and **that absence is not evidence**: those two error strings are **not plain `UE_LOG`s** — they are
`Printf`'d into an FString and pushed through a virtual on `Lobby+0x218`, so they may never reach
the log. **Disproof:** a bogus type (`dsNotice-PLACEHOLDER`, which exists nowhere in the binary)
produced the IDENTICAL trace including **`Type: dsNotice-PLACEHOLDER`** ⇒ **`Type: %s` is logged
BEFORE the handler lookup.** The 33==33 jump-table corroboration stands on its **static** evidence;
the sweep did not confirm it live.
★ **Free control, reuse it:** push a type that cannot exist. If your "handler found" detector reads
the same for the bogus type, it is not measuring what you think.
★★★ **SETTLED STATICALLY INSTEAD (`docs/fk15-handlenotif-jumptable-20260813.md`): ALL 33 CASES ARE
REAL.** `Lobby::HandleNotif`'s jump table (33 dword RVAs at `.text 0x4b04978`; index = `enum-1`,
default `0x4b048f9`) has **33/33 entries pointing into `.text` and ZERO equal to the default**
(32 distinct; idx 17/18 share the banned/unbanned pair). ⇒ **`dsNotif` reaches a real case body.**
A case = `{delegate, type descriptor}` handed to one shared deserialize+broadcast helper
(`0x4AD6020`); idx 23 verified live: `lea rdx,[rdi+0x1550]; lea rcx,[→0x9FFE6F0]; call 0x4AD6020`.
⚠ The index→type map comes from a RUNTIME `TMap` at `.data 0x9FFE2D0` — "idx 23 = dsNotif" is
INFERRED from `.rdata` order and unconfirmed; the headline holds regardless since all 33 are real.
★★★★ **AND THE SWEEP DECRYPTED THEM: 9/33 → 33/33 case bodies.** Those pages had NEVER executed in
any of the 68 prior dumps. ⇒ **driving a code path from the backend FORCES `.text` decryption for
offline RE** — a steerable version of "coverage rises with what the game has run". Banked in
`dumps/lobby-dispatch-decrypted/`. **Reuse this: push the messages, then `dumpimage`.**
⚠ **Still open for `dsNotif`: whether anything is BOUND to the delegate it broadcasts.** Needs the
live `Lobby` object, and **two routes have now been tried and failed** — do not repeat them:
(1) via the accumulate buffer `Lobby+0xC8` — fails **by construction**, the FString's Data pointer
addresses the BUFFER START, not our message inside it, so `findptr` on the message correctly
returns 0; (2) via the envelope markers — self-validating in principle (`[P]`→"LbS" **and** `[P+0x10]`→"LbE"
⇒ `P == Lobby+0xA8`) — ⚠⚠ **its "0 aligned pointers [M]" result was RETRACTED: a GREP BUG, not a
measurement.** `findptr` prints `    @0xADDR   bytes: …` and the harness matched `^ +0x…`, missing
the `@`, so every "no hit" was the parser failing. **Caught by a positive control that should have
run first** (the global at RVA `0x9FFEBD0` provably points at `0x1D24F130AE0`; the harness called
that a miss too). ⚠ **Third instrument failure of my own that session, and it came AFTER writing
method rule 10.** Re-run with a parser self-test that aborts unless it sees the known hit.
★★ **CONFIRMED MEANWHILE — the offsets are no longer inferred [M].** The ctor at `.text 0x4AF2270`:
`+0x68` "X-Ab-Platform-User-Id", `+0x78` "X-Ab-LobbySessionID", `+0x88` **"X-Ab-EnvelopeStart"**,
`+0x98` **"X-Ab-EnvelopeEnd"** (header NAMES), then `+0xA8` zeroed → resized → memcpy'd from a
global = the **VALUE** slot. ★ And the marker is the client's **baked-in default**: the global at
RVA **`0x9FFEBD0`** is `FString{Data=0x1D24F130AE0, Num=4, Max=8}` = `"LbS"`. The client chooses
the markers, tells us in the handshake, and sets its own `+0xA8`/`+0xB8` — which is why they are
never empty. ⚠ `0x1D24F130B50` (16 B later) is `"friends"`, so these globals are a config array,
**not** an adjacent LbS/LbE pair.
★ `wstrings "LbS"` uncapped returns **27**, not 12 — the first run was capped and dropped 15
candidates. 26 are standalone `"LbS "`; the 27th is the raw HTTP header line.
**Next:** the re-run scan over all 26; then descriptor globals `0x9FFE6F0`/`0x9FFE810`/`0x9FFE860`;
then `vtslot`; a shim capturing `rdi` in `HandleNotif` is decisive but is an injection, and this
surface has been driven backend-only throughout.
⚠ **No handler ACTED** — a `type:`-only frame carries no payload, so the open question is now
**per-type PAYLOAD, not routing**, and the console iterates one in seconds. ⚠ Even
`disconnectNotif` / `partyKickNotif` / `userBannedNotification` were inert: sockets held 581 s
across the whole sweep, 0 crashpad. ⚠ `AlreadyProbed` is now deliberately **EMPTY** — the old
`matchmakingNotif` record was VOID (unwrapped, never dispatched) and skipping on it would have
protected a null that never happened; **`matchmakingNotif` is fully re-testable.**
★★ **`dsNotif` then landed:** `JSON Version: {"type":"dsNotif",...}` → **`Type: dsNotif`**, and
crucially **NO** `"no specific handler case assigned"` error ⇒ it reached its **dedicated handler
case**. No NetConnection followed, so the open question is narrow (what its delegate needs), not a
silence.
⚠ **Standing lesson:** the handshake is part of the protocol. Before concluding a channel ignores
you, log what the client ASKED FOR in its upgrade request.

★★★★★ **FK-15 IS SETTLED — REFUTED AND CONFIRMED LIVE (S117, 2026-08-13).** Read
`docs/fk15-ws-push-audit.md`, then `docs/fk15-probe1-live-result-20260813.txt`.
**THE CLIENT PRINTED OUR SENTINEL BACK.** One 19-byte TEXT frame on `/notifications/players/{id}`:
```
[2026.08.13-08.48.54:314][559]LogJson: Warning: JsonObjectStringToUStruct - Unable to parse json=[FK15-PROBE-FROM-AGS]
[2026.08.13-08.48.54:317][559]LogMessenger: Warning: Messenger recieved unexpected message: FK15-PROBE-FROM-AGS
```
Baseline captured immediately beforehand was **0**, against **393 same-category `Warning`s** in the
same log. ⇒ **server→client push WORKS and reaches the application layer. Do NOT re-open it.**
The belief *"server→client WebSocket push is measured non-functional (5 negative probes)"*
(`coverage-audit-s101.md:98`) is **false**, and its evidence is **void, not merely weak**.
- ★ **BONUS, and it corrects this file's own advice: `LogJson`'s silence was NEVER-RAN, not
  suppressed.** It was written off on *0 lines in 326 logs*; it fired here at `Warning`, unprompted,
  because **nothing had ever handed it malformed JSON**. It remains the wrong detector for the
  `/lobby` probes (that path uses a hand-rolled key:value→JSON converter, not `FJsonSerializer`) but
  on the **messenger** it is a valid working instrument. Live never-ran-vs-suppressed case.
- ★★★★ **PROBE 2 SHIPPED AND CONFIRMED — the ~60 s messenger reconnect churn is FIXED**
  (`docs/fk15-probe2-live-result-20260813.txt`). On the client's binary `hb` we now also write
  **TEXT `{"Resource":"hb","Version":0,"Payload":""}`** (`enableTextHeartbeatReply`, default ON;
  set false to revert). MEASURED: before, the watchdog fired **once per ~61 s like clockwork**
  (08:49:09 / 08:50:10 / 08:51:11 / 08:52:13 UTC); after, **zero fires** and the socket held
  **325 s+** against a prior max of ~61 s, with delivery 1:1 (5 `hb` in, 5 TEXT replies out).
  ⇒ **the messenger is now a stable, usable server→client channel** instead of a socket that died
  every minute. ✅ **S85 is unaffected — checked, not assumed:** an explicit `conn.Drop()` still
  forces reconnect + resync (client back in <6 s, `GET /party/parties/…` + `/party/players/…`
  re-issued). What is gone is only the *implicit* ~60 s resync.
  ⚠ Still inert and worth removing in a follow-up: the BINARY `hb` echo and the 30 s proactive
  BINARY keepalive. Both were left untouched deliberately to keep the change single-variable.
- ★★★ **PROBE 3 CONFIRMED + SHIPPED, AND ON BY DEFAULT — a targeted per-resource resync**
  (`docs/fk15-probe3-live-result-20260813.txt`). Pushing
  `{"Resource":"/match-history/players/<id>","Version":7,"Payload":""}` produced
  `GET /match-history/players/<id>` **491 ms later with the messenger connect count UNCHANGED** —
  a targeted refetch with **no teardown**. ★ Design note worth copying: the observable was chosen
  by first measuring **which resources are POLLED vs RESYNC-ONLY** (`/mailbox/config` polls every
  ~90 s and is useless as a signal; `/progression/players`, `/inventory/players`,
  `/mmr/player-ratings`, `/match-history/players`, `/party/parties` fire **only** on resync), so a
  fetch with no reconnect is unambiguous.
  **API:** `lobby.NotifyResource(playerID, resource, version, label)`; `MarkDirty` gains a targeted
  path behind `enableTargetedResync` that falls back to the drop if it cannot push.
  ⚠⚠ **VERSION IS A FOOTGUN — pass the version the HTTP document will carry, NEITHER MORE NOR
  LESS. Both failure modes measured live:** too LOW → **silently ignored** (a `Version 3` push at
  `/party/parties/` did nothing, because `partyVer` is seeded `time.Now().UnixMilli()` ≈ 1.76e12 —
  and that null is indistinguishable from "the client doesn't handle this resource"); too HIGH →
  **UNBOUNDED REFETCH LOOP** (a `Version = now-millis` push produced **46 fetches in 4 s**, ~one per
  70 ms, not self-limiting; cleared only by restarting `ags`, which reseeds `partyVer` above the
  poisoned cache). The shipped lever is correct by construction — `notifyPartyResources` passes
  `interactive.Service.PartyVersion()`, the same counter `buildSoloParty` is served with. **Never
  invent a version, use a clock, or "add 1 to be safe."**
  ★★★★★ **THE APPLY IS PROVEN AND THE FLAG SHIPS ON (2026-08-13).** The client **REFETCHES AND
  APPLIES** the party document from a targeted push, with **NO socket teardown** — controlled
  round-trip, operator-confirmed: podium **BLUE → GOLD → BLUE** on command
  (A: backend already changed + NO push → unchanged, i.e. the client is provably unaware;
  B: push → `TARGETED RESYNC` 3→4, `/party/parties` 3→4 → applied; C: reverted + push → applied in
  reverse). **`messenger DROP` = 0 and connects = 1 throughout.**
  ⇒ **S85's socket drop is RETIRED as the primary lever** (kept as the fallback when there is no
  version source or no live messenger). ⇒ `lobby.go`'s note that the *"~1 s reconnect floor is not
  backend-controllable"* is **OBSOLETE — there is no reconnect at all now.**
  ★★ **HOW THE OBSERVABLE WAS CHOSEN — copy this.** The first attempt used the hero skin and was
  **invalid**: `loadout_fix.cpp` polls `/revival/loadout` every **~175 ms** and calls
  `SetHeroCosmeticsBundlePreference` / `SetLuxeSkinChromaPreference` / `SetSlotCosmetic`, so it
  applies any skin/slot change within ~200 ms and **cannot discriminate**. But
  `grep -ci lobbyplatform loadout_fix.cpp` = **0**, while `loadout.go:411` puts
  `lobbyPlatformPreference` **inside the party document** ⇒ the **lobby platform (the podium) is
  party-doc-driven and shim-blind**. Also: `handleSetLobbyPlatform` (`interactive.go:247`) bumps the
  version but does **NOT** call `markLoadoutDirty`, so changing it is backend-only and gives a **free
  control arm**; the push is then triggered separately by a no-op slot write
  (`{"slot":"FK15Probe","asset":""}` deletes a key that does not exist) which reaches
  `markLoadoutDirty` and carries the real `PartyVersion()`.
  ⚠ **A first attempt on 2026-08-12 was INVALID because no shim was injected** (`GET /revival/loadout`
  = 0) — the podium/skin display path did not exist, so its null was guaranteed in advance. **Launch
  WITH the shim set for any display-path test.**
- ⚠⚠ **MEASUREMENT TRAP, cost two false results in one sitting — read before timing anything
  against this game.** (a) **`rg` is NOT on PATH in the background shell** (it *is* in the
  foreground one); a watcher using it produced empty counts, an errored `[ "" -gt "" ]`, and a
  fall-through **`RESULT: HELD` — a false PASS agreeing with the hypothesis.** (b) **`Loki.log`
  timestamps are UTC while `ags`/PowerShell times are local (UTC = local + 5 h)**; a histogram
  keyed on the local hour read a window **five hours before the change** and gave a **false FAIL**.
  ⇒ **self-test every harness inside itself** (`command -v`, a positive and a negative control,
  abort on non-numeric) and **state the timezone whenever correlating a log line with a deploy.**
- ★★★ **PUSH WORKS, and the measurement already existed.** In the 2026-08-09 verbose run
  (`docs/fk11-live-result-20260809.log`) the client logs
  `AccelByte::AccelByteWebSocket::OnMessageReceived` **exactly 4 times, 1:1 with the 4 frames
  `respondText` sends** [M]. One `/lobby` socket held **3 h 43 min** with **zero** closes (the
  ~60-70 s teardown is a `/notifications` property, NOT a `/lobby` one), and the client sends each
  of its 4 requests **once** and never retries. ⇒ transport, framing, parse and SDK surfacing all
  work. **What is untested is whether an UNSOLICITED frame produces a VISIBLE effect** — a far
  narrower claim than the one on the books.
- ★★ **The 5 probes were BLIND.** All fired **2026-06-29, 41 days before FK-11's verbosity fix**.
  Every detector they name was pinned to `Warning` by the shipped `DefaultEngine.ini`, and **2 of
  the 6 — `LogPlatformLobby`, `LogPlatformQuery` — DO NOT EXIST in the binary**; they occur nowhere
  in this repo except the sentence asserting their silence. Across **326** archived client logs, all
  six detectors have emitted **0 lines, ever**. They could exclude only a *warning-level* rejection —
  not receipt, not parse, not dispatch, not a deliberate drop. ⚠ The primary observation is also
  **gone** (`docs/capture.log` is untracked and rotates; no 2026-06-29 client log survives).
- ★★ **They tested 1 of 33 notif types, and EVERY ONE has a bound dispatcher case.**
  `Lobby::HandleNotif` (`.text 0x04B02C80`) dispatches via a `TMap<FString,uint8>` at
  `.data 0x9FFE2D0` into a **33-entry jump table at `.text 0x04B04978`**, and the `.rdata`
  sub-block `0x8601A20`–`0x8602730` holds **exactly 33** names — 33 == 33 [M]. So `dsNotif` and the
  rest are dispatchable, not sender-only strings. Enumerated in
  `server/internal/lobby/vocabulary.go`, served at `GET /api/ws/vocabulary`.
  ⚠ **The count is 33, not 32.** An `endswith("Notif")` filter silently drops
  `userBannedNotification` / `userUnbannedNotification` (real cases), while a too-wide scan window
  adds `signalingP2PNotif` (which sits INSIDE the Request block and is NOT a case). Those two
  errors nearly cancel and produce a plausible 32. **Tie a recovered table to an independent
  count**, not to a regex.
- ★★ **The "ticket id" conclusion is REFUTED where the code is readable.**
  `Lobby::OnMessage` (`0x04B0ADB2`) reads only `type` (and `id` for responses) — **no ticket, no
  matchmaking state, no session id**; `HandleNotif`'s dispatch is `hash(type)`→map→jump; and
  `HandleMMv2Notif` (`0x04B07CB0`, fully decrypted, read end to end) has **no ticket gate at all**
  [M]. **Any `*Notif` type other than `messageNotif`/`messageSessionNotif` reaches the dispatcher
  with NO precondition.** ★ The real gate is `CheckMissingNotification` (`0x04B0EB40`) — a
  **`sequenceID`/`sequenceNumber` dedup** on `messageNotif`-shaped envelopes only, nothing to do
  with matchmaking. ⚠ Case bodies 8-31 sit on **all-zero (never-executed) pages in both dumps**, so
  SDK **routing** is proven but Loki's **delegate binding** is coverage-blocked.
- **The wire format was never the problem.** The binary carries its own templates:
  `"type: %s\nid: %s"` (`0x08603340`) and `"%stype: messageNotif\ntopic: %s\npayload: %s%s"`
  (`0x08612430`). JSON appears **only inside `payload:`**, never top-level. Our `buildLobby`
  already emits exactly this.
- ★ **A UTF-16-only scan cannot see the v2 vocabulary** — it is stored **ASCII** (UHT enumerator
  names). `messageSessionNotif` has its own handler (`0x04B07E80`) and `EV2SessionNotifTopic` ships
  **21** enumerators incl. `OnDSStatusChanged`. **Scan both encodings.**
- ★ **And it was picked via a WRONG-TOKEN SEARCH.** The AccelByte v1 name is **`dsNotif`, not
  `dsNotice`** — `dsNotice` is not a name this SDK uses. **`dsNotif` IS present** and has never been
  pushed. ⚠⚠ **Do NOT write "dsNotif occurs 10×"**: 9 of those hits are *inside* other tokens
  (`acceptFriendsNotif` etc. contain "Frien**dsNotif**"). **Standalone, `dsNotif` and
  `matchmakingNotif` occur ONCE EACH** — equally present, which is all the argument needs.
  **Count tokens, never substrings.**
- ★ **The recorded blocker is obsolete.** `dedicated-server-stub.md:468` blames the hero-asset gate
  for the client never sending `startMatchmakingRequest`. That gate was solved **2026-07-05**
  (`c1eaf88`) — **6 days after the probes** — and the probes have never been re-run.
- **Transport exonerated BY MEASUREMENT**, not by reading: an independent RFC 6455 decoder reads our
  frames back byte-identical at 1/2/60/125/126/127/**1462**(the phantom size class)/65535/65536 B.
  Don't re-derive it.
- ★★★ **THE OTHER SOCKET: our heartbeat has NEVER reached the client's handler.** The messenger
  class is **`UMessengerManager`** (⚠ **`LokiPlatformMessenger` does NOT exist** — 0 hits both
  encodings; it appears only in our own comments). `UMessengerManager::OnMessage`
  (`.text 0x57C8F00`) parses each **TEXT** frame as **one JSON object** into
  **`FNotificationMessage { Resource FString@0x00; Version int64@0x10; Payload FString@0x18 }`**
  (`schema.txt:37963`; scalar/Str ⇒ FK-14-trustworthy). `Resource=="hb"` clears the watchdog;
  otherwise **15 registered prefixes** match by `StartsWith` and mean *"resource X is at version N →
  refetch it"* (⚠ 15 is a **FLOOR** — the first instrument found 7 and missed 8).
  **MEASURED across 1,419 connections, re-confirmed on a second later log (23/22/0/0):**
  `connection established` 1419 · `heartbeat not received` **1418** · `recieved message` **0** ·
  `recieved unexpected message` **0**. That last line logs at **`Warning`** on a JSON parse failure,
  so our binary `hb` would have logged 1,418 times — **in a log where the same category emits 1,418
  Warnings.** ⇒ a **clean negative**: binary frames die below the application layer (no binary
  delegate is bound). **`lobby.go`'s 30 s proactive binary `hb` is invisible by construction**, and
  the ~60 s churn (median 60.0 s connect→kill, exactly ONE heartbeat per connection) cannot be fixed
  by tuning the interval. **Fix = reply in TEXT `{"Resource":"hb","Version":0,"Payload":""}`.**
  ⇒ `coverage-audit-s101.md:99`'s *"a **format** problem, not a delivery problem"* is half right and
  the wrong half is load-bearing — **delivery fails first**.
  ★ And a per-resource version-bump push refetches **exactly one** resource with **no teardown**,
  which is strictly better than S85's socket drop and retires `lobby.go`'s *"~1 s reconnect floor,
  not backend-controllable"*. ⚠ Re-verify S85 avatar latency if the heartbeat lands.
- ⚠⚠ **The ignorance map's proposed FK-15 experiment is a GUARANTEED NULL — do not fly it.**
  `partyGetInvitedNotice` has **0 hits** in either encoding (the real lobby token is
  `partyGetInvitedNotif`), and `UserNotification_PartyInvite` is a **client-side `UObject` built by
  `UUserNotificationManager` from local models — not a wire type**. The real invite path is a
  messenger version bump → `GET /party/players/{id}` → toast; **invite content never crosses the
  socket.**
- ★★ **HARNESS SHIPPED — a probe is now a button press, not a launch.** Admin panel → **"WS Push"**
  tab, plus `GET/POST /api/ws/{sockets,preview,push,sweep,vocabulary,drop}`
  (`server/internal/lobby/push.go`, `server/internal/admin/ws.go`). One **sweep** walks all 33 notif
  types in ~99 s. **Both** channels are addressable and the 7 ranked probes **auto-target the right
  socket** — a messenger frame sent on `/lobby` tests nothing.
  Guards: a **label is mandatory** (it tags the `capture.log` line), the builder emits **exactly**
  the fields given and **no `id:` line unless you supply one**, pushing into the void is an **error
  not a 200**, and **Drop is the positive control** (S85's resync is the project's one demonstrated
  server→client control signal).
  ⚠ **A sweep is a SCAN, not an experiment** — any hit must be re-run as a single frame, alone.
- ⚠⚠ **`LogAccelByte` IS NOT the dispatcher's category — raising it does NOT make the lobby talk.**
  The dispatcher logs to **`LogAccelByteLobby`**, whose live state at `.data 0x9FFE2A0` reads
  `Verbosity=Warning(3), CompileTimeVerbosity=VeryVerbose(7)` [M]. Proof: the 2026-08-09 run had
  `LogAccelByte=Verbose` → **52 lines incl. 4 receipts, and ZERO `LogAccelByteLobby:` lines / zero
  `Lobby.cpp` format strings**. Also **`LogJson` is the WRONG detector** (0 lines in 326 logs).
  Use **`configs\set-log-verbosity.ps1 -Preset Ws`** (new), which raises `LogAccelByteLobby` to
  **VeryVerbose** — required for `Type: %s` (`0x04B0B12B`), which prints the type of **every**
  routed frame — plus `LogAccelByteNotificationBuffer`, `LogAccelByteWebsocket`,
  `LogAccelByteMessagingSystem`, `LogNet`, `LogMessenger`. All verified present in the image.
- **Next — 7 pre-authored probes, ranked, one-click in the panel** (`RecommendedProbes` in
  `vocabulary.go`). **Probes 1-5 need NO ini change.**
  ★★★ **#1 is the single best experiment available: send the literal text `FK15-PROBE-FROM-AGS` on
  the MESSENGER.** `OnMessage` fails to parse it as JSON and logs
  `Messenger recieved unexpected message: FK15-PROBE-FROM-AGS` at **`Warning`** — and its baseline
  is a **measured ZERO across 1,419 connections** in logs where that same category emits 1,418
  Warnings. **One line, echoing our own sentinel back, settles FK-15 outright.**
  Then **#2** the TEXT heartbeat (stops the 60 s churn), **#3** a version-bump resync (observable in
  our OWN `capture.log`, no client log needed), **#4/#5** the `/lobby` arrival tests, **#6**
  `dsNotif`, **#7** `matchmakingNotif` re-run with the dispatcher raised — then sweep the rest.

### Before touching anything menu-shaped
Skim `docs/trackb-notes.md` (Track B endpoint surface + ClientProfileData model)
and `docs/endpoints.md` (every endpoint the client hits + handler status).

### Before touching anything extraction-shaped
Skim `docs/findings.md` and `docs/r2-findings.md` (IoStore catalog + usmap RE +
the non-standard UObjectBase layout in this build: nameOff=0x20, classOff=0x18,
NOT the stock 0x18/0x10). `docs/game-map.md` has the full 68,228-asset catalog.
S110 calibrated the other two fields live (`tools/re/item_watch.py`, 400/400 and
100%/0% controls): **ObjectFlags@0x0C, InternalIndex@0x10** — so an object's
`FUObjectArray` slot can be read straight out of the object, no scan needed.

### Before touching anything AR-bin-shaped
Read `docs/trackb-assetregistry-route.md`. The `assetregistry apply-patch`
extractor subcommand works end-to-end; loose-file AR.bin deployment has been
proven INERT in this IoStore build (UE ignores the loose file even when valid).
Deployment requires an IoStore mod-pak overlay — non-trivial.

### Before touching anything Angelscript- / deploy- / respawn- / "the ceiling" shaped
★★★ **FK-1 IS SETTLED (S113, 2026-08-09) — read `docs/fk1-angelscript-settled.md`.** S74's
*"only 18 classes are Angelscript … the native deploy/round core is the irreducible blocker …
**accept the ceiling**"* (commit `19db6a2`) is **REFUTED**, and so is the ceiling.
- ★★ **The script layer is AOT-TRANSPILED TO C++ and compiled into the exe ("StaticJIT") — it is not
  interpreted.** 1463/1463 cache function Ids appear as `mov edx,imm32` registration-stub immediates
  (control 0/4000); a **1,459-row symbol table** (script fn → raw / `_VMEntry` / `_ParmsEntry` RVAs)
  was recovered; bodies live at `.text 0x059128B0–0x05A7F070`. ⇒ **script UFunctions are callable by
  the existing S55 native-call recipe, unchanged.** ⚠ **`Func != ProcessInternal`, so the PI hook
  NEVER fires for a script UFunction** — the ignorance map's proposed "print every PI-dispatched
  UFunction for 5 s" test returns **zero AS classes even when they are perfectly callable.** It is a
  TRAP; use it only as a negative control.
- ★★★ **THE REAL WALL: four server-authority C++ functions have EMPTY IMPLEMENTATIONS in the
  shipping client** (byte-level, coverage-guarded, controls; re-verified in BOTH dumps S115 —
  `docs/fk1-stub-claim-recheck.md`). ⚠ The exec THUNK and the IMPL are different addresses; the
  thunks are real code, the impls are folded stubs:
  `ALokiGameMode::SpawnPlayer` thunk `0x534C070` → impl **`0x0F7EB50` = `xor eax,eax; ret`** ·
  `ALokiPlayerState::AuthSetSpawnTeamLeader` thunk `0x5254180` (⚠ 91-way ICF-folded, NON-IDENTIFYING)
  → impl **`0x0F7EC20` = `ret 0`** ·
  `ALokiTeamState_TeamOnly::SetDropLeader` thunk `0x2C2CE30` (⚠ 23-way ICF) → impl **`0x0F7EC20`** ·
  `ALokiDropPlane::OverridePlaneLocations` thunk `0x53372A0` → impl **`0x0F7EC20`**.
  Empty-impl base rate in this image is **1.2 % (78/6,669)**, so this is informative, not ambient.
  Likely `WITH_SERVER_CODE`-stripped [I]. **This explains ~7 failed spawn attempts
  across S68/S74 and CLOSES `AvatarActor = NULL`:** the design routes the whole GAS bind through
  `SpawnPlayer` (disassembly-verified in `FFA/LokiRespawnComponent::Respawn`, which null-checks the
  character but NOT the ASC) and the client's `SpawnPlayer` returns nullptr.
  ⇒ ★ **But the SCRIPT authority functions ARE compiled in, and a direct `Func` call bypasses
  ProcessEvent's net routing** (22 `NetServer` script fns run locally regardless of authority). The
  deploy door is shut in C++ and possibly open in script: `ULokiRespawnComponent::Respawn`
  (`0x5A6AC40`), `ALokiDropShip::SpawnDropPodForTeam` (`0x597E730`), the `ALokiDropPod` steppers,
  `UFFABotSpawnerComponent::BeginPlay`.
- ✅ **THE FOUR-STUB CHALLENGE IS RESOLVED (S115, 2026-08-12) — `docs/fk1-stub-claim-recheck.md`.**
  S114 read `0x534C070` / `0x2C2CE30` / `0x53372A0` in TWO dumps as **large real functions with
  security cookies and parameter setup**. That reading was **CORRECT — and so was FK-1's.** They
  describe **different addresses**: those RVAs are the exec **THUNKS** (real code), and the empty
  bytes belong to each thunk's **IMPL**, an address FK-1's table never printed (see the corrected
  entry above). **Neither measurement was wrong, and there is no RVA/VA or image-base confusion
  anywhere** — both dumps are flat and byte-identical at every address involved.
  ⇒ **FK-1's "the real wall" and its closure of `AvatarActor = NULL` STAND; build on them.**
  Empty-impl base rate is **1.2 % (78/6,669)**, so the finding is informative, not ambient.
  ⚠ The false statement was manufactured **in this file** — a table headed
  `| function | exec thunk | body |` was compressed to prose, dropping the column label and
  substituting `=`. **Never print a byte string next to an address it did not come from.**
  ⚠ Scope note, now sharpened: `ALokiPlayerState::AuthSetSpawnTeamLeader` `0x5254180` was never in
  dispute, but the address is **91-way ICF-folded and NON-IDENTIFYING** — it is this image's shared
  zero-parameter `execFoo` thunk (**7 real instructions**, `P_FINISH; jmp 0x00F7EC20`), not itself a
  fold. It is the registered `Func` of **91** distinct UFunctions, so it can never identify one.
  Always print fold multiplicity next to a folded RVA.
- **The round mode IS native — but that is NOT a ceiling.** Every member is a named
  UFUNCTION/UPROPERTY reachable by the primitive, and **the phase lives on `ALokiGameState` with a
  public `AuthSetCurrentPhase` setter**, so the `EGP_Combat` gate has TWO write paths. The tutorial
  **already runs** the round mode (`BP_LokiGameMode_Tutorial_C`); native `ALokiTutorialGameMode` is
  vestigial. `LokiDropInGameMode` is a *referenced native base*, is **not** a round mode, and
  "DropIn" ≠ drop phase.
- ★ **The usmap gap is CLOSED.** `tools/asdump/out/usmap/mappings+as.usmap` adds the 110 AS types;
  base round-trips **bit-identically** (11,344/11,344 structs, 2,226/2,226 enums). **263 property
  values newly decoded** across 26 assets — `BP_GameMode_Barracuda` 27 → 65 props,
  `LaserSettings` `{}` → a full 14-field struct. ⚠ Only **`UPROPERTY()`** members are reflected
  (470 of 581) — measured by a 4-arm one-variable test with a reversed-order positive control.
  **FK-14 resolved:** the extractor loads `tools/extractor/mappings.usmap` (md5 `3892b937…`).
- ⚠ **Live RPM (S113): AS UClasses are NOT registered at the menu** — 0 of 15 sampled names, against
  3 passing native controls (`LokiGameMode` 72 fns, `LokiPlayerController` 151, `LokiPlayerCheats` 65).
  AS **enums and structs ARE** live. **So any callability test needs a LOADED MAP, not the menu.**
  Probe names: `tools/asdump/out/usmap/as_schema_full.csv`, column `ue_name` (66 AS UClasses).
- ⚠ **Two memory claims are now FALSE:** *"every drop-phase step is a `BlueprintCallable` UFUNCTION"*
  (`InitializeDropPod` is not a UFUNCTION at all; 3 of 10 listed are not BPCallable, so the
  "skip the plane" two-call recipe is **not executable**), and *"fix = `AuthSetSpawnTeamLeader()`
  before spawning"* (**no body**; and `SpawnDropPodForTeam` bails on `TeamDropPodClass == nullptr`
  first). Conversely **zero `BlueprintAuthorityOnly` anywhere** — the S90 gotcha does not recur.
- ★ **FK-6 re-grade:** `ALokiPlayerCheats_AS` is a **separate script-generated UClass** from the C++
  `ALokiPlayerCheats` that FK-6 closed on, and it has **32 UFUNCTIONs with compiled native bodies**
  (`AuthCheatGrantGold`, `AuthCheatUnlockFullArmory`, `AuthCheatExecuteUAV`). `Exec == 0` across all
  500 script UFUNCTIONs — the console cannot reach them, **but the thunk can.**
  ⚠ **S114 SCOPE CORRECTION:** that `Exec == 0` is **Angelscript-only** and was never a claim about
  native UFunctions. **138 NATIVE UFunctions carry `FUNC_Exec`** (`UCheatManager` 48,
  `ALokiPlayerCheats` 25, `APlayerController` 13, `ALokiCharacter` 10, …), and as of S114 a real
  `UCheatManager` is installable on the live PlayerController, so **42 of them ARE string-reachable
  today** — see the console/exec block above.
- ⚠ **Reading discipline for `tools/asdump` output:** the per-function **disassembly appendix is
  GROUND TRUTH; the pseudo-source is a reading aid.** The structurer can **silently invert a guard**
  (46 of 1,463 functions share the risk shape). Verify anything load-bearing against the disassembly.

### Before touching anything logging- / instrumentation- / "we can't see it" shaped
★★★ **FK-11 IS SETTLED (S113, 2026-08-09) — read `docs/fk11-log-verbosity-settled.md`.** Offline,
zero launches. **Verbose/VeryVerbose are NOT compiled out.** The old rule
(`next-session-prompt-s45.md:185`, *"this is a SHIPPING build; Verbose/VeryVerbose UE_LOG is
compiled out (confirmed)"*) is **FALSE** and its "(confirmed)" was attached to a session containing
no test. **This foreclosed the cheapest instrument the project could own for ~60 sessions.**
- **MEASURED:** global `COMPILED_IN_MINIMUM_VERBOSITY` = **`VeryVerbose` (7)**; `USE_LOGGING_IN_SHIPPING`
  = **1**; of 14,030 decoded `UE_LOG` call sites, **1,339 are Verbose and 513 VeryVerbose**;
  **98.0 %** of categories have `CompileTimeVerbosity ≥ Verbose`; and **109/109 Loki-dominant
  categories are VeryVerbose — zero capped at `Log`**. There are **71 Verbose/VeryVerbose call sites
  inside `\Loki\Source\`** across 35 categories.
- ⚠⚠ **DO NOT USE `-LogCmds` — it does not parse in this binary.** `logcmds` occurs exactly 3× in the
  178 MB image and **all three are help text** (`0x076B25E0`, `0x076B26B0`, `0x076B2860`); there is no
  standalone `LogCmds=` literal. Controls: peer switch literals `LOG=`, `ABSLOG=`,
  `logcategoryfiles=`, `NOCONSOLE`, `FORCELOGFLUSH` all DO exist; on-disk exe agrees; `.rdata` is
  99.64 % complete. **The help text is what a casual scan finds and it reads like proof the flag
  works.** FK-11's own "cheapest experiment" was this flag — it would have produced nothing and the
  nothing would have been recorded as "confirmed, Verbose is compiled out."
- ★ **USE `[Core.Log]` INSTEAD — it is triple-confirmed and ALREADY BINDING.** The binary states its
  own precedence at `0x076B1FA0`: *compiled-in → ini → command line*; stage three is missing, so
  **ini is the last word**. Across a 4.10 GB / 28.7 M-line log corpus, all 15 shipped `[Core.Log]`
  entries show **zero violations** — `LogAccelByte` (which drives the whole login/catalog/store/party
  flow) emits **3 lines** vs 244–422 for unpinned peers. **We have been reading a log that was
  deliberately turned down.**
- ★★★ **FLOWN AND CONFIRMED LIVE (2026-08-09, one `-NoHook` menu launch).** Scoreboard, all three
  mechanisms in one run, each on its own category:
  **A — user `Engine.ini` `[Core.Log]`: WORKS** (`LogAccelByte` 3 → **52** lines, **46 Verbose**).
  **B — `-ini:Engine:[Core.Log]:…`: FAILED**, clean control (`LogOnline` emitted 2 `Warning:` lines,
  so it ran, and stayed pinned) ⇒ **`-ini:` is applied too late for `[Core.Log]`; use the user ini.**
  **C — `-LogCmds`: inconclusive** — the category chosen had no positive control, so its zero cannot
  discriminate "ignored" from "never logs". Both B and C were verifiably **DELIVERED** (engine echo),
  so they are failures of effect, not delivery.
  **Whole log: Verbose 13 → 1,018; Error 100,618 → 2; size 14.1 MB → 1.4 MB.** The log is now **10×
  smaller and carries 78× more Verbose.** `LogTemp=Fatal` zeroed all 100,616 spam lines.
- ★★ **What it immediately revealed:** `LogAbilitySystem` 25 → **4,161 lines / 959 Verbose** on a plain
  menu launch — **137× `Initializing new default set for LokiAttributeSet[N]`**, plus a real per-hero
  data defect (`Unable to match Attribute from SneakSpeedMultiplier (row: <Hero>.LokiAttributeSet.
  SneakSpeedMultiplier)` for **every** hero). `LogAccelByte` now traces the whole backend
  conversation (SDK entry point + verb + full URL + status + request handle), including the
  previously invisible **`[AccelByte] Key for Cached Token can not be empty.`** And
  **`AccelByteWebSocket::OnMessageReceived` fires repeatedly** ⇒ frames ARE arriving on the client
  socket, which hands **FK-15** an instrument it never had.
- **Use the shipped tooling:** `configs/set-log-verbosity.ps1 [-Preset Mechanism|ClassA|Gas]`
  (backs up, clears ReadOnly, merges `[Core.Log]`, re-sets ReadOnly; `-Revert`, `-WhatIf`) and
  `configs/check-log-verbosity.ps1` (reads the log **live**, shares the handle, prints per-category
  line + Verbose counts against measured baselines). `launch-redirect.ps1` now takes **`-ExtraArgs`**
  for raw extra switches (forwarded across elevation).
- **Mechanism (precedent already in this repo):** append `[Core.Log]` to
  `%LOCALAPPDATA%\SUPERVIVE\Saved\Config\WindowsClient\Engine.ini`, then re-set **ReadOnly**. That
  file already carries this project's own `[HTTP.Curl] bVerifyPeer=false` + `[SSL]` fix for the
  documented "`-ini:` applied too late" problem (`launch-redirect.ps1:279`).
- ★ **Two free instruments in every log:** `LogInit: Command Line:` echoes the **entire** command
  line verbatim (so any switch is verifiable as *delivered*, separately from whether it *worked*),
  and `LogConfig:` narrates config application.
- ⚠ **The dominant trap is NEVER-RAN vs SUPPRESSED.** 384 of 842 logs reach `LVL_Tutorial` but **none**
  contains combat, drop phase, bots, damage, XP or client replication. Raising verbosity on a
  never-run category changes nothing. **Class A** (owner provably ran, still silent — real
  suppression wins): `LogLokiHeroCharacter`, `LogLokiCharacter`, `LogLokiCharacterMovement`,
  `LogLokiPlayerController`, `LogGameFeatureToggles`, `LogLokiMenuActions`. **Class B** (loaded, path
  not exercised): the GAS family. **Class C** (never ran): all netcode, drop phase, inventory/damage.
- ★ **Fly `LogBlueprintLogLibrary` FIRST.** Loki's own `UBlueprintLogLibrary` exposes `Verbose` /
  `VeryVerbose` **static UFunctions** callable via the existing native-call primitive, and the
  category already emits (598 logs) — it proves the whole mechanism with **zero gameplay dependency**.
- ⚠ **Spam hazards:** `LogNetSerialization` (per-bit — it was in FK-11's own suggested line; **strike
  it**), `LogNetTraffic`, `LogRepTraffic`, `LogRepProperties`, `LogRepCompares`. **Special case:
  `LogGameFeatureToggles` is HIGH risk despite being silent** — the same subsystem already emits ~10⁵
  lines/run via `LogTemp`. Raise it to `Log` first, never straight to `Verbose`.
- **Two free wins:** `LogTemp` is **97.5 %** of the log (100,616 of 103,169 lines — the feature-toggle
  spam, at **`Error`**), so **`LogTemp=Fatal`** reclaims the whole budget (`Warning` will NOT work);
  and **`DFLLog=Fatal`** in the shipped ini mutes a real 33-method debug library — un-muting is free.
- **The Angelscript layer is silent by AUTHORSHIP, not gating** — 20 `Log::` functions exist but the
  shipped scripts call them **6 times in 4,963 syscalls (0.12 %)**. Raising verbosity cannot make
  script code talk; this downgrades the drop-phase route. The script API has no `Verbose` at all.
- ⚠ **`FLogCategoryBase` layout in this build: `Verbosity@0, DebugBreakOnLog@1, DefaultVerbosity@2,
  CompileTimeVerbosity@3, FName@4`** — FName is **LAST**. Ctor is `base+0x1063710` (**not**
  `0x1138F20`, which is `FName::FName`). Verbosities are passed as `mov r8b/r9b, imm8`, not `imm32`.

### Before touching anything console- / exec- / cheat-verb-shaped
★★★ **FK-13 IS SETTLED (S114, 2026-08-12) — read `docs/fk13-console-exec-settled.md`, then
`docs/fk13-live-run-2026-08-12.md`, then `docs/fk13-routeb-shipped.md` (its §6 corrections, §7 guards
and §9 end-to-end proof govern).** S3's *outcome* was right and **every reason it gave was wrong**;
S101's explanation of S3's error was also wrong (all 6 overturned tokens are readable in the shipped
on-disk exe with a plain ASCII search, so *"S3 scanned the packed binary"* does not explain the miss —
**do not propagate it**). And S3's operational conclusion — *"all cheap external paths are exhausted;
the remaining options require in-process code"* — is **FALSE**. That sentence is the founding
justification for the injection-only architecture.
- ⛔ **`ALLOW_CONSOLE == 0`: `~` CAN NEVER WORK, and no config, ini or command-line change alters
  that. Do not spend a launch re-testing it.** [M] via three independent instruments:
  `UGameViewportClient::Init` (`0x0384FB00`, 1,810 B, decrypted in BOTH dumps) has **zero** reads of
  `ConsoleClass` (`+0x120`) and **zero** stores to `ViewportConsole` (`+0x48`) while writing both
  neighbouring stock members; `Console.cpp` guard-exclusive literals score **8/8 controls vs 0/5
  markers** at `.rdata` **100 %**; and the gaps in `UEngine::Exec`'s literal pool are exactly the
  compile-guarded verbs. `UConsole` the CLASS *is* compiled and `ConsoleClass` IS resolved at startup —
  only the viewport never constructs one, so `GEngine->GameViewport->ViewportConsole` is NULL.
  `config-control-plane-s101.md` §5 levers **#1 and #4 are dead**; its probes **P1/P2/P4 are answered
  offline**. `ULokiGameViewportClient` does not re-add one (its vtable differs from the base in 4 of
  122 slots; neither `Init` nor `SetConsoleTarget` is among them).
- **FK-13 was THREE independent compile flags, not one** [M — UBT `TargetRules.cs:1368,1374,1429`,
  `UEBuildTarget.cs:5064,5073,5145`]: `bUseLoggingInShipping` (stock default 0, **this build 1** —
  FK-11), `bUseConsoleInShipping` (stock default 0, **this build 0**), `bUseExecCommandsInShipping`
  (**stock default 1**, this build **1**). **Never reason from one to another.** A fourth gate,
  `UE_WITH_CHEAT_MANAGER = (1 && !UE_BUILD_SHIPPING)`, is a plain `#define` with **no `Target.cs`
  escape** — that is what empties `AddCheats`.
- ★★ **THE EXEC MACHINERY IS ALIVE.** `UE_ALLOW_EXEC_COMMANDS == 1`; `UEngine::Exec` `0x3ED66C0`
  (2,521 B real body), `UGameViewportClient::Exec_Runtime`, `FSelfRegisteringExec::StaticExec`,
  `UObject::CallFunctionByNameWithArguments` `0x1343420`, and the whole IConsoleManager cvar channel
  are compiled. **138 native UFunctions carry `FUNC_Exec`** across 15 classes — `UCheatManager` 48,
  `ALokiPlayerCheats` 25, `APlayerController` 13, `ALokiCharacter` 10, `ALokiPlayerController` 8,
  `AHUD` 6, `UPlayerInput` 5, `ULokiClientPlayerCheats` 5, `ULokiTimelineManager` 5, … [M]
- ★ **The entry point is `UKismetSystemLibrary::ExecuteConsoleCommand`** (exec thunk `0x395D790`,
  flags `0x04022403` = `BlueprintCallable|Native|Static|Public`) — exactly the shape the S55
  native-call primitive already calls, **with no `.text` write**. ★★ **And this project has been
  driving that channel since ~S91 without naming it:** the force-open shim's
  `ExecuteConsoleCommand("open LVL_Tutorial?game=…")` fires at `rva 0x395D790`, and
  `Load map complete …/LVL_Tutorial` is its receipt across dozens of runs. ⇒ S3's
  `-ExecCmds="open …"` null was a **delivery** failure, not a verb failure.
  ⚠ **OPEN:** `OPEN` is *absent* from `UEngine::Exec`'s literal pool [M], so `open` must be serviced
  elsewhere on the chain (`UWorld` / `UGameInstance` / a Loki override). **Both facts are measured;
  the dispatch site is unresolved — do not write up "OPEN is compiled out."**
- ★★★★★ **ROUTE B IS SHIPPED AND PROVEN END-TO-END — a console string reached a cheat verb.**
  `APlayerController::CheatManager` (`+0x520`) was NULL in every measurement this project has ever
  taken. The new `RM_CHEATMGR` mode in `tools/sigbypass-mod/tutorial_launch.cpp` constructs one via
  `UGameplayStatics::SpawnObject(pc->CheatClass, pc)` and stores it in the reflected `CheatManager`
  UPROPERTY — **ONE aligned heap qword, readback-verified, ZERO module-image writes** (the `.text`
  arm is a compile-time REFUSAL that prints why). `CheatClass` (`+0x528`) was **already populated in
  BOTH the menu and the staged tutorial world**: the class selection was never stripped, only the
  body of `AddCheats`. **Proof:** `ExecuteConsoleCommand("LogLoc")` →
  `LogCheatManager: BugItGo 0.000000 …` in `Loki.log`, baseline 0, **both format literals confirmed
  present in the image BEFORE the run** (a pre-registered signal, not a post-hoc grep). 69 min
  uptime, 0 crashpad handoffs, Func-swap restored 18,223/18,223. **42 REAL exec verbs**
  (42 REAL / 3 FOLD / 3 COVERAGE-BLOCKED / 2 UNRESOLVED — *not* the "44" first stated).
  ★ `SpawnObject`, not `NewObject`, for a non-obvious reason: shipping has `DO_CHECK == 0`, so
  `NewObject`'s internal `ClassWithin` assert is compiled out and **a wrong Outer would be SILENT**;
  `SpawnObject`'s *runtime* Within test is the only one that survives shipping.

Builds (`tools/sigbypass-mod/build.ps1`; `.text` sha256 — **diff `.text`, never size**):

| variant | `.text` sha256 | use |
|---|---|---|
| `cheatmgr` | `750b83bf0f36e90e` | **in-world** (arms on `ReceiveTickClient`) |
| `cheatmgr-any` | `b551996df67f106b` | **menu** (`KFSNAME=""`, swaps all BP UFunctions) |
| `cheatmgr-any-verify` | `4507e376d099a3b5` | **the flown proof** — menu + executes `KCMVERIFYCMD` (default `LogLoc`) |
| `cheatmgr-verify` | `bc2abddf627bdeed` | in-world + verify — ⚠ **the on-disk build predates the R7/R8/R9 guards; REBUILD before use** |

Pre-guard builds were `a90e14dcde1dffa8` / `ef2fd89f87168871` — do not confuse them. ⚠ The S112
import-absence check (`FlushInstructionCache`/`VirtualAlloc` absent) does **NOT** verify this DLL —
it hosts other modes that legitimately import those. The no-`.text`-write property rests on source
reading plus the compiled-out refusal.

- ⚠⚠ **THREE TRAPS, EACH OF WHICH PRODUCED A FALSE RESULT BEFORE IT WAS CAUGHT**
  (`docs/fk13-routeb-shipped.md` §4 / §6 / §9.1):
  1. **`ReceiveTickClient` is never dispatched AT THE MENU** — `cheatmgr` is a silent no-op there.
     Its own watchdog said so (`NO GAME-THREAD HITS after 8000 ms … swapped=2`). Use `cheatmgr-any`
     at the menu, `cheatmgr` in-world.
  2. **`God` emits NO log line at all** — a silent instrument, so its null is uninterpretable.
     `KCMVERIFYCMD` defaults to **`LogLoc`**, whose `UCheatManager` body reaches
     `BugItStringCreator` → `UE_LOG(LogCheatManager, …)`.
  3. **A borrowed helper (`RunConsole`) read globals populated by a DIFFERENT run mode** and passed a
     null PC, so `ExecuteConsoleCommand` fell through to `GEngine->Exec(nullptr, …)` and branch 7
     never ran — while printing `console 'LogLoc' ok`. Fix = `RunConsoleOnPC(pc, cmd)` passes the PC
     as BOTH `WorldContextObject` and `SpecificPlayer`. **Check the provenance of every global a
     borrowed helper touches.**
  ⇒ ★★ **"THE CALL RETURNED OK" IS NEVER A SUCCESS CRITERION. Only the verb's OWN output is.**
  ⚠ `UPlayer::Exec`'s branches are `else if`-chained, so an earlier branch returning true swallows the
  command before branch 7 — **pick verbs that exist ONLY on `UCheatManager`.**
- **The 25 `ALokiPlayerCheats` verbs: THE ROAD IS BUILT, THE DESTINATION WAS NEVER CONSTRUCTED.**
  `ALokiPlayerController` **overrides** `ProcessConsoleExec` (`0x569BE50`, vtable slot 81 / disp
  `+0x288`): it calls `Super` first, then null-checks `[this+0xA30]` (the `LokiPlayerCheats`
  ObjectProperty) before forwarding. Routing: **YES**, offline-decisive. Instance: **NO** —
  `PC+0xA30` is NULL live in the menu *and* in the staged tutorial world (offset resolved BY NAME
  from live reflection), and `AddLokiPlayerCheats` / `FinishAddLokiPlayerCheats` are **empty folds**
  (`Func = 0x5254180`), confirmed LIVE. `ULokiGameInstance::LokiClientPlayerCheats` (`+0x298`) is
  likewise NULL, which kills the "cheapest win on the board". `ALokiGameState` and `ULokiGameInstance`
  have their own forwarders (TimelineManager / LokiClientPlayerCheats) with the same problem.
  ⚠ **OPEN:** whether spawning an `ALokiPlayerCheats` actor and writing `+0xA30` reaches those 25
  verbs has **not been tried.**
- ⚠ **DEAD — do not spend launches:** `DebugExecBindings` are config-loaded (exactly the 16 from
  `BaseInput.ini`, matching S80i's live `Num=16`) but **NEVER EVALUATED** — the whole evaluation path
  is `#if !UE_BUILD_SHIPPING`; measured as a clean `PlayerInput.cpp` literal-pool gap (6 same-file
  controls present; `NoDebugExecBindings` and `KEYBINDING` both **0**) plus **0** TArray-shaped
  accesses at displacement `0x1A8` in the PlayerInput region against a **925**-access control.
  **Do not press F9.** `-ExecCmds` **does not parse** (0 wide hits vs 5 same-class `FParse` switch
  controls that all resolve; on-disk exe agrees) — the **SECOND** non-functional UE switch after
  `-LogCmds`, so **treat every UE command-line switch as unverified until you locate its parse
  literal.** Loki's own data-driven debug menu is fully reflected but `Show/Hide/ToggleDebugMenu` are
  **empty bodies** (its `Ctrl+\` binding in `UserSettings.ini` means nothing);
  `ULokiBlueprintLibrary::CheatsEnabled` folds to `xor al,al; ret`; and `viewmode` ships the refusal
  string *"Debug viewmodes not allowed in Test or Shipping builds."*, so a null from it proves nothing.
- **cvars are a SHIM-FREE channel.** `ExecuteConsoleCommand` tries
  `IConsoleManager::ProcessUserConsoleInput()` FIRST — no instance, no pawn, no override — and cvars
  are additionally settable with **no injection at all** via `[ConsoleVariables]` in the USER
  `Engine.ini` (same file and mechanism as FK-11's `[Core.Log]`; `-ini:` is applied too late).
  44-entry `loki.*` inventory: `tools/re/out/cvar_census_tuthero.txt`. ⚠ **[I]** anything flagged
  `ECVF_Cheat` is excluded — `DISABLE_CHEAT_CVARS` is `(UE_BUILD_SHIPPING || …)`, a hard `#define`
  with no `Target.cs` escape; **which of the 44 carry that flag has not been enumerated.**
- ★ **FK-6 is RE-SCOPED, not contradicted.** Its *"console `Exec` == 0/500"* was measured over the
  **500 Angelscript** UFUNCTIONs and was never a claim about native ones. And its real closure — the
  CONSTRUCTOR (`AddCheats` = `ret 0` under `UE_WITH_CHEAT_MANAGER == 0`), not the bodies — is
  **CORRECT**; Route B is precisely the "constructing shim" the S105 retraction said would be such a fix.
- ★ **Method worth reusing: guard-exclusive marker strings.** Take `TEXT()` literals that occur ONLY
  inside a `#if` region (verified engine-wide across 24,864 UE source files) and control them with
  literals from the **SAME translation unit** outside the guard — single variable = guard membership.
  ⚠ The rule *"strings cannot decide `ALLOW_CONSOLE`"* is true only of **UHT-emitted** names and
  **FALSE** of guard-exclusive literals; recorded without that qualifier it forecloses a method that
  works. (UHT also strips the `F`/`U`/`A` prefix for reflected names, so probing `FKeyBind`/`UConsole`
  produces a false ABSENT.)
- ⚠ **Run every `.rdata` presence/absence claim against
  `dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe` (`.rdata` 100.0 %)**, never
  `merged.dump.exe` alone (63.1 %).

### Before touching anything protector- / anti-tamper- / packer-shaped
★★★ **FK-10 IS SETTLED (S113, 2026-08-09) — read `docs/fk10-protector-identified.md`.** All offline,
zero launches. **The protection is NOT VMProtect and NOT Themida** — refuted six independent ways.
It is a **bespoke stack that internally calls itself "Packer", version 3.3.1**, first-party
Theorycraft-signed. **Do not substitute a second vendor name**: the honest label is
*"bespoke protector, self-identifies as `packer/3.3.1`, vendor unidentified."* Replacing one guess
with another is the exact error FK-10 exists to correct.
- ★★ **`runtime.dll` is NOT PACKED. Its 46.6 MB of protector code is plaintext x86-64 and is
  disassemblable OFFLINE TODAY** — feed the disassembler the loader's function table at
  **RVA `0x14D8758`** (222,960 B, 18,580 entries), **NOT** the `.pdata` *section* (`0x1000`), which is
  vestigial and the loader never reads. Only the protector's *data* (`packer0`, 94.8 % of pages) and
  *resources* (`.rsrc`, 99.9 %) are encrypted; its instructions never are. It is *obfuscated*
  (MBA — `not`/`and`/`imul` ≈ 43 % of instructions), not packed. Start with `packer30` (2.2 MB,
  `call`-structured, holds the entry function and the 4 largest functions).
- ★ **The decisive ID:** at file offset `0x007C1BEC` (UTF-16) `runtime.dll` holds
  `/api/5710262/minidump/?sentry_client=packer/3.3.1&sentry_key=149a7ac2…` — **the same org, project
  and key as the game's own Sentry DSN**, differing only in `sentry_client`. A commercial packer does
  not embed the customer's private DSN.
- ★ **`deobfimports`' own 1107/1107, 0-undecodable result REFUTES the name**: its emulator supports
  21 opcodes with **no conditional branches, no `CALL`, no flags**, and `default: return 0,false`.
  A virtualized (VMProtect-style) stub would resolve **zero**. 100 % ⇒ every stub is branch-free
  arithmetic.
- ★ **The game exe is not "packed" either — it is SELECTIVELY ENCRYPTED IN PLACE** under a stock
  MSVC/UE5 section layout with **no packer sections** and its OEP (`0x751EFD0`) **inside `.text`**.
  `.text` 30,281/30,281 pages encrypted (100 %), `.pdata` 100 %, `.rdata` 28.1 %, **`.reloc` 0 %**.
  Every data directory the loader *reads* is plaintext; the **IAT**, which the loader only *writes*,
  is encrypted. ⇒ **22.8 MB of `.rdata` is plaintext ON DISK** (47 runs ≥64 KB from RVA `0x0764C000`)
  — static string work against the on-disk exe is viable there.
- ⚠ **Wall #7's "no string names the integrity check — CLEAN NEGATIVE, not coverage-blocked" is a
  SCOPE ERROR** (20th instrument-artifact instance). `tools/strxref/strxref.py:63` hardcodes
  `DEFAULT_DUMP = dumps\merged.dump.exe` — **the game exe**; `runtime.dll` appears **0 times** in
  either citing doc. The negative structurally excluded the protector.
- ⚠ **The "hunt xxHash" lead for Wall #7 is SPENT.** xxHash IS present (full XXH3 `kSecret` at RVA
  `0x9c00`) but its one-shot `0x8200f0` has exactly one caller, `0x8f9dd0`, which tests
  `(dword & 0xFFFFFFF0) == 0x184D2A50` ⇒ **it is Zstd's frame checksum, not the integrity hash.**
  **Successor lead:** SHA-256/SHA-1/MD5 tables in `packer2 0x942740–0x9467e0` (two back-to-back
  SHA-256 IVs = lane packing) tracing to a `.pdata`-free tail at **RVA `0x8ffcd4–0x93e886`, 251 KB**
  — **[I]** Intel ISA-L Crypto **multi-buffer** assembly (a BOM component the map missed). A 16-lane
  page hasher fits the dose-response *and* explains the negative Rayleigh result: a periodic timer
  sampling a SUBSET of pages gives aperiodic deaths. ⇒ the right claim is **not** "the check isn't
  periodic" but **"it doesn't verify all of `.text` every pass."**
- ★★ **FK-32 (`0x0000DEAD`) is CLOSED on mechanism:** `runtime.dll` RVA `0x80f7f0` is
  `mov edx,0xDEAD; syscall` = **`NtTerminateProcess(h, 0xDEAD)`** — the protector deliberately kills
  the process. Reached via a NULL-bounded 5-entry pointer table at `packer0 0x1831c0` whose 4th entry
  is `NtCreateThreadEx`. `preloader.dll` is ELIMINATED (0 occurrences; control: 2 in runtime.dll).
- ⚠ **The game exe's `IMAGE_DIRECTORY_ENTRY_EXCEPTION` is RVA=0 / size=0** while it ships a 6.28 MB
  *encrypted* `.pdata` (controls: runtime/tbb/steam_api64/preloader all read fine). So
  `RtlLookupFunctionEntry` finds nothing for the main image. **The "no C++-exception payloads" rule
  STANDS, but its recorded mechanism (the packer's VEH) is probably wrong** — a missing function
  table kills all three canaries identically. One probe settles it.
- Real BOM (`Loki/Binaries/Win64/thirdpartylicenses.txt`, 31,834 B): System Informer · xxHash ·
  constexpr-xxh3 · **Intel ISA-L Crypto** · MinHook · **HDE64** (`hde64_table` byte-exact at
  `packer0 0x7c6a10`) · Zstandard · mbedtls (its CA store is `.rsrc` RT_RCDATA 10001, a Zstd frame →
  579,410 B of DER — **this is what bypasses `cacert.pem`**) · tpm-tss · tiny-json · bscanf · embedded
  printf. **EAC is genuinely ABSENT**, so `-NoEAC`/`-NullEAC` are dead levers.
- ⚠ **Every behavioural string in these binaries is UTF-16LE.** An ASCII-only scan finds essentially
  nothing. `runtime.dll`'s 249,822 "ASCII strings" are dominated by 7,197 copies of `AWAVAUATVWUSH`
  — a **function prologue, not text**.

### Before touching anything native-shim-shaped
The keystone technique is a **game-thread native-call primitive**: hook
`ProcessInternal` (`base+0x13454A0`), capture a live `FFrame`, then call the target
`UFunction`'s native thunk (`UFunction.Func @ +0xE0`) **directly**. The direct call
has no guards, so it works where slot-56 `ProcessEvent` no-ops for native functions.
Param passing, OUT params (`FFrame.OutParms @ +0x80`), and `AsyncLoadPrimaryAssets`
are all RE'd on top of it. Read `docs/session-55-native-call-primitive.txt` (+ s56/
s57/s58/s59) and the `missions_nativecall_probe*.cpp` / `tools/re/*.py` families
before building a new shim. Also `docs/missions-progression-hookup.md`.

Two `ProcessInternal` hooks that stay PERMANENTLY installed race (they clobber each
other's prologue). The fix (S59): every PI-hooking shim (`mainmenu_refresh_pi8`,
`missions_fix`, `loadout_fix`) installs its 5-byte jmp only TRANSIENTLY — install →
piggyback one game-thread call → uninstall — serialized through a shared named mutex
`Local\SuperviveMissionsPIHook`, so only one has the hook installed at any instant.
That retired the old "mutually exclusive launch modes" split: all three now coexist and
inject together as the default set (see the launch procedure below).

## Launch / run procedure

From an **ELEVATED PowerShell**:
```powershell
cd "G:\git\Supervive Revival Project"
.\configs\launch-redirect.ps1              # redirect + server + game; injects the FULL shim set
.\configs\launch-redirect.ps1 -NoMissions  # everything EXCEPT missions_fix (isolate non-missions surfaces)
.\configs\launch-redirect.ps1 -NoLoadout   # everything EXCEPT loadout_fix (isolate non-customization surfaces)
.\configs\launch-redirect.ps1 -NoHook      # clean RE run, no shim injection
```

By default the launcher injects the primary `catalog_store_fix.dll` (roster + store +
cosmetics) at launch, then `configs/inject-secondaries.ps1` injects the full secondary
set once it settles: `mainmenu_refresh_pi8` (pick→center refresh), `catalog_pick_fix`
(pick-commit), `loadout_fix` (customization/skin persistence), `missions_fix`
(durable missions page), and `battlepass_adopt_fix` (PASSES / Hunter's Journey — S83).
One launch = every durable fix, together. `-NoMissions` / `-NoLoadout` / `-NoPasses`
trim individual shims; `-Hook <path>` injects exactly one DLL and no
secondaries. `-Missions` is kept as a deprecated no-op alias (missions are now default).

**★ THE SECONDARIES ARE NOW INJECTED 20 s APART, AND THE MENU TAKES ~100 s TO FULLY POPULATE.**
That is deliberate and is **not** a regression — do not "fix" it by lowering the gap. S109
(2026-08-05) measured that injecting them ~3 s apart is what kills the process: with the old
3 s gap the four secondaries landed in a ~13 s burst and the game died at **1 per 43 s**;
at ≥10 s gaps the hazard is **71× lower** (`P = 8.6e-5`). Gap sweep, treatment verified per run:

| gap | exposure | injections | deaths |
|---:|---:|---:|---:|
| 3 s (old default) | 129 s | 12 | **3** |
| 10 s | 1,210 s | 20 | 0 |
| **20 s (new default)** | 1,214 s | 20 | **0** |
| 30 s | 669 s | 12 | 2 |
| 60 s | 3,015 s | 25 | 0 |

`configs/inject-secondaries.ps1 -GapSeconds N` (or `launch-redirect.ps1 -InjectGapSeconds N`)
changes it; pass `3` to reproduce the old burst. ⚠ **MITIGATION, NOT A CURE** — residual is
~1 death per 3,054 s (~1-in-3.4 over a 15-min sitting), so keep archiving dumps and treat an
unexplained death as **possibly ours**. Full evidence: `docs/s109-dump-forensics.md` §12–§20
(§20 retracts an earlier "eliminates" claim; §16 retracts "the PI hook is the mechanism").

★★★ **S111 (2026-08-06): THE DEATHS ARE OURS — CAUSED BY INJECTION ITSELF.** MEASURED over 101
launches (`docs/s111-nohook-control.md`): a **`-NoHook` control, 11 launches × 320 s hold, produced
ZERO deaths**, against **25/90 (28 %) across all injected arms** (p = 0.036) and **9/30 (30 %)** for
a one-shim arm whose scan was disabled (p = 0.041). The comparison is clean because that one-shim arm
*also* leaves the roster/store unpopulated — so the discriminating variable is **the injected DLL,
not the workload**. Every `-NoHook` run survived **5.3× longer** than the window in which injected
runs were dying. So the ~30 % per-launch death rate is a property of **our injection**, not the game,
and it is an engineering problem rather than a hazard to budget around.
⚠ **WHICH aspect is still unknown** — manual-map vs the self-restoring `.text` jz-NOP vs the PI
prologue writes are still confounded. The cheap next step is a do-nothing DLL (`DllMain` returns
immediately), ~10 runs: if that already dies at ~30 %, manual mapping itself is the trigger.
⚠ Also MEASURED: the **~285 s code-integrity kill did not fire once in 11 runs that all crossed it** —
first direct support for "it catches a STANDING `.text` patch" (a `-NoHook` run leaves none), rather
than an inference from timing.

⚠⚠ **THE TABLE ABOVE IS UNDER RE-EXAMINATION (S111).** Do not delete it — but the outcome variable
was **never split by fault family**, and it does not survive that split. MEASURED: both deaths in the
30 s row (`knee-g30-2`, `knee-g30-3`) are `catalog_store_fix.dll`'s launch-time heap scan faulting at
`.text` RVA `0x205d` — a death the **primary** injector causes and that `-InjectGapSeconds` does not
touch at all. `sub-NoMissions-1/-2` and `sub-NoPasses-2` are the same family. So an unknown share of
the "hazard" being attributed to injection spacing is a fixed per-launch hazard from the primary
shim. Re-fit before trusting the 71× figure: classify each death by `RIP & 0xFFFF` first
(`docs/fk8-crash-timing-mined.md` §3.1, §7.2 item 3).

**★ `configs/fk24-stage.ps1` now enforces the same minimum gap** (`-InjectGapSeconds`, default
**20**). It was NOT a uniform burst — measured spacing was gft→fo **~5 s** (lethal regime),
fo→sp **19 s**, sp→probe **7–17 s** — so only the first gap was clearly bad. The gate is a
*minimum*: the existing evidence waits (world-load, `[SP] done step=4`) count toward it and only
the shortfall is slept, costing **~15–29 s** of staging rather than ~50 s. The probe now arms
around **T+175 s** instead of ~T+145 s, leaving ~110 s before the late-kill mode — so the
**T+220–250 s hold still fits, but the armed window is tighter**; budget accordingly.
⚠ Both numbers here are **staging-schedule-relative**, not properties of the game (S111): the launch
clock moved +33.0 s July→August, so re-anchor to `Load map complete …/LVL_Tutorial` when it matters.
⚠ **UNVALIDATED ON A LIVE TUTORIAL RUN.** The 71× reduction was measured on the *menu* route.
Whether it moves the ~1–5 min tutorial deaths is the open question — and it is now the single
highest-value experiment on the board.
⚠ Do NOT re-derive stage spacing from `docs/fk24-stage-*-N-*.txt` mtimes: `Copy-Item` preserves the
SOURCE's LastWriteTime, and step 1 copies a stale marker `gft` never writes, so that delta reads as
+210 s or even +41,742 s. Only steps 2–4 are real.

**RESOLVED (was VALIDATION PENDING since 2026-07-10):** the default set runs THREE PI-hookers
(`pi8` + `loadout_fix` + `missions_fix`) and the full triple now has many confirmation launches.
It is **not** the killer: S109 showed `-NoPasses` (both PI hookers present) is ~21× *safer* than
`-NoMissions` (one present), and `pi8` alone ran 90 min clean. The shared-mutex design is fine;
the injection **burst** was the problem. `-NoMissions` / `-NoLoadout` still isolate individual
shims. See `docs/s109-fk9-capture-durable.md` and `docs/fk8-crash-timing-mined.md`.

**Steam must be running first**, or login dies with `Auth Failure 14005` (SteamAPI
init fails). Easy to miss; surface this gotcha if you see Steam not running.

**Shim readiness:** the launcher fires the injectors detached then blocks on the game,
so for a consolidated "did every shim activate?" view run `.\configs\shim-status.ps1`
(or `-Watch`) in a SECOND terminal. It's read-only — reads each shim's `docs/*-marker.txt`
and classifies READY / running / FAILED / leftover (anchored to the game's start time so a
shim that finished and went quiet still reads READY, and a marker from a prior launch reads
`leftover`). Safe to run anytime, including while another session has the game open.

The script blocks until the game exits. Read live `Loki.log` at
`C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log` (NOT `docs/` — that's
the backend `capture.log` for HTTP traffic). The loopback admin panel is at
`http://127.0.0.1:9210/` while `ags` runs (hunter unlocks, store/ownership, wallet,
mission progress, per-account state; see `docs/admin-panel.md`).

### ★ Tutorial sittings (FK-7 / FK-24 / anything in `LVL_Tutorial`) — HANDS-FREE

**Do not improvise this, and do not use `-Hook <play dll>`.** `RM_PLAY` and
`RM_SPAWNPOSSESS` are **continuation** modes: they attach to an already-running tutorial
and `return 0` before the force-open block, so a lone `-Hook` **cannot work** (S107 wasted
a launch proving it).

The old recipe needed a human to press PLAY → TUTORIALS → BASIC TRAINING → START. It no
longer does. That press has exactly ONE backend effect — `POST /startSoloMode` sets
`playerState.SoloMode` — and `handleCoreGamePlayer` gates on
`forceTutorialMatch || SoloMode != ""`. So flip the flag instead:

```powershell
# 1. server/internal/interactive/interactive.go -> const forceTutorialMatch = true
& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o ags.exe ./cmd/ags

# 2. ELEVATED PowerShell. Steam must already be running.
.\configs\launch-redirect.ps1 -NoHook          # returns after launching; game keeps running

# 3. SECOND call, once the game is up — stages the world and injects the DLL under test:
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\tutorial_launch_play.dll -Label myrun
```

MEASURED: with the flag on, the client parks itself **~13 s** after launch. `fk24-stage.ps1`
pre-flights that `ags` is really arming a match and refuses to run otherwise, then injects
`gft_ready_fix` → `tutorial_launch_fo` → `tutorial_launch_sp` → your probe, **gating each
step on measured evidence** and copying the marker off after every injection.
**Set the flag back to `false` when done** — otherwise a normal launch auto-parks into the
tutorial loading screen and looks broken.

⚠ **Order is load-bearing, and each of these cost a dead run:**
- `gft_ready_fix` goes **BEFORE** the force-open. The old documented `fo → gft → sp` order
  only worked because S107 injected all four back-to-back and gft landed *during* the 5.7 s
  LoadMap. Gate between them and the run dies with the log full of
  `ULokiGameFeatureToggles::Get … called when feature toggles were not ready`.
- Wait for `Load map complete /Game/Loki/Maps/Tutorial/LVL_Tutorial` — **not** the bare
  string `LVL_Tutorial`, which the force-open's own echoed console command also contains.
- Wait for sp's own `[SP] done step=4` before injecting the probe. `ResolveSpawnPossess`
  and `RM_PLAY`'s resolve are both **one-shot, no retry**; a fixed 5 s sleep is not enough
  and the probe aborts at `[PL] ResolveWakeMove failed … -> abort` having armed nothing.
- `[SP] gm=0x0 pc=0x0 startSpot=0x0 heroClass=0x0` = the world is gone. Do not proceed.

**Expected yield: only ~2 of 4 launches reach the armed window.** Budget on *armed windows
reached*, never on launches.

Success looks like this in `docs\tutorial-launch-marker.txt`:
```
[SP]   gm=0x… pc=0x… startSpot=0x… heroClass=0x…        <- ALL FOUR non-zero
[SP]   done step=4 spawnedPawn=0x… cls=BP_HERO_Ronin_C
[PL]   *** init complete: body=BUILT; camera + WASD active ***
[ANIM] PlayAnimation(run, loop) ok / PlayAnimation(idle, loop) ok   <- locomotion animating
```

For iterative server-only restarts (game already running at menu, want to swap
backend behavior): kill `ags`, rebuild with
`& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o server\ags.exe ./cmd/ags`,
restart manually (regen certs + re-append to cacert.pem if you want a clean cert
chain). See `docs/hero-roster-attempts.md` "How to reproduce" for the exact recipe.

## Code conventions for this project

- Backend handlers live in `server/internal/<package>/<name>.go`. Each handler's
  comment block should record what was tried + what worked + what didn't, with
  dates. The trial-and-error history is the value.
- Probe-driven backend work: prefer **single-variable changes**. Bundled tests
  (10 changes at once) have repeatedly produced ambiguous results that wasted
  cycles. If a hypothesis fails, REVERT the probe before testing the next one.
- Validity model for endpoints: UE's `JsonObjectStringToUStruct` IGNORES unknown
  JSON keys and only rejects the whole doc when a key that DOES match has a wrong
  type. So adding speculative fields is safe; sending wrong-typed matched fields
  is not. See the comment at the top of `server/internal/menu/menu.go` for the
  full validity model.
- The two distinct LogLokiPlatformQuery error strings mean different things:
  `"Invalid response received"` = a required top-level field is absent.
  `"Deserialization failure"` = JSON parsed but container type mismatched target struct.

## Tooling shortcuts

- **Extractor:** `tools/extractor/` — .NET 9 / CUE4Parse-based. ★ **TRUE subcommand list is TEN**
  (`Program.cs:22`, verified S116): `dump names namesall schema assetregistry wherefile mkpak peekpak
  bpdump rawfile`. ⚠ The old list here was wrong twice: **`raw` is really `rawfile`**, and
  **`enumerate` is not a subcommand at all** — it is the no-subcommand default mode, and
  `out/allassets.txt` is the preserved crash log of someone typing it
  (`Paks: enumerate` → `DirectoryNotFoundException`). `bpdump` drove several breakthroughs and was
  undocumented. (This also settles ignorance-map row (c).)
  ⚠ **`dump` has NO output-dir and NO usmap override** — it always writes the repo `out/`, and the
  usmap is resolved ambiently by search order with no md5 logged. Output is **flat by basename** with
  **586 colliding basenames** (last writer wins). A proposed `--usmap` / `--out` / `--list` patch
  (~20-line argv pre-pass, prints the loaded usmap's md5) is at
  `scratchpad/fk14-assets/PROPOSED-extractor-flags.diff`.
  **Timing [M]:** ~32.9 ms/asset marginal + 1,436 ms startup ⇒ full re-dump **~59 min** at the current
  80-path chunking (**20.7 min of that is pure process startup**, 865 processes), or **~38 min** with
  `--list`.
  Build/run with
  `& "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release` from `tools/extractor/extractor`.
- **usmap regeneration:** `tools/usmapdump/usmapdump.exe extract <exe-path>`
  produces `mappings.usmap`. Needed when game updates.
- **usmapdump RE commands:** `strings`, `wstrings`, `xref`, `disasm`, `peek`,
  `threads`, `findgametid`, `assetmgr` — read-only RPM, no injection.
- **usmapdump dumpimage:** `usmapdump.exe dumpimage <proc> [outDir]` — snapshots the
  live UNPACKED image to a cold PE for offline Ghidra/IDA (file-offset==RVA, ImageBase
  set to the live base, so project `base+0x…` addresses map 1:1). Also dumps private
  exec regions outside the module + a coverage manifest. Pure RPM (safe). CAVEAT: the
  build demand-decrypts `.text` pages on execution, so a single dump only captures pages
  the game has RUN — ~50% of `.text` at a fresh menu. Coverage rises the more code the
  game exercises; re-dump from a richer state (in-game) for more. Also writes
  `<stem>.exports.txt` (addr→module!export map, captured live) so `reconstructiat` can
  rebuild imports OFFLINE later. Dumps land in `/dumps/` (git-ignored).
- **usmapdump mergedumps:** `usmapdump.exe mergedumps <outFile> <in.dump.exe…|dir>` —
  unions several `dumpimage` snapshots into one maximally-covered image (fills each dump's
  demand-decrypt `.text` gaps from the others). A directory arg recurses for `*.dump.exe`.
  This is the path to near-complete `.text`: dump from DIFFERENT game states (login, hero
  grid, store, missions, and especially IN A MATCH — gameplay code never runs at menu),
  each to its own `dumps/<state>/`, then `mergedumps dumps/merged.dump.exe dumps`. Gain per
  dump = how much NEW code that state ran (two idle-menu dumps barely differ). CONSTRAINT:
  all inputs must share the same module base (ImageBase); a different-ASLR-base dump is
  rejected (its relocated `.text` bytes are incompatible). `.text` union is exact; the
  reported %, being non-zero-based, slightly undercounts (readable-zero bytes read as gaps).
- **usmapdump reconstructiat:** `usmapdump.exe reconstructiat <dumpFile> [outFile]` —
  rebuilds a real import table so Ghidra/IDA name API calls instead of raw IAT thunks, when
  the dumped IAT holds DIRECT resolved export addresses (unprotected binaries, e.g.
  explorer). Maps each slot to `module!export` via the `<stem>.exports.txt` sidecar, appends
  an `.idata2` section (descriptors + INT + names), repoints the Import data-dir. Fully
  OFFLINE. Validated on explorer (1066/1066). For SUPERVIVE use `deobfimports` instead — its
  IAT is import-PROTECTED (see below), so reconstructiat resolves ~0 of its slots.
- **usmapdump deobfimports:** `usmapdump.exe deobfimports <proc> <dumpFile> [outFile]` — the
  SUPERVIVE path. Its imports are import-PROTECTED (⚠ **NOT VMProtect/Themida — that name is
  REFUTED, see `docs/fk10-protector-identified.md`**): each IAT slot points to an
  obfuscated trampoline in a packer-hidden region (NOT any registered module), computing the
  real API as `real = C2 ^ ROL64(C1 + M, 0x33)` (per-stub C1/C2 imm64; M = a per-launch data
  qword) then `jmp`-ing to it. deobfimports EMULATES each stub (x86asm decoder + tiny integer
  interpreter) against the LIVE process to recover the real target, VERIFIES it against the
  exports sidecar (exact match — a mis-emulation can only yield "unresolved", never a wrong
  name), then rebuilds the table like reconstructiat. Needs the SOURCE process ALIVE (stub
  code + M are read live; M encodes the ASLR-relocated target). Validated: **1107/1107 slots,
  0 undecodable, 0 off-target**; output parses in `debug/pe` (all 1107 named). `capture-dumps.ps1
  -Finalize` calls this automatically while the game runs.
- **Manual mapper / DLL injector:** `tools/inject/` — for no-throw payloads only.
  ⚠ The recorded mechanism ("C++ exception unwinding gets eaten by the packer's vectored exception
  filter") is now DOUBTED, though the rule stands: S113 measured the game exe's
  `IMAGE_DIRECTORY_ENTRY_EXCEPTION` as **RVA=0 / size=0** (4 control binaries read fine), so
  `RtlLookupFunctionEntry` resolves nothing for the main image — which kills all three canaries
  identically without any VEH involvement. See `docs/fk10-protector-identified.md` §4.
- **Native shims:** `tools/sigbypass-mod/` — `catalog_store_fix` (roster/store/
  cosmetics), `missions_fix` (durable missions page), `mainmenu_refresh_pi8`
  (pick→center refresh), `loadout_fix`, `tutorial_launch`, plus the
  `missions_nativecall_probe*` RE series that built the native-call primitive.
- **Tutorial sitting driver:** `configs/fk24-stage.ps1` — stages the tutorial world and
  injects a probe/candidate DLL hands-free. `-Probe <dll> [-Label <tag>] [-SkipProbe]`.
  Copies the marker off after each stage into `docs/fk24-stage-<label>-<n>-<shim>.txt`,
  because `Marker()` opens `CREATE_ALWAYS` so **every injection truncates
  `docs/tutorial-launch-marker.txt`** (FK-25). See the launch procedure above.
  ★ **S114 FIX — it was silently taxing every tutorial sitting.** The parked-state gate tail-read only
  the **last 200 KB** of `capture.log`, but the client fetches `/core-game/matches` **once, early**, so
  on any log-heavy run that evidence had already scrolled out of the window and the gate could never
  pass — the stager then burned its full 420 s `WaitParkedSec` and aborted, **wasting the launch**.
  MEASURED: one attempt passed by luck (fetch 70 KB from the end), the next had the identical fetch
  **1.1 MB out of window**. Now reads the file whole; the gate passes in ~0 s.
- **Crash-dump archiver:** `configs/archive-crashdumps.ps1` — preserves Sentry/crashpad crash
  reports (the 43.8 MB minidump + that run's own `Loki.log`) out of
  `<GameRoot>\Loki\.sentry-native\` into `dumps\crashpad-<stamp>\`, SHA-256 verified, source never
  deleted. `launch-redirect.ps1` calls it automatically before launching and after the game exits;
  safe to run by hand anytime (`-Label <tag>`). Parse a dump with
  `python tools/crashtri/mdctx.py <reports/*.dmp>` — there is no cdb/WinDbg on this machine.
- **RPM probes:** `tools/re/*.py` — Python probes driving the native-call primitive
  (struct/field/rep-layout walkers, param/OUT-param builders, mission-model dumps).
  ★ **S114 console/exec family** (mostly OFFLINE, static-image): `console_probe.py` (pure-RPM live
  console/exec state — `ViewportConsole`, `UConsole` instances, decoded `DebugExecBindings`; 6/6
  offline self-test), `console_census.py` (controlled wide+ASCII multi-image token census),
  `exec_surface_probe.py`, `exec_chain_grade.py` (grades every verb on the `UPlayer::Exec` chain),
  `uht_funcflags.py` (`FFunctionParams` decoder → the 138 `FUNC_Exec` table, output
  `out/uht_funcflags_tuthero.csv`), `cvar_census.py` (→ `out/cvar_census_tuthero.txt`, the 44
  `loki.*` cvars), `guard_markers.py` / `guard_test.py` (the guard-exclusive-literal method),
  `cheat_reach_probe.py` (cheat-object reachability), `read_field.py` (raw single-field read).
  Config-side: `configs/set-debug-execbindings.ps1` — ⚠ **largely moot**, since `DebugExecBindings`
  are never evaluated; keep it only as the untested probe of whether a user `Input.ini` is read at all.
  ⚠ **Class lookups share a blind spot:** `obj_by_class.py` matches by SUBSTRING and
  `cheat_reach_probe.py` by `endswith`, and **neither finds `PC_MainMenu_C`** — which is the live
  menu PlayerController. Using one as the "proven" cross-check for the other produced a false
  "there is no PlayerController at the menu" in S114. **Two instruments that fail the same way are
  not corroboration** — use a class-derivation walk. (`cheat_reach_probe.py`'s derivation walk was
  also broken — it reported `LokiGameInstance LIVE=0` on a running game — and was FIXED in S114;
  its own `[CTRL]` gate is what caught it.)
- **Admin panel:** loopback JSON API + embedded GUI in `server/internal/admin/`
  (`-admin`, default `http://127.0.0.1:9210/`). See `docs/admin-panel.md`.

## What NOT to do

- Don't run `launch-redirect.ps1 -Revert` casually — that strips the hosts entries
  + cacert mods. Only when the user explicitly asks to clean up.
- Don't use Steam to launch the game for testing the redirect — Steam launches the
  exe with no `-ini:` overrides, so the backend redirects don't apply.
- Don't kill the `SUPERVIVE-Win64-Shipping` process without warning — the user may
  be mid-test.
- Don't propose another C++-exception-using payload for injection. We tested
  three canary variants; the packer's exception handler kills the process even
  with `__CxxFrameHandler3` properly imported.
- Don't propose `ScanPrimaryAssetTypesFromConfig` as a shim target again — the
  function `__report_gsfailure`s mid-call regardless of thread context (verified
  via off-thread call, thread-hijack with fresh stack, thread-hijack with own
  stack, and APC on the real game thread).
- **Don't try to open the dev console, and don't re-test it.** `ALLOW_CONSOLE == 0`, measured three
  independent ways in S114: `~`, `ToggleConsole`, `ConsoleKeys`, an `EnableCheats`/`CheatManagerClass`
  ini knob and every command-line variant are all dead, and `ViewportConsole` is NULL **by
  construction** (the viewport never builds one). ⚠ Also dead: **`-ExecCmds`** and **`-LogCmds`** —
  neither has a parse literal anywhere in the image. The working channel is
  `UKismetSystemLibrary::ExecuteConsoleCommand` (thunk `0x395D790`) via the native-call primitive,
  which this project has been using since ~S91. See the console/exec block above.
- **Don't accept "the call returned ok" as evidence a verb ran.** S114 got
  `console 'LogLoc' ok` from a call that never reached a PlayerController at all. **Only the verb's
  OWN output counts** — and pick a verb that actually emits: **`God` prints nothing whatsoever**, so
  its silence is uninterpretable. `LogLoc` (→ `LogCheatManager: BugItGo …`) is the graded verifier.
- ★★★ **THE TUTORIAL ROUTE NO LONGER WRITES `.text` AT ALL (S112, shipped 2026-08-08).** RM_PLAY's
  `ProcessInternal` patch is gone: `KFUNCSWAP` and `KFSNAME` now DEFAULT to the heap
  `UFunction.Func` swap, so the shipped `tutorial_launch_play.dll` (`.text 5151621d2154e454`) arms on
  **`swapped=2` heap pointers** and touches no module image. MEASURED: standing `.text` **10/10 armed
  windows died** vs no module-image write **2/30**, Fisher **p = 0.00000008**; at a matched 600 s hold
  the heap form was **0/16**. `SafeWrite` is linker-eliminated from the shipped DLL — verifiable by
  `FlushInstructionCache` / `VirtualAlloc` / `VirtualFree` being ABSENT from its import table.
  Rollback = `build.ps1 -Variant play-textpatch` (`433cf7d8f6a0770f`), which is also the A/B's control
  arm, so the rollback is a measured quantity rather than an untested path.
  ⚠ The other PI-hookers (`mainmenu_refresh_pi8`, `loadout_fix`, `missions_fix`) STILL patch `.text`
  transiently — the MENU route is unconverted. `tutorial_launch.cpp`'s `FsScan`/`FsThunk` is the
  worked example to copy.
- Don't leave a permanent `.text` patch in place — the ~3–5 min code-integrity
  check catches it and kills the process. ★★ **S111 MEASURED THIS, and it is far worse than
  "permanent" — even a SELF-RESTORING patch is lethal while it stands.** One-variable bisect at 1
  image / 320 s: patch standing **11/12** deaths vs no patch **0/5**, p = 0.00097
  (`docs/s111-bisect-jz-is-the-trigger.md`). Removing the VEH or the exec-stub/vtable hook changed
  nothing; removing the 2-byte `.text` write stopped every death. The whole ladder is explained by
  **how long a `.text` modification stands**: `-NoHook` 0 %, inert mapped DLL 0 %, production
  (patch restored ~6 s after catalog load, so standing ~5–45 s) **28 %**, controls that never
  restore ~90 %. ⇒ **the `.text` patch is the single biggest self-inflicted hazard in the project.**
  ★ `catalog_store_fix` NO LONGER PATCHES AT ALL (2026-08-06): `KNOJZ` defaults to 1, the shipping
  build contains no `.text` write, and the roster still renders because the shim's existing
  **`[+0x354]` DATA poke** is sufficient — screenshot-verified (`docs/s111-jz-dropped-shipping.md`).
  Rollback = `-Variant jzpatch`. **Prefer a data write over a `.text` write in every new shim.**
  ★★ **AND IT IS `.text` SPECIFICALLY, NOT CODE MODIFICATION** (S111 arm J,
  `docs/s111-armj-bytecode-vs-text.md` — predicted from source *before* running, then measured):
  `catalog_pick_fix` **permanently** patches UFunction **Script bytecode** (heap `TArray<uint8>`,
  `EX_Return`+jump, never restored) and is **0/9 deaths at a 320 s hold — identical to injecting
  nothing** — while a *self-restoring* 2-byte `.text` write is **7/8** (p = 0.00041). Ladder at
  320 s: nothing **0/22** · bytecode **0/9** · transient `.text` ×3 **4/12** · standing `.text`
  **7/8**. ⇒ **express shim effects as DATA or BYTECODE writes; never touch the module image.**
  ⚠ **The `-Hook` primary injection silently fails ~1 in 10** (S111 caught one with a treatment
  guard). Never assume "copied the file ⇒ injected" — verify via `docs/inject-watch.out.log`
  changing *and* naming the DLL, or via the shim's own marker stamp.
  ⚠ The other four shims (`mainmenu_refresh_pi8`, `loadout_fix`, `missions_fix`) still install
  `ProcessInternal` prologue patches — also `.text` writes, never bisected individually.
- Don't leave a `ProcessInternal` hook PERMANENTLY installed if another PI-hooking shim
  is present — they race on the prologue. Coexisting PI-hookers must install the jmp only
  TRANSIENTLY and serialize via the shared `Local\SuperviveMissionsPIHook` mutex (the way
  `mainmenu_refresh_pi8` / `missions_fix` / `loadout_fix` do). That's what lets all three
  inject together in the default set — any NEW PI-hooking shim must follow the same pattern.
- ★★★ **Don't trust the usmap's CONTAINER INNER or ENUM UNDERLYING types — they are ~70 % wrong,
  DETERMINISTICALLY, in every usmap this project has ever produced (FK-14 SETTLED, S116).** The old
  rule here ("wrong for *replicated* container types … verify against live RPM") was mis-scoped in
  BOTH directions and is replaced by: **container inner + enum underlying types are wrong regardless
  of replication; struct names, property names, super-struct links, `StructProperty` type names,
  scalar types and enum VALUE tables are identical across every extraction ever taken and CAN be
  trusted.** Root cause = `tools/usmapdump/extract.go:115` reads a container's inner **inline at
  `FField+0x80`**, which is past the end of the object, so it captures **whatever FField the allocator
  placed next** (`ArrayProperty+0x80` is 99.8 % pointer-ranged with only **39 distinct values** — it is
  literally the next FField's vtable). ⚠⚠ **The correct offsets are PER FAMILY — they do NOT share
  one** (each 100 % with a 0 % runner-up, two independent passes over 44,398 properties):
  `FArrayProperty::Inner` **`*(+0x78)`** · `FSetProperty::ElementProp` **`*(+0x70)`** ·
  `FOptionalProperty::ValueProperty` **`*(+0x70)`** · `FMapProperty::KeyProp` **`*(+0x70)`** /
  `ValueProp` **`*(+0x78)`** · `FEnumProperty::UnderlyingProp` **`*(+0x70)`** / `Enum` **`*(+0x78)`** ·
  type-carrying families (Struct/Object/Class/Soft*/Weak/Lazy/Interface/Byte) **`+0x70`**.
  ★ **`sizeof(FProperty) == 0x70` and the layout is essentially STOCK** — `+0x70` is uniformly the
  derived class's first member. The one deviant is **`FArrayProperty`, which has an 8-byte hole at
  `+0x70` (UNIDENTIFIED — not `ArrayFlags`) with `Inner` at `+0x78`.**
  ⚠⚠ **The aggregate "containers are at `+0x78`, 96.6 %" is an OVER-GENERALISATION that holds for 1 of
  5 families** — it decomposes exactly as Array 3,548 + Map *Value* 555 at `+0x78`, and Set 142 +
  Optional 2 + Map *Key* 555 at `+0x70`. **Calibrate per family AND per member, never pooled:** a
  pooled score blesses `+0x78` at 96.6 %, clears a 90 % gate, and ships a silently-broken
  Map/Set/Optional build **certified**.
  ⇒ **The extractor is DETERMINISTIC** (3 back-to-back runs byte-identical); FK-14's "non-deterministic"
  headline is REFUTED — the variance is **heap adjacency**, frozen within a process, different across
  launches. Never take an array **stride** from the usmap. Where an element type matters use
  `tools/asdump/out/binds_members.csv` or the UHT `FPropertyParams` oracle in
  `dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe`.
  ⚠ **`tools/extractor/out` (69,142 JSON / 1.3 GB) is invalidated for container + enum values** —
  confirmed in shipped output (`BP_StoreOffer_StarterPack.json` → `"AssetGrants": [0,5,0,3,10,0,0,0]`).
  Scalars and struct-typed properties are fine, so the **backend model work is largely SAFE**
  (`endpoints.md:49`'s `CoreGamePlayer` is 4 scalars — untouched by this).
  ⚠ **Two prior walls were built on this artifact:** `DefaultMappingContexts` is
  `TArray<FDefaultContextSetting>` (so **S79/S80's "measured as EMPTY" was read against a wrong inner
  type**), and `ScreenEffectCollections` is `TArray<UMaterialParameterCollection*>` — **NOT**
  `ELokiGameFeatureToggle`, so **the S88 toggle wall chased a `labelPtr` hit on adjacent heap.**
  ⚠ **`pipeline.go:214` silently overwrites the canonical `tools/extractor/mappings.usmap` on EVERY
  `usmapdump extract`, from any CWD** — that is how the canonical file became an orphan whose
  `schema.txt` is unrecoverable. Backup: `scratchpad/fk14-safety/`. Delete that write.
  ⚠ FK-1's recorded root cause (`usmap.go:325 writeInnerOrByte`) is a **downstream workaround**, not
  the cause; its "**unknown-typed**" filter has fired **ZERO** times and its cited `SpawnSelectEndTime`
  defect is **not a defect** (UHT says `Float` is correct). Read `docs/fk14-usmap-settled.md` first.
- **Don't read "no `UECC-*` directory in `Saved\Crashes`" as "the run died with no dump."**
  Sentry's **crashpad** writes a full minidump (43.8 MB) plus that run's own `Loki.log` into
  `<GameRoot>\Loki\.sentry-native\`. `harvest.py` and every hand-rolled census that enumerates
  `UECC-*` is blind to it. The clean tell in `Loki.log` is `handing control over to crashpad`.
  ⚠ That key is **NOT the last line** (two `LogTemp` lines follow it in the one death with a
  preserved dump) — scan the whole file, never `tail`. Bare `crashpad` is useless as a key: it
  matches two **startup** lines present in every session.
- **Don't rush to save a crashpad dump — and don't trust the retired "~60 seconds" advice.**
  RETRACTED S109: the old "uploads and DELETES it within ~3 minutes" was the gap between two `ls`
  calls with a relaunch inside it. MEASURED: crashpad tries **one** upload at crash+2 s, and on
  failure the report sits in `state=Pending` **indefinitely** (65+ min observed) because
  `crashpad_handler.exe` dies with the game and cannot retry. **The NEXT GAME LAUNCH is what
  clears it.** `launch-redirect.ps1` now archives the database automatically before launching and
  after the game exits (`configs/archive-crashdumps.ps1`, SHA-256 verified, never deletes the
  source); run it standalone anytime. ⚠ It depends on the upload failing — if the archiver ever
  warns "crashpad handoff but NO report on disk", uploads started succeeding and you must
  hosts-block `o566896.ingest.sentry.io`. See `docs/s109-fk9-capture-durable.md`.
- **Don't leave an S9x diagnostic switched on and then reason about the game.** This has now
  bitten twice: `KTESTACTOR` (S106) built a second degenerate body, and `KSTATICTEST` (S108b)
  called `PlayAnimation` on a `StaticMeshComponent`, faulting every run — SEH-caught, so it
  never crashed, it just printed `anim swapping DISABLED for the rest of the session` and
  **killed the hero's walk/run animation in every session for weeks**. Both defaulted to 1
  in shipped builds. When a shim behaves oddly, audit what the *shim* is doing before
  theorising about the game.
- **Don't A/B two DLLs without diffing their `.text` sha256.** Three artifacts have shipped
  identical-but-differently-named, and an A/B against a copy of itself burns a live run.
  When a `-D` default changes, DELETE the now-redundant variant rather than leaving a
  duplicate (S108b removed `play-nostatictest`/`play-nodiag` for exactly this).

## Working style

**Never bank, never treat any wall as final.** There is always another angle. Keep pushing
continuously; do NOT recommend stopping or "banking at the ceiling."

**Why:** this is a marathon reverse-engineering effort and the user wants relentless forward motion —
every "hard wall" in this project's history was eventually cracked by finding a new lever.

- Do NOT end a session by recommending "bank it" or presenting stop-vs-continue as the main choice.
  Keep generating and testing new hypotheses.
- When context is about to run out, THEN produce (a) a fresh-session handoff prompt and (b) updated
  documentation so a new session continues seamlessly (see the existing `docs/next-session-prompt-*.md`).
- Before declaring any wall "definitive," question your own assumptions and tools first — validate
  that the primitive you're using (a ProcessEvent RVA, an offset, a call convention) is actually
  correct. **A broken tool masquerades as a wall**, which is the whole subject of the method rules
  below.

## Method rules — read `docs/method-rules.md` first

Two standing rules that are not about any one subsystem, and that have overturned more walls here
than any single investigation:

1. **★★★ The instrument-artifact pattern** — the project's dominant error mode: an instrument's
   blind spot recorded as a property of the game. **36 confirmed instances**, each of which closed a
   technique, each of which fell in minutes. Read it before recording ANY negative result as a
   property of the game. Includes the nine "how to apply" rules — positive controls, naming the
   artifact you measured, and **rule 9: grep for the claim before correcting one instance of it.**
2. **★★ Read the shipped artifacts first** — check whether the game already ships the answer in
   plaintext before reaching for a debugger. Four multi-session walls fell to that alone.

## Where knowledge lives

Everything is in the repo, under version control — there is no separate memory store (the Claude
memory directory was migrated into `docs/` and removed on **2026-08-12**; it duplicated `CLAUDE.md`
and `docs/` at a fourth compression level, and its claims could not be `git blame`d or reverted,
which is a bad property for a project whose value is its retraction history).

- **`CLAUDE.md`** (this file) — the auto-loaded digest: current status per subsystem, closed
  hypotheses, and the "what NOT to do" list. ⚠ **A digest is an instrument** — S115-d is the
  instance where compressing a table into prose here manufactured a false claim that read as a hard
  measurement conflict for a full session. Never print a byte string next to an address it did not
  come from.
- **`docs/ignorance-map-s101.md`** — the living index: the FALSE_KNOWN register, the walls register,
  instrument blindness, and the ranked focus plan. Kept in lockstep with this file.
- **`docs/<fk-n>-*-settled.md`** — the primary evidence for each settled unknown, with the
  measurements and the controls. These are ground truth; this file is a summary of them.
- **`docs/method-rules.md`** — the two method rules above.
- **`docs/next-session-prompt-*.md`** — chronological handoffs.

⚠ **Historical handoffs still say things like "read memory `supervive-x`".** Those are dated
archives and were deliberately NOT rewritten — editing them would falsify the record of what a past
session was actually told. Successors for the names that appear:

| retired memory | now |
|---|---|
| `instrument-artifact-pattern` | `docs/method-rules.md` §1 |
| `read-the-shipped-artifacts-first` | `docs/method-rules.md` §2 |
| `never-bank-directive` | this file, "Working style" |
| `ags-cert-rebuild-gotcha` | `docs/ags-cert-rebuild-gotcha.md` |
| `angelscript-layer`, `fk1-*` | `docs/fk1-angelscript-settled.md`, `docs/fk1-stub-claim-recheck.md` |
| `cheat-surface-inventory` | `docs/fk6-cheat-surface-settled.md`, `docs/fk13-console-exec-settled.md` |
| `crashpad-capture-runtime-family` | `docs/s109-fk9-capture-durable.md`, `docs/fk8-crash-timing-mined.md` |
| `tutorial-crash-fk7` | `docs/fk7-crash-settled.md` (SUPERSEDED banner) → `docs/s112-fk7-ab-results.md` |
| `gc-reachability-mechanism` | `docs/s110-item-watch-gc-mechanism.md` |
| `input-mechanism-settled` | `docs/fk2-input-settled.md` |
| `protector-identified` | `docs/fk10-protector-identified.md` |
| `log-verbosity-available` | `docs/fk11-log-verbosity-settled.md` |
| `battle-gate-fk5` | `docs/fk5-battle-gate-settled.md` |
| `dedicated-server-status` | `docs/dedicated-server-stub.md` |
| `hero-roster-blocker`, `store-status` | `docs/hero-roster-attempts.md` + the roster block above |
| `missions-page-status` | `docs/missions-progression-hookup.md`, `docs/session-59-progress-bars.txt` |
| `passes-battlepass-status` | `docs/session-83-passes-tier-grid-solved.txt` |
| `avatar-render-status`, `customization-persistence` | `docs/session-85-avatar-render.md` |
| `tutorial-launch-status` | the `docs/s108-*` family + `docs/fk31-fk32-successors.md` |
| `milestone3-trackb-status` | `docs/trackb-notes.md`, `docs/endpoints.md` |
| `strxref-symbols` | `docs/strxref-{known-addresses,open-questions,state-coverage,vtables}.md` |
| `coverage-audit-s101` | `docs/coverage-audit-s101.md` ⚠ its known/unknown map is **stale** — FK-1/5/10/11/13 have all settled since; use `docs/ignorance-map-s101.md` |

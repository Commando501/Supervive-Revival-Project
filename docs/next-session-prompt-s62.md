# Next session (S62) — make the tutorial TRAVEL: finish the /core-game/players match shape

Paste this whole file as the first message of a fresh Claude session.

---

## Goal
Get the SUPERVIVE tutorial to actually LOAD + become playable via the **real menu flow**
(`TryStartSoloMode`). Both client-side native walls are already broken (S61). The client now fires the
real `/startSoloMode` and then **rapid-polls `GET /core-game/players/{id}` waiting for a match** — the one
remaining piece is finding the exact `/core-game/players` **match shape/state** that makes the client
travel to `LVL_Tutorial` (with a session, which also creates the PlayerState). This is backend + a little
RE, no more packer-blocked native walls.

## Read first (do NOT re-derive — it's all logged)
1. **`docs/session-61-tutorial-match-setup.txt`** — the FULL S61 chain (login crack, TryStartSoloMode gate
   decode, ags side). The bottom sections ("AGS SIDE STARTED", "GATE 2 FULLY DECODED") are the live frontier.
2. Memory: **`memory/supervive-tutorial-launch-status.md`** (auto-loaded index line in `memory/MEMORY.md`).
   The last few `***`-blocks are S61's results.
3. `CLAUDE.md` (launch/run procedure, "what NOT to do", packer/anti-tamper facts).

## What S61 achieved (don't redo any of this)
1. **FORCE-OPEN route** (`tools/sigbypass-mod/tutorial_launch.dll`): loads `LVL_Tutorial` locally but
   crashes at the session layer ("PlayerState is null"). We PIVOTED to the menu route. Along the way we
   **cracked the native login reject**: it's `AGameModeBase`-derived C++ **vtable SLOT 285** (offset 0x8E8);
   `ALokiGameMode` overrides it strictly. De-override = copy the stock `AGameModeBase` vtable's slot-285
   value into the match-mode vtables (shim `PatchLoginVtables`, `kOverrideSlots={285}`). Kept as a fallback;
   NOT needed for the menu route.
2. **MENU route (now primary) — `TryStartSoloMode` native gate DECODED + bypassed:**
   - `UPartyManager::TryStartSoloMode` impl @ `0x7FF6BAD6A980` (rva `0x587A980`); exec thunk rva `0x54B5F70`.
   - Params: `Mode:FString@0x0, HeroId:Struct@0x10, StartPosition:Int@0x20, OnComplete:Delegate@0x24,
     ReturnValue:Bool@0x34`.
   - **THE BAIL = GATE 2:** the party mode string at `PartyModel+0x558+0x18` must equal `"default"` or
     `"Matchmaking"`. It was EMPTY → bail (returned false → client `PopExecutionFlowIfNot` → silent stop).
     (Gate 1 = `PartyModel+0x550` flag, was 1, passes. Gate 3 = `ClientConfigManager` version check, passes.)
   - **FIX (verified live):** poke `PartyModel+0x558+0x18 = FString{Data=L"default", Num=8, Max=8}` (heap,
     writable, persists past polls). With it, clicking START fires the REAL:
     `POST /party/parties/{id}/startSoloMode?mode=tutorialNew&hero=&soloModeStartPosition=0`.
3. **AGS side STARTED** (`server/internal/interactive/interactive.go`, builds clean, hot-swapped live):
   - `POST /party/parties/{partyId}/startSoloMode` → `handleStartSoloMode`: records `playerState.SoloMode`,
     echoes `buildSoloParty` as the 200 body.
   - `handleCoreGamePlayer` is now per-player: returns an `InProgress` `DA_Tutorial_Basics` match when
     `SoloMode != ""`.
4. **★ KEY SIGNAL:** after `/startSoloMode` the client **rapid-polls `/core-game/players`** (~3/s → ~15-20/s)
   and WAITS there — so `/core-game/players` IS the travel channel in the solo-start flow (S53's "inert" was
   OUT-OF-CONTEXT). The response parses cleanly (no `LogJson`/deserialize errors), but `State="InProgress"`
   @ `127.0.0.1:7777` did NOT trigger travel/connect (zero `LogNet`, no `Browse`, no error). **So the exact
   match STATE/SHAPE is still wrong.**

## THE NEXT STEP — iterate the /core-game/players match shape (fast loop)
Because the client polls `/core-game/players` ~15×/s while waiting, you can iterate WITHOUT a re-click IF the
same session is still live: change `handleCoreGamePlayer`'s response, rebuild + hot-swap ags, and the client
picks it up on its next poll (~60ms). Watch `Loki.log` for `Browse`/`LoadMap`/`Bringing World LVL_Tutorial`
(local travel) or `LogNet`/`NetConnection` (server connect), and `docs/capture.log` for the poll behavior.

Approaches (priority order):
1. **Iterate the match STATE** (it parses cleanly, so it's the state/logic, not field names): try
   `AwaitingReady`, then a state PROGRESSION (`Allocating`→`AwaitingReady`→`Ready`/`InProgress`) across polls,
   and any `Ready`-like value. The valid `ECoreGameMatchState` values are in `interactive.go` near
   `phantomMatchState`.
2. **RE the client's match-ready handler** (decisive): the client is parsing `/core-game/players` responses
   HOT right now, so the handler code is committed/readable. Find what field/state it checks to decide "travel
   now" and whether it does a LOCAL travel (`open LVL_Tutorial`) or a server `NetConnection`. The tutorial map
   is LOCAL, and the client made ZERO `NetConnection` attempts — so it likely wants a LOCAL-travel indicator,
   not a DS address. Consider whether `MatchInfo` needs a "local"/no-server marker vs the `127.0.0.1:7777` DS
   address currently served.
3. **Alt channel — the /startSoloMode RESPONSE shape:** we echo the party; the native `TryStartSoloMode` HTTP
   callback may parse the body into a travel/session descriptor (drives `OnStartSoloModeComplete(bSuccess,
   MessageID, QueryContext)`; `bSuccess` looked true, no error). RE the PROCEED path of the impl
   (`0x7FF6BAD6A980`, from `0x587AA69`) to find the request URL build + the response-parse struct.

## Live state at end of S61
The GAME has EXITED (was PID 49816; closed/timed-out from the stuck rapid-poll state) → **you must relaunch
fresh** (below) and re-poke gate 2. `ags` may still be running (was PID 93656, new build) — but it was killed
mid-swap in prior cycles, so just rebuild+restart it as part of the launch anyway. `playerState.SoloMode=
"tutorialNew"` is PERSISTED in `state/interactive.json` (so a fresh boot will immediately report the phantom
match — fine, and actually convenient for iterating, but see the SoloMode-persistence gotcha).

## How to run / re-enter the menu-route state (fresh)
- **Launch (ELEVATED; self-elevates; Steam must be running first):** from repo root run the DEFAULT launcher
  (NOT `-NoHook` — the menu route needs the full menu + roster):
  `.\configs\launch-redirect.ps1`
  Kill any stale game first (`Stop-Process -Name SUPERVIVE-Win64-Shipping -Force`). It rebuilds+starts ags,
  sets the redirect, injects the shim set, and launches the game. Wait for the main menu
  (`WBP_UI_MainMenu_MenuRootV2` in `Loki.log`).
- **Re-poke gate 2 (per-launch — PartyModel address changes):** find the live PartyModel with
  `scratchpad/pm_flags.py` (or re-derive: `TryStartSoloMode` UFunc → not needed; just walk objects for class
  `PartyModel`, `this+0xF8` on `PartyManager`). Then poke `PartyModel+0x558+0x18` = `{Data=<addr of a live
  L"default" wide string>, Num=8, Max=8}`. Find a `"default"` wide literal via `usmapdump wstrings ...
  "default"` (its address is per-launch). `usmapdump poke <proc> 0x<addr> <hex>` works on the heap PartyModel
  (no VirtualProtect needed).
- **COMPUTER-USE IS USER-DENIED for the game window** — you CANNOT click START yourself. The USER must click
  Basic Training → START (after you've poked gate 2). Ask them to, and arm a watcher on `docs/capture.log`
  for `startSoloMode` + `Loki.log` for travel. (Alternative: build a shim to invoke `TryStartSoloMode`
  natively via the ProcessInternal primitive — bigger, crash-risk.)
- **ags iterate/hot-swap (server-only, no game relaunch):** edit `server/internal/interactive/interactive.go`
  → `& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o server\ags.exe ./cmd/ags` → `Stop-Process -Name
  ags -Force` → restart: from `server\`, `ags.exe -http :8080 -https :443 -log "<repo>\docs\capture.log"
  -certs "<repo>\certs"` (reuses certs → **no cacert re-append needed**; needs elevation for :443).

## Key addresses / recipes (build base `0x7FF6B54F0000`, stable across restarts — re-verify each launch)
- `TryStartSoloMode` impl `0x7FF6BAD6A980` (rva `0x587A980`); gate 2 @ `0x587A9D3..`; PROCEED @ `0x587AA69`;
  bail (`xor al,al`) @ `0x587AA62`. Gate-2 accepted strings: `"default"`, `"Matchmaking"`.
- Login vtable slot **285** (force-open fallback only): match vtable RVAs Tutorial `0x8A94C48`, Round
  `0x8A52A98`, ALokiGameMode `0x8951FA0`, BattleRoyale `0x88B7CB0`, DropIn `0x8936948`; stock GameModeBase
  vtable `0x806EDD8`.
- Object layout: Class@+0x18, Name@+0x20, Outer@+0x28; UFunction.Func@+0xE0, ChildProperties@+0x58; FProperty
  Offset_Internal@+0x44, FField.Next@+0x18, Name@+0x20. NAMEPOOL rva `0x9D81450`, OBJOBJECTS rva `0x9E38930`.

## Tools
- `tools/usmapdump/usmapdump.exe`: `objects`/`peek`/`poke`/`disasm`/`vtdump`/`vtslot`/`strings`/`wstrings`/
  `xrefstr`/`callxref` (read-only RPM + `poke` writes; takes the process NAME).
- scratchpad probes (Python RPM; may not persist — key ones re-creatable from the docs): `pm_flags.py`
  (find PartyManager/PartyModel + gate flags), `find_tssm.py` (find TryStartSoloMode + commit test),
  `tssm_params.py` (param enum), `gm_probe.py`/`inst_vt.py`/`gm_config.py` (gamemode CDOs/vtables/config).
- `tools/extractor` (`bpdump <asset> <fn>` — this build HAS BP bytecode; used to decompile
  `Comp_MainMenu_QueueController.OnStartSoloModeComplete` = `OnStartSoloModeComplete(bSuccess, MessageID,
  QueryContext)`).
- `tools/sigbypass-mod/tutorial_launch.dll` (force-open + login-285 de-override shim; `kOverrideSlots={285}`).

## Gotchas
- Gate-2 poke is per-launch (re-poke each time). Durable fix = the `/party` JSON field that populates
  `PartyModel+0x558+0x18` (key not yet mapped — a follow-up RE: trace the /party parse → PartyModel).
- `playerState.SoloMode` PERSISTS in `state/interactive.json` → `/core-game/players` reports the phantom match
  at every boot (inert per S53, but consider clearing it on match-end or not persisting).
- `hero=` was EMPTY in the `/startSoloMode` call (no hero selected). Will matter for the drop-in HERO once the
  tutorial travels — plan to select a hunter first (roster fix is in the default launch) and/or inject
  `catalog_store_fix`.
- Packer re-hides `.text` after execution — native functions are only readable while/just after they run
  (and only if they don't crash). `/core-game/players` client handler is readable WHILE the client polls.
- Don't re-grind ruled-out paths: URL options on the force-open (all crash at native Login), slot-176 login
  patch (wrong slot — it's 285), `/core-game/players` OUT of the solo-start flow (inert). The force-open route
  hits "PlayerState is null" (session layer) — the menu route is the way to get a real session.

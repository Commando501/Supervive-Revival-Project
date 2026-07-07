# Continue: SUPERVIVE Missions page — Session 55 pickup

Paste this into a fresh Claude session in `G:\git\Supervive Revival Project` (branch
`dedicated-server-stub`). Session 54 ran very long; this is the distilled handoff. The
authoritative technical detail is **`docs/session-54-ds-missions-replication.txt`** (read it —
especially the sections dated 2026-07-07). Memory: `supervive-dedicated-server-status`,
`supervive-missions-page-status`.

---

## TL;DR — the strategy pivoted mid-session; here's the current plan

Goal (unchanged for many sessions): make the **MISSIONS modal render** in the live SUPERVIVE client.
Missions is the ONE menu surface with no easy client-side shortcut (session 52).

Session 54 arc, in order:
1. **DS replication route WORKS for the DATA (breakthrough).** Built a stub-replicated
   `LokiPlayerState_Missions`; after fixing the schema, the client accepts the mission bunch and stays
   stable. This ALSO fixed the session-53 garbage-thread crash. **But then:**
2. **The DS route can't produce a VISIBLE modal.** The DS-connected client never loads the main-menu
   HUD (the menu is GameMode-driven; the stub can't supply the client-only BP menu classes, and the menu
   controller `PC_MainMenu_C` collides with the session-41 stock-PC constraint). So a networked client =
   no menu = nowhere to show missions.
3. **PIVOT to a CLIENT-SIDE SHIM (Option C), on the STANDALONE client** — where the full menu AND the
   Missions modal already work (modal opens EMPTY). The only missing piece there is the mission DATA.
4. **The entire missions ingestion is NATIVE** (no BP entry point the pi8 primitive can call). So we need
   a **game-thread native-UFunction-call primitive**.
5. **ProcessEvent-from-the-pi8-hook DEFINITIVELY no-ops for native** (validated the address by disasm;
   the native thunk was never entered). Confirms session 52.

**=> The whole thing now reduces to ONE unlock: a reliable game-thread native-call primitive.** Once we
have it, calling one native ingestion function on the standalone client (working menu) renders the modal.
This is also the keystone for the user's broader vision: **client-side shims do the work; the server
becomes an "activation / confirmation" layer that just triggers them.**

---

## YOUR JOB (Session 55): get the native-call primitive working

Two avenues remain (both un-done). **Recommended order: B first (lower risk), then A.**

### Avenue B — call ProcessEvent from a NON-re-entrant game-thread context
Hypothesis: ProcessEvent no-ops for native because we call it RE-ENTRANTLY (from inside the
`ProcessInternal` pi8 hook, mid-script). BP calls re-enter `ProcessInternal` fine (that's why
`mainmenu_refresh_pi8` works), but `ProcessEvent` bails for native when already executing script.
Test: hook a game-thread point that is NOT inside `ProcessInternal` — a per-frame native tick / main
loop — and call `ProcessEvent(obj, nativeFunc, parms)` from THERE. Re-use the **unambiguous thunk-hit
probe** (`missions_nativecall_probe2.cpp`): run-through-hook the target's native thunk and count entries
during the call. `thunkHits > 0` = PRIMITIVE WORKS.
- Finding a non-PI game-thread hook: candidates = `UGameEngine::Tick` / `UWorld::Tick` /
  `FTSTicker` / the game's main loop. Resolve via usmapdump (`strings`/`xref`/`disasm` on the live exe)
  or vtable scan. OR: hook a native `Tick` that runs once per frame. Must be on the game thread
  (`GGameThreadId` @ base+0x9D49158) and OUTSIDE script execution.

### Avenue A — DIRECT native-thunk call (bypass ProcessEvent entirely)
We HAVE the thunk address: `UFunction.Func @ UFunction+0xE0`. Build a minimal `FFrame` and call the
thunk `(*Func)(Context=obj, FFrame& Stack, void* Result)` directly. This is the ultimate primitive
(works regardless of ProcessEvent's guards). **Risk:** prior scan-shim attempts hit `__report_gsfailure`;
the `GetMissionsModel` thunk prologue is `mov rax,[rdx+0x20]; xor r9d,r9d; test rax,rax; setne r9b; ...`
so it READS `FFrame+0x20` — the frame must be built validly. FFrame has an FOutputDevice vtable at +0;
for a no-param getter, P_FINISH just steps `Code`, but you must supply a valid `Code` ptr and likely
`Node`/`Object`. Do it on a SAFE READ first (e.g. `GetMissions`), confirm, then a write.

### Once the primitive works → RENDER THE MODAL
Call ONE native ingestion function on the standalone client (menu already up), then open the modal:
- `LokiPlayerState_Missions.ServerAddMissionProgress` / `SetMissionProgress` (add a mission's progress)
- `UProgressionManager.AddProgressToMission`
- `UMissionsModel.CreateMissionsModel(PSMissions)` (build the model from a LokiPlayerState_Missions)
The modal is already reachable+empty on the standalone client; a populated `MissionsModel` + its
`OnUpdated` broadcast makes the category widgets rebuild. (Broadcast: the widgets subscribe to
`ProgressionManager.GetMissionsModel().OnUpdated`; the ingestion natives fire it. If not, `pi8` can
broadcast a delegate that a BP is bound to.)

---

## KEY FACTS you'll need (RE offsets, addresses, recipes)

**RE method (read-only RPM):** the client's RVAs are CONSTANT per exe build; only the module base
changes (ASLR). Get base from the process module list, pass to `tools/re/*.py`. Constants:
`NAMEPOOL=base+0x9D81450`, `OBJOBJECTS=base+0x9E38930`, `GGameThreadId=base+0x9D49158`,
`ProcessInternal=base+0x13454A0`, `ProcessEvent=base+0x12C5A10` (VALIDATED = UObject::ProcessEvent).
UObject: `InternalIndex@+0x10 Class@+0x18 Name@+0x20 Outer@+0x28`. UStruct/UClass:
`Children(UField*)@+0x50`, `ChildProperties(FField*)@+0x58`. UField `Next@+0x30`. FField:
`FFieldClass@+0x08 Next@+0x18 Name@+0x20 Flags@+0x38`. FStructProperty `Struct@+0x70`, FArrayProperty
`Inner@+0x78`. UScriptStruct `StructFlags@+0xB8(low u32)`. UFunction: `Script.Num@+0x70`,
`Func(native thunk)@+0xE0`. ProgressionManager `MissionsModel@+0x3B8`.

**RE tools (tools/re/):** `struct_probe.py` (find class/struct by name, dump), `field_walk.py` (walk a
class/struct's FField properties + flags), `func_enum.py` (enumerate a class's UFunctions, BP vs native
via Script.Num), `rep_expand.py` / `rep_expand_class.py` (expand a struct/class like FRepLayout),
`objprop_probe.py`, `field_off_probe.py`. Usage: `python tools/re/<t>.py <PID> <BASE-hex> <objAddr-hex>`.

**Shim probes (tools/sigbypass-mod/):** `missions_nativecall_probe.cpp` (ProcessEvent return test),
`missions_nativecall_probe2.cpp` (DEFINITIVE thunk-run-through-hook test — reuse this pattern for
avenue B). `mainmenu_refresh_pi8.cpp` = the working pi8 ProcessInternal→BP-call primitive. Build:
`clang++ -shared -O2 <f>.cpp -o <f>.dll -lkernel32` (clang++ at
`C:\Users\eastr\AppData\Local\Programs\Swift\Toolchains\6.3.2+Asserts\usr\bin\clang++.exe`).
Inject: `tools\inject\inject.exe mmap <PID> <dll>`. **ONLY ONE ProcessInternal-hooking shim per
client.**

**Standalone-client recipe for shim work** (elevated PS; Steam running):
`configs\launch-redirect.ps1 -Hook "...\tools\sigbypass-mod\catalog_store_fix.dll"` — full working menu,
`ProgressionManager`+`MissionsModel` live, and NO pi8 (explicit `-Hook` skips the secondaries) so your
probe's PI hook is the only one. Wait for `HUD BeginPlay - BP_MainMenuHUD_C` in the client Loki.log
(`C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log`). Then inject your probe. The full menu
takes ~3-4 min (login → lobby). NOTE: base has been `0x7FF6B54F0000` on recent launches (ASLR gave the
same base repeatedly, but re-read it each run).

**The missions data model (RE'd this session — the usmap was WRONG twice):**
- `LokiPlayerState_Missions` (native `/Script/Loki`): `Missions` is `TArray<Object*>` — array of
  `/Script/Loki.BaseMission : AActor` REFERENCES (NOT structs). `FinalMissionProgress` is
  `TArray<FMissionProgress>`.
- `FMissionProgress`: ID(FString), AssetId(FPrimaryAssetId), PoolId(FPrimaryAssetId), Complete(bool),
  Failed(bool), **ObjectiveProgress(TArray<FMissionObjectiveProgress>** — NOT int64 as the usmap said),
  MillisUntilExpiry(int64), Expiry(FDateTime), GrantedAt(FDateTime). FDateTime HAS
  STRUCT_NetSerializeNative.
- Client path: `Missions` OnRep → `OnMissionsUpdated` → native `OnPSMissionsUpdated` → `UMissionsModel`
  → `WBP_UI_MissionModal` renders. Menu GameMode = `BP_MainMenuGameMode_C`; menu classes =
  `BP_MainMenuHUD_C`, `PC_MainMenu_C`, `BP_MainMenuGameState_C`, `BP_MainMenuPawn_C` (all `/Game` BPs).

---

## WHAT'S DONE (don't redo these)

- **DS replication route** (branch `dedicated-server-stub`): `LokiPlayerState_Missions` replicates
  correctly (`Missions`=object array, `FinalMissionProgress`=struct array). Committed. FMissionProgress
  wire format is CORRECT. This is proven but leads to the bare-menu dead-end for a VISIBLE modal — so
  it's on the shelf unless we solve the DS main-menu-HUD problem (also documented; hard).
- **Modal reachability on DS = NO** (main-menu HUD doesn't load; root-caused: GameMode class mismatch).
- **Option 2 (BP-callable ingestion) = CLOSED** (all missions natives are Script.Num=0).
- **ProcessEvent-from-pi8-hook for native = CONFIRMED NO-OP** (definitive thunk-hit test).

## Gotchas
- Steam MUST be running before launching or login dies (Auth Failure 14005).
- `catalog_store_fix` is UNSAFE in the DS-connected context (crashes itself) — but FINE on the standalone
  client (its normal use). For standalone shim work, use it (full menu).
- ONE ProcessInternal-hooking shim per client (pi8 and the probes all hook it).
- Intermittent menu-load crash (~1 in a few launches) — just relaunch.
- The game exe is packed; anti-tamper (`preloader.dll`) hooks `NtCreateThreadEx` — don't hook thread
  creation.
- `usmapdump disasm` printed only a header for me (no instructions) — read bytes via a Python RPM script
  and decode manually if needed.
- Everything is committed; working tree only has runtime churn (certs/markers/capture logs) — ignore.

## First moves for Session 55
1. Read `docs/session-54-ds-missions-replication.txt` (the 2026-07-07 sections) + the two memory files.
2. Decide avenue B vs A (recommend B). For B: RE a non-`ProcessInternal` game-thread hook point
   (tick/main-loop), then adapt `missions_nativecall_probe2.cpp` to call ProcessEvent from there and
   re-run the thunk-hit test on `GetMissionsModel`.
3. If the primitive works: call an ingestion target on the standalone client, open the Missions modal
   (computer-use — request access; the game window process is `supervive-win64-shipping.exe`), verify
   tiles.

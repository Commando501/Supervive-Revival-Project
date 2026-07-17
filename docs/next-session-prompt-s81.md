# Next session (S81) — START HERE: the connection drops, and that invalidated most of S80's live tests

## The one-paragraph state
S80 **root-caused and fixed the hero-movement wall** (a NULL GAS attribute set — the hero physically moved,
velocity 500, in a genuinely live tutorial session). It also discovered, at the very end, that **the client
disconnects from the DS stub ~2 minutes after every join**, which means **most of S80's later "null results"
were measured in a MAIN-MENU session, not the tutorial**. Before anything else, **fix or characterise the
disconnect** — every downstream test is meaningless until the client can stay connected.

---

## ★ DO THIS FIRST (cheap, decisive, ~6 minutes, no code)
Fresh stub + client, join, then **INJECT NOTHING** and watch for ~5 minutes.

* **Stays connected** ⇒ **S80's injections caused the stall.** Every ds_hybrid mode does multiple
  `ForEachObject` sweeps (~175k objects) on the GAME THREAD, and S80 injected constantly. Fix by doing
  discovery OFF-thread (RPM from outside, pass addresses in) and caching handles at setup.
* **Drops anyway** ⇒ **the DS route itself cannot hold a connection.** That is the real S81 wall; hero /
  drop / WASD are all unreachable until it is fixed.

**The disconnect signature** (client's `Loki_2.log` / newest `Loki*.log`):
```
UNetConnection::Tick: Connection TIMED OUT. Closing connection.. Elapsed: 0.00, Real: 19.99, Good: 19.9
-> UEngine::Browse "/Game/Loki/Maps/LVL_Login?closed" -> GameNetDriver shut down -> LVL_LobbyV2_Persistent
```
`Elapsed: 0.00` with `Real: 19.99` = **~20s CLIENT-side game-thread stall**. Stub side logs
`Result=ControlChannelClose`. One cause was FOUND AND FIXED (see "my bugs" below); the drop persists, so
there is at least one more.

---

## ★★★ THE BIGGEST TRAP: the "BRALL / DROP LEADER" screen is the **MAIN MENU**
Live-proven while the user was looking at it:
```
LocalPlayer->PC = PC_MainMenu_C        <- MAIN MENU controller
PC->Pawn        = BP_HERO_Ronin_C      <- a hero pawn = the menu's hunter display
GameState       = BP_MainMenuGameState_C ; World = LVL_LobbyV2_Persistent
```
SUPERVIVE's main menu poses your hunter with a **DROP LEADER** pill + **EMOTE WHEEL**, so it *reads* as a
pre-drop screen. **It is not.** Seeing it means **you are disconnected**.

**This invalidated a large fraction of S80's late testing** — the hero "getting GC'd", 48/48 widget
collapses with no visual change, 720 WASD inputs moving nothing, `GetDistanceFromHeightMap ... GameState
was null`. In every one of those cases the client had already dropped to the menu.

⇒ **ALWAYS verify you are actually in the session before believing ANY result:**
```
LocalPlayer->PC should be LokiPlayerController (native)   NOT PC_MainMenu_C
World should be LVL_Tutorial                              NOT LVL_LobbyV2_Persistent
a live LokiGameState should exist                         NOT BP_MainMenuGameState_C
```

---

## ★★★★★ THE BIG WIN (keep, reuse): hero movement is SOLVED
**Root cause, traced end-to-end with every link measured:**
```
AddMovementInput ✓ -> APawn::ControlInputVector ✓ -> CMC consumes (LastControlInputVector) ✓
  -> CMC Acceleration = (50000,0,0) ✓
  -> CalcVelocity: Velocity += Accel*dt ; Velocity = Velocity.GetClampedToMaxSize(GetMaxSpeed())
       LokiCharacterMovementComponent::GetMaxSpeed  [CMC vtable slot 153 = +0x4c8] = base+0x55ACB90
         -> tail-call `jmp [hero_vtable+0xC00]` (slot 384) = base+0x558BD90
           -> base+0x55AC9F0 : `mov rbx,[rcx+0xF08] ; test rbx,rbx ; je -> return 0`
  -> GetMaxSpeed()==0  =>  Velocity CLAMPED TO 0  =>  NO MOVEMENT
     (gravity still works: PhysFalling applies it OUTSIDE the clamp — that is why the hero falls+lands
      perfectly while never moving horizontally)
```
**The NULL:** `hero->AttributeSetStorage @+0xF08`. Also NULL: `AbilitySystemComponentStorage @+0xF00`,
`AttributeSetHealthStorage @+0xF10`. `bCharacterMovementEnabled @+0xB59 = 1` (movement is NOT disabled).

**THE FIX (8 writes, no construction) — live-proven: `GetMaxSpeed()` 0 → 500, hero MOVED (vel 500, X 0→51.6):**
1. **Do NOT spawn `LokiPlayerState_HeroAffiliated`** — it **CRASHES the client instantly** (its ASC init
   derefs server-side context; no `[VEH]`, Sentry catches it). Its name lies: chain is
   `LokiPlayerState_HeroAffiliated <- Actor <- Object` — it is **not** a PlayerState.
2. Use its **CDO's default subobjects** (already constructed, nothing to build):
   `Default__LokiPlayerState_HeroAffiliated` → `AbilitySystemComponent @+0x3E8`, `AttributeSet @+0x3F0`,
   `AttributeSetHealth @+0x3F8`.
3. Write them into the hero's `+0xF00 / +0xF08 / +0xF10`.
4. **Write the WHOLE movement attribute block** on the `LokiAttributeSet`. Wiring the set makes the Loki CMC
   read EVERY movement value from attributes instead of its base UPROPERTYs — a set with only `MoveSpeed`
   gives `MaxAcceleration=0` ⇒ `Accel = 0*input = 0` ⇒ still no movement (observed!).
   `FGameplayAttributeData { float BaseValue@+0x8; float CurrentValue@+0xC }`:
   ```
   MoveSpeed@+0xF0=500  MaxMoveSpeed@+0x100=500  MaxAcceleration@+0x120=50000
   GroundFriction@+0x130=8  BrakingDecelerationWalking@+0x140=2048  Mass@+0x170=100
   ```
   (values copied from the CMC's own base props, read live)
5. `SetMovementMode(MOVE_Walking=1)` — a raw hero spawns at `MovementMode=0 (MOVE_None)`.
   `MovementMode @+0x231` (uint8), `CustomMovementMode @+0x232`.
6. Wire `nativePC->Pawn @+0x3F8 = hero` and `hero->Controller @+0x400 = hero's PC`.

**Why the attributes are 0 in the first place:** all **467** live `LokiAttributeSet`s read `MoveSpeed=0` —
the values are **server-authoritative and our stub replicates NO attributes**. Borrowing another actor's set
is useless; the NUMBER must be supplied. *A stub-side attribute implementation is the "proper" fix.*

**All of this is implemented in `MODE_PLAYABLE` (36)** in `tools/sigbypass-mod/ds_hybrid.cpp`.

---

## ★★ NEVER DO THESE AGAIN (each cost S80 hours, each is live-refuted)
1. **Never null the native PC's `Player @+0x458`.** It owns the NetConnection; UE resolves an RPC's owning
   connection through the PC↔Player link. Zeroing it made `ServerEcho` fail (`"No owning connection for
   actor LokiPlayerController_..."`) → GameNetDriver shutdown → TravelManager bounced the client to
   LVL_Login, **destroying a 23-hour session**. (MODE_DEVSWAP now leaves it intact.)
2. **Never walk CurrentPhase 4→5→6→7.** S80 tried it; the client then **NEVER LEAVES THE LOADING SCREEN**
   (verified with NO shim injected, so it is the game's own behaviour). Reconfirms S73/S77. The loading
   dismiss is **phase-gated to `EGP_SpawnSelect(4)` specifically** — 4 is the destination, not a waypoint.
   REVERTED; `AdvanceRoundPhase()` is retained unused in `LokiStubGameMode.cpp` purely as a tombstone.
3. **Never do file I/O or full-object walks on the GAME THREAD.** `Markerf` = CreateFile+WriteFile+CloseHandle
   **per line**; the widget census did ~1,244 of them → ~20s stall → connection dropped. A per-frame
   re-census (175k objects every ~5s) made the game **visibly choppy for the user**.
4. **Never trust an `N/N` count when `N` equals a cap.** `ResolveSpectatorCam` collects into a **48-slot**
   array using broad substrings; the client has **5,293** UUserWidgets, so it fills with the first 48
   matches and `WBP_UI_PredropScreen` never makes the list. S80 read "48/48 widgets collapsed" as success
   for several runs. It was the array being full.
5. **Never hide widgets to reveal the world.** Collapsing all 5 pre-drop widgets by exact class name
   (`vis 4→1`, fault=0) changed the screen **not at all** — because we were in the MENU (see the trap above).

---

## Tooling (all read-only RPM, no injection, seconds each — USE THESE BEFORE THEORISING)
| tool | question it answers |
|---|---|
| `tools/re/comp_census.py <pid> <base> <obj> [substr...]` | **state**: what components/objects does X actually have? (reflection; exact, no caps) |
| `tools/re/ufunc_survey.py <pid> <base> <obj> [substr...]` | **runnability**: Func native-vs-ProcessInternal, `Script.Num`, PropertiesSize, params, flags |
| `tools/re/script_dump.py <pid> <base> <cls> <FnName>` | **behaviour**: a BP function's bytecode, operands resolved to names |
| `tools/re/ubergraph_dump.py <pid> <base> <cls> <UbergraphFn> <entry>` | **behaviour**: the real BP graph (operand-aware). BP events are 18-byte `ExecuteUbergraph_X(EntryPoint)` thunks — **ALWAYS FOLLOW THE JUMP** (entries are `Jump -> X`) |
| `tools/re/disasm_live.py <pid> <base> <rva> [n]` | **behaviour**: capstone on the live process |
| `tools/re/find_func.py <pid> <base> <substr...>` | which class owns a UFunction (BP/native) |
| `tools/re/input_ctx.py` | LocalPlayer → PC → PlayerInput → AppliedInputContexts |
| `usmapdump nameid <proc> <substr>` | FNamePool substring search (asset/type vocabulary) |

`ds_hybrid.cpp` modes (`-DKMODE=`): **PLAYABLE(36)** = the full hero assembly + per-frame WASD;
**WGTCENSUS(37)** = one-shot buffered widget+visibility dump (ONE file write — safe mid-match);
**HIDEPREDROP(38)** = collapse widgets by exact class name; MOVETEST(35), DEVSWAP(34), BPCALL(33).

---

## Reusable primitives born in S80
* **`CallBP(obj, ufunc, args, len)`** — runs BP-folded UFunctions **correctly**. The old `CallNative`
  hardcodes `FFrame.Code=0`, which is harmless for a native thunk but a **NULL DEREF** for a BP fn (whose
  `Func` IS `ProcessInternal`, which executes bytecode from `*Stack.Code`). Fix = `Code =
  UFunction->Script.GetData()@+0x68`, `Locals` = zeroed `PropertiesSize@+0x60` buffer. **RawUnhook() first.**
  Also **reset `FFrame::FlowStack@0x48`** (TArray<uint32,TInlineAllocator<8>>: Inline[32]@+0, Secondary@+0x20,
  Num@+0x28, Max@+0x2C = 0x30 bytes → `0x48+0x30` = 0x78 PreviousFrame / 0x80 OutParms / 0x88 PropChain,
  matching the project's existing FF_ constants) — ubergraph bail paths rely on "empty stack == return".
* **`base+0x12C5A10` is NOT ProcessEvent** — its prologue saves only `rcx`/`rdx` and never touches `r8`, so
  it is a 2-arg fn that ignores the Parms buffer. The S54 "slot 56" id is wrong. **The real ProcessEvent is
  unidentified and NOT NEEDED** (BP fns' `Func` is already ProcessInternal).

---

## Facts worth not re-deriving
* **Input** = **legacy FName `K2Node_InputActionEvent`** nodes, NOT Enhanced Input, NOT IMCs (that is why no
  IMC assets exist anywhere — the game never needed them). 137 hits: `BP_LokiPlayerController_C` **39**,
  `BP_LokiSpectator_C` 25, `Comp_PlayerController_Emotes_C` 24, `BP_LokiPlayerController_Code_C` 6.
  **The native `LokiPlayerController` (the DS client's ACTIVE PC) owns ZERO input events.**
* PC class chain: `BP_LokiPlayerController_Dev_C <- BP_LokiPlayerController_C <- BP_LokiPlayerController_Code_C
  <- LokiPlayerController_AS <- LokiPlayerController <- LokiBaseController <- PlayerController`.
  (`_AS` ⇒ likely **Unreal AngelScript**.)
* **`BP_LokiPlayerController_Dev_C` is NOT LOADED** in a fresh DS session (`devCls=0x0`) — so
  `MODE_SPAWN_P2` **fails** there, and S74/S79's `DropPlaneComponentSetup` / `UpdateIsInDropPod` /
  `FinishDropPhaseHiding@PC+0xF28` route is **unavailable**. MODE_PLAYABLE self-spawns the hero for this reason.
* **The drop machinery that DOES exist here**: `Comp_PlayerState_DropPlane_C` (`SetDropPodDestination`,
  `ClearSelectedDropPodDestination`, `BP_OnDropPodLaunched`) + `BP_DropPlane_MultiStationary_C`. It is a
  **PlayerState component**, not the PC. None were live while in the menu — re-check from a real session.
* **The hero was never missing anything cosmetic**: it HAS `Mesh@+0x450`
  (`BP_Assault_DefaultSKMeshComponent_C` → `SK_Assault_Default_LOD1`, bVisible, bRecentlyRendered) and a
  fully-configured `SpringArmComponent@+0x1990` (`TargetArmLength=3020` — the authentic top-down distance).
  `CountHeroSkeletals()` is BROKEN (greps "SkeletalMeshComponent"; the class is "…SKMeshComponent…").
* `LokiPlayerController::MoveForward` is the **SPECTATOR/free-cam** path — `base+0x569A1B1` does
  `cmp [this+0x3F8],0 / jne <epilogue>`, i.e. it RETURNS when the PC HAS a pawn. Hero movement is
  `APawn::AddMovementInput`.

## Live-test recipe (Steam UP first, else Auth Failure 14005)
Stub + client are driven entirely from the agent side (the user cannot navigate the UI once force-loaded):
```powershell
# stub (rebuild only if you touched unreal-stub; kill UnrealEditor-Cmd first or LNK1104)
& "H:\Unreal Engine\UE_5.4\Engine\Build\BatchFiles\Build.bat" LokiEditor Win64 Development -Project="G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"
Start-Process "H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" -ArgumentList @(
  '"G:\git\Supervive Revival Project\unreal-stub\Loki.uproject"','/Engine/Maps/Entry?listen','-game','-server',
  '-Port=7777','-nullrhi','-NoSplash','-Unattended','-abslog="G:\git\Supervive Revival Project\docs\ds-server-s81.log"')
# client: launch the exe DIRECTLY with the -ini overrides (launch-redirect.ps1 needs UAC + would start a 2nd ags).
# hosts + cacert are already in place; ags is already running. See the S80 transcript for the exact -ini list.
```
Then: `tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\ds_hybrid_playable.dll`; read `docs/ds-hybrid-marker.txt`.
**Module base has been `0x7FF6AF000000` every launch, but heap addresses change — re-resolve objects BY NAME.**

## Method (the whole lesson of S80: 8 investigated "walls" → 8 measurement/tool bugs, 0 game limits)
Read **state** by reflection, **behaviour** by disassembly, check **runnability** first — and
**verify the MEASUREMENT before believing any "X is missing/broken"**. S80's own additions to the fake-wall
pile: "no mapping context", "bindings exist", "the pre-drop view is a preview stage" (right mechanism, wrong
context — it was the menu). **When a live observation contradicts a tool, believe the observation** — the
user's screen was right every single time it disagreed with my memory reads.

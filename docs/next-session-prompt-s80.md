# Next session (S80) — DEPLOY-SEQUENCE RECONSTRUCTION: the wall is REOPENED (ProcessEvent may be a false wall)

## The one-paragraph state
We took the S79 client-side moonshot from "spectator-only ceiling" all the way to a **possessed,
camera-followed hero standing in the live tutorial world** (object-graph + camera fully working;
committed `018292b`). Then began the **deploy-sequence reconstruction** to make the hero VISIBLE +
CONTROLLABLE. Mapped the whole deploy state machine, drove `LivingState`→Alive, traced the mesh to
its root (needs a `CosmeticsAssetID` + the cosmetics controller + the BP deploy setup). Concluded the
BP deploy functions "fault out-of-context"… **then questioned the tool and found that conclusion is
likely WRONG: `ProcessEvent` BP calls THEMSELVES fault, while native direct-thunk calls work fine on
the same object.** So the "deploy context wall" may be a *false wall* caused by a ProcessEvent-calling
bug. **That is the live frontier — fix the BP-call mechanism and the deploy reconstruction reopens.**

## ★ READ FIRST (don't re-derive — this session mapped it all)
- `docs/session-79-moonshot-plan.md` — the FULL S79 + deploy-reconstruction log, every phase + result.
  The last section ("WALL REOPENED") is the current frontier.
- Memory `supervive-dedicated-server-status` (S79 landmark + deploy reconstruction + the reopening).
- Memory `supervive-never-bank-directive` — user directive: never bank; keep pushing; question your own
  tools before calling a wall final (this session proved why: the "wall" was a broken tool).
- `tools/sigbypass-mod/ds_hybrid.cpp` — one file, ~30 compile-gated modes (`-DKMODE=MODE_*`). All the
  deploy work is here. Commits `018292b`→`754215c` on branch `dedicated-server-stub`.

## ★ THE LIVE LEAD (start here) — ProcessEvent is NEUTERED; build a BP invoker on ProcessInternal
**RESOLVED this session (`MODE_BPTEST3`):** `ProcessEvent` (`base+0x12C5A10`, vtable slot 56, RVA confirmed) fails to
dispatch **even a NATIVE function** — `GetCosmeticsController` returns `0x…C4173C0` via the direct-thunk primitive but
fault/ret-0 via ProcessEvent, on the SAME hero. So ProcessEvent is a broken/neutered path in this build (reconfirms the
S54 finding — it's WHY the direct-thunk primitive exists). ⇒ **Every `FAULTED` line in the BPDEPLOY/CONTEXT/DEPLOYEVT runs
was ProcessEvent failing to dispatch — the BP deploy functions NEVER ACTUALLY RAN. The "deploy needs match-init context"
conclusion is UNPROVEN. The wall is retracted.**

### THE task: make BP-folded functions actually EXECUTE, then retry the deploy
BP-folded functions have `UFunction.Func == ProcessInternal` (`base+0x13454A0`), so the direct-thunk primitive can't run
them (it calls Func with our minimal template FFrame; ProcessInternal needs a REAL frame). Build ProcessEvent's core
ourselves (the neutering is only in the ProcessEvent wrapper, not ProcessInternal):
1. Find two offsets on the UFunction/UStruct via a field walk: **`UFunction::Script`** (a `TArray<uint8>` — Code =
   its `.GetData()`) and **`UStruct::PropertiesSize`** (int32 — the locals/frame size). (Also `UStruct::MinAlignment`
   maybe.) Cross-check against UE 5.4 layout; this build's UObjectBase is non-standard (nameOff=0x20, classOff=0x18).
2. `CallBPProper(obj, ufunc, argsBuf, argsLen)`: allocate `locals = _alloca(PropertiesSize)` (or a big static), zero it,
   copy args into it; fill an FFrame (reuse the captured template; set `Node=ufunc`, `Object=obj`,
   `Code=Script.GetData()`, `Locals=locals`, `OutParms=0`/or BuildOutParms), then call
   `ProcessInternal(obj, &frame, resultBuf)` **with the PI hook RawUnhook()'d first** so it doesn't re-enter our stub.
   (Return/out values land in `locals` at the function's ReturnValue offset.)
3. Validate with `GetCosmeticsController` (native, expect `0x…C4173C0`) then a BP getter, THEN re-run the deploy setup
   (`ClientInitialComponentSetup` / `BP_PostSetupCosmetics` / `ReceiveRestarted` / `TryLocalControlSetup`) + RefreshCosmetics
   → check for a skeletal mesh + a visible hunter.
4. If a BP call still doesn't build the mesh, THEN (and only then) the real context gaps show — investigate those with the
   deploy functions actually executing. Alternative validation of ProcessInternal-call correctness: `usmapdump disasm
   base+0x13454A0` (C/SeDebugPrivilege RPM works in-match) to see the FFrame fields it reads.
Gotcha: the current hero (`0x28577E6D560`) is heavily hand-mangled + drifted over the void — spawn a FRESH
`BP_HERO_Assault_C` for clean tests (SPAWN_P2 → NPOSSESS to re-establish a possessed hero, or just spawn + test).

### ★ UFunction layout found (`MODE_UFUNCDUMP` on `ReceiveRestarted` @0x28504D23000) + a WRINKLE
Confirmed offsets (this build, relative to the UFunction/UStruct base): `Func @+0xE0` (== ProcessInternal for BP-folded),
`FunctionFlags @+0xB8`. UStruct tail: **`PropertiesSize` (int32) @+0x60**, `MinAlignment` (int32) @+0x64, then the
**`Script` TArray @+0x68** (ptr @0x68 / num @0x70 / max @0x74). `+0xF0` = a `.text` ptr (EventGraph/native entry?), `+0xF8`
hi = 0x41.
★ **WRINKLE:** `ReceiveRestarted` has `PropertiesSize=0` and an **EMPTY Script** — because BP *events* don't carry their own
bytecode; they dispatch into `ExecuteUbergraph_BP_*(EntryPoint)`. So a naive "Code=Script.GetData()" invoker won't run a BP
event. Options: (a) dump a function that HAS real Script (`ExecuteUbergraph_BP_LokiHeroCharacter` — a BP fn WITH params +
bytecode) to confirm the Script fields are non-zero there, then call the setup via `ExecuteUbergraph(hero, <EntryPoint>)`
with the entry point of the deploy node (find the EntryPoint by inspecting the event's tiny stub, or brute-force small ints);
OR (b) find NATIVE deploy functions that do the same work (native calls already work via the direct-thunk primitive — prefer
these where they exist); OR (c) fully replicate `UObject::ProcessEvent` (it allocates locals, inits the frame incl. the
event→ubergraph jump, calls ProcessInternal) minus whatever neuters the shipped one — the cleanest general fix. Validate any
invoker on `GetCosmeticsController` (native, expect `0x…C4173C0`) BEFORE trusting it on deploy fns. New mode: UFUNCDUMP.

## Everything banked (facts/offsets — re-resolve VAs by NAME each launch; base is ASLR'd)
- Local-player wiring: `LocalPlayer->PlayerController @+0x38`; `PC->Pawn @+0x3F8`; `Pawn->Controller @+0x400`;
  `AController::PlayerState @+0x3C0`; `Pawn::PlayerState @+0x3D8`; camMgr view target `@+0x420`.
- The RENDER/INPUT pipeline follows the **native PC** (`LokiPlayerController`), not a swapped-in PC — so hand
  the hero to the native PC (Possess no-ops on the networked proxy → raw-wire Pawn/Controller). Camera follows
  it + holds (beat the S78 revert). Camera drivable via the hero `CameraComponent` +
  `K2_SetWorldLocationAndRotation` (world-space; local frame is flipped). Authentic top-down ≈ 3000-4000 up.
- Hero deploy/visibility: `LokiCharacter::LivingState @+0x1090` (uint8 enum, 0=None/1=Alive; set→Alive holds);
  `HeroPredropHidden @+0x1BE8`; native `GetLivingState`/`OnRep_LivingState`/`OnCharacterVisibilityUpdated`.
- Mesh: NO character SkeletalMesh on a raw hero; native builder `RefreshCosmetics`(0x…39E420) needs a
  `CosmeticsAssetID` (fields `@+0x1FF0` + `OverrideCosmeticsAssetID @+0x2000`) — skin type = `HeroCosmeticsBundle`,
  default = `AssaultDefault` (`server/internal/menu/cosmetics.go` + `data/skins.txt`); cosmetics CONTROLLER
  already exists (`GetCosmeticsController` → non-null). But mesh build ALSO needs the BP deploy setup → ProcessEvent.
- `ProcessEvent = base+0x12C5A10` (vtable slot 56). Reusable helpers in ds_hybrid.cpp: `CallGuardedBP(obj,ufunc)`,
  `CallGuardedBPP(obj,ufunc,params)`, `RawUnhook()`, `ListFuncsMatching`, `ListPropsMatching`, `ListAllFuncs`,
  `CountHeroSkeletals`, `OuterChainReaches`, `BdGetController`.

## Recipe to reproduce the live state
Steam UP first (else Auth Failure 14005). The FULL stack was LEFT RUNNING at handoff — client
`SUPERVIVE-Win64-Shipping` **PID 48788** (native Loki PC possessing a hand-assembled hero, camera top-down over
LVL_Tutorial, mesh invisible), + `ags` + the stub `UnrealEditor-Cmd`. If it's gone, rebuild the DS stack per
`docs/session-79-moonshot-plan.md` "Live-test recipe" (ags `ConnectionDetails.address="127.0.0.1:7777"` +
`forceTutorialMatch`; stub-first on `LVL_Tutorial`/`Entry?listen` seeded `EGP_SpawnSelect`; `launch-redirect.ps1
-NoHook`; then run the S79 hero-assembly chain: SPAWN_P2 → SWAP → NPOSSESS → LIVINGSTATE → SETCOSMETIC to rebuild
a possessed hero to test on — OR just spawn a fresh hero for BP tests).
Build a mode: `clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS -DKMODE=MODE_<X> ds_hybrid.cpp -o ds_hybrid_<x>.dll
-lkernel32 -luser32`. Inject: `tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\ds_hybrid_<x>.dll`. Read
`docs/ds-hybrid-marker.txt`. Anti-tamper dodged throughout via transient-per-fire hooks / off-thread RPM (never a
standing `.text` hook). ~30 clean injections into the ONE session with no crash.

## Mode index (all in ds_hybrid.cpp, `-DKMODE=`)
SPAWN_P2(7) SWAP_CENSUS(8) SWAP(9) POSSESS(10) DEPLOY(11) UNHIDE(12) NPOSSESS(13) CAMFIX(14) DEPLOYRECON(15)
CRESTART(16) CAMFRAME(17) STATERECON(18) LIVINGSTATE(19) MESHDIAG(20) MESHMGRRECON(21) COSMETICS(22) COSMENUM(23)
SETCOSMETIC(24) BPDEPLOY(25) CONTEXT(26) DEPLOYEVT(27) VTDUMP(28) BPTEST(29) BPTEST2(30).

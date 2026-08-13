# Route B — SHIPPED AND WORKING: a live `UCheatManager` on the PlayerController

**S114, 2026-08-12.** Built, run on the menu route, and externally verified.
Evidence: `docs/fk13-routeb-menu-install-2026-08-12.txt` (shim marker),
`tools/re/out/fk13_reach_tutorial_2026-08-12.txt` (prior state).
Background: `docs/fk13-console-exec-settled.md`, `docs/fk13-live-run-2026-08-12.md`.

---

## 0. Result

`APlayerController::CheatManager` (`+0x520`) was **NULL in every measurement this project has ever
taken**. It is now populated with a real `UCheatManager`, and `UPlayer::Exec` **branch 7** — dead in
every prior reading — is live.

```
[CHM] PC=0x24983CBC040 class=PC_MainMenu_C  CheatManager@0x520 CheatClass@0x528 (by name, not literals)
[CHM] CheatClass=0x2484A275100 (CheatManager)
[CHM] SpawnObject params: ObjectClass@0x0 Outer@0x8 ReturnValue@0x10
[CHM] SpawnObject ok -> 0x24A071D2D60
[CHM] constructed 0x24A071D2D60 class=CheatManager
[CHM] *** INSTALLED: PC->CheatManager@0x520 = 0x24A071D2D60 -- readback verified ***
[FS]  disarm: restored=18223 of 18223 swapped
```

**Externally verified** (the shim's own readback does not count):
`cheat_reach_probe.py` reports `CheatManager CDO=1 **LIVE=1** -> 0x24A071D2D60`, the chain row reads
`+0x520 -> 0x24A071D2D60 class=CheatManager`, and a raw `read_field.py` shows the object's `classPtr`
`0x2484A275100` equal to the independently CTRL-resolved `UCheatManager` UClass. `[CTRL]` passed on
every probe run. Zero crashpad handoffs; **zero** `UGameplayStatics::SpawnObject` warnings (its three
guards stayed silent — the pass condition). Process healthy 41 min post-install. [M]

## 1. What it does

New `RM_CHEATMGR` mode in `tools/sigbypass-mod/tutorial_launch.cpp` — a mode, not a new DLL, so it
inherits the Func-swap, SEH, guards and markers.

`UGameplayStatics::SpawnObject(CheatClass, pc)` → store into the reflected `CheatManager` UPROPERTY.
`InitCheatManager()` is deliberately **skipped**: it does only `ReceiveInitCheatManager()` (a
BlueprintImplementableEvent, no-op for the native class), a broadcast to
`OnCheatManagerCreatedDelegate` (which has **zero** registrants anywhere in stock UE), and an
`OnEndPlay` cleanup binding. None is on the `ProcessConsoleExec` path. [M]

**Zero module-image writes.** It arms via the heap `UFunction.Func` swap; the `KFUNCSWAP=0` path —
which every *other* mode in this file uses, and which is `SafeWrite(g_pi, jmp, 5)`, a standing 5-byte
`.text` patch at `ProcessInternal` — is an **explicit compile-time refusal** that prints why. S112
measured that construct at 10/10 armed-window deaths vs 3/36 (Fisher p = 7e-8).

⚠ The S112 import-absence check (`FlushInstructionCache`/`VirtualAlloc` absent) **does NOT apply to
this DLL** — the file contains other modes that legitimately import them. The no-`.text`-write
property rests on source reading plus the compiled-out refusal, not on the import table.

## 2. Why `SpawnObject` was the right primitive — a sharper reason than first stated

In a shipping build `DO_CHECK == USE_CHECKS_IN_SHIPPING == 0` and `WITH_EDITOR == 0`, so
`NewObject`'s internal `check()` for `ClassWithin` (UObjectGlobals.cpp:3357) is **compiled out — a
wrong Outer would be SILENT**. `UGameplayStatics::SpawnObject` performs an explicit *runtime*
`ClassWithin` test (GameplayStatics.cpp:827-831) that is independent of `DO_CHECK`. It is therefore
**the only reachable construction primitive whose Within validation survives shipping.** [M]

`UCheatManager` is `UCLASS(Blueprintable, Within=PlayerController)`; `IsA` resolves to `IsChildOf`,
so `PC_MainMenu_C` and `BP_LokiPlayerController_Dev_C` are both valid outers. [M]

## 3. GC correctness — closed

`APlayerController::CheatManager` is `UPROPERTY(Transient, BlueprintReadOnly)`, and **`Transient` does
NOT remove a property from the GC reference token stream** (`AssembleReferenceTokenStreamInternal`
applies no `CPF_Transient` filter). Stock UE relies on this one Transient UPROPERTY as the cheat
manager's **sole** keep-alive for its entire lifetime, so the install invents no lifetime policy. [M]

⚠ **Correction to an earlier claim in this session:** `RF_StrongRefOnFrame` (0x01000000), which
`SpawnObject` allocates with, is **not a keep-alive and grants no grace period** — its only consumer
is the ubergraph persistent-frame collector. Storing immediately is still correct; the stated
mechanism was wrong.

Durability: there are exactly **two** write sites for `CheatManager` in all of Engine/Source —
`AddCheats` (stubbed here) and `APlayerController::Destroyed` (sets NULL). No `OnRep`, no
`ClientRestart` write. Nothing will clobber the install short of PC destruction. [M]

## 4. ★ The first attempt was a silent no-op, and the shim said so

`cheatmgr` arms on `KFSNAME="ReceiveTickClient"`, chosen by S112 from a **settled tutorial world**
profile. That function is **never dispatched at the menu**. The watchdog printed:

```
[FS] *** NO GAME-THREAD HITS after 8000 ms (allThreadCalls=0 swapped=2) ***
[CHM] done (installed=0x0 pc=0x0 called=0 hitsGT=0)
```

A silent failure here is indistinguishable from success if the only check is "did it crash".
⇒ **Use `cheatmgr-any` (KFSNAME="", 18,223 pointers) at the menu; `cheatmgr` in-world.** S112 measured
the wide arm at 0/8 deaths over 600 s holds, and this mode is one-shot (seconds). [M]

## 5. ★ The reflection guard earned its keep

`FindCheatablePC` accepts a candidate only if its class reflects **both** `CheatManager` and
`CheatClass`. Live, it rejected `LokiPlayerControllerUAVComponent` and accepted `PC_MainMenu_C` — a
class matching *no* name pattern. That is exactly the blind spot that produced this session's own
false "no PlayerController at the menu" reading, now guarded structurally rather than by convention.

## 6. Corrections to earlier statements in this session

| Stated earlier | Corrected |
|---|---|
| "44 real exec verbs" | **42 REAL / 3 FOLD / 3 COVERAGE-BLOCKED / 2 UNRESOLVED** (byte-level) |
| `InitCheatManager` implied absent | **Real, 650 B**, plain virtual at vtable slot 139 / `+0x458`. Skipped by choice, not necessity |
| `RF_StrongRefOnFrame` = a GC grace period | Not a keep-alive at all (§3) |
| Verify with `God` | ⚠ **`God` emits NO log line** — a silent instrument, the FK-11 trap. `KCMVERIFYCMD` now defaults to **`LogLoc`**, paired with `[Core.Log] LogScriptCore=Verbose` (USER `Engine.ini`; `-ini:` is applied too late) as the "the router ran at all" control |

## 7. Guards added after the first run (R7/R8/R9)

The first install succeeded, but three checks were missing — it was luck, not a guard:

- **R7 class identity.** The object was stored without confirming it derives from `UCheatManager`.
  Branch 7 does `mov rax,[rcx]; call [rax+0x288]`, so a wrong class would execute whatever sits at
  that slot, on the first console command, unattributable afterwards. Now walks the super chain.
  (`SpawnObject`'s Within check constrains the OUTER, not the constructed class — it is not this check.)
- **R8 alignment.** The by-name offset was never checked for 8-byte alignment; branch 7 reads the
  field from the game thread with no lock, and x86-64 guarantees atomicity only for aligned qwords.
- **R9 offset cross-check.** By-name stays authoritative, but it now WARNs (never aborts) if it
  disagrees with the measured `0x520`/`0x528`.

## 8. Builds

| Variant | `.text` sha256 | Use |
|---|---|---|
| `cheatmgr` | `750b83bf0f36e90e` | in-world (`ReceiveTickClient`) |
| `cheatmgr-any` | `b551996df67f106b` | **menu** (swaps all BP UFunctions) |
| `cheatmgr-verify` | *(rebuild before use)* | +1 dim: also executes `KCMVERIFYCMD` |

Pre-guard builds were `a90e14dcde1dffa8` / `ef2fd89f87168871` — do not confuse them.
`verify_dll.py`: PASS (no C++ exception machinery, no CRT).

## 9. ★★★★★ END-TO-END PROVEN — a console string reached a cheat verb

**2026-08-12, menu route, PID 50016.** Baseline `BugItGo` = 0 and `LogCheatManager` = 0 in `Loki.log`.
After `ExecuteConsoleCommand("LogLoc")` routed through the PC:

```
LogCheatManager: BugItGo 0.000000 0.000000 0.000000 -2.150000 -90.000000 -0.000000
LogCheatManager: ?BugLoc=X=0.000 Y=0.000 Z=0.000?BugRot=P=-2.150000 Y=-90.000000 R=-0.000000
```

Those are the two `UE_LOG(LogCheatManager, Log, ...)` calls inside `UCheatManager::BugItStringCreator`,
which only `UCheatManager::LogLoc` reaches. Both format literals were confirmed present in the image
BEFORE the run (wide=1 each, against three known-present controls), so this was a pre-registered
signal, not a post-hoc grep. The zero coordinates are correct for a menu pawn at the origin — the
point is that the body executed. [M]

⇒ **The full chain is proven:** `ExecuteConsoleCommand` → `APlayerController::ConsoleCommand` →
`UPlayer::ConsoleCommand` → `UPlayer::Exec` → **branch 7 `PlayerController->CheatManager->
ProcessConsoleExec`** → `CallFunctionByNameWithArguments` → `UCheatManager::LogLoc`.

Health after: process **69 min** uptime, responding, **0 crashpad handoffs**, Func-swap restored
**18,223 of 18,223**. Evidence: `docs/fk13-routeb-logloc-proof-2026-08-12.txt`.

### 9.1 ⚠ The first verify attempt was a false "ok" — and why

Attempt 1 reported `[SHOT] chm-verify: console 'LogLoc' ok` while `BugItGo` stayed at **0**. The call
did not fault; it simply did nothing. Cause: `RunConsole()` passes
`WorldContextObject = g_wmPC ? g_wmPC : g_worldCtx` and `SpecificPlayer = 0`, and BOTH globals are
populated by other run modes (`ResolveWakeMove`, the force-open's ProgressionManager lookup) — they
are **zero in RM_CHEATMGR**. Stock `ExecuteConsoleCommand` then evaluates

```
UWorld* World = GetWorldFromContextObject(null) -> null
TargetPC = (Player || !World) ? Player : World->GetFirstPlayerController()
         = (false  || true )  ? null   : ...    -> nullptr
-> GEngine->Exec(nullptr, Cmd)                      // never touches a PlayerController
```

so `UPlayer::Exec` never ran and branch 7 was never reached.

**Fix:** `RunConsoleOnPC(pc, cmd)` passes the PC as BOTH `WorldContextObject` and `SpecificPlayer`;
a non-null `Player` short-circuits the lookup to `TargetPC = Player`.

★ Two lessons worth keeping. **"The call returned ok" is not a success criterion** — only the verb's
OWN output is; the marker now says so in the line it prints. And a helper that reads globals set by a
*different* run mode will silently no-op in a new one — check the provenance of every global a
borrowed helper touches.

## 10. What is NOT proven

**No exec verb has been executed.** The install proves branch 7 is *populated*, not that a console
string *traverses* it. ⚠ `UPlayer::Exec`'s branches are `else if`-chained, so an earlier branch that
returns true swallows the command before branch 7 — pick a verb that exists ONLY on `UCheatManager`.
The end-to-end test is `ExecuteConsoleCommand("LogLoc")` with `LogScriptCore=Verbose`.

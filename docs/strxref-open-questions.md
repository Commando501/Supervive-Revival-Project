# strxref applied to the project's open questions (S103)

**Date:** 2026-07-26 · **Mode:** 100% offline static analysis. No game launch, no injection,
no writes to `dumps/`. Everything below is reproducible from `dumps/merged.dump.exe` +
`tools/strxref/strxref.py` with no running process.

Every claim is tagged **MEASURED** (read directly out of the image) or **INFERRED**
(a reading of measured bytes). FK-3 and FK-4 both exist because a measurement artifact
was recorded as a structural fact; this document is written so that mistake is not repeated.

---

## 0. What was added to the tool first

`strxref` gained three modes because the questions needed them. Two are new *techniques*,
not conveniences.

### `native <UFUNCTION name>` — name string → exec thunk → native implementation

UE5 emits, per class, two generated tables. **The discriminator between them was measured,
not assumed** — confusing them yields a plausible-but-wrong function address:

| table | where | layout | what you get |
|---|---|---|---|
| `FClassFunctionLinkInfo[]` | `.rdata` | `{ UFunction*(*Z_Construct)(); const char* Name; }` — **pointer first** | the class's complete UFUNCTION list + each `Z_Construct_UFunction_<Class>_<Name>` |
| `FNameNativePtrPair[]` | `.data` | `{ const char* Name; FNativeFuncPtr Exec; }` — **name first** | the real `execXxx` thunk, whose last non-helper `rel32` callee is the implementation |

Classification rule (implemented in `_classify_slot`): if the slots at ±16 also hold name
pointers and slot−8 is a `.text` pointer, it is link-info (ptr-first) and *this* entry's
constructor is at **slot−8**; otherwise slot+8 is the exec thunk. Getting this backwards
silently returns the *next* function's constructor.

**Why this matters more than it sounds:** the `.rdata` tables are **99.64% readable**
(FK-3's correction), so `native` recovers a function's address *even when the code that
registers it is in an undecrypted `.text` page*. Coverage stops you from *disassembling*
the target, not from *locating* it.

**Ground-truth validation ×2 — both against results produced by live RE, never by this tool:**

1. `native GetFeatureTogglesReady` → exec `0x5376E00` → impl `0x565E1A0` → tail-jmp `0x55DDA50`:
   ```
   055DDA74  mov   rax, qword ptr [rax + 0x5a0]
   055DDA80  movzx eax, byte ptr [rax + 0xb3]
   055DDA87  shr   al, 6
   055DDA8A  and   al, 1
   ```
   S89 established exactly this by live disassembly + injection: *"bit6 of
   `[LokiGameState+0x5A0 = ServerAuthConfig +0xB3]`"*. **Exact match, offline, from a string.**
2. `native TryUpdateAbilitySystem` → exec `0x5438C20` → tail-jmp **`0x56CE5F0`**.
   `docs/coverage-audit-s101.md:232` records S102's *live* finding: *"the `+0xE0` thunk is a
   textbook exec-thunk tail-jumping to `0x56CE5F0`"*. **Exact match.**

### `nattable <slot>` — walk the table → a class's whole native API

`nattable 0x089790E8` prints **159** `ULokiGameplayStatics` UFUNCTIONs with their
constructors. `nattable 0x088DB718` prints **251** for `ALokiCharacter`;
`nattable 0x08A26AF8` prints **133** for `ALokiPlayerState`. Offline, no symbols, no RTTI.

### `near <rva>` — string neighbourhood = translation unit

MSVC lays a source file's literals out contiguously. When the target string has 0 xrefs
(its page is undecrypted), a *neighbour* that does have one lands you in the same TU. This
is what turned "`ALokiGameMode` has no readable code" into an anchor list.

Tool self-validation after the changes: **21 checks, 0 failed**.

---

## 1. The S89/S90 loading-overlay wall — ANSWERED, with a directly callable native

### The overlay teardown is a native function and we now have its address

| symbol | exec thunk | implementation | evidence |
|---|---|---|---|
| **`ClearMatchTransition`** | **`0x548F630`** | **`0x588ED60`** | MEASURED: thunk tail-jmps there at `+0x15` |
| `AsyncLoadMatchTransitionWidget` | `0x548F5F0` | `0x588B720` | MEASURED |
| `GetLokiTransitionWidgetManager` | `0x5490C00` | `0x589D0C0` | MEASURED |

Those three are one `FClassFunctionLinkInfo[]` (`0x08A90440..0x08A9046F`) — MEASURED, so
they are the complete native surface of that class. A second 3-entry table
(`0x08A8FC60..0x08A8FC8F`) is the widget manager itself:
`NotifyTransitionInComplete` (exec `0x5490E30` → `0x58A6B30`), `StartTransitionIn`
(exec `0x5490E50`), `StartTransitionOut` (exec `0x5490E70`).

`GetLokiTransitionWidgetManager` @ `0x589D0C0` is three instructions — `call 0x57ACC60` then
`return [rax+0x38]` (MEASURED) — i.e. the manager is field `+0x38` of whatever `0x57ACC60`
returns. That is the `this` a shim needs.

**State machine, MEASURED from the two entry points:**
```
0588B720  AsyncLoadMatchTransitionWidget:  cmp qword [rcx+0x50], 0 ; jne <bail>
0588ED60  ClearMatchTransition:            cmp qword [rcx+0x50], 0 ; je  <bail>
```
`[this+0x50]` is the "a transition is currently mounted" handle: async-load refuses when it
is set, clear refuses when it is not.

Callers of `0x588ED60` (MEASURED, exhaustive `E8`/`E9` scan of `.text`): the exec thunk at
`0x548F645`, a `call` at `0x58A02DB`, a tail-`jmp` at `0x58B14E6`.

**What this means (INFERRED):** S90's stated next step was *"rebuild the stale `ds_hybrid.dll`
… kMode=MODE_SPECTATOR_CAM, which HIDES the `WBP_UI_MatchTransition` overlay widget."* That
hand-hides a widget. `ClearMatchTransition` is the game's own teardown for the same overlay
and is reachable through the existing S55 native-call primitive by name. It is the cleaner
lever, and it comes with its own precondition (`[mgr+0x50] != 0`) that tells you whether the
overlay is actually mounted — a diagnostic the hide-the-widget approach cannot give you.

### The readiness EVENT — clean negative, but the addresses are recovered

`PollForFeatureTogglesReady`, `FeatureTogglesReadyOrChanged` and
`ReceiveFeatureTogglesReadyOrChanged` are **`ALokiCharacter` members** (MEASURED: all three
sit in the 251-entry `ALokiCharacter` link-info table at `0x088DAA88..0x088DBA37`). That is
itself informative — the readiness wait is on the *character*, not on a UI subsystem.

| symbol | exec thunk | body in this dump |
|---|---|---|
| `PollForFeatureTogglesReady` | `0x5302DE0` | **all-zero page — undecrypted** |
| `FeatureTogglesReadyOrChanged` | `0x52FEF50` | **all-zero page — undecrypted** |
| `ReceiveFeatureTogglesReadyOrChanged` | — (BP event, no native pair) | n/a |

**This is a clean negative, and here is the state that would fix it.** `ALokiCharacter`
code does not execute at the menu, and `dumps/merged.dump.exe` is effectively one
menu-state dump. To read these: `usmapdump dumpimage` **from inside a match / the tutorial
world** into `dumps/ingame/`, then `usmapdump mergedumps dumps/merged.dump.exe dumps`, then
`strxref.py --rebuild`. The addresses above are already enough to call or hook them.

`OnClientGameFeatureTogglesReady` (`0x08A16438`) has **0 registrar sites and 0 data pairs** —
MEASURED. It is a multicast delegate property, not a UFUNCTION with a native thunk, so it has
no exec pointer to find. Use `tools/re/offline_xref.py ptr 0x08A16438` for its property
descriptor.

Also settled, negatively: **there is no `WBP_UI_MatchTransition` string in the image**, and
no `GearUp`, `WaitForFeatureToggles` or `LoopForFeatureToggles` string either (MEASURED,
both ASCII and UTF-16). Those names in the record come from Blueprint assets, not the binary.

---

## 2. `ALokiGameMode::SpawnPlayer` returns null (S74) — ANSWERED, decisively

**`ALokiGameMode::SpawnPlayer`'s native body is `return nullptr`. Literally.**

MEASURED chain:
```
native SpawnPlayer
  FNameNativePtrPair slot 0x09BDB230 -> exec thunk 0x534C070
    ... P_GET_* helpers ...
    0534C228  e8 23 29 c3 fb   call 0xf7eb50        <-- the implementation call
    0534C22D  49 89 06         mov qword ptr [r14], rax   <-- stored as the return value
    0534C23B  call 0x751deb0   (__security_check_cookie)

00F7EB50  33 c0   xor eax, eax
00F7EB52  c3      ret
```
`0x00F7EB50` is the COMDAT-folded `return 0` body — 58 call sites reach it (MEASURED). So the
compiled body of `SpawnPlayer` in this shipping client is `{ return nullptr; }`.

**What this means (INFERRED, but tightly):** `SpawnPlayer` is a `BlueprintNativeEvent` whose
C++ `_Implementation` is an empty stub; the real spawn logic lives in the Blueprint override
(`BP_LokiGameMode_*`). S74's *"SpawnPlayer returns null"* is therefore **not a runtime
condition failing and not a missing precondition** — there is nothing to fix in the native
path. Calling the native thunk directly (the S55 primitive's default) **bypasses the
Blueprint graph by construction**. To get a spawn, the call must go through `ProcessEvent`
/ the BP-bytecode primitive (`CallBPGuarded`, S91-93), not `CallNativeGuarded`.

That distinction is exactly the trap CLAUDE.md already documents in the other direction
("the direct call has no guards, so it works where slot-56 `ProcessEvent` no-ops for native
functions"). Here the polarity is reversed, and it is checkable offline from now on: **if
`native <name>` resolves to `0x00F7EB50`, the native body is empty and the logic is in
Blueprint.**

### The rest of `ALokiGameMode` — clean negative with anchors

`near 0x08B1FCE0` shows the whole `LokiGameMode.cpp` literal block, and essentially all of
it reads `refs=0` (MEASURED) — `ALokiGameMode` is authority-side code that never runs at the
menu. Not absence; non-decryption. The few that *do* resolve are anchors into the decrypted
part of that TU:

| string | function |
|---|---|
| `Starting graceful shutdown: %s, %u` | `0x56012E0` |
| `Failed to find a victim or killer for a death event` | `0x560AFE0` (+0x52A7) |
| `We're ALokiGameMode but aren't using an ALokiGameState!` | `0x560A020` and `0x560A090` |

⇒ `ALokiGameMode`'s code region is around **`0x5600000`–`0x5620000`**. Its 72-entry
link-info table is at `0x08944EE8..0x08945367` (`nattable 0x08945308`), listing
`AllowSpawnAtLocation`, `GetPlayerStartsForTeam`, `OnPlayerSpawned_BP`, `SpawnPlayer`,
`SetPlayerStartName` and 67 more — every one with its `Z_Construct`, offline.

---

## 3. The GAS / ability-system wiring — CONFIRMED offline, plus a named candidate for the open field

`TryUpdateAbilitySystem` is an **`ALokiPlayerState`** member (MEASURED: it is entry [129] of
the 133-entry link-info table `0x08A262E8..0x08A26B37`, alongside `OnRep_HeroClass`,
`ServerSetHeroClass`, `GetHeroAsset`, `HeroAffiliatedEndPlay`, `AuthAddAbilityPoints`).

- exec thunk **`0x5438C20`** → tail-jmp impl **`0x56CE5F0`** (MEASURED) — this independently
  reproduces S102's live result, offline.
- `0x56CE5F0`'s body is an **all-zero page in this dump** — undecrypted. Clean negative:
  ability-system code does not run at the menu. S102 read it live; a from-a-match dump would
  make it readable statically too.
- `OnRep_HeroClass` → exec `0x5438450` → impl `0x56C47D0`; a second registration
  (exec `0x5457670` → `0x56C47E0`) exists, i.e. **two classes** declare it — consistent with
  `ALokiPlayerState` and `ALokiPlayerState_HeroAffiliated` (INFERRED).
- `ServerSetHeroClass` exec `0x5438720` — its thunk contains no `FUNC_Net` dispatch, matching
  S102's falsification of the RPC-dispatch theory.

### A named candidate for `PlayerState+0x4F8`

`coverage-audit-s101.md:232` leaves open: *"the real gate: an embedded interface subobject at
`PlayerState+0x470` whose accessor (`0x56BA9E0`) reads `PlayerState+0x4F8`, measured live as
NULL"*, and §1.7 asks what writes it.

`near 0x08A26E28` gives the `ALokiPlayerState` UPROPERTY-name block in declaration order
(MEASURED):
```
Wallet · HeroAffiliatedObject · StatsObject · OnPlayerUIDataChanged · DropGems ·
PawnComponent · bNeedsInitialInventory · bNeedsInitialCharacterEffects
```
**INFERRED:** `+0x4F8` is the reflected UPROPERTY **`HeroAffiliatedObject`**. The accessor
returns `[that+0x3E8]`, which the audit already identified as the ASC offset on the
`LokiPlayerState_HeroAffiliated` CDO — so a field holding a `LokiPlayerState_HeroAffiliated*`
is exactly what `HeroAffiliatedObject` names.

**Why that is worth acting on:** it converts §1.7 from "find an unnamed offset's writer" into
"resolve a *named, reflected* property" — reachable with the existing
`tools/re/class_props.py` / `objprop_probe.py` by name, no new RE. It is a **hypothesis with
a cheap live check**: confirm `HeroAffiliatedObject`'s reflected offset == `0x4F8`. Do not
record it as fact until that check runs.

---

## 4. The deterministic 173–201 s crash — SOLVED (this is the single most valuable result)

`ignorance-map-s101.md:222` set the experiment: *"Take those 8 RVAs into
`dumps/merged.dump.exe` and disassemble. One session. The `+0x700` offset identifies the
field."* Done, in minutes, with `func`.

### The stack, identified by strings

Chain as recorded: `1153803 7555f4e 3c5dc52 3c5d255 3c34b22 3c596b3 39c7884 37f8b8c`
(innermost first — confirmed below by the arithmetic, not assumed).

| frame | entry | tier | identified by | confidence |
|---|---|---|---|---|
| `0x1153803` | `0x11536F0` | MED | `CrashHandlingTimeoutSecs`, `CrashReportClient` | **crash handler** — solid |
| `0x7555F4E` | `0x7553F40` | LOW | none; region `0x755xxxx` = packer trampolines | weak |
| **`0x3C5DC52`** | **`0x3C5DBC0`** | HIGH | see below | **the faulting PC** |
| `0x3C5D255` | `0x3C5CFC0` | HIGH | `FreeCam`, `FreeCam_Default`, `Fixed`, `ThirdPerson`, `FirstPerson` | **camera-mode code** — solid |
| `0x3C34B22` | `0x3C349A0` | HIGH | no strings | region only |
| `0x3C596B3` | `0x3C59650` | HIGH | no strings | region only |
| `0x39C7884` | `0x39C7509` | **LOW** | `TickInGamePerfTrackersRT`, `Media` | **weak — see caveat** |
| `0x37F8B8C` | `0x37F8820` | HIGH | `UGameEngine::Tick.ViewportClosed`, `Slow GT frame detected (GT frame %u…)`, `causeevent=`, `TickRenderingTimer` | **`UGameEngine::Tick`** — solid |

> **Caveat, stated because it nearly became a fifth false-known.** My first pass attributed
> `0x39C7884` to `0x39C6E70` (whose strings are `ConnectionFailed` / *"Your connection to the
> host has been lost."*) and I was one keystroke from writing "the crash is in the disconnect
> path". It is not: the query address lies **past that function's own extent bound**, so the
> attribution was invalid. Re-running with `--raw` gives a LOW-tier entry with unrelated
> strings. `0x39C7884` is **not identified**. Do not propagate a disconnect story from it.

### The faulting instruction — exact

```
03C5DBC0  <fn entry>   (rcx = this, rdx = out-param, xmm2 = float)
03C5DBC8  mov  rbx, rdx
03C5DBD0  mov  rdx, qword ptr [rdx]      ; obj = *(void**)Arg2
03C5DBD6  test rdx, rdx ; je <skip>      ; obj null-checked -- and it is NOT null
03C5DBF3  call 0x3317590                 ; fast path, returns bool in al
03C5DBFA  je   0x3c5dc45                 ; fast path failed -> virtual fallback
...
03C5DC45  mov  rcx, qword ptr [rbx]      ; rcx = obj
03C5DC4F  mov  rax, qword ptr [rcx]      ; rax = obj->vptr
03C5DC52  ff 90 00 07 00 00              ; call qword ptr [rax + 0x700]   <-- FAULT
```

**MEASURED and self-consistent:** the recorded faulting address is `0x700`; the displacement
in the faulting instruction is `0x700`; those are equal **only if `rax == 0`**. That also
confirms the frame ordering — `0x3C5DC52` is the faulting PC itself, not a return address
(a return address would be `0x3C5DC58`).

**So the crash is NOT a null-pointer field read.** The object pointer is non-null (it passed
the `test rdx,rdx` at `0x3C5DBD6`); its **vtable pointer is zero**. That is freed-and-zeroed
memory, or an object being destructed — a **use-after-free / use-during-destruction**, and it
is a *virtual dispatch through slot `0x700`* (index 224), not a field access.

**INFERRED identification of the function.** `0x3C5DBC0` writes its results as
`[rbx+0x10]` (xmmword), `[rbx+0x20]` (double), `[rbx+0x28]` (xmmword), `[rbx+0x38]` (double),
`[rbx+0x40]` (float) — the shape of `FMinimalViewInfo{Location, Rotation, FOV}`. Its only
inbound frame is the camera-style function `0x3C5CFC0`. Neither `0x3C5DBC0` nor `0x3C5CFC0`
has **any** direct `E8`/`E9` caller anywhere in `.text` (MEASURED, exhaustive scan) — they are
virtuals reached through vtables. Read together: `0x3C5DBC0` is
`APlayerCameraManager`'s view-target evaluation (`FTViewTarget` in, `FMinimalViewInfo` out),
`*(void**)Arg2` is `FTViewTarget.Target` (an `AActor*`), and vtable slot `0x700` is
`AActor::CalcCamera`.

**What this means.** The deterministic 173–201 s crash is a **stale `ViewTarget.Target`**:
the camera manager still holds a pointer to an actor whose memory has been freed/zeroed, and
the per-frame camera update virtual-calls through its dead vptr under `UGameEngine::Tick`.

That lands directly on this project's own code path. S93: *"camera FIXED to top-down (spawn a
`CameraActor` + re-assert the view target)"*. A force-spawned `CameraActor` that is later
destroyed or garbage-collected while still being the view target produces exactly this
instruction, exactly this fault address, on exactly this per-frame path — and it explains
*determinism* (GC runs on a timer) far better than any anti-tamper theory.

**Next moves this enables (offline work is done; these are live checks):**
1. Root the spawned `CameraActor` against GC (`AddToRoot` / hold a hard `UPROPERTY` ref) and
   re-run the tutorial past 201 s. Single variable, direct falsification.
2. Before that, confirm the actor identity live: read `PlayerCameraManager->ViewTarget.Target`
   each second and watch its first qword go to zero.
3. FK-7 should be **re-scoped**: it is not "an unlocated deterministic crash", it is a
   use-after-free on the view target. The *"~3–5 min integrity check"* (FK/§7) and this crash
   are **different phenomena** — this one has an ordinary UAF signature, as the audit itself
   suspected (*"an ordinary null-field deref, not the messy poison-jump anti-tamper signature"*).

---

## 5. The ~3–5 min `.text` integrity check — CLEAN NEGATIVE, and two false leads killed

**No string in this module names a `.text` integrity check.** MEASURED, both encodings:
`tamper`, `VMProtect`, `code has been modified`, `anti-cheat` → **zero** matches image-wide.

Two leads that look promising in a string list and are **not** the mechanism — worth
recording so nobody spends a session on them:

- **`integrity_check` (`0x08D586E0`) and `IntegrityCk` (`0x08D5A9E0`) are SQLite.** `near`
  shows their neighbours: `journal_mode`, `mmap_size`, `incremental_vacuum`, `index_xinfo`
  … and `ResetSorter`, `CreateBtree`, `ParseSchema`, `RowSetAdd`. These are SQLite pragma
  names and VDBE opcode names from a statically linked SQLite. Nothing to do with `.text`.
- **The EAC path is a shutdown handler, not a checker.** `ShowEACIntegrityViolationWidget`
  → exec `0x534BE80` → impl `0x5611090`, inside `0x5610CE0`, whose only string reference is
  `Starting shutdown for request exit: %s, %u` (MEASURED). It *reacts* to a verdict; it does
  not compute one. `IsEasyAntiCheatEnabled` exec `0x52FD980` (body undecrypted).
- `EACIntegrityViolationEventListener` (`0x08A13C38`) — 0 refs, no native pair; a delegate
  property.

The `xxHash`/`Zstd` hunt suggested by the audit also comes back empty as a *string* search:
the only `Zstd`-family literal is the four bytes `ZSTD` at `0x0925213C` (a magic constant, not
a code path), and there is no `xxhash` literal at all.

**Reading this honestly (INFERRED):** the absence of any naming string is itself evidence.
An in-module integrity checker written in C++ with logging would leave *something*; a checker
that leaves nothing is either (a) fully inside the packer's own obfuscated region — which is
not registered as a module and is therefore outside `.text` and outside this dump's section
coverage entirely — or (b) out of process (the EAC service/driver). Both are consistent with
S43's controlled A/B. String-xref **cannot** reach either; this question is not blocked by
`.text` decryption and more coverage will not help it. The statistical-modulo test on the 86
`SecondsSinceStart` values remains the right next probe.

---

## Summary table

| # | question | verdict | key address |
|---|---|---|---|
| 1 | loading-overlay wall | **partially answered + new lever** | `ClearMatchTransition` impl `0x588ED60`, exec `0x548F630` |
| 2 | `SpawnPlayer` returns null | **ANSWERED — the native body IS `return nullptr`** | `0x00F7EB50` (ICF `xor eax,eax; ret`) |
| 3 | GAS wiring | **confirmed offline; named candidate for the open field** | exec `0x5438C20` → `0x56CE5F0`; `HeroAffiliatedObject` |
| 4 | 173–201 s crash | **SOLVED — use-after-free on the camera view target** | faulting PC `0x3C5DC52`, `call [rax+0x700]`, `rax==0` |
| 5 | ~3–5 min integrity check | **clean negative; two false leads killed** | — |

## Reproduce

```powershell
cd "G:\git\Supervive Revival Project\tools\strxref"
python strxref.py native   "ClearMatchTransition"
python strxref.py native   "SpawnPlayer"
python strxref.py nattable 0x08A26AF8          # ALokiPlayerState, 133 UFUNCTIONs
python strxref.py func     0x3C5DC52           # the crash frame
python strxref.py func     0x37F8B8C --raw     # UGameEngine::Tick
python strxref.py near     0x08B1FCE0          # LokiGameMode.cpp literal block
```

## The standing coverage note

Every "undecrypted" result above (`PollForFeatureTogglesReady`, `FeatureTogglesReadyOrChanged`,
`TryUpdateAbilitySystem`'s body) is one dump away from being readable. `dumps/merged.dump.exe`
is effectively a single **menu-state** capture — its four extra inputs contributed ~1.2 KB.
`.text` is 52.29% readable by page; character/gamemode/ability code has simply never run.
Dump from inside the tutorial world, `mergedumps`, `--rebuild`. That is the one action that
raises the ceiling on all of this, and it is the same lever the ignorance map calls
*"state coverage IS binary coverage."*

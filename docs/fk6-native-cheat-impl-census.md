# FK-6 settled: the native cheat `_Implementation` census

> ## ⚠ SUPERSEDED AS THE VERDICT — S105, 2026-07-27 → **`docs/fk6-cheat-surface-settled.md`**
> This document and `docs/fk6-cheat-impl-census.csv` are **retained as data with a caveat**, not as
> the answer. An independent re-resolution (different rule, same dumps) isolated the one subset where
> the dispatch target is not a judgement call — thunks ending in an unambiguous tail-`jmp` out of the
> function. **13 such rows. This census agrees on 1 and is wrong on 12** (hand-verified that the tail
> targets are not further hops). Three of the 12 flip a `LokiPlayerCheats` verdict from REAL to empty:
> **`CheatTravelToMainMenu`, `LogActorsAtWorldOrigin`, `TryInitializeAfterController`** all share exec
> thunk `0x5254180`, whose entire body is `P_FINISH ; jmp 0xF7EC20` = `ret 0`. That moves the
> `owner=LokiPlayerCheats` REAL count **17 → 12** (with `AdminOnly`/`HotkeyCheatsEnabledOnly`
> reclassified as hardcoded exec-gates, `0x1F67DF0` = `mov byte [rdx],1; ret`).
>
> ⚠ **Do NOT extrapolate "92% wrong."** The 13 tail-jmp rows are the adjudicable subset; the ~160 rows
> resolved via `call rel32` are **not** invalidated, and the naive alternative rule is *worse* on them
> (it picks FString/TArray teardown calls). Correct statement: **per-row verdicts are PROVISIONAL
> until re-audited; the tail-jmp handling is measurably broken.** Fix that before citing a row.
>
> Also corrected here: `UCheatManager` is **39 REAL / 3 `ret 0` / 1 `mov al,1;ret`**, not "54 real,
> zero stubs" (that figure was a *thunk* census). `ViewClass`/`ViewActor`/`ViewPlayer` are
> UNVERIFIABLE, not real.

**Date** 2026-07-27 · **Method** offline only (no launch, no injection) ·
**Tool** `tools/re/cheat_impl_census.py` (new) · **CSV** regenerate with `--csv <path>`

The belief under test
(`memory/supervive-cheat-surface-inventory.md:135-148`):

> "★ DEFINITIVE CLOSE — THE CHEAT FUNCTION BODIES ARE COMPILED OUT OF SHIPPING
> (S74, disasm-verified)" … "the cheat surface as a shortcut to a playable hero is
> CLOSED" … "retroactively explains every no-op."

Evidence behind it: **two** disassembled bodies out of 65. This document replaces
that with **every** body the cold image can show.

---

## 0. Two counting corrections first

**"219 native entries, not 65" is wrong.** The S74 dump's `LokiPlayerCheats` block
is `[0] LokiPlayerCheats (65) + [1] Actor (153) + [2] Object (1)` — 219 is the
**inheritance chain**, not the class. `LokiPlayerCheats` declares exactly **65**
UFunctions; S74's 65 was right. (MEASURED, `docs/session-74-cheat-enum-dump.txt:237,369,677`.)

**The thunk census is not evidence either way**, and this was flagged in the brief
but is worth restating with the mechanism: an `exec` thunk unpacks `FFrame` params
and therefore always contains real code. `AreHotkeyCheatsEnabled`'s thunk is 43
bytes of real instructions; the impl it calls is `xor al,al; ret`.

---

## 1. New capability that made this measurable: the `.text` union

`.text` pages are **byte-identical across dumps taken at different ASLR bases** —
**0 conflicts** over every page present in ≥2 of the 10 dumps in `dumps/`,
including `dumps/rcb` (base `0x7FF79D3B0000` vs merged's `0x7FF6AF000000`).
That confirms strxref's "x64 here is 100% RIP-relative": nothing in `.text` is
relocated, so `mergedumps`' base-mismatch rejection is unnecessary **for `.text`**.

Unioning all 10 raises `.text` from **15,833 decrypted pages (52.29%)** to
**16,435 (54.27%)** — and decisively, it decrypts `AreHotkeyCheatsEnabled`'s thunk
page (`0x52FD000`), which `merged.dump.exe` alone does not have. `dumps/toggles`
alone contributed 539 new pages. The union is rebuilt in-process by the tool and
cached to `%TEMP%\supervive_union_text.bin`.

---

## 2. The resolution rule (and the trap that inverts it)

**A "rare callee" multiplicity filter gives the wrong answer.** MSVC `/OPT:ICF`
folds every byte-identical function in the image to one address, so a *stripped*
impl accumulates thousands of call sites while a *real* impl has one:

| address | body | image-wide call sites |
|---|---|---|
| `0x0F7EC20` | `C2 00 00` — `ret 0` (canonical empty `void f(...){}`) | **4,784** |
| `0x0F7EB60` | `32 C0 C3` — `xor al,al; ret` (canonical `return false`) | **192** |
| `0x0F7EB50` | `33 C0 C3` — `xor eax,eax; ret` (canonical `return nullptr`) | **58** |
| `0x0B9E1F0` | `B0 01 C3` — `mov al,1; ret` (canonical `return true`) | **81** |

Ranking by rarity discards exactly the stubs the question is about. The rule used
instead is structural — the **final dispatch** of the thunk, found by scanning
backwards past the epilogue and past guarded teardown calls
(`test rcx,rcx; je +N; call <dtor>`), resolving three encodings:

* rel32 `call`/tail-`jmp` → the impl directly;
* `mov rax,[this]; jmp qword [rax+disp]` → **vtable slot** (many `_Implementation`s
  are `virtual`), resolved against the class vtable from `tools/strxref/vtables.py`;
* `mov rax,[this]; mov rbx,[rax+disp]; … call rbx` → same, slot hoisted to a register.

**Validators** (228 non-script resolutions): 25.9% land on the independent
`P_FINISH` anchor; **63.6%** land *exactly* on a recovered `.pdata` function entry;
**86.0%** start with a plausible prologue byte. **Measured residual error: 19/272
(7.0%)** resolve onto a known `FFrame` helper — those are reported as `SUSPECT`,
never scored. All 19 are *inherited* `AActor`/`UActorComponent` functions
(dispatch on a **parameter's** vtable, not `this`); **none** is in the
`LokiPlayerCheats`-declared set, so the headline numbers are unaffected.

---

## 3. THE NUMBERS — `_Implementation` bodies, `LokiPlayerCheats`-declared (65)

| verdict | n | what it means |
|---|---:|---|
| REAL | **17** | a genuine body |
| TRIVIAL | 1 | real 17-byte body (`EnableForceDisplayCharacterName`) |
| SCRIPT | 3 | thunk **is** `ProcessInternal` — BP/Angelscript, no native impl exists |
| RET_STUB | **6** | `ret 0` — empty |
| FALSE_STUB | **2** | `xor al,al; ret` — unconditional `false` |
| ZERO_STUB | **5** | `xor eax,eax; ret` — unconditional `nullptr` |
| UNVERIFIABLE | **31** | thunk page never decrypted in **any** of the 10 dumps |

**Verifiable: 34 of 65 (52.3%).** Of those 34 — **18 have a body (52.9%)**,
**13 are stubs (38.2%)**, 3 are script. The 31 UNVERIFIABLE bound how strong any
conclusion can be; they are not scored either way.

### Stubbed (MEASURED, byte-exact)

| function | impl | body |
|---|---|---|
| `AreHotkeyCheatsEnabled` | `0x0F7EB60` | `xor al,al; ret` |
| `IsForceDisplayCharacterNameEnabled` | `0x0F7EB60` | `xor al,al; ret` |
| `CheatAddMissionProgress` | `0x0F7EC20` | `ret 0` |
| `CheatSetXP` | `0x0F7EC20` | `ret 0` |
| `CheatSetRankedPoints` | `0x0F7EC20` | `ret 0` |
| `CheatTeleportCursor` | `0x0F7EC20` | `ret 0` |
| `LogActorsInRadiusNear` | `0x0F7EC20` | `ret 0` |
| `ServerBoostPlayer` | vtable[+0x820] → `0x0F7EC20` | `ret 0` |
| `GetPlayerController` | `0x0F7EB50` | `xor eax,eax; ret` → **nullptr** |
| `GetHeroCharacter` | `0x0F7EB50` | **nullptr** |
| `GetPlayerState` | `0x0F7EB50` | **nullptr** |
| `GetAbilitySystemComponent` | `0x0F7EB50` | **nullptr** |
| `GetLocalLokiPlayerCheatsBP` | `0x0F7EB50` | **nullptr** |

Independent corroboration for the four getters: their **thunks are ICF-folded to a
single address** (`0x54071C0`), which is only possible if all four call the same
impl. Likewise `CheatSetXP`/`CheatSetRankedPoints` share thunk `0x52FD8F0`, and
`AreHotkeyCheatsEnabled`/`IsForceDisplayCharacterNameEnabled` share `0x52FD980`.

### Real (MEASURED)

`AdminOnly`, `HotkeyCheatsEnabledOnly`, `CheatAutoStrafe`, `CheatTravelToMainMenu`,
`EnableHotkeyCheats`, `EnableForceDisplayCharacterName`, `GetActorsByName`,
`GetObjectsByName`, `GetGameplayEffectsByName`, **`GetClientCursorLocation`**,
**`GetUnusedTeamIndex`**, `HeightMapVisualize{,HideAbyss,Radius}`, `Note`,
`TestErrorMessage`, `LogActorsAtWorldOrigin`, `TryInitializeAfterController`.

---

## 4. Three mechanisms this exposed that "bodies compiled out" does not capture

**(a) The Blueprint cheat gate is hard-wired to the hidden pin.**
`AdminOnly` and `HotkeyCheatsEnabledOnly` ICF-fold to one impl at `0x1F67DF0`:

```
mov byte ptr [rdx], 1 ; ret       ; *OutputExecs = 1
```

Enum values recovered from the reflection tables (MEASURED — the qword after each
name pointer): `EAdminOnlyExecPins{AdminOnly=0, Hidden=1}` and
`EHotKeyCheatsEnabledOnlyExecPins{HotKeyCheatsEnabledOnly=0, Hidden=1}`. Both
exec-pin gates therefore take **`Hidden`, unconditionally**. This is a *third*
measured stub beyond S74's two, and it is the one that closes the Blueprint route.

**(b) Setter real, getter stubbed — the hotkey close has a mechanism.**
`EnableHotkeyCheats_Implementation` (`0x55D39B0`) is real and writes
`[LokiPlayerCheats+0x390] = (Enabled != 0.0)`. `AreHotkeyCheatsEnabled_Implementation`
never reads `+0x390` — it is `xor al,al; ret`. Same pattern for
`EnableForceDisplayCharacterName` (writes `+0x392`) vs
`IsForceDisplayCharacterNameEnabled` (`xor al,al; ret`).
This *confirms* the FK-6 adjudication ("the native HOTKEY dispatch really is
closed") and explains it: the flag is still stored, nothing ever reads it.

**(c) The accessor layer is gutted, which matters more than the cheat bodies.**
`GetPlayerController`, `GetHeroCharacter`, `GetPlayerState`,
`GetAbilitySystemComponent` and the static entry `GetLocalLokiPlayerCheatsBP` all
return **nullptr**. `GetLocalLokiPlayerCheatsBP` is the entry point the memory file
named as the way in; it cannot hand back an instance. That is consistent with, and
supersedes, S96's "no live `LokiPlayerCheats` instance exists".

---

## 5. The 31 UNVERIFIABLE — how far the vtable takes them

`ALokiPlayerCheats`'s vtable is `0x08A1A690` with **266** slots; plain `AActor`'s
vtable (`0x07C2C7D8`, shared verbatim by dozens of no-new-virtual Actor subclasses)
has **247**. So slots **247–265 (19)** are class-introduced virtuals. Classifying
all 19 against the image (`.rdata` is readable, so this works even where `.text` is not):

```
[247] 0x55DF3E0  REAL       (same body Note's thunk calls)
[248] 0x55E4500  REAL
[249..261]       ret 0      x13
[262] 0x55D0230  REAL       mov [rcx+0x3B4],edx ; add rcx,0x3B8 ; jmp 0x3071C30
[263..265]       ret 0      x3
```

**16 of the 19 are `ret 0`.** `LokiPlayerCheats` declares exactly **19** Net
UFunctions (18 `Server*` + `ClientHypeUpdated`), matching 19 slots. Slot 262 is
identifiable as `ClientHypeUpdated_Implementation`: it stores an int at `+0x3B4`
then broadcasts the delegate at `+0x3B8`, and the Angelscript bind table's last two
`ALokiPlayerCheats` properties are `int LastHypeReceived` and
`FOnHypeUpdated OnHypeUpdated`.

* **MEASURED** — `ServerBoostPlayer`'s decrypted thunk tail-dispatches
  `jmp qword ptr [rax+0x820]` = slot 260 = `ret 0`. Its `_Implementation` is empty.
* **STRONG INFERENCE** — 19 RPCs ↔ 19 class-introduced slots, 16 of which are the
  empty stub ⇒ ~16 of the 18 `Server*` cheat RPCs (the `ServerCheatSpawn*` /
  `ServerCheatChangeHero` family) have empty implementations.
  **Which** 3 slots are the real ones is not determined offline, and the fact that
  slot 247 holds the body `Note`'s non-RPC thunk calls means the 19↔19 mapping is
  not proven. Do not upgrade this to MEASURED without a live read.

**Why those pages are undecrypted is itself informative**: `.text` decrypts on
execution, and no dump — including two taken in-match — ever ran them.

---

## 6. What is NOT closed

**`UCheatManager` (stock engine) ships almost entirely intact: 39 of 57 REAL**,
3 `ret 0`, 1 `mov al,1;ret`, 4 trivial, 2 SUSPECT, 3 unverifiable. Real bodies
include `God` (`0x35AFD70`), `Fly` (`0x35AB340`), `Ghost` (`0x35AFCB0`),
`Walk` (`0x35C64D0`), `Teleport` (`0x35C3E20`), **`Summon` (`0x35C2B00`)**,
`Slomo`, `DamageTarget`, `DestroyAllPawnsExceptTarget`, `PlayersOnly`,
`EnableDebugCamera`, `ViewSelf`, `SetWorldOrigin`. The build even keeps the
`…\Engine\Source\Runtime\Engine\Private\CheatManager.cpp` path string. `Summon` +
`Teleport` + `God` are exactly the spawn/immortality primitives the project wants.
Open question this leaves: whether a `UCheatManager` instance can be obtained
(`APlayerController::AddCheats`) — **not answered here**.

**`ULokiClientPlayerCheats`: 5 of 5 REAL** — `CheatFakeLobbyRewardFlow`,
`CheatLobbyAddBadge`, `CheatResetClientProfile`, `TestDeeplink`, `TestErrorMessage`.
Nothing stripped. (Menu/lobby surface, not gameplay.)

**The Angelscript cheat surface routes around every stub.** The decompiled
`ConsoleCommandCheatSpawnEnemyWisp` chain is
`GetClientCursorLocation()` → `+Z 500` → `GetUnusedTeamIndex()` →
`ServerSpawnWispAS(TeamIndex, Location)`. Cross-checked against this census:

* `GetClientCursorLocation` — **REAL**, 127-byte body (`0x55D5B50`);
* `GetUnusedTeamIndex` — **REAL**, 192-byte body (`0x55DB2A0`);
* `ServerSpawnWispAS` — **script bytecode**, an AS-declared `NetServer` RPC
  (`_Implementation` = 138 dwords / 81 instructions,
  `tools/asdump/out/modules/PlayerController/LokiPlayerCheats.as.txt:1148`).

It never touches `ServerCheatSpawnActor`, never touches the nullptr getters, and
never touches the hotkey gate. **Its only two native dependencies are both intact.**

---

## 7. Verdict on S74's generalisation

* **S74's two samples are CORRECT.** `AreHotkeyCheatsEnabled_Impl = xor al,al; ret`
  is re-confirmed here **independently and offline** at `0x0F7EB60`.
  `ServerCheatSpawnActor`'s thunk page is undecrypted in all 10 dumps, so S74's
  **live** read of it stands unchallenged — and is consistent with 16/19 of the
  class's RPC vtable slots being `ret 0`.
* **The generalisation from 2 → 65 → "the technique" was not warranted, and is
  wrong in three specific ways.** Of the 34 `LokiPlayerCheats` bodies that can be
  read, **18 (53%) are real, not stripped**. `UCheatManager` is 39/57 real —
  including `Summon`/`Teleport`/`God`. `ULokiClientPlayerCheats` is 5/5 real.
  "The cheat function bodies are compiled out of shipping" is false as stated.
* **But the specific conclusion it was used for survives, for a better reason.**
  The `LokiPlayerCheats` route to a hero is closed not because bodies were
  compiled out, but because (a) both Blueprint exec gates hard-return `Hidden`,
  (b) the readback of the hotkey flag is `false`, and (c) **every accessor that
  hands out a PlayerController / HeroCharacter / PlayerState / ASC — and the
  static instance getter — returns nullptr.** A cheat surface whose accessors
  return null is closed no matter how real its bodies are.
* **Corrected wording for the memory file:**
  *"`LokiPlayerCheats`'s ACCESSORS are nullptr stubs and both BP exec gates
  hard-return Hidden, so that class is not a route to a hero. Its bodies are
  mixed (18 real / 13 stub of 34 readable). `UCheatManager` is 39/57 real —
  unexamined. The Angelscript cheat surface is disjoint, has real bodies, and its
  spawn path's only native dependencies (`GetClientCursorLocation`,
  `GetUnusedTeamIndex`) are both intact."*

---

## 8. Live probes that would close what is left

1. **Pin the RPC vtable slots** (turns 16/19 STRONG_INFERENCE → MEASURED):
   with the game at a menu, RPM-read `ALokiPlayerCheats`'s vtable slots 247–265
   and disassemble each `Server*` thunk (live pages are decrypted on demand — the
   thunk decrypts as soon as you *execute* it, so instead read
   `UFunction.Func @ +0xE0` for each `Server*` UFunction and disassemble at that
   address). One-bit criterion: does the thunk's final dispatch land on `0x0F7EC20`?
2. **Is a `UCheatManager` obtainable?** Read
   `APlayerController::CheatManager` on the live LokiPlayerController. One bit:
   non-null. If yes, `Summon`/`Teleport`/`God` are callable through the existing
   `ProcessInternal` native-call primitive with no new technique.
3. **Is the console open?** (FK-13.) `DefaultInput.ini` has `+ConsoleKeys=Tilde`.
   If the console accepts input, every `ConsoleCommandCheat*` in the Angelscript
   module is reachable by typing, with no shim at all. One bit: does pressing
   `~` produce a console widget?

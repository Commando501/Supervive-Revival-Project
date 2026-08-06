> ## ⚠⚠ RETRACTION — THIS BANNER GOVERNS. Read it before anything below.
> **The ASC, the carrier and both attribute sets are the SHIM'S OWN creations, not the game's.**
> `EnsureHeroAffiliatedCarrier` (`tutorial_launch.cpp:4511`) **spawns** `LokiPlayerState_HeroAffiliated`
> with `SpawnActorCls`, its constructor builds the ASC, and the shim then calls `K2_InitStats` twice to
> make the two attribute sets. The census deltas I read as the game wiring the hero up —
> ASCs 424→425, initialised 344→345, companions 0→1 — are **our objects appearing**. The marker proves
> it: `[GAS] HeroAffiliatedObject@0x4F8 = 0x0` *before*, then `carrier=0x27617F91750` — the exact
> address the census reported as the ASC's owner.
>
> **What still stands, unchanged:** every measurement. The ASC exists with `OwnerActor` set,
> `SpawnedAttributes` **Num=2**, **`AvatarActor` NULL**, **`ActivatableAbilities` Num=0**; the pawn's
> `@0xF00/0xF08/0xF10` are a cache and the `[GAS]` verdict line that reads them is misleading (FK-30's
> real content); 344 initialised ASCs on scenery; and **no game-spawned hero or AI pawn exists** in the
> tutorial world, so the spawn-path hypothesis remains untestable and unsupported.
>
> **What is retracted:** the *attribution*. The correct headline is **"the shim's own S101 carrier route
> got further than its verdict line reported"** — NOT "the game gives the hero an ability system".
>
> **How I got it wrong, and it is the same error this very document lectures about:** I swept live
> objects and never asked *which of these did my own shim create*. §4 below congratulates the probe for
> catching two artifacts; it missed the third, in the same session, in the write-up itself. The question
> "is this a fact about the game or about my instrument?" has to include *"…or about my own shim?"*.
>
> **Follow-up measured 2026-08-05 (§7):** there is **no reflected function anywhere that binds the
> avatar**, and `TryUpdateAbilitySystem` — already called twice by the shim — is not it.

# S111 §1 — "the hero owns no ability system" is FALSE. The ASC exists, is populated, and is missing ONE field.
### ⚠ Title overstated — see the retraction banner. The ASC exists because WE built it.

**2026-08-05.** `docs/next-session-prompt-s111.md` §0 asked the cheapest question that could halve the
simulation problem: **do game-spawned pawns have an ASC, and does ours?** The answer inverts the
premise the route has carried since S94.

Instrument: `tools/re/asc_census.py` (new, read-only RPM, no injection) plus the existing
`tools/re/gas_recon.py`. Raw output in this document; no armed `play` window was needed — only
`gft_ready_fix` + `tutorial_launch_fo` to load the world, then `tutorial_launch_sp` for the contrast.

---

## 1. The finding

The force-open hero's ability system **exists and is two-thirds built**:

| | state |
|---|---|
| `LokiAbilitySystemComponent` object | **EXISTS** — `0x274BDE53400` |
| `OwnerActor` | **SET** — the `LokiPlayerState_HeroAffiliated` companion |
| **`AvatarActor`** | **NULL** ← *the gap* |
| `SpawnedAttributes` | **Num=2** — `LokiAttributeSet` + `LokiAttributeSetHealth` |
| `ActivatableAbilities` | **Num=0** ← *the other gap* |
| `DefaultStartingData` | Num=0 |

And the carrier is fully populated (`gas_recon` §G):

```
LokiPlayerState_HeroAffiliated 0x27617F91750
     AbilitySystemComponent  @0x03E8  0x274BDE53400 (LokiAbilitySystemComponent)
     AttributeSet            @0x03F0  0x27581318040 (LokiAttributeSet)
     AttributeSetHealth      @0x03F8  0x27613744780 (LokiAttributeSetHealth)
     PlayerInventory         @0x0408  0x27483E11F00 (LokiInventoryComponentComboItems)
```

**The delta against a working ability system is one field and one grant call.** Every scenery ASC in
the world has `OwnerActor == AvatarActor == the actor`. The hero's has `OwnerActor` set and
`AvatarActor` **null** — i.e. the second half of `InitAbilityActorInfo(owner, avatar)` never ran, so
the ASC is not bound to the pawn. Nothing has been granted, either.

⇒ **This is a bounded job, not "reconstruct the whole server-authoritative deploy".** And the whole API
needed is already reachable through the ProcessInternal native-call primitive as native thunks
(`gas_recon` §E): `BP_AuthGiveAbilityWithInputID`, `AuthGiveAbilityWithSourceObject`,
`TryActivateAbilityByInputID`, `K2_InitStats`, `GiveInstanceOfAbility`.

---

## 2. Why this was missed for so long — and it is the project's signature error

Both existing instruments read the **hero pawn's cache**, not the object:

```
[GAS] AFTER  AbilitySystemComponentStorage  @0xF00 = 0x0 (NULL)
[GAS] AFTER  AttributeSetStorage            @0xF08 = 0x0 (NULL)
[GAS] AFTER  AttributeSetHealthStorage      @0xF10 = 0x0 (NULL)
[GAS] ===== RESULT: initialised 0 -> 0  *** STILL NOT INITIALISED *** =====
```

`gas_recon.py` prints **"NO ASC on the hero"** from the same three reads and then skips its own sections
B/C/D. S100 had already written down that these are *a cache* — "the real owner is
`LokiPlayerState_HeroAffiliated`" — and the conclusion "the hero has no ASC" was drawn anyway, by two
different tools, and carried into `supervive-cheat-surface-inventory` ("the hero has no ASC, so cheats
gate nothing") and into the S111 brief.

**An instrument's blind spot recorded as a property of the game** —
`memory/supervive-instrument-artifact-pattern.md`, now 17+ instances. The fix that found it was not
cleverness: it was **sweeping objects nobody had a hypothesis about** (every ASC in the process,
grouped by owner) instead of reading the three fields we expected to be interesting.

---

## 3. The measurements, in order

All three sweeps are the same read-only probe on the same launch.

**A. Parked (no world loaded) — the baseline, and a near-miss.**

```
live objects=177353   pawn-like=1   ASC objects=36
   BP_MainMenuPawn_C  x1  (class has no AbilitySystemComponentStorage)
   live non-CDO ASC objects              : 36
   ...with OwnerActor or AvatarActor set : 0
VERDICT: dormant pool. Nothing in this world has ever run the init; we would be first.
```

⚠ **That verdict is WRONG, and only because the world was not loaded.** Had the session stopped here it
would have recorded "the ability system never runs in this game" as a fact. The world-loaded sweep
below contradicts it outright. *A negative from an empty world is not a negative.*

**B. Tutorial world loaded by the game (gft + fo only — no hero of ours):**

```
live objects=150961   pawn-like=2   ASC objects=424
   BP_LokiPregameSpectator_C x1 / BP_LokiSpectator_C x1   (neither has the property)
   ...with OwnerActor or AvatarActor set : 344
initialised ASCs by OWNER class:
   BP_Brush_C x199 · BP_PineTree_ScavBay_C x71 · BP_PineTree_Base_C x63 · BP_BrushTall_C x8
   BP_BK_WoodenWall_01_Destructible_C x1 · LokiUnownedCueExecutor x1 · BP_CapturePoint_Tutorial_C x1
```

**344 initialised ability systems.** The game runs GAS constantly here — for destructible scenery and
for at least one real gameplay actor (`BP_CapturePoint_Tutorial_C`). There are **no hero or AI pawns**
in the world at this stage, only spectators, so the "compare a game-spawned hero to ours" test cannot
be run — the game has not spawned one.

**C. After injecting `tutorial_launch_sp` (our hero appears):**

```
live objects=151377   pawn-like=3   ASC objects=425   PlayerState companions=1
   BP_HERO_Ronin_C  x1  @0xF00  non-null: 0/1
        0x274BE21D560 BP_HERO_Ronin_C   storage=NULL   <== OUR HERO
   ...with OwnerActor or AvatarActor set : 345
   ASCs owned by a HERO or a PlayerState: 1
      ASC 0x274BDE53400  owner 0x27617F91750 (LokiPlayerState_HeroAffiliated)
```

**The deltas are the whole story: ASCs 424→425, initialised 344→345, companions 0→1.** Spawning the
hero created an ability system and a carrier. The pawn's cache stayed null, which is the only thing the
old instruments looked at.

*(Cross-check: the probe resolved `AbilitySystemComponentStorage @0xF00` independently, matching the
shim's own `[GAS] … @0xF00`. Two instruments, same offset.)*

---

## 4. Instrument artifact caught **in this probe**, before it produced a wrong number

The first version tested `"Character" in name` over the class chain and reported
**"0 of 107 pawn-like actors have an ASC"**. The denominator was junk: UMG widgets
(`WBP_UI_CharacterNameplate_*`), components (`CharacterMovementComponent`,
`LokiCharacterSpringArmComponent`) and subsystems, all matched because *their own leaf names* contain
"Character". Exactly **two** of the 107 were real pawns.

A substring test on a leaf name is not an inheritance test. Fixed to exact-match an ancestor named
`Pawn` or `Character`; the same sweep then reported `pawn-like=1`. The comment is in the source so the
next person does not re-introduce it.

---

## 5. What to do next, cheapest first

1. **Set `AvatarActor` on the hero's ASC** and see whether `IsAbilitySystemInitialized` flips. The
   proper route is whatever the game calls — `LokiPlayerState::TryUpdateAbilitySystem` is native and
   parameterless (`tutorial_launch.cpp:4450`) and the shim already resolves it; the crude route is a
   direct write of `ASC+0x410`. **Try the native call first**, because it will also populate whatever
   else the real path does (including, plausibly, the three pawn-side caches).
2. **Grant one ability** with `BP_AuthGiveAbilityWithInputID` and fire it with
   `TryActivateAbilityByInputID`. Ability *content* is the open question — `gas_recon` §D found no
   ability classes assigned on the hero, so check `BP_HeroAsset_Ronin_C` (which the shim already
   resolves) for the ability list.
3. **Re-read `supervive-cheat-surface-inventory`'s FK-6 conclusion.** "The hero has no ASC, so cheats
   gate nothing" rests on the same false premise and should be re-graded.
4. ⚠ **Do not read the pawn's `@0xF00/0xF08/0xF10` as the ability-system state again.** They are a
   cache. `asc_census.py` reads the objects.

---

## 7. FOLLOW-UP — "call `TryUpdateAbilitySystem` to bind the avatar" is ALREADY DONE, and cannot work

Measured live, read-only, at a parked menu (`tools/re/class_funcs.py`).

**It is already called, twice.** `tutorial_launch.cpp:4624` (step 3) and `:4641` (step 3b, re-run after
forcing `Role = ROLE_Authority`), both after the carrier is installed and `ServerSetHeroClass` +
`OnRep_HeroClass` have run. The verdict every time is `initialised 0 -> 0`. The shim's own comment at
`:4505` already says why it cannot bootstrap: **"TryUpdate is update-not-create"**. Re-running it costs
an armed window and returns a known null.

**And nothing else reflected can do it either.** The full live UFunction enumeration:

| class | ability-related UFunctions |
|---|---|
| `LokiCharacter` | `AbilitySystemIsTargeting`, `AuthAddAbilityPoints`, `AuthRemoveAbilityPoint`, `GetAbilityLevel`, `GetAbilityPointsForLevelUp`, `GetKillCreditAbility`, `GetLokiAbilitySystem_BP`, `IsAbilityBlocked`, `IsAbilitySystemInitialized`, **`RemoveFromAbilitySystem`** |
| `LokiPlayerState` | `AuthAddAbilityPoints`, **`TryUpdateAbilitySystem`** (Native, not even BPCallable) |
| `LokiPlayerState_HeroAffiliated` | **zero UFunctions of its own** — a pure data carrier |

★ **There is a `RemoveFromAbilitySystem` and no `AddToAbilitySystem`.** The add/bind half is not
reflected at all — consistent with UE, where `InitAbilityActorInfo(Owner, Avatar)` is C++-only and is
called from `PossessedBy` / `OnRep_PlayerState`. The Angelscript bindings agree: they expose
`GetAvatarActorFromASC()` and **no setter**.

**Why a direct write of `AvatarActor` is not the shortcut it looks like.** `OwnerActor@0x408` and
`AvatarActor@0x410` *are* reflected UPROPERTYs, so writing one is mechanically easy — but the thing
abilities actually read is `FGameplayAbilityActorInfo` behind a `TSharedPtr`, and this probe confirmed
`AbilityActorInfo` is **not on the class chain** (not reflected). Writing the UPROPERTY alone would
produce a half-bound system that still fails wherever it matters. Do it only as a *diagnostic*, with
`IsAbilitySystemInitialized` and `GetLokiAbilitySystem_BP` as the two witnesses.

**The route, and it is OFFLINE.** Find the native implementation and call it raw through the existing
native-call machinery. Anchors measured this session (base `0x7FF6505C0000`):

```
RemoveFromAbilitySystem  exec thunk RVA  0x5302ED0     <- the paired Add is usually adjacent
TryUpdateAbilitySystem   exec thunk RVA  0x5438C20
```

Disassemble those thunks in `dumps/merged.dump.exe` to reach the real implementations, then look for
the sibling that calls `InitAbilityActorInfo`. `tools/re/offline_xref.py` / `disasm_live.py`, no game
time. ⚠ A raw call to a non-UFunction has no `FFrame` and no guards — it is a different and riskier
primitive than everything the shim does today; treat it as new work, not a variation.

---

## 8. THE `0x5302ED0` DISASSEMBLY — it cannot be read, and the "paired add" does not exist

§7 proposed `RemoveFromAbilitySystem`'s exec thunk (RVA `0x5302ED0`) as the anchor for finding a paired
`AddToAbilitySystem`. **Both halves of that plan are dead. I proposed it; it was wrong twice over.**

**1. The page never decrypts.** Verified three ways:
* `dumps/merged.dump.exe` → 48 bytes of **zeros** at `0x5302ED0` (and at the `TryUpdateAbilitySystem`
  implementation `0x56CE5F0` too);
* a **fully staged in-world process** — tutorial map loaded, hero spawned and possessed, GAS chain run
  (`[FOW] GAS step3: TryUpdateAbilitySystem (native) ok`) — live RPM at `0x5302ED0` **failed outright**:
  the page is not even committed;
* nothing in the build ever *calls* `RemoveFromAbilitySystem`, so the demand-decrypt never fires for it.

**2. The anchor was wrong in principle even if it had decrypted.** `0x5302ED0` is an **exec thunk**. UE
emits exec thunks in a generated, name-ordered block; they are not laid out beside the implementations
they call. "The paired Add is usually adjacent" is true of *implementations*, not of `exec*` stubs.

**3. And there is no paired add.** Direct search of the 169 MB in-world image:

```
AddToAbilitySystem         ascii=-          utf16=-      <-- does not exist, anywhere
InitAbilityActorInfo       ascii=-          utf16=-      (C++ method, no reflection name — expected)
RemoveFromAbilitySystem    ascii=0x88DFEA8               (reflection metadata)
TryUpdateAbilitySystem     ascii=0x8A2CBF0
AbilitySystemInitialized   ascii=0x8859E3A
```

`RemoveFromAbilitySystem` is reflected and has no reflected counterpart. **The Remove/Add symmetry I
assumed is not in this build.** Searching for it by name is closed.

### What the trip did yield

**`ALokiPlayerState::TryUpdateAbilitySystem` implementation @ `base+0x56CE5F0`** (reached through the
exec thunk's `P_FINISH` + tail-jump at `base+0x5438C20`), readable, and its shape confirms
*update-not-create* **from the binary** rather than from the shim's comment:

```
mov  rbp, rcx                       ; this (LokiPlayerState)
add  rcx, 0x470 ; mov rax,[rcx] ; call [rax+0x10]      ; virtual fetch of the current subject
mov  eax, [rdi+0xc] ; shr eax, 0x1e ; not al ; test al,1 ; je null   ; RF_Garbage validity check
mov  rax, [rbp+0x650]
cmp  rdi, rax
je   +0x56CE889                     ; ★ unchanged -> RETURN, having done nothing
```

★ **That `[rdi+0xc] >> 0x1e` is an independent confirmation of S110's `ObjectFlags@0x0C` calibration** —
the game's own code reads `EObjectFlags` bit 30 (`RF_Garbage`) at exactly that offset.

A sibling in the same translation unit, **`base+0x56CEDB0`**, called from `+0x56CE835`, repeats the
change-detect shape against `[rdi+0x658]` after two validity checks. That pair is the PlayerState-side
ability-system wiring and is the place to keep reading.

### ★ A 67.42% IN-WORLD IMAGE DUMP — `dumps/tutorial-hero/`

Captured from the staged state above with `usmapdump dumpimage`:

```
base     0x7FF6505C0000     coverage 120,094,720 / 178,130,944 (67.42%)
.text    53.2%      .rdata 100%      .data 100%      .pdata 100%
```

**This is the first genuinely non-menu capture state the project has ever taken** — FK-18's "cheapest
experiment", finally executed. ⚠ It **cannot** be merged into `dumps/merged.dump.exe`: different
ImageBase (`0x7FF6505C0000` vs `0x7FF6AF000000`), and `mergedumps` rejects mismatched bases by design.
It stands as its own image, and it is the right one for any ability-system or in-world question.

### Next, structurally rather than by name

The bind is whoever calls `InitAbilityActorInfo`. In the captured state the hero **is possessed**, so
`PossessedBy`'s page is decrypted: walk the hero's vtable to `APawn::PossessedBy`, read its calls, and
look for the ASC being handed `(PlayerState, Pawn)`. Entirely offline against `dumps/tutorial-hero/`.

---

## 9. THE `PossessedBy` WALK — the bind is NOT there. The pawn side is stock engine code.

§8's remaining route was: the hero is possessed in the captured state, so walk its vtable to
`PossessedBy` and find the ASC being handed `(PlayerState, Pawn)`. **Done, and it is a clean negative.**

### The chain, each hop measured

`PossessedBy` has no UFunction, no reflection name and no RTTI, so the only handle is the vtable slot.
Recovering the slot index without a reference build:

| step | result |
|---|---|
| `AController::Possess` exec thunk (from `class_funcs.py`) | `base+0x3702740` |
| its `P_FINISH` + tail call → implementation | `base+0x36E2B60` |
| inside it, the only deep-vtable call, with `rdx` still holding `InPawn` | `call [rax+0x868]` ⇒ **`OnPossess` = controller slot 269** |
| controller vtable (live) slot 269 | `base+0x569AB30` — a **Loki override**, `ALokiPlayerController::OnPossess` |
| its first call, `this`/pawn preserved ⇒ `Super::OnPossess` | `base+0x3C422A0` |
| inside `AController::OnPossess`, the deep-vtable call on the pawn | `call [rax+0x848]` ⇒ **`PossessedBy` = pawn slot 265** |
| **hero vtable** `base+0x89A6DA0`, slot 265 (`+0x848`) | **`base+0x353C310`** |

Two facts fell out of that walk for free, both corroborating existing project constants:
* `AController::Possess` reads its pawn at `[rcx+0x3F8]` — **exactly the `pawnOff` fallback
  `tutorial_launch.cpp` already hardcodes**;
* the pawn's own Controller sits at `+0x400`, and `UObject::ProcessEvent` is controller slot `+0x270`.

### The negative

`base+0x353C310` is **`ACharacter::PossessedBy` — engine code. `ALokiCharacter` does not override it.**
(Loki code lives at `0x5xxxxxx`; this is `0x35xxxxx`.) Its entire body:

```
call base+0x3BB1C00            ; Super = APawn::PossessedBy
cmp  qword [rbx+0x450], 0 ; je ret
test byte  [rbx+0x68], 0x10 ; je ret
cmp  byte  [rbx+0x72], 2  ; jne ret
call [rax+0x5b0]               ; a virtual on self
or   byte [rax+0xc29], 1       ; sets one bit and returns
```

And `APawn::PossessedBy` (`base+0x3BB1C00`) calls only `[rax+0x538]`, `[rax+0x738]`,
`base+0x1258BF0`, `0x33A4B30`, `0x3CA9890`, `0x3C917D0` — **every one of them engine-range. Not a
single Loki-range call in the whole `PossessedBy` chain.**

⇒ **The avatar bind does not happen on the pawn side in this build.** The stock UE pattern
(`PossessedBy` → `ASC->InitAbilityActorInfo(PS, this)`) is simply not what this game does — which is
consistent with the ASC living on a `LokiPlayerState_HeroAffiliated` companion rather than on the pawn
or its PlayerState. §7's reasoning-by-analogy-with-stock-UE was wrong about where to look.

### Where that leaves it

Back to the PlayerState side, with a narrowed target. `TryUpdateAbilitySystem` (`base+0x56CE5F0`)
makes exactly **three Loki-range calls** — `base+0x49361B0`, `base+0x5276450`, `base+0x4933B00` —
plus its same-TU sibling `base+0x56CEDB0`. Everything else it calls is an engine helper. Those four
are now the entire candidate set for the wiring, and all of them are readable in
`dumps/tutorial-hero/`. **That is an offline job with a four-item shortlist**, which is a much better
position than §7's "find a function whose name does not exist".

⚠ **Method note, and it cost a capture.** The first hero-vtable dump wrote nothing, because I piped it
through `Select-Object -First 6` — PowerShell tears down the upstream command, so the script died
before its final write. **That is the same trap recorded in §6 of the S110 write-up and in the S111
brief's trap list, hit again by its own author.** Use `| Out-Null` and read the file, or `-Last`.

---

## 10. THE FOUR CALLS — `TryUpdateAbilitySystem` is a change-detector that BROADCASTS. It never binds.

§9 left a four-item shortlist. All four are now disassembled, entirely offline against
`dumps/tutorial-hero/`, and they close the question of what `TryUpdateAbilitySystem` actually does.

| callee | what it is | how it is known |
|---|---|---|
| `base+0x5276450` | **lazy type-getter for `GameEvent_AbilitySystemChanged_PlayerState`** | the string is *in the function*: `lea r8,[rip+…]` → `wide="GameEvent_AbilitySystemChanged_P…"`, cached into a static at `0xA0160A8` |
| `base+0x4933B00` | **generic game-event broadcast helper** (takes the event struct by pointer, null-checks `[rdx]`/`[rdx+8]`, `movups xmm0,[rdx]`) | **27 call sites** across Loki code |
| `base+0x49361B0` | **the game-event bus / subsystem lookup** (global singleton at `0x9FB9A70`) | **52 call sites** |
| `base+0x56CEDB0` | same-TU sibling: another change-detect, on `[this+0x430]` vs `[this+0x658]`, ending in the same broadcast helper | reads/compares only; calls `0x4933B00` too |

★ **The decisive cross-reference: `base+0x5276450` has EXACTLY ONE call site in the entire image —
`+0x56CE860`, inside `TryUpdateAbilitySystem`.** So that function is the sole producer of the
`AbilitySystemChanged` event, and every Loki-range thing it does is *broadcasting*, not wiring.

### What `TryUpdateAbilitySystem` is, from the binary

```
fetch    virtual call on [this+0x470] slot +0x10        -> the current subject
validate RF_Garbage check at [subject+0x0C] bit 30
compare  mov rax,[this+0x650] ; cmp rdi,rax ; je RETURN  <- ★ unchanged => does NOTHING
otherwise: update the cache, build GameEvent_AbilitySystemChanged_PlayerState, broadcast it
```

It is a **change-detector plus an event broadcast**. It contains no bind, no `InitAbilityActorInfo`,
nothing that touches `AvatarActor`. "TryUpdate is update-not-create" — the comment at
`tutorial_launch.cpp:4505` — is now confirmed at instruction level, and it is *narrower* than that
comment implies: it does not even wire, it only announces.

### ★★ The mechanism hypothesis this produces, and it explains everything

The bind must live in a **listener** of `GameEvent_AbilitySystemChanged_PlayerState`. And the broadcast
only fires **when the cached value changes**.

The shim builds its carrier by hand — `SpawnActorCls` + `AddComponentByClass` + `K2_InitStats` — and
installs it with a **direct property write** to `PlayerState.HeroAffiliatedObject@0x4F8`. It never goes
through whatever normally assigns that, so when it then calls `TryUpdateAbilitySystem`, the
change-detector plausibly sees **no change** (or a null fetch), returns at the `je`, and **no event is
broadcast — so no listener ever runs, and nothing ever binds the avatar.** That is consistent with
every measurement in this document: ASC present, attribute sets present, `AvatarActor` null,
`ActivatableAbilities` 0, and `initialised 0 -> 0` on both call attempts.

### The next experiment, and it is cheap and read-only first

1. **Read `PlayerState+0x650` and the subject the virtual at `[this+0x470]`/`+0x10` returns**, before
   and after the shim's GAS chain. If they are equal — or the fetch is null — the early `je` is taken
   and the whole event path is dead. That is a `vtable_dump.py` + two RPM reads, no writes.
2. If confirmed, the fix is to make the fetch see a change: poke `+0x650` to something different (or
   null) *before* calling `TryUpdateAbilitySystem`, so the comparison fails, the event fires, and the
   real listener does the wiring the shim has been trying to hand-roll for three sessions.
3. Only if that fails does finding the listener matter — and it is findable: xref the event-bus
   registration rather than the type-getter.

⚠ Note the shape of the last three steps of this investigation: **`AddToAbilitySystem` (§8) and
`PossessedBy` (§9) were both guesses from stock-UE analogy, and both were wrong.** §10 is the first
step that came from reading what the binary actually does, and it produced a testable mechanism rather
than another name to search for. Prefer following the code over predicting it.

---

## 11. ★★★ CHAIN CLOSED — the gate is the hero's own `@0xF00`, and the fix is one 8-byte write

§10's hypothesis was **wrong, and the experiment that killed it handed over the real answer.** Both
values were read live, before and after the shim's GAS chain, read-only, in one run.

### The measurement

| field | BEFORE (world up, no GAS chain) | AFTER (GAS chain run) |
|---|---|---|
| `PS+0x650` cached subject | NULL | **`LokiAbilitySystemComponent`** |
| `PS+0x430` sibling gate | — | **`BP_HERO_Ronin_C`** (our hero) |
| `PS+0x658` sibling cache | NULL | **NULL** ← still |
| `PS+0x4F8` HeroAffiliatedObject | NULL | the carrier |
| hero `@0xF00` ASCStorage | — | **NULL** |
| `ASC.AvatarActor` | — | **NULL** |

**`+0x650` went NULL → ASC.** So the change-detector *did* see a change, did *not* take its early `je`,
and *did* broadcast `AbilitySystemChanged`. **§10's "no change ⇒ no broadcast ⇒ no bind" is falsified.**

### The two getters, and they are one-liners

Both `GetAbilitySystemComponent()` implementations, disassembled offline from `dumps/tutorial-hero/`:

```
PlayerState side   base+0x56BA9E0   (called with rcx = PS + 0x470)
    mov rax,[rcx+0x88]      ; PS+0x470+0x88 = PS+0x4F8  = HeroAffiliatedObject
    test rax,rax ; je ret_null
    mov rax,[rax+0x3E8]     ; carrier->AbilitySystemComponent
    ret

hero side          base+0x55A9610   (called with rcx = hero + 0x7F0)
    mov rax,[rcx+0x710]     ; hero+0x7F0+0x710 = hero+0xF00 = AbilitySystemComponentStorage
    ret
```

### ★ The complete causal chain, every link measured

1. The shim builds the carrier + ASC + 2 attribute sets and writes `PlayerState.HeroAffiliatedObject`. ✓
2. `TryUpdateAbilitySystem` → the **PlayerState-side** getter walks `HeroAffiliatedObject->ASC` and finds
   it → `+0x650` NULL→ASC → change detected → **the event is broadcast.** ✓
3. The sibling `base+0x56CEDB0` gates on `PS+0x430` — the hero pawn, **present** ✓ — and then calls the
   **hero-side** getter, which is `return hero->AbilitySystemComponentStorage@0xF00` → **NULL** →
   **it bails.** `+0x658` is never set, and `AvatarActor` is never bound. ✗

⇒ **`@0xF00` is not a symptom. It is the gate.** The field the shim and `gas_recon` have been reading
for four sessions and reporting as "not initialised" is the exact input the wiring tests, and because
the carrier was built by hand nothing ever populated it.

### The fix, and it is the same shape as the one that worked

**Write the carrier's ASC pointer into the hero's `AbilitySystemComponentStorage@0xF00`, then let the
chain run.** One 8-byte write to a **reflected UPROPERTY on an object the shim itself created** — the
same shape as `KANIMREF`, which is the one fix this project landed cleanly (§4e). After it, the
hero-side getter returns non-null, the sibling proceeds past its bail, and does the wiring the shim has
been trying to hand-roll.

Order matters: write `@0xF00` **after** `EnsureHeroAffiliatedCarrier` (so the ASC exists) and **before**
`TryUpdateAbilitySystem` (so the sibling sees it). In `tutorial_launch.cpp` that is between `:4575`
and `:4624`. Offsets to resolve by name, not hardcode: `AbilitySystemComponentStorage` on the hero,
`AbilitySystemComponent` on the carrier.

Registered prediction for that run: `IsAbilitySystemInitialized` flips to 1, `ASC.AvatarActor` becomes
the hero pawn, and `PS+0x658` stops being NULL. **`ActivatableAbilities` may well stay 0** — granting is
a separate step (`BP_AuthGiveAbilityWithInputID`), so a bind without abilities is a *success*, not a
partial failure.

⚠ Note what worked here, after two sessions of guessing: **§8 and §9 were analogies to stock UE and
both were wrong; §10 read the binary and got a mechanism but the wrong one; §11 tested §10's mechanism
read-only and the falsification itself pointed at the answer.** The cheap read-only test was worth more
than either guess, and it cost one staged run with no writes.

---

## 6. Reproducing

```powershell
# any state, read-only, no armed window needed
python tools\re\asc_census.py                       # auto pid/base
python tools\re\asc_census.py auto auto --hero <heroHex>   # marks our hero in the output
```

To get a loaded world without a full staging run: `forceTutorialMatch = true`, launch `-NoHook`, then
inject `gft_ready_fix.dll`, wait ≥20 s, inject `tutorial_launch_fo.dll`, and wait for
`Load map complete /Game/Loki/Maps/Tutorial/LVL_Tutorial`. Add `tutorial_launch_sp.dll` for our hero.
That is **three injections and no `play` build** — cheaper and more reliable than a full armed window,
and it is the right shape for any question about the world rather than about the hero's own loop.

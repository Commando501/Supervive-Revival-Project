# S111 §1 — "the hero owns no ability system" is FALSE. The ASC exists, is populated, and is missing ONE field.

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

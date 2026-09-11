# NEXT SESSION (S156) — Verify `0x4453EC0` first; that grounds the WALL P live-read recipe

**Paste-ready opener for a fresh Claude session:**

> Read `docs/next-session-prompt-s156.md` first. Execute §1 (verify `0x4453EC0`'s
> return type) as the first offline task, then hand back with the discriminator
> result. Do NOT launch the game or inject anything until the offline verification
> lands.

---

**One line:** S155 closed the S153 session by folding 16 new rules into
`docs/method-rules.md` (row total 131 → 136). The S154 state-tracker profile is
recorded but rests on a WEAK LINK — one workflow angle's assertion that
`0x4453EC0` returns a pawn (so `[+0x400]` is `APawn::Controller`). That's the
smallest, most load-bearing verification not yet done offline. Fifteen minutes
of disassembly either grounds the ALokiPlayerController class identification in
directly-measured evidence, or shifts it — which changes the WALL P live-read
recipe. **This is the last obvious offline lever before flying.** Reproducible
from commit `3cbf8aa` on `dedicated-server-stub` (14 S153-through-S155 commits
`1941246..3cbf8aa`, all pushed to origin).

## 0. What's new since `next-session-prompt-s154.md`

Read `docs/next-session-prompt-s154.md` for the full S153 session package
(session §0-§9 there). Two additions since it was written:

1. **S154 state-tracker profile** (`docs/wall-p-statetracker-class-s154.md`) —
   multi-agent workflow `wf_4b66ad0b-994` identified the WALL P state-tracker
   subobject as `ALokiPlayerController` [MEASURED via vtable RVA `0x8A1AEE0`],
   mapped its 8 state bytes to 4 phases + auth gate + latch + timing floats,
   and REFUTED `0x56A5370` as the delegate broadcast (it's a 2-D vector
   commit helper). **First same-session refutation of a workflow synthesis
   verdict in project history — the synthesizer initially picked
   `ULokiCharacterMovementComponent` from a LOW-confidence citation; CLAUDE.md's
   own `[pawn+0x400]=Controller` (S135/S136) settled it.** WALL P block
   relocates for the 4th time this arc, now to "downstream in the sibling
   handler tails".

2. **S155 method-rules consolidation** — 16 new rules (R-S153-a..k +
   R-S154-a..e) folded into `docs/method-rules.md`. 5 as new instrument-artifact
   rows (S153-a/b, S154-a/c/e); 3 as new "How to apply" items 16-18; 2 as new
   item 19 offline TECHNIQUES; 6 as subsystem findings in evidence docs.
   Row total 131 → 136.

## 1. First action — verify `0x4453EC0`'s return type

The WALL P state-tracker profile identifies the class as `ALokiPlayerController`
based on a chain that begins with:

```
BEGIN fn 0x5515C55:
    r14 = 0x4453EC0(rcx)        ; returns some object
    validate via 0x54F8DC0       ; interface cast (LokiHeroCharacter)
    r14 = [r14 + 0x400]          ; deref to subobject
```

The class identification depends on `0x4453EC0` returning a **pawn**
(specifically a `LokiHeroCharacter`, since gate 3 validates it as one), which
then makes `[+0x400]` the Controller per CLAUDE.md's S135/S136 finding.
**But `0x4453EC0`'s actual disassembly has not been read.** One workflow angle
cited it as `GetAvatarActorFromActorInfo` (which returns a pawn) but the
citation itself has never been ground-truthed against the bytes.

**If `0x4453EC0` returns something OTHER than a pawn** (e.g. the ASC, the
ability spec, or the source-object), `[+0x400]` is a different field entirely
and the class is not `ALokiPlayerController`. The whole live-read recipe would
shift.

### The task

Disassemble `0x4453EC0` (offline, `dumps/merged14.dump.exe`) and identify:

1. **Function bounds** from `tools/strxref/index/pdata_union.csv`
2. **Return-value type discipline:**
   - Does it start with `mov rax, [rcx+X]` — a simple field getter? If so, X
     tells you which field.
   - Does it read `rcx+0x18` / `rcx+0x28` — the FGameplayAbilityActorInfo
     shape? (AvatarActor is at `+0x28` or `+0x18` depending on UE version.)
   - Does it dispatch through a vtable? Which slot?
   - Does it call any known helper (`0x338C990` = validate/getter helper;
     others should be searched)?
3. **Cross-reference:** callers of `0x4453EC0` — rel32 scan of `.text` for
   `call/jmp` to that address. Are the callers ability-system-shaped
   (`ULokiAbilitySystemComponent`, `UGameplayAbility` derivatives)?

### Three possible outcomes (pre-registered)

| finding | verdict | next action |
|---|---|---|
| `0x4453EC0` reads `rcx+0x18` or `rcx+0x28` (AvatarActor from FGameplayAbilityActorInfo) — returns a pawn | **`ALokiPlayerController` class-id CONFIRMED [MEASURED]** | Proceed with the WALL P live-read recipe as written in `docs/wall-p-statetracker-class-s154.md` §"Updated live-read preregistration" and `docs/next-session-prompt-s154.md` §1. |
| `0x4453EC0` returns an `ASC` / `GameplayAbility` / other non-pawn object | **CLASS-ID SHIFTS** — `[+0x400]` is a different field | Re-run the offset-`+0x400` interpretation against the actual return type. The state-tracker byte offsets (`0xC0D`, etc.) are still real; only the enclosing class name changes. Re-derive R-S154-b if needed. |
| `0x4453EC0` is a virtual dispatch that could return multiple types depending on runtime state | **CLASS-ID CONDITIONAL** | Note that MiniDash's specific runtime state must resolve to a pawn; live confirmation moves from "sanity gate" to "primary test". |

### Tools needed (all offline)

- `dumps/merged14.dump.exe` (or `dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe`)
- `tools/strxref/index/pdata_union.csv` for function bounds
- `capstone` for disassembly (already available per S153 tooling)
- `tools/re/uht_funcflags_tuthero.csv` — search for functions whose params
  match a "returns AActor*" signature
- `tools/asdump/out/binds_members.csv` — if the reflected UFunction registry
  has a match

### Estimated time

~15 min. Single disassembly + rel32 scan.

## 2. Once #1 is confirmed — the WALL P live-read recipe

If §1 CONFIRMS `ALokiPlayerController`, execute the live-read recipe from
`docs/next-session-prompt-s154.md` §1 (which is already updated with the
concrete class name and vtable sanity gate).

If §1 SHIFTS the class, first update:
- `docs/wall-p-statetracker-class-s154.md`'s §"Class identification"
- `docs/next-session-prompt-s154.md` §1's target line
- CLAUDE.md's WALL P auto-fire mechanism paragraph
- The R-S154-b rule in `docs/method-rules.md` item 17

Then execute the live-read recipe against the corrected class.

## 3. Offline follow-ups if the game stays dead longer

Each ~15-30 min, ranked by yield:

1. **Handler tail disassembly** (offered/deferred 3 times in the S153/S154
   arc). The 4 sibling auto-fire handlers (`0x5679D50`, `0x5679DF7`,
   `0x5679E80`, `0x5679F2C`) each end shortly after their `call 0x56A5370`.
   Extending 20-50 B further would either find the `OnGameplaySpellEnded`
   delegate broadcast site (finalizing the WALL P layer chain), a fold
   tail-call (WALL P block localized to a specific instruction pair), or
   nothing (broadcast is deeper still). ~20 min.

2. **UHT `PropPointers[]` walk for `ALokiPlayerController`** — names the
   actual UPROPERTY fields backing the 8 state bytes. Uses S136 methodology
   (`docs/s136-ai-controller-settled.md` §7). Upgrades three STRONG_INFERs to
   MEASURED. ~30 min. Only worthwhile if §1 confirms `ALokiPlayerController`.

3. **`ULokiSpellSwapper` counter-check** — R-S153-a says the whole subsystem
   is gutted. Grep 596 GS blueprints for `SpellSwapper` references. If no
   shipping hero routes through it, R-S153-a is moot for gameplay (same
   methodology as R-S153-e's refutation). ~20 min.

## 4. Reproducibility sanity check

Before doing ANY of the above, verify:

```bash
git log --oneline 02da3f1..HEAD  # should show 14 commits, top: 3cbf8aa
git status --short               # non-S153/S154/S155 dirty files inherited
                                 # from pre-session; ok

python tools/sigbypass-mod/text_digest.py tools/sigbypass-mod/build/tutorial_launch_play.dll
  # RAW=9bc10a4552c596e1  (regression gate — MUST match)
python tools/sigbypass-mod/text_digest.py tools/sigbypass-mod/build/tutorial_launch_botai.dll
  # RAW=5e47c13cf7f0a158  (regression gate — MUST match)

# Re-derive the method-rules count:
grep -cE '^\| \*\*[^|]*S[0-9]+[A-Za-z0-9]*-[a-z]+\*\*' docs/method-rules.md
  # 136 (previously 131 as of S142; +5 from S155 consolidation)
```

If any gate value differs from these, DO NOT proceed — the source tree has
drifted and S153/S154 findings may not reproduce.

## 5. What NOT to do (S153-through-S155 derived cautions)

Inherited from `docs/next-session-prompt-s154.md` §7, plus:

- **Do NOT trust the S154 state-tracker profile's class identification as
  MEASURED** until §1 verifies `0x4453EC0`'s return type. The current
  `[MEASURED]` grade rests on two-signal convergence, but one signal (the
  chain evidence) has a WEAK LINK at `0x4453EC0` itself. Grade it STRONG_INFER
  in the interim.
- **Do NOT extend the S155 method-rules table with any new rules from this
  session's work** without re-running the row-count grep — S142 recorded a
  divergence where the tally was itself an instrument artifact (see S130-f
  and item 15 of "How to apply").
- **Do NOT launch the game** until §1 is complete. If §1 shifts the
  class-id, the live-read target changes, and a live session run against
  the wrong class produces uninterpretable results (like the pre-fix WALL P
  reads did).

## 6. Frontier state at S155 close

- **WALL P** — state-tracker CLASS identified as `ALokiPlayerController`
  [STRONG_INFER pending §1 verification], 4-phase state machine mapped,
  broadcast layer NOT `0x56A5370`, block localized to sibling handler tails
- **WALL E** — S148 shim source-fixed at S153 (`1941246`), rebuildable,
  unflown
- **Movement** — S141 T3 block is stock UE, architectural, not stub-driven
- **Drop chain** — S150-drop lands hero on ground, works
- **Mount/dismount** — S131/S132 recipes hold
- **Missions** — R-S153-b noted, backend passthrough not yet checked
- **FK-1 hunt** — offline SATURATED at 318 stripped stubs; further gains
  require live decrypt of DARK pages (see `docs/fk1-dark-pageclusters-s153.md`
  for fire targets)
- **Method-rules** — 136 tabulated instrument-artifact rows, 19 "How to
  apply" items (last three items 16-19 added S155)

Session-end commit: `3cbf8aa` on `dedicated-server-stub`, pushed to origin.

## 7. Recommended fly-order for a live session (once §1 confirms)

Same as `next-session-prompt-s154.md` §2:

1. **WALL P state-tracker read** (non-mutating RPM, no injection) — highest
   info-yield, lowest risk
2. **S148 rebuild + Move 4 WALL E Phase 1a** (mutating; unblocked by S153
   thunkExact fix)
3. **DLP drop-chain-in-one-injection** if bandwidth remains

The WALL P read is entirely non-mutating and can be combined with either
mutation arm in the same live session.

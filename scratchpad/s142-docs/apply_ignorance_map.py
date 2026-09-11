"""S142: bring docs/ignorance-map-s101.md back into lockstep (stale since S138).

Adds a top banner for the S139-S141 movement arc and FK-47 in the summary table's own
3-column blockquote convention (FK-44..46 live there, not in the register section).
"""
import io

p = 'docs/ignorance-map-s101.md'
s = io.open(p, encoding='utf-8').read()

if 'FK-47' in s:
    raise SystemExit('FK-47 already present - refusing to double-apply')

# ---------------------------------------------------------------- 1. banner
anchor_top = "# SUPERVIVE Revival — The Ignorance Map (S101, inverted audit)"
banner = """> ★★★ **S139–S141 (2026-08-23/24) — THE ENGINE MOVER CHAIN RUNS, AND AN AI-CONTROLLED HERO PAWN
> WALKS.** ⚠ **This map was last maintained at S138 and had ZERO coverage of that arc until S142;
> anything below written before it may be stale in the movement area — see FK-47.**
> **[M]** One 4-byte `GravityScale = 1.0f` write made the player hero fall **23,189 uu**; one
> `Velocity = (600,0,0)` kick made the AI pawn fall, land and **walk 13,196 uu at exactly
> 500.0 uu/s**, steered by its own AI, reproduced in a second sitting. So
> `TickComponent → ControlledCharacterMove → PerformMovement → StartNewPhysics → PhysFalling` all
> execute on this client. ⛔ **"`Velocity == 0` stops the mover" is DEAD; do not re-open it.**
> ⚠⚠ **AND THE INSTRUMENT THAT SAID OTHERWISE WAS INVALID:** `CMC+0x16C8` is not a latch — it reads
> `0` in every world (FK-47). **Any statement below that the physics step never runs is HISTORICAL
> and UNGRADED, not negative.**
> ⚠ **Do not upgrade this to "bots work".** It is an AI-controlled hero pawn that moves after
> artificial pokes; `ServerSetHeroClass` and `SetPlayerTeam` are still stripped folds.
> Start at `docs/next-session-prompt-s142.md`, then `docs/s141-tier3-settled.md` (§4 and §6 govern)
> and `docs/s140-tier1-cfg.md` (§4 and §5 govern).

"""
assert anchor_top in s, 'top anchor missing'
s = s.replace(anchor_top, banner + anchor_top, 1)

# ---------------------------------------------------------------- 2. FK-47 row
# Insert immediately after the FK-46 row, matching the summary table convention.
lines = s.split('\n')
idx = next(i for i, l in enumerate(lines) if l.startswith('> | **FK-46**'))

body = (
 '✅ **NEW + SIX FALSIFIED, and one of them was the founding premise of three sessions.** '
 '**(a) `CMC+0x16C8` IS NOT A STICKY LATCH** — the belief that `latch == 0` proves '
 '`ULokiCMC::StartNewPhysics` never ran. `ULokiCMC` vtable disp `0xA50` = **`0x0530ABF0`** '
 '(`80b9c816000000 / 7407 / c681c816000000 / e98bbb2cfe`) **clears** it, and engine '
 '`PerformMovement` calls that slot at **`0x035EB569`** with `rcx = this` — later in the same call, '
 'on a path the `StartNewPhysics` call site **DOMINATES**. ⇒ it reads `0` whether the step runs every '
 'frame or never. **Named from its own consumer:** `.data 0x09BC9AD0 = {"GetRecentVelocity", '
 '0x0530C7E0, 0x0530AC10}` → `cmp byte [rcx+0x16c8],0 / mov eax,0x16b0 / mov r8d,0xe8 / '
 'cmove eax,r8d` = a per-frame `TOptional<FVector>` validity flag over the `+0x16B0` Velocity '
 'snapshot. Derived independently **three times in one session**. ⚠ **The MEASUREMENT was correct** '
 '(it really did read 0 on all 37 components); only the **inference** is dead, and everything resting '
 'on it is **UNGRADED, not negative**. ★ Root cause (`S140T1-a`): **the field was named from the site '
 'that SETS it and nobody enumerated the sites that CLEAR it.** ★★ A free coherence check was '
 'skipped — 37/37 zeros means *nothing in the world can move at all*. ★★★ **The doc\'s own '
 'pre-registration caught it and was overridden**: `docs/s139-f1-BOT.txt` prints '
 '`THE BISECTOR IS UNINTERPRETABLE THIS SITTING` **34 lines below** the number that became '
 '`[M] banked` (`S140T1-g`). '
 '**(b) "the player does not fall" — IT WAS OURS.** `sp`\'s LIFT-TO-SEE step '
 '(`tutorial_launch.cpp:12877-12890`) sets `GravityScale = 0`, and **`CMC+0x1A0` IS `GravityScale`** '
 '(engine `GetGravityZ 0x035E3680 mulss xmm0,[rbx+0x1a0]`, three instruments). '
 '`docs/s138-flight9-movement-not-simulating.md:17` had recorded **BOT 1.000 / PLAYER 0.000 the day '
 'before**. S132\'s dismount is explained too — it was a `GravityScale` **restore**, which is why that '
 'hero fell with X and Y frozen. '
 '**(c) "`Velocity == 0` is a fixed point that stops the mover" — DEAD.** The player fell from '
 '`Velocity.Z` exactly zero. The real gate is **2-D**: `PhysFalling`\'s `SizeSq2D` clamp zeroes only '
 'the gravity-space horizontal components (the store at `0x035ED9AC` is `movups` — 16 bytes over a '
 '24-byte `FVector` of doubles), and gravity integrates **before** it every iteration. '
 '**(d) "a seventh exit may hide in engine `PerformMovement`" — REFUTED.** Four independently written '
 'CFGs: **1461 instructions, 0 indirect jumps, 0 decode failures, 0 coverage gaps (6538/6538 bytes), '
 '2 backward edges and NEITHER able to reach the call.** Five of the six exits **dominate** the call. '
 '⚠ But **`CMC+0xC0 WorldPrivate` has never been read live** despite three docs implying it was — '
 'grade that exit **[I, strong]**. '
 '**(e) the S139 "next step" ranking — REFUTED IN BOTH ITEMS.** Loki `PerformMovement` reaches its '
 'Super **unconditionally** (142/322 reach `0x055B85C1`, zero edges leave the set), and both flagged '
 'branches target `0x055B85B4` — **13 bytes BEFORE the Super call** — so they skip a **loop**. And '
 '`IsSimulatingPhysics()` **had** been read. ⚠ The handoff said "three gates"; it is **five mandatory '
 'plus a non-mandatory sixth** — the settled docs were right and the compressed digest line was stale. '
 '**(f) "pin `LogCharacterMovement` for a per-frame line" — FALSE.** All three reachable sites are on '
 'arms that do not execute here. ★ But the `FLogCategory` is at **`.data 0x9F85E68`** (two agreeing '
 'derivations) ⇒ **one RPM byte says whether a category is suppressed without it having to emit.** '
 '⚠⚠ **New instrument blindness:** capstone 5.0.7 reports `movups` **stores as READS** via '
 '`regs_access` (29/29 wrong in one function, hiding 16 CMC-field stores incl. the recommended '
 'receipt `0x055C244F`) — classify from `operands[0].type == MEM`; `pdata_union.csv` has **no row at '
 'all** for `0x055C2430` ⇒ union a pdata sweep with a **vtable** sweep; and a rip-relative `lea` scan '
 '**cannot see UE log strings** (they are reached through a 32-byte record struct) — **a positive '
 'control validates the MECHANISM IT EXERCISES, not the question you are asking** (`S140T1-b/c/d`). '
 '⇒ **STILL OPEN: the wall MOVED, it did not close.** The AI pawn is the only thing that does not '
 'move **and it is the pawn that HAS INPUT** — a **Z-only** kick leaves `Velocity (0,0,0)` and 0.000 '
 'uu, a **horizontal** kick walks it 13,196 uu. The discriminator is the **kick axis**. ⚠ **Not a '
 'bot:** `ServerSetHeroClass` / `SetPlayerTeam` are still stripped folds and every capability here '
 'rests on pokes the game never performs itself. '
 '`docs/s140-tier1-cfg.md`, `docs/s140-tier2-sentinel.md`, `docs/s140-t2-armj-THE-BOT-WALKS.md`, '
 '`docs/s141-tier3-settled.md`, `docs/s141-t3-arml-result.md`, `docs/next-session-prompt-s142.md`'
)
row = ('> | **FK-47** — S139–S141 movement-arc false-knowns (batched) | **S140–S141** | ' + body + ' |')
assert row.count('|') == 4 + body.count('|'), 'pipe accounting'
assert '|' not in body, 'unescaped pipe in body'
lines.insert(idx + 1, row)
s = '\n'.join(lines)

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('ignorance map: top banner + FK-47 summary row added')

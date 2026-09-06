import sys
NL = "\n"
p = 'CLAUDE.md'
s = open(p, encoding='utf-8', newline='').read()
CRLF = "\r\n" if "\r\n" in s[:4000] else "\n"


def rep(old, new, label):
    global s
    n = s.count(old)
    if n != 1:
        print("!! %s: count=%d -- NOT APPLIED" % (label, n)); return False
    s = s.replace(old, new, 1); print("ok: %s" % label); return True


def J(lines):
    return CRLF.join(lines)


# ---------------- 1. the primary retraction -> the measured opposite ----------------
old1 = J([
'  ⚠⚠⚠ **THE SECOND HALF OF THAT HEADLINE IS RETRACTED (S140) — "`StartNewPhysics` NEVER RUNS" was',
'  never measured; its sole support was the `+0x16C8` latch, which is invalid (see below and',
'  `docs/s140-tier1-cfg.md`). It is now UNGRADED, not `[M]`.** The DeltaTime half stands.',
])
new1 = J([
'  ⚠⚠⚠ **THE SECOND HALF OF THAT HEADLINE IS REFUTED, NOT MERELY RETRACTED — AND THE TRUTH IS THE',
'  OPPOSITE. `ULokiCMC::StartNewPhysics 0x055C2430` RUNS, on the bot AND the player, essentially',
'  every frame [M, S140 TIER 2]. Read `docs/s140-tier2-sentinel.md`.** S140 Tier 1 showed the',
'  `+0x16C8` latch is an invalid instrument (it reads 0 in every world), which made "never runs"',
'  UNGRADED; Tier 2 then MEASURED the answer with a **pre-poisoned payload**. The DeltaTime half',
'  stands and is now joined by the physics-step half.',
])
rep(old1, new1, '1. primary retraction -> refutation')

# ---------------- 2. the "residual" line ----------------
old2 = J([
'  from instruments unrelated to `+0x16C8`. **"A zero `Acceleration` does not stop GRAVITY" still',
'  stands, and the input wall and the movement wall are still two problems.** ⚠ But "fly the port and',
'  read the latch in the same pass" is now **the wrong experiment** — the latch would read 0 either',
'  way. Use the sentinel test below.',
])
new2 = J([
'  from instruments unrelated to `+0x16C8`. **"A zero `Acceleration` does not stop GRAVITY" still',
'  stands, and the input wall and the movement wall are still two problems.** ⚠ But "fly the port and',
'  read the latch in the same pass" is now **the wrong experiment** — the latch would read 0 either',
'  way. Use the sentinel test below.',
'  ★★★★★ **AND S140 TIER 2 SETTLED IT: THE PHENOMENON SURVIVES BUT ITS CAUSE IS NAMED. `Velocity` is',
'  not merely never written — it is ACTIVELY COMPUTED AND WRITTEN TO ZERO EVERY FRAME [M].** Flight 2',
'  re-wrote a `Velocity` sentinel every ~2 ms for 400 iterations: the payload at `+0x16B0` held the',
'  sentinel **396/400** (`hitPoison=0`, `hitOther=0`), and `Velocity` had lost it by read time in',
'  **36 of 400** 2 ms windows — exactly the windows a physics step landed in.',
])
rep(old2, new2, '2. residual line -> velocity is actively zeroed')

# ---------------- 3. the NEXT(S141) block -> DONE + the new next ----------------
old3 = J([
"  ★ **NEXT (S141), and it is one experiment:** **THE VELOCITY-SENTINEL TEST.** Write a small",
'  distinctive sentinel (e.g. `(0.0009765625, 0, 0)` — exactly representable, negligible speed) into',
'  `Velocity @CMC+0xE8/F0/F8`, wait ≥3 frames, then read `CMC+0x16B0..+0x16C7` and re-read `+0xE8` as',
"  the probe's own control. **Sentinel present in the payload ⇒ `ULokiCMC::StartNewPhysics` ran with",
'  `Iterations == 0` [M]. Payload still `(0,0,0)` while `+0xE8` holds the sentinel ⇒ it did not [M].**',
'  The payload is durable (disp `0xA50` clears only the flag byte; the only CMC-side writer of',
'  `+0x16B0` is `0x055C244F` inside `StartNewPhysics`). ⚠ Do NOT use a large sentinel — it perturbs',
'  the system under test. ⚠ It needs an external `WriteProcessMemory`, a repo-recorded **unresolved',
'  hazard** (n=1, confounded); pair it with a matched no-write sitting.',
])
new3 = J([
'  ★★★★★ **DONE AT S140 TIER 2 — AND THE HANDOFF’S RECIPE WOULD HAVE RETURNED A FALSE NEGATIVE.',
'  Read `docs/s140-tier2-sentinel.md`; its §3 and §5 govern.** Two staged clients, two injections.',
'  **[M] `ULokiCMC::StartNewPhysics 0x055C2430` RUNS on both components, essentially every frame.**',
'  ⚠⚠ **THE SENTINEL-ONLY DESIGN IS DEGENERATE and Tier 1 §7 says so** — with `Velocity` resting at',
'  `(0,0,0)` and `NewObject` zero-filling, "snapshotted a zero" and "never written" are THE SAME',
'  BYTES, which is why S139 already banked `R1.velsnap@0x16B0 (0.000,0.000,0.000)` and it means',
'  NOTHING. **The fix is to PRE-POISON the payload** with a distinctive value first: that breaks the',
'  degeneracy WITHOUT touching `Velocity`, and the poison is provably unreachable by any consumer',
'  (its only reader `GetRecentVelocity` returns it solely when the flag at `+0x16C8` is non-zero, and',
'  the only writer of `flag=1` overwrites the payload `0x1A` bytes earlier in the same block).',
'  MEASURED: both poisons overwritten within **250 ms**, on the bot AND on a **velocity-write-free**',
'  player arm; neither payload ever held the other object’s poison (a two-sided addressing control',
'  that could have failed). Flight 2’s 2 ms burst then caught the payload holding a `Velocity`',
'  sentinel **396/400**, refuting the one alternative (a non-`StartNewPhysics` writer of `+0x16B0`).',
'  ⚠⚠⚠ **AND IT NEEDED NO EXTERNAL `WriteProcessMemory`** — the write is in-process on the game',
'  thread, which sidesteps that hazard entirely. **But the READ CANNOT HAPPEN IN THE ARM: [M]',
'  `BsLadderStep` runs ON THE GAME THREAD inside `OnPI`, so every `Sleep()` in it BLOCKS THE GAME',
'  THREAD AND NO FRAMES PASS.** A write-Sleep-read there is *guaranteed* to read the un-updated',
'  payload and would have been written up as "StartNewPhysics does not run". ★ Sample on the',
'  **existing Worker thread between `FsDisarm()` and `BsFinalReport()`** (the `RM_DROPPLANE` B4',
'  precedent) — no `CreateThread`, and `[BS] done` stays last in the marker.',
'  ⚠⚠ **A worker thread spawned INSIDE the arm also fails**: the ladder holds the game thread for a',
'  further ~4.4-5.2 s after `BsPsExperiment()` returns (trailing `Sleep(750)` + the A2 census).',
'  ⚠⚠ **AND THE `[M]` THAT MOTIVATED ALL OF THIS IS AN INSTRUMENT ARTIFACT:**',
'  `tutorial_launch.cpp:15883`’s *"one hit is all this world state delivers (hitsGT=1)"* is',
'  self-inflicted — `OnPI` increments `g_hitsGT` AFTER its `if(g_done||g_inHook) return;`, so a',
'  one-shot ladder can never report more than 1 whatever the dispatch rate. Control:',
'  `docs/fk24-s128-poolspawn-RESULT.txt`, identical `KFSNAME=""` and identical `swapped=17563` but a',
'  PACED ladder — **`hitsGT=588`, ~73 dispatches/s.**',
'  ★★ **THE THREE FREE READS ARE ALL TAKEN, and reproduce across two clients [M]:**',
'  **`CMC+0xC0 WorldPrivate` is NON-NULL and names `LVL_Tutorial`** ⇒ engine `PerformMovement` exit 2',
'  moves **[I,strong] → [M]**; **`CMC+0x3E4 MaxSimulationIterations = 1`** (>0, so the fourth engine-',
'  `StartNewPhysics` early-out at `0x036009B5` does NOT bail) and **`CMC+0x3E0 MaxSimulationTimeStep',
'  = 0.2`** — ⚠ **NEITHER is the stock UE default (8 and 0.05); both are overridden in this build**,',
'  and a one-iteration substep budget is a real constraint recorded nowhere else; and the live',
'  **vptr == `base+0x088F8570`** on both ⇒ it really is a `ULokiCMC`, so disp `0x720` really is',
'  `0x055C2430`. ⚠ Had it been the engine base, disp `0x720` is `0x03600990` and nothing touches',
'  `+0x16C8`/`+0x16B0` — the whole test would have been void; the probe checks for exactly that.',
'  ★★★★★ **⇒ THE WALL IS NOW DOWNSTREAM, IN `CalcVelocity`, AND AN OFFLINE LANE FOUND THE MECHANISM',
'  — ONE COMPARE [I, strong]:** `0x035D64F2 comisd` against **`1.0e-4`** (`.rdata 0x076B49E8`);',
'  below it, `0x035D6520 movups [rbx+0xe8], ZeroVector` + `0x035D6527 movsd [rbx+0xf8]` write',
'  **`Velocity := (0,0,0)` every frame whatever `Acceleration` is** — including immediately after the',
'  `Velocity += Acceleration*DeltaTime` store two instructions earlier. The tested quantity is',
'  `MaxInputSpeed = max(GetMaxSpeed() * AnalogInputModifier, GetMinAnalogSpeed())`, and:',
'  • **`AnalogInputModifier @CMC+0x3D0` reads 1 on the ARM-G-treated bot** (0 on the untreated',
'    player; it was **0** on both in S139 flight 1, i.e. BEFORE ARM G) ⇒ **it is NOT the zero** [M].',
'  • **`GetMaxSpeed()`** (vt disp `0x4C8` → `0x055ACB90`) is **GAS-backed** — it tail-jumps to',
'    `[Owner_vt+0xC00]`, which returns `0.0f` when `Character+0xF08 AttributeSetStorage == NULL`',
'    (`0x055ACB73 xorps xmm0,xmm0; ret`). **NEVER READ LIVE.**',
'  • **`GetMinAnalogSpeed()`** (vt disp `0x7C8` → `0x035E3D20`, **not overridden**) returns',
'    **`MinAnalogWalkSpeed @CMC+0x290`** for `MovementMode ∈ {1,2,3}` — and both pawns are',
'    **`MOVE_Falling(3)`, which is in that set**. **NEVER READ LIVE.**',
'  ⚠ **NOT OBTAINED: `CMC+0x290` was never read** — the probe was written and the client died (FK-32)',
'  before it ran. It is now wired into `tools/re/cmc_earlyout_readout.py`, so **S141’s first move is',
'  ONE READ-ONLY RPM RUN against a staged client, with NO injection at all.** The probe prints the',
'  disjunction rather than a verdict: **`MinAnalogWalkSpeed >= 1e-4` ⇒ the `max()` cannot fall below',
'  `1e-4`, so this clamp is NOT what zeroes `Velocity` and the lane’s headline is REFUTED;',
'  `< 1e-4` ⇒ the whole question reduces to what `GetMaxSpeed()` returns on a treated bot.**',
'  ⚠ **Both S140 T2 clients died of FK-32** (`0x0000DEAD`, no artifact) at **T+350.5 s** and',
'  **T+318.0 s**, both on the **4th** manual-map. The `0xDEAD` series is now **7 / 6 / 4 / 4 / 4**',
'  injections at 1144 / 334 / 350 / 318 s — **still no dose-response**, but 4 is now the modal count.',
'  ★ Nothing was lost to either death: every result was captured as produced. **Capture as you go.**',
'  **Arms** (RAW): `gasattr-sentinel` **`ce56fd715de835a1`** (flight 1) · `sentinel-burst`',
'  **`62b5423febd6f779`** (flight 2) · `sentinel-nogas` `f62d3a9cc4cf0562` (built, unflown).',
'  Regression gates `botai 5e47c13cf7f0a158`, `gasattr 2fcc2536e21f18e3`, `gasattr-ctrl',
'  4465ebc4d7168c03` **all reproduce EXACTLY** from the edited source.',
'  ⚠⚠ **`driverecompute a2a952babfed256b` IS NOT A VALID GATE.** `build.ps1` gives `driverecompute`',
'  `-DKBSPSARMS=0xA0` and `gasattr-ctrl` `-DKBSPSARMS=0x0A0` — the SAME VALUE — so from one source',
'  state they must be byte-identical, and today both build to `4465ebc4d7168c03`. The archived DLL',
'  has a different `.text` SIZE (134,144 vs 134,656) ⇒ it predates a source change and was never',
'  rebuilt. `text_digest.py --dupes` independently flags the pair as a HAZARD. Same pattern as',
'  `botspawn_readonly`.',
'  ⚠⚠ **AND AN `#else` "ARM H skipped" MARKER LINE MOVED `gasattr` `2fcc2536e21f18e3` →',
'  `6d81e34e675f97f1` WHILE LEAVING ITS `.text` SIZE AT 137,728 BYTES** — the repo’s own "diff the',
'  hash, never the size" rule demonstrating itself. **A skip message compiled into the CONTROL builds',
'  is not free.** Put arm code behind a PREPROCESSOR `#if`, with no `#else`.',
'  ⚠⚠ **`cmc_earlyout_readout.py`’s `RANK-1 VERDICT` block printed the RETRACTED latch inference**',
'  and would have handed a successor a confident wrong answer. **Fixed** — it now prints the',
'  retraction plus a payload recogniser, raw hex of both 24-byte ranges, and the free reads.',
])
rep(old3, new3, '3. NEXT(S141) -> DONE + the new next')

open(p, 'w', encoding='utf-8', newline='').write(s)
print("written")

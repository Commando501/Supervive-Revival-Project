NL = "\n"

# ---------------- CLAUDE.md ----------------
p = 'CLAUDE.md'
s = open(p, encoding='utf-8', newline='').read()
CRLF = "\r\n" if "\r\n" in s[:4000] else "\n"

anchor = '  ★★★★★ **⇒ THE WALL IS NOW DOWNSTREAM.**'
i = s.find(anchor)
assert i > 0, 'anchor'

block = CRLF.join([
'  ★★★★★★ **S140 TIER 2 FLIGHT 3 — THE BOT FALLS, LANDS AND WALKS. READ',
'  `docs/s140-t2-armj-THE-BOT-WALKS.md` BEFORE ANYTHING ELSE ON THIS SURFACE.**',
'  **[M] ONE write of `Velocity = (600,0,0)` — once, never re-written — and the AI-controlled hero',
'  fell at terminal velocity (`Velocity.Z` pinned `-4000`, `Z 13240 → 3349 → 1349`), LANDED on the',
'  tutorial floor at `Z = 90.150` (the exact ground-rest Z S132 independently recorded), then moved',
'  horizontally with speed CAPPED AT EXACTLY `500.0 uu/s` — `|(-240.132,-438.562)| = 500.0` and',
'  `|(-233.334,442.216)| = 500.0`, i.e. NUMERICALLY EQUAL TO THE `MoveSpeed`/`MaxMoveSpeed` ARM G',
'  WROTE — travelled 13,187 uu, and finally walked off the island edge under its own AI**',
'  (`TimeSinceFallingStart` RESET 8.6001 → 1.5357; the external probe caught it at',
'  `(3364.362, 2611.051, -29425.4)` falling). `Acceleration` tracked the heading at magnitude 50,000',
'  throughout ⇒ **the AI wander driver is steering it.**',
'  ⇒ ★★★★★ **"THE PHYSICS DOES NOT WORK" IS DEAD.** Gravity, landing, ground movement, GAS speed',
'  clamping and AI steering are ALL measured working on a client this project has called broken',
'  since S138. **The wall was never in the mover.**',
'  ⇒ ★★★★★ **`Velocity == 0` IS A FIXED POINT [M]**: at exactly zero nothing — not the acceleration',
'  integration, not gravity — moves it off zero; perturbed by any real amount the whole chain runs',
'  and SELF-SUSTAINS. **The remaining problem is a KICK-OFF problem and it is small.** ⚠ The',
'  MECHANISM of the fixed point is **[S]** and is now the single open question; the offline candidate',
'  is the below-tolerance skip (`0x055B8838/3E/4A` → `je 0x55B8865`) and the `<= 1e-3` `SizeSq` arm',
'  near `0x035ED98E`/`0x035ED9BB`. It does not by itself explain why GRAVITY fails to accumulate.',
'  ★★ **AND THE `CalcVelocity` CLAMP IS REAL AFTER ALL — the S141 handoff\'s [S] grade is CORRECTED',
'  to [M], and the refutation of it is itself REFUTED.** `MinAnalogWalkSpeed @CMC+0x290` — the S140',
'  T2 NOT-OBTAINED read — is now MEASURED **0 on BOTH objects** (`< 1e-4`), so',
'  `MaxInputSpeed = GetMaxSpeed() × AnalogInputModifier` alone. BOT `AnalogInputModifier = 1` ⇒ the',
'  clamp must NOT fire ⇒ **it sustains 500**. PLAYER (untreated, no `AttributeSetStorage`)',
'  `AnalogInputModifier = 0` ⇒ `MaxInputSpeed = 0 < 1e-4` ⇒ the clamp MUST fire ⇒ **its injected',
'  600 uu/s decayed monotonically 600 → 33 → 22 → 8.7 → 0.9 → 0 and it moved only 795 uu and never',
'  fell.** ⇒ **the clamp is the PLAYER\'S wall.** The verifier chain that "refuted" it',
'  (*`GetMaxSpeed` shares the `+0xC00` slot with `GetMaxAcceleration`, which measured 50000, so',
'  `GetMaxSpeed != 0`*) is **sound for the BOT and INVALID for the PLAYER** — the player has no',
'  attribute set at all, so BOTH getters return `0.0f` there. **It applied a bot-derived premise to',
'  the player.** ⇒ pre-registered outcome **E** (the two arms disagree) — a real GAS-treatment',
'  dependency in the MOVER, in the predicted direction.',
'  ★ **Free confirmation of ARM H\'s mechanism, from a moving object:** at +250 ms payload',
'  `(34.906, 0, -4000)` vs `Velocity` `(34.039, 0, -4000)` — the payload is visibly the PRE-STEP',
'  snapshot and `Velocity` the post-step value, exactly as `0x055C2448`/`0x055C244F` says.',
'  **Arm:** `build.ps1 -Variant sentinel-big`, RAW **`52fceb9be6de532f`** (`KBSPSARMS=0xBA0`,',
'  `KSHSENTX=600.0`, `KSHPLRY=600.0`). ⚠ It PERTURBS BY DESIGN — the opposite of ARM H\'s inert',
'  `2^-10` — and it does NOT restore the player\'s velocity. **Not a shipping fix.**',
'  ⚠⚠ **`mergedumps` NEEDS FILE PATHS, NOT DIRECTORIES.** Given directories it printed',
'  `skip … : Incorrect function.` for both donors, **still wrote an output file, still reported a',
'  plausible `51.91 % non-zero merged`, and exited 0** — while a page census showed **gained 0,',
'  byte-identical to the seed.** ⇒ **always page-census a merge against its seed before adopting it.**',
'  `dumps/merged14.dump.exe` = **16,816 / 30,281 = 55.53 %**, verified a STRICT SUPERSET of',
'  `merged13` (**lost 0**, gained **+16**, 0 conflicts). `strxref.py` `DEFAULT_DUMP` moved to it.',
'',
])
s = s[:i] + block + s[i:]
open(p, 'w', encoding='utf-8', newline='').write(s)
print('CLAUDE.md updated')

# ---------------- handoff: correct the [S] grade and re-point ----------------
p3 = 'docs/next-session-prompt-s141.md'
t = open(p3, encoding='utf-8', newline='').read()

a = '# S141 — `StartNewPhysics` RUNS, and `Velocity` is written to ZERO. Find the writer.'
assert t.count(a) == 1
t = t.replace(a, '# S141 — THE BOT WALKS. `Velocity == 0` is a FIXED POINT. Find what kicks it off zero.', 1)

a2 = '''⚠⚠ **S139's `[M]` "StartNewPhysics has NEVER run on either component" is REFUTED.**'''
ins = NL.join([
'★★★★★★ **AND THEN FLIGHT 3 CHANGED THE WHOLE PICTURE — READ',
'`docs/s140-t2-armj-THE-BOT-WALKS.md` FIRST; EVERYTHING BELOW IT IN THIS FILE IS OLDER.**',
'**One write of `Velocity = (600,0,0)`, once, never re-written, and the AI-controlled hero FELL at',
'terminal velocity, LANDED on the tutorial floor at `Z = 90.150`, and WALKED — speed capped at',
'exactly `500.0 uu/s` = the `MoveSpeed` ARM G wrote — for 13,187 uu, steered by its own AI, until it',
'walked off the island edge.**',
'',
'⇒ **The mover works. Gravity, landing, ground movement, GAS speed clamping and AI steering are all',
'measured working.** The wall was never in the mover.',
'⇒ **`Velocity == 0` is a FIXED POINT [M].** At exactly zero nothing moves it off zero; perturbed by',
'any real amount the whole chain runs and self-sustains. **The remaining problem is a KICK-OFF',
'problem.** ⚠ Its MECHANISM is **[S]** and is the single open question.',
'⇒ **The `CalcVelocity` clamp is REAL [M], not [S] — §1.2 below is SUPERSEDED.**',
'`MinAnalogWalkSpeed @CMC+0x290` measured **0 on both** (`< 1e-4`), so `MaxInputSpeed =',
'`GetMaxSpeed() × AnalogInputModifier`. BOT `AnalogInputModifier = 1` ⇒ clamp does not fire ⇒',
'sustains 500. PLAYER `= 0` ⇒ clamp fires ⇒ its 600 uu/s decayed to exactly 0 and it never fell.',
'**The verifier chain in §1.2 is sound for the BOT and INVALID for the PLAYER** (no attribute set ⇒',
'both getters return 0.0f) — it applied a bot-derived premise to the player.',
'',
a2])
assert t.count(a2) == 1
t = t.replace(a2, ins, 1)

a3 = '## 1. TRAP: THE OBVIOUS TARGET IS PROBABLY NOT IT — READ THIS BEFORE PLANNING ANYTHING'
assert t.count(a3) == 1
t = t.replace(a3, NL.join([
'## 1. [SUPERSEDED BY FLIGHT 3 — kept as the dated record of what was believed before it]',
'',
'⚠⚠ **Everything in this section was written BEFORE flight 3 and its conclusion is now CORRECTED:',
'the clamp is [M] REAL and it IS the player\'s wall. Read §0 and',
'`docs/s140-t2-armj-THE-BOT-WALKS.md` §3 instead. The bytes below are all still accurate.**',
'']), 1)
open(p3, 'w', encoding='utf-8', newline='').write(t)
print('handoff updated')

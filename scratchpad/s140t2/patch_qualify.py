NL = "\n"

QUAL_DOC = NL.join([
'',
'### 1.5 ⚠⚠ QUALIFICATION — "`Velocity` is actively written to zero" IS WEAKER THAN IT LOOKS',
'',
'An adversarial verifier, working offline and without sight of the flight, established a mechanism',
'that bears directly on this: **a small non-zero `Velocity` can CONVERT A NO-WRITE INTO A WRITE.**',
'On the below-tolerance arm of a `GetSafeNormal`-shaped block the three `ucomisd` at',
'`0x055B8838 / 0x055B883E / 0x055B884A` all fall through to `je 0x55B8865` and **the write is',
'SKIPPED**; above tolerance it executes. And in engine `PhysFalling`, `2^-10` gives',
'`SizeSq = 9.5367431640625e-07` (`0x035ED9B3 call 0x035F4620`), after which',
'**`0x035ED9BB movups [rsi],xmm0` + `0x035ED9C3 movsd [rsi+0x10],xmm1` write the result into',
'`Velocity`** on the `<= 1e-3` arm.',
'',
'⇒ **What is established, precisely:**',
'',
'| claim | grade |',
'|---|---|',
'| `StartNewPhysics` runs on both components | **[M]** — rests on the POISON being overwritten, which is independent of any `Velocity` write, and the PLAYER arm is entirely velocity-write-free |',
'| something writes the BOT `Velocity` when it holds a small non-zero value | **[M]** |',
'| anything writes `Velocity` when it is EXACTLY ZERO | **NOT ESTABLISHED** — and the mechanism above gives a specific reason the exactly-zero case may SKIP the write |',
'',
'⚠ **Both flights put the sentinel there themselves**, so every observation of `Velocity` changing is',
'made in a world we perturbed. The player, whose `Velocity` we never touched, stayed `(0,0,0)` —',
'which is equally consistent with "never written" and with "written to zero".',
'',
'★★ **This is favourable in one direction: it may make the standing phenomenon a FIXED POINT** —',
'zero ⇒ no write ⇒ stays zero — which would be a different and much simpler wall than a routine that',
'computes zero. **And it hands the next session a NAMED CANDIDATE SITE**: `0x035ED9BB` /',
'`0x035ED9C3` inside engine `PhysFalling`. ⚠ The verifier is explicit that it did **not** establish',
'`0x035ED98E` is *reached* on a given frame.',
''])

p = 'docs/s140-tier2-sentinel.md'
s = open(p, encoding='utf-8', newline='').read()
a = '---' + NL + NL + '## 2. THE THREE FREE READS'
assert s.count(a) == 1
s = s.replace(a, QUAL_DOC + NL + '---' + NL + NL + '## 2. THE THREE FREE READS', 1)

# soften the headline
h = '> **And `Velocity` is actively COMPUTED AND WRITTEN every frame, to ZERO.**'
assert s.count(h) == 1
s = s.replace(h, NL.join([
'> **And something WRITES the bot\'s `Velocity` once it holds a non-zero value** — ⚠ but see §1.5:',
'> both flights put that value there themselves, and an exactly-zero `Velocity` may SKIP the write',
'> path entirely, which would make the standing null a FIXED POINT rather than a computed zero.']), 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('doc qualified')

# ---------------- CLAUDE.md ----------------
p2 = 'CLAUDE.md'
s2 = open(p2, encoding='utf-8', newline='').read()
CRLF = "\r\n" if "\r\n" in s2[:4000] else "\n"
a2 = '  ★★★★★ **⇒ THE WALL IS NOW DOWNSTREAM. `Velocity` is measurably WRITTEN TO ZERO, so a writer exists'
i = s2.find(a2)
assert i > 0
j = s2.find(CRLF, i) + len(CRLF)
j2 = s2.find(CRLF, j) + len(CRLF)   # the following line too
new2 = CRLF.join([
'  ★★★★★ **⇒ THE WALL IS NOW DOWNSTREAM.** ⚠⚠ **BUT QUALIFY THE SECOND HEADLINE: "`Velocity` is',
'  actively written to zero every frame" IS WEAKER THAN IT LOOKS.** Both flights put the sentinel',
'  there themselves, and an adversarial verifier established a mechanism by which **a small non-zero',
'  `Velocity` CONVERTS A NO-WRITE INTO A WRITE** — below tolerance the three `ucomisd` at',
'  `0x055B8838/3E/4A` all fall through to `je 0x55B8865` and **the write is SKIPPED**; and in engine',
'  `PhysFalling`, `2^-10` gives `SizeSq 9.54e-07` (`0x035ED9B3 call 0x035F4620`) after which',
'  **`0x035ED9BB movups [rsi],xmm0` + `0x035ED9C3 movsd [rsi+0x10],xmm1` write `Velocity`** on the',
'  `<= 1e-3` arm. ⇒ **[M] something writes the BOT `Velocity` once it holds a small non-zero value;',
'  NOT ESTABLISHED that anything writes it when it is EXACTLY ZERO.** The `StartNewPhysics` result',
'  is UNAFFECTED — it rests on the POISON being overwritten, and the PLAYER arm is entirely',
'  velocity-write-free. ★★ **This may make the standing null a FIXED POINT (zero ⇒ no write ⇒ stays',
'  zero), a much simpler wall than a routine that computes zero — and it NAMES A CANDIDATE SITE',
'  (`0x035ED9BB`/`0x035ED9C3`, engine `PhysFalling`).** ⚠ Whether `0x035ED98E` is reached on a given',
'  frame is NOT established.',
''])
s2 = s2[:i] + new2 + s2[j2:]
open(p2, 'w', encoding='utf-8', newline='').write(s2)
print('digest qualified')

# ---------------- handoff ----------------
p3 = 'docs/next-session-prompt-s141.md'
s3 = open(p3, encoding='utf-8', newline='').read()
a3 = '    *** Velocity is ACTIVELY COMPUTED AND WRITTEN TO ZERO every frame ***           [M, S140 T2]'
assert s3.count(a3) == 1
s3 = s3.replace(a3, NL.join([
'    something WRITES the bot Velocity once it holds a small non-zero value        [M, S140 T2]',
'      ^ QUALIFIED: both flights put that value there. Whether anything writes an',
'        EXACTLY-ZERO Velocity is NOT ESTABLISHED -- and a verifier found a mechanism',
'        by which the exactly-zero case SKIPS the write. See section 2, MOVE 2.']), 1)

a4 = '- **`GetGravityZ 0x055AB8C0` (disp `0x4C0`) and `NewFallVelocity 0x055B6AD0` (disp `0x7A0`) ARE Loki'
i3 = s3.find(a4)
assert i3 > 0
ins = NL.join([
'- ★★ **A NAMED CANDIDATE SITE, from the lane-2 verifier:** in engine `PhysFalling`, a `2^-10`',
'  velocity gives `SizeSq = 9.5367431640625e-07` (`0x035ED9B3 call 0x035F4620`) and then',
'  **`0x035ED9BB movups [rsi],xmm0` + `0x035ED9C3 movsd [rsi+0x10],xmm1` write `Velocity`** on the',
'  `<= 1e-3` arm. ⚠ It did **not** establish that `0x035ED98E` is reached on a given frame.',
'- ★★★ **AND THE STANDING NULL MAY BE A FIXED POINT.** On the below-tolerance arm of a',
'  `GetSafeNormal`-shaped block the three `ucomisd` at `0x055B8838/3E/4A` all fall through to',
'  `je 0x55B8865` and **the write is SKIPPED**. If `Velocity == 0` skips the write path, then',
'  zero ⇒ no write ⇒ stays zero, which is a **much simpler wall** than a routine that computes zero',
'  — and it predicts that a LARGE injected `Velocity` would persist and move the pawn. **That is a',
'  cheap, decisive follow-up arm** (⚠ and deliberately NOT the inert `2^-10`: this experiment needs',
'  a value ABOVE the tolerance, so it perturbs by design and must be flown as such).',
''])
s3 = s3[:i3] + ins + s3[i3:]
open(p3, 'w', encoding='utf-8', newline='').write(s3)
print('handoff qualified')

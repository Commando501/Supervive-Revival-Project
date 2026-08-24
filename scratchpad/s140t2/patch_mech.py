NL = "\n"

MECH = NL.join([
'',
'## 4b. ★★★★★ THE FIXED-POINT MECHANISM IS NAMED — AND IT RETRODICTS BOTH FLIGHTS, IN OPPOSITE',
'##      DIRECTIONS, FROM A DERIVATION THAT NEVER SAW THEM',
'',
'The 13-agent offline workflow finished after this flight. Its adjudicator — working only from',
'`merged13`, with its own PE reader and CFG, and with no knowledge of ARM H or ARM J — derived:',
'',
'> **[M] Engine `PhysFalling` ZEROES `Velocity` below a gravity-space `SizeSq2D` threshold.**',
'> `0x035ED98E comisd xmm1, [rip → .rdata 0x077F5180]`, where that constant is',
'> **`0.0009999999747378752` = `(double)(float)1e-3`**; `0x035ED996 ja` skips it, so the',
'> fall-through `0x035ED998 xorps xmm0,xmm0 … 0x035ED9BB movups [rsi],xmm0 /`',
'> `0x035ED9C3 movsd [rsi+0x10],xmm1` **writes `Velocity`**.',
'> `rsi = &Velocity` is **[M] by dominance**: the only defining `lea rsi,[rdi+0xe8]` in the body is',
'> `0x035EC9AC` (the other `rsi` def, `0x035EE519`, is the epilogue restore), and node-removal shows',
'> it **DOMINATES both writes** (reachable-avoiding-the-lea = `False` for each).',
'',
'**Checked against every bot observation this session produced:**',
'',
'| state | `SizeSq2D` | ratio to the gate | predicted | MEASURED |',
'|---|---|---|---|---|',
'| ARM H sentinel `2^-10` | `9.5367e-07` | **0.00095×** — below | **zeroed** | zeroed within 250 ms ✓ |',
'| the resting state `(0,0,0)` | `0` | **0×** — below | **zeroed** | `Velocity` has never left `(0,0,0)` ✓ |',
'| ARM J sentinel `600` | `360000` | **3.6e8×** — above | **kept** | fell, landed, walked 13,187 uu ✓ |',
'| the bot at +10 s, walking | `250000` | **2.5e8×** — above | **kept** | still walking at the 500 cap ✓ |',
'',
'⇒ ★★★★★ **THE FIXED POINT IS EXPLAINED, AND ITS GRADE GOES `[S]` → `[M, offline; retrodicts 4/4',
'in both directions]`.** `Velocity == 0` ⇒ `SizeSq2D = 0` ⇒ below the gate ⇒ **written back to zero',
'every frame** ⇒ it can never leave zero on its own. Any perturbation above `|V_xy| ≈ 0.0316` escapes',
'and the whole chain runs. **That is the entire wall, and it is one `comisd`.**',
'',
'★★ **This is the strongest form of evidence available here**: a mechanism derived offline, blind to',
'the flights, that predicts a *reversal* — zeroed below, kept above — and both arms of the reversal',
'were measured. Neither could have been fitted to the other.',
'',
'⚠⚠ **AND IT SAYS THE "INERT SENTINEL" INSTINCT WAS EXACTLY BACKWARDS.** ARM H chose `2^-10`',
'*because* it was physically negligible — and negligible is precisely what puts it under the gate.',
'**A smaller, "more inert" sentinel is zeroed HARDER.** The adjudicator recommends `2^-20` for a',
'different gate (`SizeSq2D < 1e-8`, `|V_xy| < 1e-4`) in `ULokiCMC::PhysFalling` at `0x055B877D`, and',
'that is worth keeping for any future *inertness* argument — but for THIS gate no inert value exists.',
'⇒ ★★ **ARM H\'s poison-the-payload design is what saved the flight.** Had it depended on the',
'sentinel surviving, it would have returned a false negative for a reason nobody had identified yet.',
'',
'⚠ **[I], not [M]: whether `Velocity.Z` is zeroed too.** The Z store takes `xmm1`, and this document',
'does not establish `xmm1 == 0` there. Flight 1 read `(0,0,0)` including Z, and flight 3 shows Z',
'accumulating to terminal velocity once above the gate — consistent with Z also being zeroed below',
'it, which would explain the no-fall phenomenon as well. **One read of the instruction settles it.**',
'',
'⚠ **The PLAYER\'s decay is a DIFFERENT site.** Its `600` on +Y is also far above this gate, yet it',
'decayed monotonically to 0 — that is the `CalcVelocity` `MaxInputSpeed` clamp of §3, which fires',
'because the untreated player has `AnalogInputModifier = 0`. **Two distinct zeroing sites, each with',
'its own measured signature. Do not merge them.**',
''])

p = 'docs/s140-t2-armj-THE-BOT-WALKS.md'
s = open(p, encoding='utf-8', newline='').read()
a = '## 5. WHAT THIS CHANGES'
assert s.count(a) == 1
s = s.replace(a, MECH + NL + '---' + NL + NL + a, 1)

old = NL.join([
'⚠ **The MECHANISM of the fixed point is [S] and is now the single open question.** The offline',
'candidate is the below-tolerance skip the lane-2 verifier found — `0x055B8838 / 0x055B883E /',
'`0x055B884A` all falling through to `je 0x55B8865`, and the `<= 1e-3` `SizeSq` arm in engine',
'`PhysFalling` around `0x035ED98E` / `0x035ED9BB`. **That is a hypothesis with a named address, not a',
'measurement.** It also does not by itself explain why *gravity* fails to accumulate.'])
new = NL.join([
'★★ **The MECHANISM is NAMED and it is one `comisd` — see §4b.** It was `[S]` for about an hour.'])
assert s.count(old) == 1
s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('walks doc: mechanism section added')

# ---------------- CLAUDE.md ----------------
p2 = 'CLAUDE.md'
t = open(p2, encoding='utf-8', newline='').read()
CRLF = "\r\n" if "\r\n" in t[:4000] else "\n"
olds = '  and SELF-SUSTAINS. **The remaining problem is a KICK-OFF problem and it is small.** ⚠ The'
i = t.find(olds)
assert i > 0
j = t.find('near `0x035ED98E`/`0x035ED9BB`. It does not by itself explain why GRAVITY fails to accumulate.', i)
assert j > i
j = t.find(CRLF, j) + len(CRLF)
new2 = CRLF.join([
'  and SELF-SUSTAINS. **The remaining problem is a KICK-OFF problem and it is small.**',
'  ★★★★★ **AND THE MECHANISM IS NAMED — [M, offline], AND IT RETRODICTS 4/4 OBSERVATIONS IN BOTH',
'  DIRECTIONS FROM A DERIVATION BLIND TO THE FLIGHTS. Engine `PhysFalling` ZEROES `Velocity` below a',
'  gravity-space `SizeSq2D` gate: `0x035ED98E comisd xmm1,[rip→.rdata 0x077F5180 =',
'  0.0009999999747378752 = (double)(float)1e-3]` / `0x035ED996 ja` skips ⇒ the fall-through',
'  `0x035ED998 xorps xmm0,xmm0 … 0x035ED9BB movups [rsi],xmm0 / 0x035ED9C3 movsd [rsi+0x10],xmm1`',
'  WRITES Velocity.** `rsi = &Velocity` is [M] **by dominance** — the sole defining',
'  `lea rsi,[rdi+0xe8]` at `0x035EC9AC` dominates both writes (node-removal False/False).',
'  ⇒ resting `(0,0,0)` gives `SizeSq2D = 0` ⇒ **below the gate ⇒ written back to zero every frame ⇒',
'  it can never leave zero on its own.** Escape needs `|V_xy| ≳ 0.0316`.',
'  **The reversal was MEASURED both ways: `2^-10` (SizeSq 9.54e-07, 0.00095× the gate) was zeroed in',
'  250 ms; `600` (SizeSq 360,000, 3.6e8×) was kept and the bot walked.** Neither could be fitted to',
'  the other.',
'  ⚠⚠ **AND IT MAKES THE "INERT SENTINEL" INSTINCT EXACTLY BACKWARDS — a SMALLER, more inert',
'  sentinel is zeroed HARDER.** ⇒ ★★ **ARM H\'s poison-the-payload design is what saved that flight**;',
'  had it depended on the sentinel surviving it would have returned a false negative for a reason',
'  nobody had identified yet.',
'  ⚠ **[I], not [M]: whether `Velocity.Z` is zeroed too** — the Z store takes `xmm1` and nothing here',
'  shows `xmm1 == 0`. One instruction read settles it, and it would explain the no-fall phenomenon.',
'  ⚠ **The PLAYER\'s decay is a DIFFERENT SITE** — its 600 is far above this gate yet it decayed to 0,',
'  which is the `CalcVelocity` `MaxInputSpeed` clamp firing on `AnalogInputModifier = 0`.',
'  **TWO distinct zeroing sites, each with its own measured signature. Do not merge them.**',
''])
t = t[:i] + new2 + t[j:]
open(p2, 'w', encoding='utf-8', newline='').write(t)
print('CLAUDE.md: mechanism upgraded')

# ---------------- handoff ----------------
p3 = 'docs/next-session-prompt-s141.md'
u = open(p3, encoding='utf-8', newline='').read()
a3 = 'problem.** ⚠ Its MECHANISM is **[S]** and is the single open question.'
assert u.count(a3) == 1
u = u.replace(a3, NL.join([
'problem.**',
'★★★★★ **AND THE MECHANISM IS NAMED [M, offline, retrodicts 4/4 in both directions]:** engine',
'`PhysFalling` ZEROES `Velocity` below a gravity-space `SizeSq2D` gate —',
'`0x035ED98E comisd xmm1,[rip→.rdata 0x077F5180 = 0.0009999999747378752 = (double)(float)1e-3]` /',
'`0x035ED996 ja`; the fall-through `0x035ED9BB movups [rsi],xmm0` / `0x035ED9C3 movsd [rsi+0x10],xmm1`',
'writes it, with `rsi = &Velocity` proven by dominance from the sole `lea rsi,[rdi+0xe8]` at',
'`0x035EC9AC`. Resting `(0,0,0)` ⇒ `SizeSq2D = 0` ⇒ below the gate ⇒ zeroed every frame ⇒ **it can',
'never leave zero on its own.** Escape needs `|V_xy| ≳ 0.0316`.',
'⇒ **S141 IS NO LONGER "find the mechanism". IT IS: (1) confirm `xmm1 == 0` at `0x035ED9C3` — one',
'instruction read, and it would explain the no-fall phenomenon too; (2) find what the GAME uses to',
'kick a character off zero (jump / launch / knockback / the initial spawn impulse), because that is',
'the shipping-shaped fix; (3) transcribe the path from the `0x830` dispatch to `0x035ED98E` to see',
'what else gates it.**']), 1)
open(p3, 'w', encoding='utf-8', newline='').write(u)
print('handoff: mechanism + new plan')

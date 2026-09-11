# S111 — arm J. ★★ **The protector watches `.text`, not code modification in general.**

**2026-08-07 00:38 → 01:35. 9 valid launches × 320 s hold** (+1 voided), no-patch primary alone via
`-Hook` plus `catalog_pick_fix` mapped by hand. Total S111 series: **224 launches**.

---

## 0. The prediction, made before the run

`catalog_pick_fix` was read first, and it turned out **not to be a `.text` patcher at all**. It writes
`0x06` (`EX_Return`) plus a jump offset into `ScriptOf(ufunc)` — the `UFunction`'s **heap-allocated
Blueprint bytecode array** (`catalog_pick_fix.cpp:105-125`) — and it **never restores** (line 171
re-applies forever).

That made it a discriminating test rather than a fourth data point, and the prediction was recorded
in advance:

> If the protector integrity-checks the **module image**, arm J ≈ **0 %** despite being a permanent
> code patch. If it detects **code modification generally**, arm J ≈ **88 %** like arm E.

**Predicted ~0 %. Observed 0/9.**

## 1. The ladder

| arm | what it modifies | runs | deaths | rate |
|---|---|---:|---:|---:|
| `-NoHook` | nothing | 11 | 0 | **0 %** |
| D — inert mapped DLL | nothing | 11 | 0 | **0 %** |
| **J — + `catalog_pick_fix`** | **UFunction `Script` bytecode (heap), PERMANENT** | **9** | **0** | **0 %** |
| I — + 3 PI hookers | `.text` prologue × 3, **transient** | 12 | 4 | **33 %** |
| E — patched primary alone | `.text` `jz`-NOP, **standing** | 8 | 7 | **88 %** |

| comparison | p | |
|---|---:|---|
| **J vs E** (bytecode vs standing `.text`) | **0.00041** | **significant** |
| J vs I (bytecode vs transient `.text`) | 0.083 | not significant |
| J vs inert floor | — | identical (0 % both) |

## 2. What this establishes

**The trigger is specifically modification of the module image, not code modification as such.** A
*permanent* patch to executable Blueprint bytecode — code the VM really executes — is completely free
(0/9), while a *self-restoring* two-byte `.text` write kills 88 % of runs. That is a much sharper
statement than "don't patch code", and it is directly actionable:

> **Rewrite shim mechanisms as data/bytecode writes wherever the effect can be expressed that way.**

Two independent confirmations of that rule now exist:
- the `jz`-NOP → `[+0x354]` **data poke** swap (roster still renders, `.text` write eliminated), and
- `catalog_pick_fix`'s **bytecode** patch, permanent and free.

This also retro-explains why `catalog_pick_fix` never showed up in the corpus as a death family
despite being in the default set since S48.

## 3. ⚠ Limits

- **J vs I is p = 0.083 — not significant.** 0/9 vs 4/12 is suggestive, not proven. The clean,
  significant statement is J vs E.
- n=9 valid. A single death in the next few runs would move the point estimate a long way.
- One boot, one machine, menu route, 320 s holds. Arms not interleaved.
- Only the protector family is counted; scan faults were 0 throughout.

## 4. ⚠ A reliability finding worth keeping

Run `J4_1` came back **`VOID-primary-not-injected`**: `docs/inject-watch.out.log` was unchanged across
the run, and its next write (01:01:51) belongs to J5's launch, so the `-Hook` primary genuinely failed
to map. **The `-Hook` injection path silently fails occasionally** — roughly 1 in 10 here.

Every arm in this session verified injection positively (`armx`/`armpi` require the log to change and
name the DLL; `batch.ps1` requires the shim's own marker stamp), so no arm is contaminated. But any
future experiment that assumes "I copied the file, therefore it was injected" will silently mix
no-injection runs into a treatment arm — which, in an experiment whose control is *no injection*,
biases everything toward the null.

## 5. Where this leaves injection hardening

| lever | measured value |
|---|---|
| drop standing `.text` patches | **largest** — 88 % → 0 % in isolation; shipped for the primary |
| express effects as data/bytecode | **free** — 0 % at n=9 permanent |
| trim the injected set | real — 5 DLLs → 1 was 17 % → 4 % at 60 s |
| shorten the PI transient window | **small** — the transient design already captures most of it |

The remaining `.text` writers are the three PI hookers, at 33 % combined (320 s). Converting a PI
hook to a non-`.text` mechanism is the only large lever left, and it is a design change rather than a
tuning knob.

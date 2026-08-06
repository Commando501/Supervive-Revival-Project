# S111 — first live run of the `catalog_store_fix` scan fix (run 1)

**2026-08-05 20:44:13 → ~20:45:59 local. Menu route** (`forceTutorialMatch = false`), full default shim
set, elevated launcher, Steam up. Baseline before launch: **92** UECC dirs, **45** crashpad archives,
`.sentry-native/reports/` **empty**.

## Verdict in one line

**The catalog-scan death family did NOT fire, and the fixed shim did its whole job — but the process
still died at ~106 s, of the *other* self-inflicted family (the protector), which this fix does not
address.** N=1: this clears the window, it does not establish a rate.

## 1. The fixed build was actually live — attribution, not assumption

```
[0] catalog_store_fix worker started (ready-gate + purchasable poke) build=Aug  5 2026 20:38:09 scan=SAFECOPY-S111
```
The `scan=SAFECOPY-S111` stamp is new in this build (ignorance-map gap F3: "nothing distinguishes
'the target ran and did nothing' from 'we never reached the target'"). Every claim below is anchored
to it. ⚠ Note the trap this avoided: the launcher injects `tools\sigbypass-mod\catalog_store_fix.dll`
**beside the sources**, NOT `build\`. `build.ps1` writes to `build\` by default, so the first build
would not have been the DLL under test. Both were verified `.text`-identical (`4c9f1604…`) before
`-InPlace` deploy; deployed `.text` is `202a6c7d…` (87,040 B, was 86,528 B).

## 2. FUNCTIONAL POSITIVE CONTROL — PASSED

The fix rewrote the scan onto `ReadProcessMemory`. The risk was not "does it crash", it was **"does it
still find anything"** — a scan that reads nothing never faults and would look like a pass.

```
[cm] live CatalogManager @0x1FE02E94A00 (map Num=1004) — catalog loaded
[hb] catMgr=0x1FE02E94A00 jz=1/1 unhook=1 purchIters=160 lastPurch=1339
```

**MEASURED:** the rewritten scan located the live CatalogManager with a **1004-entry** catalog map;
the `jz` was patched **and self-restored** (`1/1`, so no persistent `.text` mod); slot 110 was
unhooked; **1,339 CatalogEntries** poked across 160 iterations. The shim is functionally intact.

## 3. The death — family A (protector), NOT the scan

Dump archived + SHA-256 verified before the next launch could destroy it:
`dumps/crashpad-20260805-204616-s111-scanfix-run1/` (43,578,336 B, sha `2DAE0B7C07CF52F5…`),
session log captured (297,413 B), `handing control over to crashpad` present.

| discriminator | family B = our scan | family A = protector | **observed** |
|---|---|---|---|
| `RIP & 0xFFFF` | `0x205D` | `0x0001` | **`0x0001`** |
| `ExceptionInformation[0]` | `0` (READ) | `8` (EXECUTE) | **`8` (EXECUTE)** |
| RIP vs accessed addr | differ | **equal** | **equal** (`0x7FFD3B400001`) |
| RIP inside a registered module | yes (the shim) | no | **no** |

Shape match against the three family-A addresses already in the corpus:

```
corpus : 0x7FF90E000001   0x7FF8F0400001   0x7FFB9EE00001
THIS   : 0x7FFD3B400001      <- <base>+1, low16 = 0x0001, EXECUTE
```

**This is categorically not the scan.** A `ReadProcessMemory`-backed scan cannot produce an EXECUTE
fault at all — it performs no jumps and dereferences nothing. Family A is pre-existing and is the
corpus's largest self-inflicted class (24 of 114 before this run; **25** with it).

⚠ `runtime.dll` is **absent from this dump's module list**, so `RIP-1 == runtime.dll base` could not
be confirmed here. That absence is not new and not an error: the write-up records `runtime.dll`
missing from crashpad module lists in **0/22**, now **0/24** — a reproducible property that remains
**unexplained** (`docs/fk8-crash-timing-mined.md` §6, where the earlier "manual mapping" explanation
for it was refuted). Re-verified at the corrected address: **no module is based at `RIP-1`, and RIP
falls inside no registered module**, in both dumps (221 and 220 modules).

> ### ❌ CORRECTION — the fault address first published for this run was wrong (arithmetic, mine)
> The first version of this file gave `0x7FFDF4200001`. The dump reports decimal
> **140725597503489**, which is **`0x7FFD3B400001`** — I converted it by hand and got it wrong. The
> *classification is unaffected* (low16 `0x0001`, EXECUTE, RIP == accessed address, no module), and
> every other number here stands.
>
> **How it was caught, and the general lesson:** running the two dumps through
> `tools/crashtri/fk8_classify.py` returned the **same** RIP for both, which looked exactly like the
> wrong-`ThreadContext` artifact this project has already been bitten by (`§8` item 7 — "every crash
> is at one identical address", 22/22). Chasing that disagreement found the error in *my arithmetic*,
> not in the tool. **Two crashes at one address was the correct answer**: the write-up measured that
> the EXE base is **per-boot, not per-process**, so two runs in the same boot session legitimately
> share `<protector base>+1`. A suspicious-looking identical value is not automatically an artifact —
> but it is always worth one check by a second instrument.

## 4. What this run does and does not establish

**Does:**
- The fixed DLL was live and is functionally intact (§2) — the fix did not break the shim.
- No fault at `0x205d`, and no fault anywhere in the shim's image.
- The run cleared the entire 15–45 s band in which every recorded catalog-scan death sits
  (crashpad class: 6 of 22 deaths fall in 15–45 s).

**Does not:**
- **N=1.** There is no per-launch base rate for the scan family — the exposure denominator is open
  item #1 and still unmeasured. A single clean pass through 15–45 s is equally consistent with "the
  fix works" and with "the fix does nothing and this launch got lucky." **Do not record the 11-death
  family as closed on this run.** Several launches are needed.
- It says nothing about the tutorial route (this was a menu run).

## 5. ⚠ A hypothesis this run raises, and cannot settle

`ReadProcessMemory` is a classic memory-scanning API, and the fix newly introduces it into a
manually-mapped DLL **inside an anti-tamper-protected process**. It is therefore worth asking
whether the fix could *increase* family-A kills.

**Against:** family A has 24 pre-existing instances spanning the whole 42-day corpus, on both menu
and tutorial routes, entirely predating this change — so it is plainly not *caused* by it.
**Unresolved:** whether the *rate* moved. N=1 cannot tell. If subsequent runs show family-A kills
clustering earlier or more often than the corpus baseline, suspect this first.

The cheap discriminator already exists and needs no new tooling: classify every future death by
`RIP & 0xFFFF` before attributing it to anything.

## 6. Next

1. Repeat this launch 3–5× and count `0x205d` occurrences against the 11-death baseline. Each run is
   ~2 minutes, and the marker stamp makes attribution unambiguous.
2. Open item #1 (exposure denominator) would turn these counts into an actual rate.
3. Family A is now the dominant unaddressed self-inflicted class. Open item #5 — a `-NoHook` run held
   past 300 s — is the control that would say whether it is our injection at all, and **the corpus
   contains no such run**.

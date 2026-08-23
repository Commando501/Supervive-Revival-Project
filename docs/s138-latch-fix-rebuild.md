# S138 — the substring-latch fix, rebuilt and re-digested as a unit

Written 2026-08-23. Fixes the defect recorded in `docs/s138-offline-followup.md` C3 /
`docs/s138-flight2-arme-fired.md` §2b C3. Source + rebuild + re-verification done together, as the
handoff required — a source edit without a matching rebuild would leave `build/` inconsistent and
risk a successor flying an unverified arm.

## 1. THE DEFECT

`tutorial_launch.cpp` `BsClassify` latched the live GameState with

    if(PhChainHas(cls,"LokiGameState",chain,sizeof(chain)))     v|=32;

`PhChainHas` walks the class chain and tests each element with **`strstr`**. So
`strstr("LokiGameStateUAVComponent","LokiGameState")` succeeds and the census latched an
**ActorComponent** as the GameState. ARM E's pre-flight then read `TeamStates` at `[+0x600]/[+0x608]`
off that component — an offset read on an unrelated object — and printed
`TeamStates[+0x600].Num=0`, which **reached a published document as fact.**
Both G3 and G4 were VOID. The function's own comment two lines above documents this exact trap for
GameMode and fixes it there (`"LokiRoundGameMode"`), leaving the GameState line defective.

★ Fifth member of the class-lookup blind-spot family: `obj_by_class` substring · `cheat_reach_probe`
endswith · `class_props` class-of-class · `bpframe_readout` first-match · **this**.

## 2. THE FIX — four parts

1. **New `PhChainHasExact(cls, want, chainOut, chainSz)`** — identical walk, `strcmp` per chain
   element instead of `strstr`. A component can never satisfy it for a class it does not derive from.
2. **The GameState predicate uses it.** The GameMode predicate is deliberately **left alone**: it
   already uses the narrow `"LokiRoundGameMode"` and it demonstrably worked in flight (G5 resolved
   `BP_LokiGameMode_Tutorial_C` and reached `Comp_BP_BotSpawner`). Changing a working latch to
   exact-match risks breaking it if the chain carries no literal `LokiRoundGameMode` element —
   untested, so not touched.
3. **Candidate ARRAYS, not first-match** (`g_psGsCandA[4]`, `g_psGmCandA[4]`, with counts). A
   first-match latch cannot report ambiguity, which is how it selected the wrong object silently.
4. **The G3/G4 readout was rewritten** to:
   - print **every** candidate with its **FULL CHAIN**, so a recurrence of the trap is visible in
     the marker itself rather than needing a disassembly pass to find;
   - cross-check against **`World->GameState`** (`UWorld+0x258`, resolved by name with `0x258` as
     the recorded fallback) and **prefer the World's answer**, which is authoritative and outranks a
     census first-match — the same pattern `PhPickGameMode` already uses;
   - emit an explicit **`*** NOT MEASURED ***`** state when nothing was latched AND the World has no
     readable GameState, saying in the marker that this is **NOT** "TeamStates is empty" and that
     downstream reasoning is UNINTERPRETABLE;
   - flag **AMBIGUOUS** when more than one candidate exists and the World's answer is absent;
   - carry the S138 offline result inline: **TeamStates can NEVER be non-empty on a client**
     (`GetOrCreateTeamState` impl `0x5634BD0` returns nullptr unconditionally; `SetNumTeams` is the
     void fold), so a future reader does not mistake `Num=0` for a defect.

Diff: **+79 / −13** lines, one file. CRLF preserved (17,453 CRLF, **0** bare LF; the file is
all-CRLF and the patch was applied byte-wise with explicit `\r\n`).

## 3. ⚠ THE DIFFERENTIAL — what my edit did and did NOT move

Built the **same five variants from HEAD source** (edit stashed) and from **HEAD + the edit**, and
compared. This is the "before/after differential inside ONE method" the repo prescribes, and it is
what makes the attribution a measurement rather than an assumption.

| arm | HEAD source | **HEAD + fix** | pre-fix archive | attribution |
|---|---|---|---|---|
| `botai` | `5e47c13cf7f0a158` | **`5e47c13cf7f0a158`** | `5e47c13cf7f0a158` | **REGRESSION GATE HOLDS** — unchanged all three ways |
| `botspawn` | `b2203efd62161182` | **`b2203efd62161182`** | `1a8fa5fe06f87019` | **NOT my edit** — see below |
| `lokibot` | `e934636bea0fb9b4` | **`b3c6041c5cdf3fb3`** | `e934636bea0fb9b4` | moved BY the edit ✓ |
| `spawnbot_premade` | `ec6ca40c8b46297a` | **`302c2d29dfa3c4c5`** | `ec6ca40c8b46297a` | moved BY the edit ✓ |
| `spawnbot_readonly` | `a6cad1bb25f78c52` | **`8a3f794f204c1305`** | `a6cad1bb25f78c52` | moved BY the edit ✓ |

★★ **HEAD source reproduces the FLOWN digests bit-for-bit** for `botai`/`lokibot`/`premade`/
`readonly` — which independently proves the build is deterministic *and* that yesterday's flown arms
really were built from HEAD.

⚠⚠ **`botspawn`'s recorded digest was STALE, and this is a finding, not a side note.** Its archived
DLL was dated **2026-08-21 02:36** — built from source ~17 hours older than HEAD. HEAD source and
HEAD+fix both produce `b2203efd62161182`, so **my edit does not touch it** (`KBSPS` defaults to 0 and
every change is inside `#if KBSPS`; the new `PhChainHasExact` is `static` and dead-strips when
unused — proven by `botai` being byte-identical).
⇒ **The `botspawn` DLL flown in S138 flight 2 was NOT built from the source at HEAD.** It worked (it
executed `SpawnBot` and decrypted the page, which is all it was asked to do), but anyone quoting
`botspawn e48c90bc6cf17c93` (VSIZE) or `1a8fa5fe06f87019` (RAW) is quoting a build that no longer
reproduces. **Current: RAW `b2203efd62161182` / VSIZE `213e0010ed8fd003`.**

## 4. THE NEW GATES — record these

| arm | RAW | VIRTUALSIZE |
|---|---|---|
| `tutorial_launch_botai.dll` | `5e47c13cf7f0a158` | `f34ab2bf31cb0b34` |
| `tutorial_launch_botspawn.dll` | `b2203efd62161182` | `213e0010ed8fd003` |
| `tutorial_launch_lokibot.dll` | `b3c6041c5cdf3fb3` | `14c8c7ad0c2c4ef7` |
| `tutorial_launch_spawnbot_premade.dll` | `302c2d29dfa3c4c5` | `ebd0300408d590af` |
| `tutorial_launch_spawnbot_readonly.dll` | `8a3f794f204c1305` | `8a3f794f204c1305` |

Archived: **`dumps/s138-arms-v2/`**, all five verified byte-identical to `build/`.
Pre-fix arms preserved at `dumps/s138-arms-prefix/` (and the flown set at `dumps/s138-arms/`).

⚠ **`spawnbot_readonly` is now RECIPE-DEGENERATE**: `VirtualSize == SizeOfRawData` (pad 0), so RAW
and VIRTUALSIZE are the same bytes and **cannot discriminate between the two recipes for that file**.
That is not an arm-identity problem — it still differs from `spawnbot_premade` — but do not cite it
as evidence about which recipe is in use.

## 5. VERIFICATION BATTERY — all run after the rebuild

- **Reproducibility:** built twice from the patched source; all five digests identical both times.
- **Duplicate scan** (`text_digest.py --dupes` over `build/`, 87 artifacts): **0 HAZARD groups**
  under BOTH recipes. `spawnbot_premade` (`302c2d29dfa3c4c5`) ≠ `spawnbot_readonly`
  (`8a3f794f204c1305`) — the control is not a copy of its treatment. The flagged degenerate group
  (`play` ≡ `play_nopimutex` ≡ `play_strictroot`) is the **pre-existing S136 one**, unrelated.
- **`verify_dll.py`: VERDICT PASS on all five** — no C++ exception machinery, no CRT import,
  `IMAGE_FILE_DLL` set.
- **No module-image write:** `WriteProcessMemory` / `FlushInstructionCache` / `VirtualAlloc` /
  `VirtualFree` **absent from all five**. ⚠ `VirtualProtect` is present, as always — other run modes
  in the same TU use it — so the import-absence signature is *suggestive, not proof*; the property
  rests on the source path.
- **Static two-sided probe, 10 rows, expectations stated BEFORE measuring — 10/10 match:**

| needle | premade | readonly | lokibot | botai | botspawn |
|---|---|---|---|---|---|
| `KERNEL32` *(pos ctrl)* | 1 | 1 | 1 | 1 | 1 |
| `S137 PLAYERSTATE SUMMARY` *(KBSPS ctrl)* | 1 | 1 | 1 | . | . |
| `ARM E SKIPPED by KBSPSARMS bit6` *(bit6-clear ctrl)* | . | . | 1 | . | . |
| `G3/G4 GameState candidates` *(NEW)* | 1 | 1 | . | . | . |
| `EXACT chain match` *(NEW)* | 1 | 1 | . | . | . |
| `NOT MEASURED` *(NEW)* | 1 | 1 | . | . | . |
| `TeamStates can NEVER be non-empty` *(NEW)* | 1 | 1 | . | . | . |
| **`G3/G4 LokiGameState=0x` (OLD buggy print)** | **.** | **.** | **.** | **.** | **.** |
| `ARM E CALLING SpawnBot(comp=` | **1** | . | . | . | . |
| `ARM E NOT CALLING (KBSSBCALL=0` | . | **1** | . | . | . |

  **The old buggy print is gone from all five**, the fixed print is in both ARM E arms, and the
  CALLING / NOT-CALLING banners remain **mutually exclusive** — so this is still not the S135
  dead-arm failure.

⚠⚠ **A CORRECTION I MADE TO MYSELF MID-CHECK, worth keeping.** My first probe predicted the new
strings would appear in `lokibot` (it has `KBSPS=1`) and scored it a MISMATCH. **The binary was
right and my expectation was wrong:** the G3/G4 block lives inside `BsPsSpawnBot`, which `lokibot`
(`KBSPSARMS=0x20`, bit6 CLEAR) **dead-strips entirely**. Its `.text` still moves — via the
`BsClassify` predicate, which is a *code* change and invisible to a string scan. The zeros are
interpretable only because two positive controls pass in that same column. **A needle reading 0
without a positive control in the same column is uninterpretable, and I nearly recorded my own bad
expectation as a build defect.**

## 6. WHAT THIS DOES AND DOES NOT BUY

**Does:** G3/G4 is now trustworthy, self-documenting, and fails loudly instead of silently. Any
future marker shows the candidate count, every chain, and the World's authoritative answer.

**Does not:** it changes no conclusion from flight 2. The divert ambiguity is still 4-way
(`0x556DD63`, `0x556DE6A`, `0x556DE76`, `0x556DE82`), and branch (b) is closed regardless because
`TeamStates` is unpopulatable. The remaining live question is unchanged: **read `[PS+0x8C8]` after
the call** — non-zero ⇒ the naming block ran ⇒ the divert was `0x556DE6A`; still zero ⇒ `0x556DD63`.
That is one RPM read on any staged client and should ride along with other work, not justify a
dedicated launch.

⚠ **Nothing here has been flown.** All five arms are rebuilt, verified and archived; none has been
injected since the change.

---

# 7. ADDENDUM — v3: the DUPLICATE-CANDIDATE defect, found by flight 3's own output

The v2 arms above were flown (`docs/s138-flight3-divert-settled.md`). The latch fix worked, and its
output immediately exposed a **second, smaller defect in the fix itself**:

    [PS] G3/G4 GameState candidates: 2
    [PS]   gsCand[0] 0x2C9C76610F0 'BP_LokiGameState_Tutorial_C' ...
    [PS]   gsCand[1] 0x2C9C76610F0 'BP_LokiGameState_Tutorial_C' ...     <- THE SAME POINTER

**Cause:** `BsScanWorld` runs **three** passes (`A0` 15673, `A1` 15686, `A2` 15773) and nothing reset
the candidate latches between them, so one object was recorded **once per pass**. Consumers run
after A1, hence exactly 2 entries — and it tripped the spurious *"more than one GameState candidate
→ AMBIGUOUS"* warning, i.e. a **false positive on the very ambiguity signal the fix exists to give.**
The same accumulation bug affected `g_psWorldN` and `g_psGmCandN`.

**Fix — two guards, because either alone leaves a hole:**
- **`BsPsResetCands()`** at the top of every pass, so the candidate set describes the CURRENT sweep;
- **`BsPsAddCand()`** de-duplicates on insert, so a repeated object can never be double-counted even
  if a pass is re-entered or the reset is missed.

★ **Safety established by inspection, not assumption:** every consumer (`BsPsPrecondition` 15456,
`BsPsSpawnBot` 15515) runs **after A1 and before A2**, and a grep over everything past line 15773
finds **zero** reads of `g_psWorld` / `g_psGsCand` / `g_psGmCand`. So resetting per pass cannot strand
a consumer.
★ The reset deliberately sits **after** `BsScanWorld`'s two early-return guards, so a *failed* sweep
leaves the last good candidate set intact rather than wiping it.

### v3 digests (**these supersede §4**)

| arm | RAW | VIRTUALSIZE | moved by the dedupe fix? |
|---|---|---|---|
| `tutorial_launch_botai.dll` | `5e47c13cf7f0a158` | `f34ab2bf31cb0b34` | **no — REGRESSION GATE HOLDS** |
| `tutorial_launch_botspawn.dll` | `b2203efd62161182` | `213e0010ed8fd003` | **no** (`KBSPS=0`) |
| `tutorial_launch_lokibot.dll` | `e123816b65d68e5e` | `6748058e0aa4cd56` | yes |
| `tutorial_launch_spawnbot_premade.dll` | `6cb296bbf3c8c696` | `a100dc6283ea859a` | yes |
| `tutorial_launch_spawnbot_readonly.dll` | `64d55e27e5d99213` | `01d1363246feed92` | yes |

★ **Two-sided attribution:** the two `KBSPS=0` arms are byte-unchanged and the three `KBSPS=1` arms
moved — so the `#if KBSPS` guard is correct in both directions, not just asserted.
★ `spawnbot_readonly` is **no longer recipe-degenerate** (pad 256, was 0).
Archived: **`dumps/s138-arms-v3/`**, all five verified byte-identical to `build/`.
Flown v2 set preserved at `dumps/s138-arms-v2/`.

### v3 verification

- **A STANDALONE LOGIC TEST OF THE HELPER — 10/10 PASS.** The shipped `BsPsAddCand` was copied
  verbatim into a test harness and compiled with the same clang, covering: the exact flight-3 bug
  (same pointer × 3 passes → **1** candidate), 3 distinct → 3, interleaved dupes → 3, cap clamping
  at 4 with no overflow, a duplicate when full, a new distinct when full, and **both sides of the
  AMBIGUOUS predicate** (one real GameState → `n>1` FALSE; two → TRUE). Testing the fix's logic
  directly is far cheaper than discovering it in flight, which is how this defect was found.
- `verify_dll.py` **PASS ×5**; `WriteProcessMemory`/`FlushInstructionCache`/`VirtualAlloc`/
  `VirtualFree` **absent ×5** (`VirtualProtect` present as always — suggestive, not proof).
- Duplicate scan: **0 HAZARD** under both recipes; the one flagged degenerate group
  (`play` ≡ `play_nopimutex` ≡ `play_strictroot`) is the **pre-existing S136 one**, unrelated.
- Static probe **10/10** against pre-stated expectations, three positive controls passing, old buggy
  print still absent, CALLING/NOT-CALLING still mutually exclusive.

⚠ **v3 has NOT been flown.** The behavioural prediction for the next flight is precise and
falsifiable: **`G3/G4 GameState candidates: 1`**, one `gsCand[0] = BP_LokiGameState_Tutorial_C`, and
**no AMBIGUOUS line**.
⚠ **Still unfixed and pre-existing:** the wrong-world latch — flight 3 printed
`World->GameState = NULL or unreadable`, so the World candidate chosen still has no GameState and
the code fell back to the census. The fallback behaved correctly and said so, but the underlying
S137 world-selection defect remains.

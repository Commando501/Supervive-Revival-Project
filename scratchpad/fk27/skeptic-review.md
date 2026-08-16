# FK-27 successor — ADVERSARIAL REVIEW of the two-population / roots-are-re-marked claim

**Reviewer role:** refute, not confirm. Default verdict when uncertain = *not established*.
**Date:** 2026-08-15. **Target:** `tools/re/rootset_census.py`, evidence `scratchpad/fk27/census-run2.txt`.
**Prior belief under attack:** `docs/s110-item-watch-gc-mechanism.md` §4c + the `obj_state()` docstring in
`tools/re/item_watch.py` — *"Root-set objects are excluded from marking"*, `ROOTED+MARK` a *"CHIMERA …
0.03 % of the natural population"*.

**Everything below is read-only `ReadProcessMemory` against the already-running `SUPERVIVE-Win64-Shipping.exe`
(pid 24252, base `0x7FF7BFF50000`). Nothing was injected, launched, killed or written.** New instruments
live in `scratchpad/fk27/` and neither `rootset_census.py` nor `item_watch.py` was modified.

---

## 0. Verdicts at a glance

| claim | verdict |
|---|---|
| **N1** two populations; prefix has "no free slot ever" | **CONFIRMED** (conclusion) / **evidence REFUTED.** The two populations, the count 32, and the boundary `[0, 39295)` are all correct and now [M] against a named engine field. **The "zero holes … against 7,282 free slots scattered above it" argument is wrong on its facts and must be deleted** — see §2.5, §2.5b. |
| **N2** the prefix is a permanent / disregard-for-GC pool, excluded by INDEX | **CONFIRMED.** `GUObjectArray.ObjFirstGCIndex = 39295` and `ObjLastNonGCIndex = 39294`, read live by me at `.data 0x9E38920` (§2.5b), plus the 20 never-marked unrooted objects inside the prefix (§3). Exclusion is positional. ⚠ My own first-draft claim that 39295 was a purge-hole artifact is **RETRACTED**. |
| **N3** the 32 are AddToRoot callers, re-marked on every GC pass | **SURVIVES-WITH-SCOPE — but its stated evidence is REFUTED.** "Re-marked" is *confirmed on much stronger evidence* (9 rotations, 32/32, 0 exceptions). The 32/32 **statistic** is void — it reads **0/32** in one of my runs and **32/32** in the other, driven by a GC-pass mode seen 1 time in 9. *"Identical to 40/40 ordinary controls"* is **false**. "Genuine AddToRoot callers" is **[I], strongly supported, not measured**. |
| **N4** S110's exclusion claim is a pooling artifact | **SURVIVES-WITH-SCOPE** — the pooling diagnosis is [M], but S110 is less wrong than N4 implies, and **N4 does not rescue the shim or reopen FK-27.** |

**The claimant's own pre-registered falsification criterion was met.** They wrote: *"a FASTER sampling
period should make MORE ordinary objects fail while still leaving rooted at 0. Report it as REFUTED if
rooted objects start failing too."* At 0.5 s, **rooted objects failed 32 of 32.** By that criterion the
*metric* is refuted. The *mechanism* it was reaching for is probably true anyway, for a reason the metric
was structurally unable to see.

### 0b. Per claim: what survives, and the control that decided it

| | **survives** | **dies** | **deciding control** |
|---|---|---|---|
| **N1** | two bit-30 populations, 39,275 + exactly **32**, split by a 5,705-slot gap; identical index lists across every census over ~1 h; the boundary `[0, 39295)` is exactly right | *"no slot is ever free … against 7,282 free slots scattered above it"* — wrong on its facts and not the reason the boundary is real | **free-slot histogram by index.** `[45000..169999]` — 125,000 slots, 3.2× the prefix — **also has zero holes and is not rooted**, so the signature is not specific. And 5,705 of the 7,282 free slots are ONE contiguous run *at* the boundary (the unused reserve up to `MaxObjectsNotConsideredByGC = 45000`), not "scattered above" it |
| **N2** | **all of it** — prefix carries no reachability value, exclusion is **positional**, and the boundary `[0, 39295)` is exact | nothing. (My own counter-claim that 39295 was a purge-hole artifact dies — §2.5b) | **two, and they agree.** (a) the **20 unrooted live objects inside the prefix**: low nibble `0`, neither rooted nor marked, *and not collected* — a flag-driven GC would have purged them, an index-driven one skips them (new evidence; the claimant had none). (b) **`GUObjectArray.ObjFirstGCIndex = 39295` / `ObjLastNonGCIndex = 39294`, read live by me** at `.data 0x9E38920` |
| **N3** | **re-marked on every pass** — 9 rotations, 32/32, 0 exceptions, single-bit, identity-revalidated | the *"32/32 carrying the current value"* statistic; *"identical to 40/40 ordinary controls"*; "genuine AddToRoot callers" as [M] | **raw flag words at 0.4–0.5 s.** The boolean reads 0/32 in one run and 32/32 in the next; the nibble sequence `1→4→2→1…` is stable in both. And **`enum_validate`'s bit24 ⟺ ClusterRootIndex<0 at 100.000 % over 200,437 objects** is what raises "bit30 = RootSet" from a name-guess to a strong inference |
| **N4** | the pooling diagnosis (S110's 6-of-4915 *is* today's 32) | "S110 said roots are never marked" as a flat reading; any implication for the shim or FK-27 | **S110's own §3 table**, which already records four shim-rooted objects going `40000004 → 40000002` and calls it *"they are RE-MARKED"*. The overturned text is one sentence in §4c plus a docstring, not S110's finding |

---

## 1. The decisive new measurement: raw flag words at 0.5 s

`scratchpad/fk27/skeptic_track.py` (new) reads the FUObjectItem of each tracked object **directly**, in a
~3 ms burst, and records the **full 32-bit flag word**; it brackets that burst with two independent
strided population reads so a torn/mid-rotation sample is detectable rather than silently scored.

Two runs, on the same live process:
- **`fast`** — 418 samples, 0.5 s, 210 s, 3 rotations, 1/418 mid-rotation, 0/144 identity changes.
- **`fast2`** — 999 samples, 0.4 s, 400 s, 6 rotations, **0/999** mid-rotation, 0/144 identity changes.

(`scratchpad/fk27/skeptic-fast.txt`, `skeptic-fast2.txt`, CSVs, analysis `analyze_fast.py`.)

★ **Read-order control:** the burst reads HI-ROOTED **first**, so if read position mattered the roots
would look *less* converted, not more. They look more. The two ordinary groups are read 2nd and 3rd and
disagree with each other, which also rules read order out.

Low nibble (the reachability *value*) per group, at the pass beginning t=27.5 s:

```
 smp     t   cur | HI-ROOTED(32)  | ORDINARY-idxmatched(32) | ORDINARY-lowidx(40)
   0   0.0     0 | 1:32           | 1:32                    | 1:40
  55  27.5     0 | 4:32   <== ALL | 1:15 4:17               | 1:40
  81  41.0     0 | 4:32           | 1:1  4:31               | 1:19 4:21
 150  75.9     2 | 4:32           | 4:32                    | 1:5  4:35
 152  76.9     2 | 4:32           | 4:32                    | 4:40   <== last ordinary object
 175  88.4     1 | 2:32           | 2:32                    | 2:40
 297 149.5     0 | 1:32           | 1:32                    | 1:40
```

Three things follow, and each kills something.

**[M] 1a. The 32 rooted objects ARE re-marked — and this is now the best-supported part of the claim.**
Their low nibble runs `1 → 4 → 2 → 1` in run `fast` and `2 → 1 → 4 → 2 → 1 → 4 → 2` in run `fast2`:
**nine rotations across two runs, 32 of 32 objects, zero exceptions, identity revalidated at every
sample.** That is the value *changing*, which the original boolean could never demonstrate. The
"multi-bit trivialisation" alternative is excluded: the low nibble held **exactly one** bit at all
418 + 999 samples for all 144 tracked objects.

**[M] 1b. `dominant_reach_bit()` is a LAGGING MAJORITY VOTE, and during a mark ramp the original test's
POLARITY INVERTS.** The roots acquired the new value at s55 (t=27.5); the population-majority vote only
flipped at s84 (t=42.5) — **29 samples / 15 s later**. For that entire window the probe's yardstick
`cur` was the OLD value, so every correctly, promptly re-marked object scored as **"missed"**. The metric
does not measure "was re-marked"; during a ramp it measures **"was marked LAST or not at all."**

**[M] 1c. In that pass, roots and ordinary objects were NOT "identical" — they were maximally different.**
All 32 roots converted inside a single 0.5 s sample. The **index-matched** ordinary controls (the control
the original probe lacks) took until t=75.9 — a **48.4 s** spread. First-slice conversion: roots
**32/32** vs matched ordinary **17/32**, Fisher one-tailed **p = 3.6e-6**.

⚠⚠ **BUT THE REPLICATION KILLS THE GENERALISATION, AND I AM CORRECTING MY OWN FIRST DRAFT HERE.** Run
`fast2` (999 samples, **0.4 s**, 400 s, `skeptic-fast2.txt`) crossed **six** rotations at 43.3 / 104.6 /
165.4 / 226.7 / 288.0 / 348.9 s (spacing 61.3 / 60.8 / 61.3 / 61.3 / 60.9 — the known 61.1 s clock) and
**every single one was atomic**: all 144 tracked objects, all four groups, converted in the *same sample*,
every time. 0 of 999 mid-rotation. 0 misses in any group.

⇒ **The mark ramp occurred in 1 of 9 observed passes.** The other 8 completed in under 0.4 s — consistent
with S110 §4b's *"232 of 256 control objects flipping inside a single 250 ms sweep"*. Eight passes carry
**no ordering information at all**: that is silence, neither support nor refutation.

⇒ **"Roots are marked at the head of the traversal" is [I] — one well-controlled observation, not an
established property.** It is the best evidence anyone has produced for the mechanism, and it is n=1.

### 1d. The between-run variance the coordinator flagged — and the prediction fails in BOTH directions

| run | period | passes | HI-ROOTED always | ORDINARY always |
|---|---|---|---|---|
| run 1 | 3 s | ~2 | 32/32 | 40/40 |
| run 2 | 3 s | 2 | 32/32 | 21/40 |
| **fast (mine)** | **0.5 s** | **3 (1 ramped)** | **0/32** | **0/40** |
| **fast2 (mine)** | **0.4 s** | **6 (0 ramped)** | **32/32** | **40/40** |

**It is NOT the sampling period.** A 3 s sampler would see a 49 s ramp with near-certainty; so would a
0.4 s one. The driver is **whether a ramped pass happens at all during the window** — measured here at
**1 in 9**. The metric is therefore **bimodal on a rare GC-pass mode**, and its value on any given run is
close to a coin flip on an event nobody was controlling.

**The coordinator's pre-registered prediction is refuted in both directions:**
- *"...while still leaving rooted at 0 [failures]"* → at 0.5 s **rooted failed 32/32**. Their own stated
  criterion: *"Report it as REFUTED if rooted objects start failing too."* Met.
- *"a FASTER sampling period should make MORE ordinary objects fail"* → at **0.4 s, the fastest run,
  ZERO ordinary objects failed** (40/40 always). Faster sampling did not increase ordinary failures; it
  produced the cleanest all-pass run of the four.

⇒ Nothing about this statistic is a property of the objects. **Retire it.**

⚠ **The set-mismatch worry is not the explanation, but it is also not checkable from the artifacts.**
`track()` never prints group membership. In my runs the selection is deterministic and byte-identical
(`boundary=39295`; HI-ROOTED = the same 32 indices in every census I took over ~40 min; ORDINARY-lowidx =
45002…45041 in both). Run 2 reports the same boundary and the same 32/40/40 counts, so it is very likely
the same set — but **run 1's membership is unrecoverable**, so the coordinator's cross-run comparison
cannot be validated, only made plausible.

⚠ **`track()` prints its FIRST sample as a "rotation"** (`last_bit` starts `None`). So census-run2's
`[t=0.4] rotated -> bit1` is initialisation, and run 2 crossed **two** rotations, not three. "Across 3
rotations" should be re-counted wherever it appears.

---

## 2. Attack-by-attack

### 2.1 Is bit 30 actually `RootSet`? — I could not refute it, and I found the control the claimant lacked

The prompt is right that **C3 cannot discriminate**: every UClass is also permanent, so C3 reads
identically under "RootSet" and under "permanent". The claimant's identification rested on class *names*.

**Do not try to identify bit 30 directly — test whether the whole `EInternalObjectFlags` TABLE sits at its
stock bit positions**, using bits whose truth is checkable against a *separate field*
(`scratchpad/fk27/enum_validate.py`, over all 200,437 live objects):

| control | result |
|---|---|
| **bit24 `ClusterRoot` ⟺ `ClusterRootIndex < 0`** | **PASS, agreement 100.000 % — 2,234 TP, 0 FP, 0 FN** |
| bit23 `ReachableInCluster` ⇒ `ClusterRootIndex > 0` | one-way holds **1,024/1,024, zero violations** |
| bits 0/1/2 = rotating reachability value | prior, FK-28 — matches UE 5.4 `ReachabilityFlag0/1/2` |

bit24 is **item-internal**: a flag bit compared against a numeric field four bytes away in the same
24-byte record. No second object read, no name resolution, nothing the permanent pool can confound, and
it could have failed. It did not, at 100.000 % over 200 k objects. ⇒ **the stock enum numbering is in
force in this build**, and `RootSet = 1<<30` sits in the same table.

Supporting, name-level:

- The **only two `Canvas`-class objects carrying bit 30 are `CanvasObject` and `DebugCanvasObject`** —
  exactly the two objects `UGameViewportClient::Init` calls `AddToRoot()` on in stock UE — against
  **1,176 high-index unrooted** objects matching the same substring.
- `LokiGameEngine` (#45001), `OnlineEngineInterfaceImpl` (#45000 — UE's `GetSingleton()` AddToRoots it),
  `World LVL_LobbyV2_Persistent` (#93843 — `UWorld::CreateWorld` AddToRoots it), `CrowdManager`, `ImageCache`.

**False-negative hunt (the prompt's damning test): none found.** Every high-index *unrooted* candidate I
checked is a `UPROPERTY` of a rooted owner in stock UE, i.e. correctly not rooted:
`LokiGameViewportClient#55354`, `LokiAssetManager#45078`, `LokiGameUserSettings#45137`,
`LocalPlayer#55355`, `BP_LokiGameInstance_C#49351`. And the one object I expected to be a false negative
— `GEngine` — **is** in the 32.

⇒ From my own instruments alone: **bit 30 = `RootSet` is [I], strongly supported, not directly measured.**
I did not disassemble `UObject::AddToRoot`. (My attempt at a static byte-scan for the atomic setter,
`scratchpad/fk27/rootbit_id.py`, is a linear-sweep false-positive machine with no decoder — its output is
garbage and I discarded it rather than reporting it.)

★★ **Independent corroboration from a different instrument, converging:** sibling agents doing *offline
disassembly* (`scratchpad/fk27/addtoroot-re.md`, `gc-mark-re.md` — **which I have not audited**) report
`RootSet == bit 30 == 0x40000000` confirmed three ways, and that the GC's root *seed* is a
`TSet<int32>` of InternalIndices at `.data 0x99D3CA0` with **`Num() = 31` (merged2) / `29` (tuthero)** —
against my live **32**. Two instruments that fail differently (live RPM enum cross-check vs static
disassembly) landing on the same table and the same population size. That architecture also **predicts my
§1c observation**: if `GC.MarkRootObjectsAsReachable` is a separate pass seeding the traversal, root
objects must acquire the new value before graph-reachable ones — which is exactly the one ramp I caught.
⚠ I verified *one* load-bearing number from that work myself (§2.5b) and it held; I did not verify the
rest, so treat the disassembly claims as corroboration, not as audited.

### 2.2 Is the "always-carried-current" test vacuous? — YES for two of the three groups

- **ORDINARY, run 1 (40/40):** vacuous. Section 1 of the census already states that **100.0 %** of
  non-bit-30 objects carry the current value at any snapshot (161,070 of 161,090). Drawing 40 of them and
  finding 40 hits is the same number restated.
- **ORDINARY, run 2 (21/40):** discriminates — but §1d shows it discriminates on **sampling phase**, not
  on the objects.
- **PERMANENT (0/40 always, 40/40 missed): a TAUTOLOGY, and it must not be written up as a finding.**
  Those objects carry **no low bit at all** — census §1 already says so (39,275 of 39,307 rooted objects
  carry none). "Missed at least once" is guaranteed by construction. It is the same measurement twice,
  not an independent control. My tracker confirms: PERMANENT low nibble = `0` at **1,417 / 1,417**
  samples across both runs — which is a *finding about the permanent pool*, but not a *control* for
  anything, because it cannot come out any other way.
- **HI-ROOTED 32/32:** as §1b shows, this is not a measure of re-marking at all.

### 2.3 Sampling / aliasing — quantified

The original bound is 3 s + census time (~0.5 s), so **~3.5 s**. My bound is **0.4–0.5 s**, and it
resolved the one ramp that occurred. Aliasing does **not** threaten N3's *conclusion*: a value that
changes `1→4→2→1` across nine rotations cannot be faked by missing a transient. It also is **not** what
produced N3's statistic — §1d shows the driver is the rare ramped-pass mode, not the period. Note the
mark phase is normally **shorter than 400 ms** (8 of 9 passes), so *any* practical sampler is blind to
mark ordering on a normal pass; the only reason the question is answerable at all is that one pass took
49 s.

### 2.4 Is `dominant_reach_bit()` sound? — **NO, and this is the core defect**

Max low bit with a ≥40 % floor. It is a **majority vote**, therefore **lagging**: it flips only when the
new value overtakes the old across the whole heap. Measured lag on the one resolvable pass: **15 s**
(s55 → s84). It cannot fake N3 (a mis-call cannot make an unchanging word appear to rotate) but it can and
did **hide** N3 and invert its sign. Confirmed: the t=0.3/0.4 s "rotation" is initialisation, not a
rotation (§1d); the other three in my run are real and 61.1 / 61.1 s apart.

### 2.5 Is the boundary real? — the "no holes" argument is REFUTED

Three separate problems, in increasing severity:

1. **Circular.** 39295 is *defined* as `first_free`. "39,295/39,295 live, zero holes" below it is a
   tautology of the definition. The non-tautological statement is `min(free index) = 39295`.
2. **"7,282 free slots scattered above it" is factually wrong.** [M] **5,705 of the 7,282 form ONE
   contiguous run, `[39295..44999]`**, sitting immediately at the boundary; the other 1,577 are all at
   index ≥ 170,000. 157 distinct free runs in total. ⚠ **My first draft continued "…so the prefix's lower
   edge is the bottom of a purge hole, not a structural pool edge." That inference is RETRACTED — see
   §2.5b.** The run `[39295..44999]` is the **never-allocated reserve** up to
   `MaxObjectsNotConsideredByGC = 45000`; nothing was ever freed there. The *factual* correction to the
   claimant's wording stands; the causal story I attached to it did not.
3. **Decisive: the signature is not specific.** Free slots by 10k bucket:
   `30k:705, 40k:5000, 170k:8, 190k:1372, 200k:197`. So **`[45000..169999]` — 125,000 consecutive slots,
   3.2× the size of the prefix — ALSO has zero free slots, and is overwhelmingly NOT rooted.** "No holes"
   does not distinguish the prefix from a non-rooted range three times larger.

For completeness, the arithmetic the prompt asked for: under a uniform model,
`P(no free slot below 39295) = (1 − 39295/207719)^7282 = e^−1527 ≈ 10^−663`. **That number is real and
also worthless** — the data itself refutes the uniform model it is computed against.

⇒ **Drop the "no holes" evidence.** It does not establish the boundary. Something else does — see next.

**The probe's own control said so and was ignored.** `boundary_scan` printed
`the two boundaries differ by 7038 slots <-- DISAGREE: do not call this a pool boundary`, and N2 calls it
a pool boundary. ⚠ Note the control is *also* badly built: it compares **index distance**, when the real
disagreement is **20 objects (0.05 %)**. A mis-scaled control that cried wolf, then got ignored — the
worst of both worlds.

### 2.5b ⚠⚠ RETRACTION — MY OWN. The boundary IS real, and 39295 is an engine field, not an artifact

My first draft of this review said *"39295 is the bottom of a purge hole, not a structural pool edge"*.
**That is wrong and I am retracting it.** A sibling agent's offline disassembly (`gc-mark-re.md`) reported
`GUObjectArray.ObjFirstGCIndex` at `.data 0x9E38920`. I did not take it on faith — **I read it live myself**,
one 4-byte RPM, dumping the whole neighbourhood so the layout is visible rather than the single value:

```
rva 0x09E38920  39295     <== ObjFirstGCIndex        == my measured first_free, exactly
rva 0x09E38924  39294     <== ObjLastNonGCIndex      == ObjFirstGCIndex - 1
rva 0x09E38928  45000     <== MaxObjectsNotConsideredByGC
rva 0x09E38930  ...       <== RVA_OBJOBJECTS, the project's existing constant (0x10 above)
rva 0x09E38944  207719    <== NumElements, matches the header parse
```

That resolves the whole geometry, and it inverts my causal reading:

- `[0 … 39294]` — the **actual** disregard-for-GC pool, bounded by `ObjLastNonGCIndex`. All live.
- `[39295 … 44999]` — **reserved but never allocated**, the unused tail up to
  `MaxObjectsNotConsideredByGC = 45000`. This is not a purge hole; **nothing was ever freed here.**
- `[45000 …]` — the normal collected heap. **And 45000 is exactly where the 32 begin** (`#45000 =
  OnlineEngineInterfaceImpl`, `#45001 = LokiGameEngine`).

⇒ **There are no holes below 39295 because objects below `ObjFirstGCIndex` are never collected, so their
slots are never freed.** The observation was right, my explanation of it was wrong, and the claimant's
stated boundary `[0, 39295)` is **exactly correct** — for a reason neither of us had measured.

⇒ **N1's boundary and N2's "excluded by INDEX" are upgraded to [M]**, on a named engine field read live
and agreeing with two independent cold images. My §2.5 points 1–3 stand as criticism of the *evidence
offered*; they no longer bear on the *conclusion*.

⚠ For the record: I criticised the claimant for reasoning past their own DISAGREE control, then over-read
the free-run geometry in the opposite direction. Same failure, opposite sign, three sections apart.

### 2.6 Address reuse — tested, and it does not bite

`track()` keys by address and never revalidates, so a slot freed and reissued at the same address is
invisible (`disappeared=0` cannot catch it). I added the guard: every sample checks `item[idx].Object`
is still the same pointer, and class+name are re-resolved at the end. **0 of 144 tracked slots changed
object/class/name over 210 s.** Not a live defect here; still an unguarded hole in the shipped probe.

### 2.7 Torn census — tested, does not bite, but is unguarded

`track()` derives `cur` from the same `full_census` walk that reads the targets — a ~0.2–0.5 s chunk-order
walk. My two-sided population read found **1 mid-rotation sample in 418**. So tearing is not the
explanation for anything here. (It also could not be: 24 of the 32 hi-rooted objects sit in the *same
chunk* as the ordinary controls, so an inter-chunk tear cannot separate them.)

### 2.8 Reproducibility of the group

The same **32** high-index bit-30 indices appear in every census I took across ~40 minutes, and all 25
that `census-run2.txt` printed are a subset of my 32 (it printed only the top 25 descending). Stable.

---

## 3. What N2 gains — evidence the claimant did not have

`enum_validate.py` identified the **20 live objects below the boundary that lack bit 30**:
`Default__EdGraphPin_Deprecated`, `DmgTypeBP_Environmental_C` (+CDO), `Default__BlendProfile`, and two
Blueprint-generated class families (`BP_ThumbnailGenerator_SkySphere_C`, `BP_Thumbnail_CustomDepth_Script_C`)
with their functions, components, SCS nodes and CDOs.

**[M] All 20 carry low nibble `0` — flags `00000000` or `00100000`.** They are neither rooted nor marked,
and they are not collected.

That is the first real discriminator between the two candidate mechanisms:
- under a **flag-driven** model these 20 are unreachable garbage and should have been purged long ago;
- under an **index-driven** model (traversal starts past the prefix) they are simply never visited.

⇒ **"excluded by INDEX, not by the flag" is now supported** — but note it is still [I] as a *named UE
mechanism*; "disregard-for-GC pool" is engine knowledge, not a measurement, and the boundary's exact index
remains unresolved (somewhere in `[32257, 39295)`).

---

## 4. What N4 must NOT claim

- **[M] The pooling diagnosis is right.** S110's own 1-in-8 sample recorded *"rooted 4915, of which 6
  carry the current flag"* — 6 × 8 = 48, the same population as the 32 measured at full resolution. The 32
  were in S110's data and were written off as 0.03 % noise. The `obj_state()` docstring's **numbers are
  correct**; only the label "CHIMERA" is wrong.
- **⚠ S110 is less wrong than N4 implies.** `docs/s110-item-watch-gc-mechanism.md` §3 and §4d **already
  recorded rooted objects being re-marked** — *"the FOUR OTHER shim-rooted objects go `40000004 ->
  40000002` <- GC pass: they are RE-MARKED"*, and *"at the pass, every shim-poked object is traversed like
  an ordinary object"*. §4c's sentence is scoped to *the engine's own* root set. So what is being
  overturned is **one sentence in §4c plus the `obj_state()` docstring**, not S110's finding. Write it
  that way or the retraction will over-reach.
- **⛔ N4 does NOT rescue the shim and does NOT reopen FK-27.** S110's poked objects were *also* in
  ROOTED+MARK and were collected anyway (§4d: rooted 33.1 s ahead of the pass, destroyed at it). Nothing
  measured here touches "poking bit 30 is inert".
- **⚠ Pre-existing contradiction to fix while you are in there:** `item_watch.py`'s `obj_state()` comment
  says the shim's poke produces **`ROOTED+MARK`**; `rootset_census.py`'s `track()` docstring says the
  poked object *"went **ROOTED+STALE** and died"*. Both are in the repo, they disagree, and N4 cites the
  second. (§4d supports ROOTED+MARK → ROOTED+STALE *at the pass*, i.e. both are half-right — which is
  exactly why the sentence needs rewriting rather than picking a side.)

---

## 5. Defects found in `rootset_census.py`

| # | defect | consequence |
|---|---|---|
| **P1** | `dominant_reach_bit()` is a **lagging majority vote**; measured lag **15 s** | during a mark ramp the "current value" is the OLD one |
| **P2** | `track()`'s *always-carried-current* therefore measures **"marked LAST"**, not "re-marked"; **polarity inverts** during a ramp | the headline 32/32 becomes 0/32 at 0.5 s. **Decisive.** |
| **P3** | `track()` stores a **boolean, never the flag word** | cannot show re-marking; cannot exclude the multi-bit trivialisation |
| **P4** | the **PERMANENT control row is a tautology** (those objects carry no low bit; census §1 already says so) | must not be reported as a finding |
| **P5** | `track()` **never prints group membership** | run-to-run comparability unverifiable; run 1 is unrecoverable |
| **P6** | `track()` keys by **address**, never revalidates identity | unguarded (did not bite: 0/144 over 210 s) |
| **P7** | `cur` comes from the **same torn census** that reads the targets | unguarded (did not bite: 1/418 mid-rotation) |
| **P8** | `boundary_scan()` agreement test compares **index distance**, not population | printed "differ by 7038 — DISAGREE" when the real disagreement is **20 objects (0.05 %)** |
| **P9** | `track()` prints its **first sample as a rotation** | "3 rotations" in run 2 is really 2 |
| **P10** | **C3 cannot fail informatively** (every UClass is also permanent) yet sits beside three controls that can | borrowed credibility |

**Defects in MY OWN instruments, for the record** (same failure mode, same session — rule 1 applies to the
reviewer too):
- `rootbit_id.py`: a byte-pattern scan with **no decoder**; its "immediates" are mis-decoded instruction
  bytes. Output discarded, nothing in this review rests on it.
- `enum_validate.py`'s **C-gamma (bit25 vs `RF_MarkAsNative`) and C-eps (bit30 vs `RF_MarkAsRootSet`) are
  TAUTOLOGIES** — UE strips `RF_MarkAsNative|RF_MarkAsRootSet` in the `UObjectBase` constructor before
  storing `ObjectFlags`. Measured: **0 of 6,000** objects carry either EObjectFlag, while **977** carry the
  corresponding internal flag. My predictions P3 ("≥99 % agreement") and P4 ("zero violations") were
  therefore un-failable and un-passable respectively. **Both rows are void; only bit24/bit23 count.**
  The positive control for `ObjectFlags@0x0C` itself did pass: `RF_ClassDefaultObject` on **306/306**
  `Default__` objects.

---

## 6. What should be written up, and how

**Safe to state [M]:**
- Two bit-30 populations: **39,275** at index `< 39295` and **exactly 32** at index `≥ 45000`. Stable
  across five censuses over ~1 h; group membership **byte-identical** between my runs.
- The 32 are **re-marked on every GC pass** — raw low nibble across **nine rotations in two runs**,
  32/32 objects, zero exceptions, single-bit at all 1,417 samples, identity revalidated.
- The prefix objects carry **no reachability value at all**, and so do the **20** unrooted live objects
  inside it ⇒ exclusion is **positional**, not flag-driven.
- `EInternalObjectFlags` **bit 24 = ClusterRoot at 100.000 %** over 200,437 objects ⇒ stock numbering.
- The GC clock is **61.1 s** (six intervals measured: 61.3 / 60.8 / 61.3 / 61.3 / 60.9), confirming FK-28.

**Also [M], and it supersedes most of the inference above** — `GUObjectArray` at `.data 0x9E38920`,
read live: `ObjFirstGCIndex = 39295`, `ObjLastNonGCIndex = 39294`, `MaxObjectsNotConsideredByGC = 45000`.
**Cite the field, not the hole-count.**

**Must be marked [I]:** "genuine `AddToRoot()` callers"; **"roots are marked first" (n = 1 of 9 passes)**.
bit 30 = `RootSet` is [I] from my instruments but independently corroborated by offline disassembly I did
not audit (§2.1).

**Must be deleted:** the "no slot is ever free … 7,282 free slots scattered above it" argument;
"32/32 carrying the current reachability value" as evidence of anything; "identical to 40/40 ordinary
control objects"; the PERMANENT control presented as a finding.

**Must be re-counted:** "3 rotations" (run 2 crossed 2 — the first is `track()`'s initialisation print).

**⚠ Remaining weaknesses, in order:**
1. **The roots-first ordering rests on ONE of nine mark passes.** 8 of 9 complete in <0.4 s. To settle it
   you need a way to *provoke* an incremental/ramped pass (raise the live-object count, or force GC while
   the heap is large) rather than waiting for one.
2. **bit 30 = RootSet is still inferred.** The clean finish is a disassembly of `UObject::AddToRoot` /
   `FUObjectItem::ThisThreadAtomicallySetFlag` showing a `lock cmpxchg` on `[item+8]` with `or …,
   0x40000000`. A naive byte scan will NOT do it (see §5) — it needs a real decoder.
3. **Single process state (main menu), single process lifetime.** Everything here is one pid.

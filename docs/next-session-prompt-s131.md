# NEXT SESSION (S131) — FK-22: bail 2 is FIXED. The question is now whether the pod is functional.

**Written 2026-08-20 at the end of S130.** Read `docs/s130-actor-pool-gate-settled.md` (**§11 → §13**),
then `docs/fk22-dropphase-reachability.md` §25–§28.

---

## 0. WHAT S130 DID

1. **The pool gate is named** — `ULokiActorPoolManager` slot 90 reads
   `ALokiGameState::bSupportsActorPoolPriming` (`+0x898`), false because the tutorial GameState
   Blueprint ships it `False`. **No ini route.**
2. ⚠ **The pool was never the blocker** — an unprimed pool cannot return NULL (`FindOrAdd` + a
   shipped fallback into a normal `UWorld::SpawnActor`).
3. ✅ **The NULL was `AActor::bCanEverReplicate`** (`CDO+0x6C`), which `AActor`'s ctor sets to 1 and
   the acquire rejects at `C7 @ 0x564820C`.
4. ✅✅ **AND IT IS FIXED, MEASURED:** poke `CDO->bCanEverReplicate = 0` on the drop-pod CDOs and
   `SpawnDropPodForTeam` returns **`true`** with **DropPod +2** (S127: `false` / `+0`); both pooled
   spawns return live actors (S128: NULL / `+0`). One heap byte, readback-verified, zero `.text` writes.

**FK-22's bail 2 is closed.** Do not re-open the pool, the gate, or C7.

---

## 1. START HERE — the pods exist; nobody has looked at what they ARE

`SpawnDropPodForTeam` succeeding means its caller's `if (spawn != null)` body ran **for the first
time**: `GetTeamDropLeader`, `InitializeDropPod`, `FinishSpawningActor`, `RemovePlayerFromPlane`,
`AuthPlayerEnterWorldAttachedToRidable`, `MulticastOnDropPodLaunched`, `AddTeamDropEvent`.
**Nothing has inspected any of it.** The census counts objects, not behaviour.

Cheapest first reads on the two spawned pods (read-only RPM, and the probe already prints their
addresses):
* is `PodTeamIndex` set (registry default is `-1`)? is `LeaderPod` non-null? `bIsTeamLeaderPod`?
* did `AuthPlayerEnterWorldAttachedToRidable` do anything — or did it hit the **FIFTH wall**
  (`0x55CD510`, a real body that always bails on a stripped fold)? That is the *expected* stopping
  point and confirming it is a result.
* is the hero attached to a pod? does `RemovePlayerFromPlane` show in the log?

⚠⚠ **TAKE THESE READS THE INSTANT THE ARM REPORTS, NOT AFTER.** S130's attempt 4 delivered every
result and then died artifact-less minutes later, taking its two spawned pods with it — the questions
above were free at the time and are now gone. **All 3 armed windows in S130 ended in artifact-less
deaths** (`s130-actor-pool-gate-settled.md` §13.7) against a recorded base rate of 3/36; n=3, so that
is suggestive rather than established, but **budget one armed window per result and write everything
to disk as it is produced.**

⚠ **C8 and C9 never fired.** They are **unexercised, not excluded** — if a later run produces a null
again, they are still the branches to read.

---

## 2. THE CHEAPEST STRENGTHENING, IF YOU WANT THE A/B TIGHTER

The control for S130's result is **cross-session** (S127/S128 on different clients). Flying
`poolspawn-cdoctrl` (`.text 4e9c12ae866f5359`) — byte-for-byte the S128 experiment plus a read-only
CDO print — converts it into a **within-session** control. One staged launch.
⚠ It must be a **fresh process**: once the CDOs are poked the process is committed, so a same-process
reversal is not possible.

⚠⚠ **Do NOT ship the poke.** It mutates a **class default** for the process lifetime and may break the
pod's replication — which is exactly what `bCanEverReplicate` exists to declare. It is a diagnosis.
If a durable route is wanted, the question to answer first is *why the shipped game's own drop path
calls a pooled spawn that its own class defaults forbid* — see §12.5/§13.5, still unanswered.

---

## 3. FREE, OFFLINE, AND UNSTARTED — do this while waiting for a client

**Re-run the `.data` `{name_ptr, exec_thunk, impl}` record instrument over all 100 `(class, func)`
keys of FK-22 §2.5.** Because the fold addresses are known constants (`0xF7EC20` = `ret 0`,
`0xF7EB50` = `xor eax,eax; ret`, `0xF7EB60` = `xor al,al; ret`, `0x0B9E1F0` = `mov al,1; ret`), the
record's third field yields a **REAL / EMPTY** verdict **without the code page being decrypted**.
§2.5 filed **16 of 100** keys as COVERAGE-BLOCKED; S130 showed that is an instrument limit for at
least 6 of them. **Expected yield: the COVERAGE-BLOCKED bucket collapses to near zero and the true
empty-stub count for the drop path becomes exact for the first time.**
⚠ Its negative control is degenerate — Angelscript names have **zero byte occurrences** in the image,
so "AS functions have no record" is a fact about name storage, not about the record table. Usable as
a discriminator; state it that way.

Also free and unstarted:
* **Three sibling pooled-spawn helpers** (`0x55EE1BE`, `0x5618E5E`, `0x56D4F4E`, each ~497 B, each
  referencing the same fallback string at `+0x6C`). **If `SpawnDropPodForTeam` inlines one, it
  inherits the identical fallback-not-null behaviour** — which would independently confirm that
  FK-22's bail 2 is nowhere near pooling.
* ✅ **`AActor` CDO `+0x6C` is ANSWERED — it is `AActor::bCanEverReplicate`** (`s130-actor-pool-gate-settled.md` §11). ⚠ The FIRST offline attempt failed and §11 records why, so the method matters: a bool record's `SetBitFunc` displacement is an offset within its **own** outer, and the generic `propscan.py` decoder is misaligned for variant record types. What worked was **picking the class first and walking ITS `PropPointers` array with per-type decoding** — `scratchpad/s130/tools/classprops_uht.py --seed-name bAlwaysRelevant --covers 0x6c`, with three positive controls. **Reuse that tool for any “what is at ClassX+N” question.**
---

## 4. IF YOU DO ENABLE THE POOL (optional -- it is NOT on the FK-22 path) — it is now a clean, cheap, well-understood experiment

Not because it fixes FK-22 (§0 says it probably does not), but because it is a **fully graded
one-byte change with a built-in positive control**, and it settles what the pool is for.

* **Lever:** `byte [GS+0x898] = 1` (readback-verify) **then** a raw direct call to `PrimePools`
  (`0x3356000`), `rcx = *(GS+0x428)`, `rdx` = a zeroed buffer ≥0xA8 bytes.
  `PrimePools` is **not reflected**, so the S55 name route cannot reach it; a plain direct call from
  an injected DLL is the recipe (same class as FK-27's settled `AddToRoot` recipe). It performs
  **zero module-image writes**.
* **Arms A → B → A**, single variable, arming by heap `UFunction.Func` swap (`RM_PHASELADDER`
  pattern). ⛔ **Never `RM_GOTOPHASE` / `InstallHook()`** — standing `.text`, measured 10/10 vs 3/36.
* **Positive control:** `PrimePools` logs before it decides, so a reachable call cannot be silent.
  ⚠⚠ **Baseline-count first — the skip line is already in the log from `BeginPlay`, so PRESENCE does
  not discriminate, only the COUNT does.** A silent Arm A ⇒ **the sitting is VOID.**
* **PASS/FAIL readouts:** `s130-actor-pool-gate-settled.md` §8.

---

## 5. TOOLING GOTCHAS THAT COST TIME THIS SESSION

1. **`fkdis.py findptr` caps at 200 rows** — a row count from it is a **floor, never a count**.
   Uncapped: `0x0F7EC20` 165,789 · `0x0B9E1F0` 26,444 · `0x0F7EB50` 27,217 · `0x12C7260` 2,823.
2. ⚠⚠ **`strxref.py func`'s `extent … EXACT` is per-`.pdata` ROW, not per function.** The acquire
   reports 1,086 B and is **3,702 B**. **Never take a function size from that line** — union the
   chained rows from `tools/strxref/index/pdata_union.csv`.
3. **`fkdis.py d <rva>` prints a BLANK result on a non-instruction-boundary rva** — which reads
   exactly like an undecrypted page and is not.
4. **`strxref.py` is the right tool for string→code work.** Hand-rolled scans have now failed in this
   subsystem on interior string offsets, `4C 8D`/`49 8D` REX encodings, and pointer-table indirection.
5. **`fkdis.py` has an `s129` dump alias now** (added S130): `--dump s129|merged2|tuthero|merged`.
6. ⚠ **`extractor bpdump <asset> @props` used to be gated behind the asset having UFunction exports**, so a DATA-ONLY Blueprint printed `No matching UFunction '@props' found` — which reads as *“no such property”* and means *“not looked at”*. **Fixed in S130** (`Program.cs:1137`). If you change that file, re-validate on a known-good asset before trusting a dump.
7. **New offline tools in `scratchpad/s130/tools/`:** `classprops_uht.py` (per-class UPROPERTY → offset map, with controls), `ar_query.py` / `ar_joint.py` (cooked AssetRegistry tag queries — the one offline source for a class's EFFECTIVE default), `boolscan.py`, `recs.py`. Read the README there: two of the six recovered tools are only partially verified.

---

## 6. REPO STATE

- ✅ Everything from S130 is committed, **including the C7 result (§11 / §26) and a fix to `tools/extractor/extractor/Program.cs`**: `docs/s130-actor-pool-gate-settled.md`,
  `docs/fk22-dropphase-reachability.md` §25 (+ a REFUTED banner on §23.3), the CLAUDE.md drop block,
  five new rows in `docs/method-rules.md` §1, `scratchpad/s130/` (session-lead thread + the six raw
  lane reports and six verifier verdicts as JSON), and the `s129` alias in `scratchpad/fk27/fkdis.py`.
- ✅ `forceTutorialMatch` remains committed as **`false`** (the safe baseline). **Flip it to `true` and
  rebuild `ags` before any tutorial sitting**, then set it back.
- Built `.dll`s under `tools/sigbypass-mod/build/` are git-ignored; the `.text` hashes in
  `docs/next-session-prompt-s130.md` §4 are the record. **Rebuild and diff `.text` before flying one.**
- The staging recipe is unchanged: `next-session-prompt-s130.md` §3 (`-AllowStale` is required, and
  **stage promptly after park** — both S127/S128 successes staged near 110 s uptime).

---

## 7. WHERE FK-22 STANDS

```
markers        REFUTED  (S124)
phase          SOLVED   (S124)
subscription   DEAD     (S124)
SpawnPlane     FAULTS   (S124/S17) -- but dropplane_b1only still creates a live LokiDropShip
SpawnDropPodForTeam  ->  RETURNS TRUE, DropPod +2      <-- FIXED S130 §28
  |
  +- bail 2 was C7: AActor::bCanEverReplicate on the pod CDOs
  +- NEXT: are the spawned pods FUNCTIONAL?             <-- YOU ARE HERE
  |    the caller's `if (spawn != null)` body ran for the first time and
  |    nobody has looked at what InitializeDropPod / FinishSpawningActor did
  +- then the rider handoff, which is the FIFTH wall
     (AuthPlayerEnterWorldAttachedToRidable 0x55CD510, always bails on a stripped fold)
  +- C8 / C9 never fired: unexercised, NOT excluded
```

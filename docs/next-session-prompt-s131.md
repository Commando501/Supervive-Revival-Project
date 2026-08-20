# NEXT SESSION (S131) — FK-22: the NULL is settled; the next wall is C8/C9, and one live read remains

**Written 2026-08-20 at the end of S130.** Read `docs/s130-actor-pool-gate-settled.md` (**§11 first**),
then `docs/fk22-dropphase-reachability.md` §25–§26. This file is the plan; those are the evidence.

---

## 0. WHAT CHANGED — read this before anything else

S129 handed over two tasks; **both were done offline, with no launch.** Then the session's own
first task (C7) was *also* done offline, so **the entire S130 plan is complete and this is a fresh
frontier.**

1. **The pool gate is named:** `ULokiActorPoolManager` slot 90 returns
   `Cast<ALokiGameState>(GetWorld()->GameState)->bSupportsActorPoolPriming` (`+0x898`), false because
   **`BP_LokiGameState_Tutorial`'s shipped class default sets it `False`**. There is **no ini route**;
   `ActorPoolManagerPrimingConfig` is a USTRUCT with zero properties and no consumer.
2. ⚠ **The pool was never the blocker.** An unprimed pool **cannot** return NULL — the acquire
   `TMap::FindOrAdd`s and a pool miss falls to a shipped fallback into a normal `UWorld::SpawnActor`.
3. ★★★★★ **THE NULL IS `bCanEverReplicate`.** `C7 @ 0x564820C` is
   `cmp byte ptr [CDO + 0x6C], 0 ; jne -> NULL`, `AActor+0x6C` is `AActor::bCanEverReplicate`,
   `AActor`'s ctor sets it **1** (`0x03371841`), neither drop-pod Blueprint overrides it, and
   `SpawnDropPodForTeam` wraps its entire body in `if (spawn != null)` with **no else**.
   ⇒ **bail 2 is explained end to end, with no reference to the actor pool.**

**Do not spend a launch on the actor pool.** It is a shipped design decision, fully characterised.

---

## 1. START HERE — ONE read, and it is the only thing blocking the model

**Read `byte[CDO(BP_GemV2_C) + 0x6C]` on any live client that has a world.**

Why this one: the cooked class default says `bCanEverReplicate = true` for **both** the drop pod
**and** `BP_GemV2` — and gems are the one class Angelscript explicitly opts into pooling
(`LokiGem.as:1129`), whose caller has the **identical** no-fallback shape. So on cooked values gems
fail the same gate, which the shipped game appears to contradict. Exactly one of these is true and
**none is measured**:

| # | hypothesis | what the read shows |
|---|---|---|
| 1 | something clears the byte at class load / `PostInitProperties` | reads **0** |
| 2 | gems/pods never use this path in real matches | reads **1** |
| 3 | the path is genuinely inert for replicated actors in this build | reads **1** |

★ **If it reads 0, then the runtime CDO is not the cooked value and C7 may not fire at all** — in
which case re-read `byte[CDO(BP_DropPod_Tutorial_C)+0x6C]` before believing anything downstream.
⚠ **Until this read exists: C7 is [M] for the COOKED class default and [I, strong] for the RUNTIME
byte. Do not collapse the two.**

`GUObjectArray` walk: `RVA 0x9E38920`, `ObjObjects` at `+0x10`, chunk table, stride 24, class at
obj`+0x18`, name id at obj`+0x20`. Find `Default__BP_GemV2_C` and `Default__BP_DropPod_Tutorial_C`.

---

## 2. THEN — the repair, if the read confirms 1

**Poke `CDO(BP_DropPod_Tutorial_C) + 0x6C = 0`**, readback-verify, then dispatch
`SpawnDropPodForTeam` via the existing Route E (ProcessEvent slot 78, `droppod_pe` build).

* **Write class:** one aligned byte on a class default object — the safest measured class
  (nothing 0/22 · bytecode 0/9 vs transient `.text` 4/12 · standing `.text` 7/8), free readback.
* **Arms A → B → A**, single variable, DropPod census as the readout (`dP` delta), exactly as S128.
* ⚠ **It mutates a CLASS DEFAULT** — every drop pod for the process lifetime, and it may break the
  pod's replication. Not a default-set shim.
* ⚠ **Expect the next wall at C8 or C9**, which are **untested rather than excluded**: C7 returns
  before either is reached, so nothing downstream of it has ever executed.
  C8 = `PoolMgr->GetWorld() == null` (`0x5648D97`) · C9 = `UWorld::SpawnActor` null, **or never
  invoked because `rbx == 0` at `0x5648E34`** (`0x5648E6F`).
* ★ And even a spawned pod hits the **FIFTH wall** at the rider handoff —
  `AuthPlayerEnterWorldAttachedToRidable` (`0x55CD510`) always fails on a stripped fold.

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
markers        REFUTED  (S124 -- they exist in LVL_Tutorial; Skylands_WP has none)
phase          SOLVED   (S124 -- one GoToPhase call self-drives the round to EGP_Combat)
subscription   DEAD     (S124 -- ServerOnly; the DropPlane component is not in the invocation list)
SpawnPlane     FAULTS   (S124/S17 -- 2 of 3 tagged markers are not streamed in)
SpawnDropPodForTeam  runs via ProcessEvent slot 78, returns false   = bail 2
  |
  +- the pooled spawn returns NULL
       +- NOT because the actor pool is disabled      <-- REFUTED  S130 §25
       +- because C7 rejects bCanEverReplicate = true <-- SETTLED  S130 §26
            |
            +- ONE live read left: byte[CDO(BP_GemV2_C)+0x6C]   <-- YOU ARE HERE
            +- then the one-byte CDO poke + Route E dispatch
            +- then C8 / C9, which have NEVER been reached
            +- and then the FIFTH wall at the rider handoff
               (AuthPlayerEnterWorldAttachedToRidable, always fails on a stripped fold)
```

⚠ **Every arrow above is measured. The only [I] left in the chain is whether the RUNTIME CDO byte
equals the cooked class default — which is exactly what §1 reads.**

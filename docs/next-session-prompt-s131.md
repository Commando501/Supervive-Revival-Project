# NEXT SESSION (S131) — FK-22: the pool was a red herring; the NULL is C7, C8 or C9

**Written 2026-08-20 at the end of S130.** Read `docs/s130-actor-pool-gate-settled.md` first, then
`docs/fk22-dropphase-reachability.md` §25. This file is the plan; those are the evidence.

---

## 0. WHAT CHANGED, IN ONE PARAGRAPH

S129 handed over two tasks: *read `ActorPoolManagerPrimingConfig`* and *resolve vtable slot `0x2D0`
(needs one staged launch)*. **Both are done, offline, with no launch.** The gate is
**`ALokiGameState::bSupportsActorPoolPriming`, a `bool` at `ALokiGameState+0x898`**, and it is FALSE
because **`BP_LokiGameState_Tutorial`'s own shipped class default sets it `False`** while the C++
constructor sets it `true`. `ActorPoolManagerPrimingConfig` is **INERT** — a USTRUCT with zero
reflected properties and no UHT consumer; there is **no ini route**.

**But the important result is the one nobody asked for:** S128's §23.3 suspicion — *"the pool being
disabled is WHY the pooled spawn returns NULL"* — is **REFUTED [M]**. An unprimed pool cannot produce
that NULL: the acquire uses `TMap::FindOrAdd` (never null) and a pool miss falls to a **shipped
fallback** that calls a normal `UWorld::SpawnActor`. ⇒ **stop working on the pool.**

---

## 1. START HERE — one read-only RPM read can end this, with no launch beyond a staged client

The surviving NULL causes inside the acquire `0x5648050` are exactly three:

| # | site | condition |
|---|---|---|
| **C7** | `0x5648210` | `CDO(BP_DropPod_Tutorial_C)->byte@0x6C != 0` |
| **C8** | `0x5648D97` | `PoolMgr->GetWorld() == null` |
| **C9** | `0x5648E6F` | `UWorld::SpawnActor` returned null, **or was never invoked** because `rbx == 0` at `0x5648E34` |

**C7 is decidable by reading ONE BYTE.** Walk `GUObjectArray` for `Default__BP_DropPod_Tutorial_C`
and read `+0x6C`. **If it is non-zero, C7 alone is the entire NULL and none of this ever had anything
to do with pooling.** That is the first thing to do.

The full Phase-A read list (pre-registered predictions in `s130-actor-pool-gate-settled.md` §8):
`World+0x258` and its class · `byte[GS+0x898]` · `[GS+0x428]`/`[GS+0x430]` ·
`CDO+0x6C` · `CDO+0x2D3` · `[PoolMgr+0x38]` element count.

★ **Two of those reads can falsify the S130 model outright** — `[GS+0x898] == 1` kills §1–§2, and
`CDO+0x6C != 0` kills §5's premise. **Both are pre-registered. Do not fly anything until they run.**

---

## 2. FREE, OFFLINE, AND UNSTARTED — do this while waiting for a client

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
* **Name `AActor` CDO `+0x6C`** — ⚠ **S130 tried this offline and it did NOT work; read
  `s130-actor-pool-gate-settled.md` §10 item 9 first.** A bool record's `SetBitFunc` displacement is an
  offset within its OWN outer, and the generic `propscan.py` decoder is misaligned for variant record
  types. It needs a per-class walk of `AActor`'s `PropPointers` with correct per-type decoding,
  validated on a gold value. **The one live RPM read in §1 is strictly cheaper and unambiguous.**
  (Original idea, for reference: via the UHT `FPropertyParams` oracle (the same route that named
  `bSupportsActorPoolPriming`: find the record whose `SetBitFunc`/offset is `0x6C` on an `AActor`-
  rooted `FClassParams`, and require `findptr` multiplicity 1).

---

## 3. IF YOU DO ENABLE THE POOL — it is now a clean, cheap, well-understood experiment

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

## 4. TOOLING GOTCHAS THAT COST TIME THIS SESSION

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

---

## 5. REPO STATE

- ✅ Everything from S130 is committed: `docs/s130-actor-pool-gate-settled.md`,
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

## 6. WHERE FK-22 STANDS

```
markers        REFUTED  (they exist in LVL_Tutorial; Skylands_WP has none)
phase          SOLVED   (one GoToPhase call self-drives the round to EGP_Combat)
subscription   DEAD     (ServerOnly is `mov byte [rdx],0; ret`; the component is not in the list)
SpawnPlane     FAULTS   (null-deref; 2 of 3 tagged markers not streamed in)
SpawnDropPodForTeam  runs via ProcessEvent slot 78, returns false  =  bail 2
bail 2         the pooled spawn returns NULL
  └─ NOT because the pool is disabled   <-- REFUTED S130
  └─ C7 / C8 / C9 inside the acquire 0x5648050   <-- YOU ARE HERE
       C7 costs ONE read-only RPM read and needs no launch
```

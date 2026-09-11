# S130 offline instruments — RECOVERED, with honest provenance

These six scripts were written by the S130 decode lanes as throwaway scratch tools. **The session
lead deleted them while tidying untracked files, then recovered them from the agent transcripts.**
That recovery is imperfect and you must read this file before trusting any of them.

All are **read-only offline** analysis over the cold PE dumps (flat images: file offset == RVA).
No live process, no injection. Dump aliases are hardcoded: `s129` / `merged2` / `tuthero`.

| file | what it does | verified by the session lead? |
|---|---|---|
| `boolscan.py` | decodes every UHT **`FBoolPropertyParams`** record and, crucially, disassembles its **`SetBitFunc`** to recover the property's **real byte offset and mask**. This is what NAMED the pool gate. | ✅ **RUNS AND REPRODUCES THE FINDING** — `boolscan.py --off 0x898` gives `0x08983A50 bSupportsActorPoolPriming … SetBitFunc=0x053800D0 [mov byte ptr [rcx + 0x898], 1] disp=0x898 mask=0x1 fold=1`, out of **13,156** Bool records, **selected: 1** |
| `recs.py` | the **`.data` `{name_ptr, exec_thunk, impl}` record instrument** — resolves a UFUNCTION name to its exec thunk AND its implementation, and labels the impl against the known fold constants. **It works without the code page being decrypted**, which is why it can answer questions FK-22 §2.5 filed as COVERAGE-BLOCKED. | ✅ **RUNS AND REPRODUCES A GOLD VALUE** — `recs.py SpawnPlayer` → `rec=0x9bdb230 thunk=0x534c070 impl=0xf7eb50 FOLD xor eax;ret`, byte-identical to `docs/fk1-stub-claim-recheck.md` |
| `propscan.py` | generic `F*PropertyParams` record scanner (`--name` / `--off` / `--gen`). `boolscan.py` imports it. | ⚠ **RUNS, WITH A DEFECT — see below** |
| `propowner.py` | record rva → the single `PropPointers` slot pointing at it → the array base → `FClassParams+0x28` → the owning UClass. This is how ownership was pinned to `ALokiGameState` (index 106 of 155). | ⛔ **not re-run by the session lead** |
| `implof.py` | thunk → implementation resolution by disassembly | ⛔ **not re-run** |
| `revmap.py` | reverse address → record/slot lookups | ⛔ **not re-run** |

## Two defects you must know about

1. ⚠⚠ **`propscan.py` was recovered from a PRE-EDIT snapshot.** The lane later added `GENMASK` in
   place (via an edit, not a rewrite), so the transcript only had the earlier body. `boolscan.py`
   imports `propscan.GENMASK` and crashed with `AttributeError` on the recovered file. **The session
   lead re-added `GENMASK = 0x1F`** (matching `propscan`'s own `v & 0x1F` type-mask usage) and
   `boolscan.py` then ran correctly. Any *other* in-place edit the lane made is **lost** — treat
   `propscan.py` as reconstructed, not as the artifact that produced the lane's numbers.

2. ⚠⚠ **`propscan.py`'s `gen=` LABEL IS WRONG FOR BOOLS — do not read it.** It prints
   `gen=WeakObject|Config` for `bSupportsActorPoolPriming`, because its `GEN` table maps
   `0x0A: 'Bool'` / `0x0C: 'WeakObject'` while `boolscan.py` empirically selects Bool records with
   `(gflags & 0x1F) == 0x0C` — and that filter is the one that is right (it selects 13,156 records
   that all carry a valid `SetBitFunc`). So the **type-name table is misaligned for this build**.
   Likewise `propscan.py` prints `off=0x1` for this record: a **generic** decoder applied to a Bool
   record reads the wrong field, because a bool record's `+0x20` region holds
   `ElementSize/SizeOfOuter/SetBitFunc`, not `Offset`.
   ⇒ **For bools, the ground truth is the disassembled `SetBitFunc`, and nothing else.** That is what
   `boolscan.py` prints and what §1 of `docs/s130-actor-pool-gate-settled.md` rests on.

## Why this is in `scratchpad/` and not `tools/re/`

Because four of the six have not been re-run by anyone but their author, and because the recovery
above means the files on disk are not provably the files that produced the lane numbers. **Every
load-bearing S130 claim was independently re-derived by the session lead or by an adversarial
verifier before it was written up** — the doc does not depend on these scripts being correct. If one
of them earns a place in `tools/re/`, promote it after it has been validated on a gold value in a
later session.

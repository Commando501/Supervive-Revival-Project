# LANE L5 — TASK A3: COMPLETE WRITER CENSUS FOR `CMC+0x12B0` (TimeSinceFallingStart)

S139 used "+0x12B0 advances at wall-clock rate" as evidence that `PerformMovement` runs, then had to
**RETRACT** the inference because the accumulate at `0x055B840C` is upstream of the Super call. Close
the question: enumerate every writer, so it is known exactly what an advancing `+0x12B0` does and
does not prove.

## Three writers are believed to exist

Two are already confirmed present in raw bytes by the session lead (see the brief). The third is
reported and unverified:

| id | address | context | status |
|---|---|---|---|
| **A** | `0x055B840C` addss / `0x055B8414` movss | `ULokiCMC::PerformMovement`, `xmm6` = DeltaSeconds | confirmed |
| **B** | `0x055C2483` addss / `0x055C248B` movss | `ULokiCMC::StartNewPhysics`, Iterations>0 arm, behind `jle 0x055C2475` and `cmp byte [rcx+0x231],3` | confirmed |
| **C** | `0x055A74D6` `movss [rsi+0x12b0], xmm6` | reported as a "client-correction bulk float restore" | **UNVERIFIED — settle what function it is in and what it does** |

## METHOD

**The previous attempt's method was garbage and MUST NOT be repeated:** it back-decoded from every
occurrence of the dword `0x000012B0`, produced obvious desync artifacts, and failed to find two
instructions already known to exist. Instead:

1. Identify the set of functions belonging to `ULokiCharacterMovementComponent`. Use the vtable at
   `.rdata 0x088F8570` (413 slots) for the virtual ones, and expand to non-virtual members by taking
   every direct-call target reachable from those, or by using
   `tools/strxref/index/pdata_union.csv` for function extents. **STATE which enumeration you used and
   that it is a FLOOR on a 55%-decrypted image.**
   ⚠ `pdata_union.csv` drops size-1 placeholder rows BY CONSTRUCTION, so it is blind on dark pages.
2. Build a CFG per function and collect memory operands with displacement `0x12B0` from **CAPSTONE
   OPERANDS**. Separate READS from WRITES.
3. **Positive control:** your scan MUST find all three of A, B and C. If it misses any, your
   instrument is broken — fix it before reporting. **State the control result explicitly.**
4. **Negative/scope control:** also report *reads* of `+0x12B0`, and say whether any writer exists
   OUTSIDE the Loki CMC class that you can see (and that the answer is a floor).

## For writer C specifically

Name the containing function (find its entry via `.pdata` / prologue), grade it FOLD/REAL/DARK,
determine what value `xmm6` holds there, and whether the function is on the per-frame path or a
network-correction path. **Whether it could be responsible for the observed 1.0×-real-time advance is
the question that matters.**

## FINALLY — the deliverable that matters most

State in one paragraph, precisely, **what an advancing `+0x12B0` DOES prove and what it DOES NOT
prove.** Enumerate which writers are consistent with the S139 live observation (bot 33.14 → 43.34
over 10.2 s; player 380 → 390) and whether they can be distinguished by any offline reasoning or only
by a live read.

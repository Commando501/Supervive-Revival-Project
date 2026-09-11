# LANE L4 — TASK A2b: PROGRESS LADDER FOR `ULokiCMC::PerformMovement 0x055B8370`, AND SETTLE WHETHER IT REALLY REACHES ITS SUPER

This lane exists because **S139 made exactly this mistake**: it read "+0x12B0 advances" (a fact about
the LOKI WRAPPER, since the accumulate at `0x055B840C` is UPSTREAM of the Super call at `0x055B85C1`)
as "the ENGINE impl runs", and had to retract. A future flight must be able to tell those apart.

---

## PART 1 — is the Super call unconditional?

S139 claims `ULokiCMC::PerformMovement` reaches its Super at `0x055B85C1` **UNCONDITIONALLY** (0 rets
before it; the only skip-branch is AFTER the call). **RE-DERIVE THIS INDEPENDENTLY.**

Build the CFG of `0x055B8370`, compute the set of instructions that can reach `0x055B85C1`, and
enumerate every edge that leaves that set — the same sound method as lane L1 (backward reachability,
NOT a forward-address predicate).

**If ANY bail exists between entry and the Super call, that is the answer to the whole session and
you must say so loudly.**

Pay particular attention to these two forward branches S139 flagged but never read live:

    0x055B845E  test byte [CharacterOwner+0x580], 8 / jne
    0x055B846B  mov ebp,[rsi+0x1988] / sub ebp,1 / js

For each: **does it actually skip the Super call, or only skip something else?** Name the field,
offset and owning object for both. If they do NOT gate the Super call, say so — S139 listed them as
the next thing to read and that ranking may be wrong.

---

## PART 2 — the ladder

Enumerate every store to a CMC field between the `+0x12B0` store at `0x055B8414` and the Super call
at `0x055B85C1`, with the same discipline as lane L3 (register tracking to establish `this`; capstone
operands not byte searches; classify GOOD/WEAK/USELESS discriminating power; unconditional vs
branched). Also cover entry..`0x055B840C` if any stores are there.

The goal is a field a live probe can read to distinguish:

- **(a)** `ULokiCMC::PerformMovement` was entered
- **(b)** it got past the HitStop region
- **(c)** it reached the Super call
- **(d)** the engine impl was entered

Say which of (a)–(d) each candidate receipt actually separates. **If no receipt separates (c) from
(d), say so plainly** — that is a real and useful negative.

---

## PART 3 — after the Super returns

Transcribe briefly what happens after the Super call returns (`0x055B85C6` onward). If Loki writes
movement state after Super, that is another readout surface.

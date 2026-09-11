# LANE L3 — TASK A2a: BUILD A PROGRESS LADDER FOR ENGINE `PerformMovement 0x035E9EC0`

Today the only live receipt for "how far did engine `PerformMovement` get" is the `CMC+0x16C8` latch,
which is all-or-nothing. **Find INTERMEDIATE receipts.**

## What to enumerate

Every **store to a CMC field** on the path from `0x035E9EC0` to the `StartNewPhysics` call at
`0x035EB13A`. A CMC field store is a write whose memory operand base register holds the `this`
pointer.

You **MUST do register tracking** to establish which register holds `this` at each point (it is `rcx`
at entry; MSVC will move it — commonly to `rbx`/`rdi`/`rsi`/`rbp` — and it may differ between
blocks). Do NOT assume one register for the whole function; **show your work**.

Take displacements from **capstone OPERANDS**, never from a byte search (a prior byte-pattern attempt
desynced and produced `adc byte ptr [rbp+0x12b0]`).

## For each store report

- address, offset, width, and the value written: constant? computed? from where?
- **DISCRIMINATING POWER — this is the point of the lane.** A store of constant `0` into a field that
  is already `0` is USELESS as a receipt. Classify each as:
  - **GOOD** = writes a value distinguishable from the field's resting/default state
  - **WEAK** = writes a value that may coincide with the default (say what baseline would be needed)
  - **USELESS** = provably indistinguishable
- whether it is **UNCONDITIONAL** on the path from entry to the call, or **inside a branch** (name
  which);
- how far along the path it sits — order them so they form a **LADDER**.

## Two known starting points to calibrate against

    0x035E9F82  mov byte  [rbx+0x703], al    -- early; al is a computed bool from a preceding ucomisd
    0x035EB130  mov dword [rbx+0x3dc], r15d  -- immediately before the call, r15d == 0

Verify both, including that `rbx` really is `this` at each, and establish what `0x703` and `0x3dc`
are.

## Naming

Any store to a field that stock UE would name (`bMovementInProgress`, `LastUpdateLocation`,
`LastUpdateVelocity`, `LastUpdateRotation`, `bDeferUpdateMoveComponent`, ...) is worth naming — but
only **[I]** unless you can tie the offset to a UHT property record. Say which.

## OUTPUT

A **RANKED table** of live-readable checkpoints — offset, what reaching it proves, discriminating
power, and any baseline it requires. Rank by (discriminating power) × (how much of the path it
covers). **Flag explicitly any that need a known non-default baseline to be interpretable.**

# LANE L6 — TASK A4: IS THE LATCH INSTRUMENT ITSELF VALID?

*(session lead's addition; it may dissolve the whole contradiction)*

The entire "`StartNewPhysics` has never run" claim rests on `CMC+0x16C8` reading `0`. The session lead
established (see brief, item 2) that the write at `0x055C2469` is on the `Iterations==0` path ONLY,
and that `+0x16C8` is **cleared-then-set** inside that call rather than being a pure sticky latch.
That raises a question nobody has asked:

> **Does anything else write or clear `CMC+0x16C8`?**

If some routine clears it every frame, then `latch==0` is consistent with `StartNewPhysics` running,
and the contradiction dissolves — and every S139/S140 conclusion resting on it needs re-grading.

## DO

1. **Census every read and write of displacement `0x16C8`** across the ULokiCMC function set and as
   widely as you can. Same method discipline as the `+0x12B0` lane: capstone operands, CFG-based,
   never a byte-pattern search. State your enumeration and that it is a FLOOR on a 55%-decrypted
   image.
   **POSITIVE CONTROL:** your scan must find `0x055C2438` (cmp), `0x055C2441` (store `r8b`) and
   `0x055C2469` (store `1`). If it misses any, the instrument is broken.

2. **Establish what `+0x16B0` / `+0x16C0` / `+0x16C8` are as a group.** The code at
   `0x055C2448`–`0x055C2466` snapshots Velocity (`+0xE8`, 16 bytes) into `+0x16B0` and a qword from
   `+0xF8` into `+0x16C0`, then sets `+0x16C8`. That smells like a saved-state struct with a validity
   flag. If so, **find the CONSUMER** — who reads `+0x16B0`/`+0x16C0` and under what condition?
   **A consumer that clears the flag after use would make the latch a per-frame flag, not a latch.
   This is the crux of the lane.**

3. **Try to name these fields.** Check UHT property records / `binds_members.csv` (`tools/asdump/`)
   for a `ULokiCharacterMovementComponent` property at `0x16B0`/`0x16C0`/`0x16C8`. If they are not
   reflected, say so — **absence of a UPROPERTY is not absence of a field.**

4. **SEPARATELY: re-derive the vtable dispatch.** Verify that `ULokiCMC::StartNewPhysics` really is
   the slot at displacement `0x720` on `ULokiCharacterMovementComponent` — i.e. that `0x035EB13A`'s
   `call [rax+0x720]` on a Loki CMC lands at `0x055C2430` and not somewhere else. `rax` there is
   loaded from `[rbx]` (the object's vptr). Read the vtable at `.rdata 0x088F8570 + 0x720` and report
   the qword; remember `.rdata` in a dumped image holds **ABSOLUTE VAs**, so subtract ImageBase
   `0x7FF608F40000`.
   **Positive control:** read a slot whose answer you already know (e.g. disp `0xAA8` must be
   `0x055B8370`, disp `0x3D0` must be `0x055C2B90`) and report whether they come back right.

5. **Report the VERDICT plainly:** is "latch == 0 proves `StartNewPhysics` never ran with
   Iterations==0" **SOUND**, or is there a clearing path that makes it uninterpretable?

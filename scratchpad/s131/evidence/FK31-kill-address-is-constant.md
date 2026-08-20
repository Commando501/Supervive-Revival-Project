# FK-31 / FK-7 — THE KILL JUMPS TO ONE FIXED ADDRESS, AND IT IS THE SAME ADDRESS EVERY LAUNCH

**S131, 2026-08-20. Offline, from crash minidumps already on disk. Zero launches spent on it** — it
fell out of triaging S131's own launch-1 staging death.

Tools (read-only, re-runnable): `scratchpad/s131/tools/ripfamily.py`, `ripdelta.py`, `modscan.py`.

---

## 1. The measurement

Filter, applied to every `dumps/crashpad-*/reports/*.dmp` on disk: exception code `0xC0000005`,
`ExceptionInformation[0] == 8` (**an execute-access violation**), faulting address `& 0xFFF == 1`.
**31 minidumps match** (unit: minidump files; several are the archiver's DEATH/follow-up pairs of the
same crash, so the number of *distinct crashes* is roughly half that — see §4).

Every matching dump's faulting address is **exactly one of three values**, and which one it is
depends only on the boot session:

| address | dumps | dates |
|---|---|---|
| `0x00007FFD3B400001` | 13 | 2026-08-08 → 2026-08-09 |
| `0x00007FFA42600001` | 11 | 2026-08-12 → 2026-08-15 |
| `0x00007FFB57400001` | 7 | 2026-08-19 → 2026-08-20 |

**[M] Within a boot session the address is bit-for-bit identical across every launch** — while
`SUPERVIVE-Win64-Shipping.exe` and `preloader.dll` are re-based by ASLR on **every** launch. In the
third era the RIP−preloader delta takes four different values (`0xD880001`, `0xB2C0001`, `0xAA40001`,
`0xA970001`) across the four crashes; the RIP does not move.

## 2. It is not an offset from any loaded module either

`RIP − base` for five reference system DLLs, over all 31 dumps:

| reference | distinct values |
|---|---|
| `ntdll.dll` | **3** — `0x2B0001`, `0x330001`, `0x3B0001` |
| `kernel32.dll` | **3** |
| `kernelbase.dll` | **3** |
| `user32.dll` | **3** |
| `combase.dll` | **3** |

Three values each, one per era — i.e. the deltas track the era, not the address. **No reference
module yields a single delta**, so the target is not "module X + constant" for any module in the
process. [M]

**And no module covers it**: the address is inside no loaded module in any of the 31 dumps, and
S131's own crash-era image dump (`dumps/crash-20260820-021637`) has **no executable-region row
covering `0x7FFB57400000`** at all.

⇒ The process jumps to an address that is **not mapped executable**, and the fault is an execute
violation at exactly that address. This is not a corrupted pointer: a corrupted pointer does not
reproduce to the bit across 13 launches.

## 3. What this unifies

The three eras' dumps are drawn from work this project has been tracking as **separate** death
classes:

* **FK-7 / S112 ship-arm deaths** (`crashpad-20260808-*`, `20260809-*`, the `s112p3-trt` / `s112ship`
  arms) — the standing-`.text`-patch kills;
* **FK-31 staging-hazard deaths** (`s127-fk31-staging-death`, `s128-fk31-longpark`,
  `s130-cdopoke-att1`, and S131's launch-1 death) — the ones that fire with only `gft`+`fo` resident,
  before any probe is injected;
* **an S114 FK-13 stage death** and several S115/S121 menu-route deaths.

**All of them land on the one address for their boot session.** ⇒ **[M] one kill routine, not three.**
That is a real consolidation: FK-31 was split out of FK-7 on the (correct, at the time) grounds that
the *window* and the *resident set* differ, and this says the differing preconditions still converge
on the same final act.

⚠ It does **not** say the *trigger* is the same. Two different detections can call one kill routine.
What is measured is the terminal jump, nothing upstream of it.

## 4. Honest limits

* **The dumps are not 31 independent crashes.** `configs/archive-crashdumps.ps1` archives before and
  after a run, so a crash commonly yields a `-DEATH`-tagged archive and an untagged follow-up
  containing the same report. Treat 31 as **files**, and the distinct-crash count as roughly half.
  The per-era *constancy* is unaffected: the eras contain crashes from clearly different sittings.
* **"Per boot" is [I], not [M].** The three groups line up with long date gaps, which is consistent
  with reboots, but no reboot timestamp was checked. What is [M] is that the address is constant
  across launches inside each group.
* **The `& 0xFFF == 1` filter is part of the selection**, so "every matching dump ends in `001`" is
  partly by construction. **The full 64-bit address being identical is NOT selected for** — that is
  the finding.
* Two `0xC0000005` dumps in the corpus (`crashpad-20260814-155319`, `-155530`) do **NOT** match: they
  are read faults (`ExceptionInformation[0] == 0`) at heap addresses. A different class, correctly
  excluded rather than folded in.

## 5. ⚠ A RECORDED DETECTION RULE THAT CANNOT BE APPLIED AS WRITTEN

`CLAUDE.md` says: *"Detect the kill by **fault family** (`RIP == runtime.dll base + 1`, EXECUTE,
`ExceptionInformation[0]==8`), never by elapsed time."*

**[M] `runtime.dll` has NO module entry in any crashpad minidump** — 0 of 14 recent dumps sampled,
against a positive control in the same scan (`preloader.dll` present in 14 of 14). So the
`runtime.dll base` half of that rule **cannot be evaluated from a minidump module list**, and anyone
who tries will find the module missing and may record "the family does not match" — an instrument
artifact of exactly the kind this project keeps cataloguing.

The two halves that ARE checkable — EXECUTE and `ExceptionInformation[0] == 8` — plus the now-known
constant address are a complete and cheaper test. **Restate the rule as: `ExceptionInformation[0]==8`
+ faulting address == the boot session's constant kill address.**

## 6. ★ THE LEVER THIS HANDS US, AND IT IS CHEAP

The kill target is **knowable in advance within a boot session** — read it off the last crash.

That makes a new experiment possible that this project has never been able to run: **map an
executable page at that address before arming.** `VirtualAlloc(0x7FFB57400000, 0x1000,
MEM_COMMIT|MEM_RESERVE, PAGE_EXECUTE_READWRITE)` and write a `ret` at `+1`. If the jump then
*returns* instead of faulting:

* the process may survive the kill outright, and
* the **return address on the stack names the caller** — which is the protector code that decided to
  kill, i.e. the thing FK-10's "Wall #7" (what performs the integrity check) has been trying to find.

⚠ Unknowns to respect before spending a launch on it: the address may already be RESERVED (in which
case `VirtualAlloc` at that base fails and the probe must say so rather than silently continuing);
the jump may be a `call` rather than a `jmp` (then a `ret` is right) or a tail `jmp` (then the stack
top is the *grandparent* frame); and returning into protector code mid-routine may simply crash
somewhere else. **All three are observable outcomes and all three are more informative than the
present state, which is a silent process death.**

★ It needs no `.text` write, no PI hook, and no game knowledge — one `VirtualAlloc` in an injected
DLL. On this project's measured hazard ladder that is the safest class of change there is.

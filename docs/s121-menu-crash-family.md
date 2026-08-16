# S121 — a REPRODUCIBLE menu-idle crash family, twice in one day (2026-08-15)

Successor material for FK-31/FK-32. **Not** FK-7 (that is closed) and **not** the S120
shim-image-scan family. Claims are **[M]** measured / **[I]** inferred / **[S]** speculative.

## The signature — byte-identical across two separate processes

| | run 1 (pid 19620) | run 5 (pid 48604) |
|---|---|---|
| time of death | **T+81 s** | **T+78 s** |
| exception | `0xC0000005` | `0xC0000005` |
| `ExceptionInformation[0]` | `0x8` = **EXECUTE** | `0x8` = **EXECUTE** |
| faulting address | **`0x7FFA42600001`** | **`0x7FFA42600001`** |
| stack top (return addr) | **`0x7FFA415B7374`** | **`0x7FFA415B7374`** |
| `rbp` | `0x537AC9E1` | `0x537AC9E1` |
| `r11` | `0x95654773B3BC` | `0x95654773B3BC` |
| modules loaded | 182 | 221 |

Only `rdx`/`rbx`/`r8`/`r9`/`r10` differ, and those hold high-entropy values consistent with the
protector's MBA obfuscation (FK-10: `not`/`and`/`imul` ≈ 43 % of its instructions).

★★ **The faulting address is IDENTICAL across two processes.** That makes it deterministic rather
than a wild pointer — the same code path, twice.
⚠ **But do NOT phrase this as "despite ASLR".** [M] `ntdll` and `kernel32` have the SAME base in
both dumps, because Windows fixes system-DLL bases per **boot**, not per process, and this address
sits in that zone. The stability is therefore expected, not remarkable, and carries far less weight
than it first appears. (An earlier draft of this file leaned on it; see the shim section for the
discriminator that actually does the work.)

★★ **`RET = KERNEL32.DLL + 0x17374`** [M] — resolved in the 221-module dump; run 1's 182-module
dump could not place it. A KERNEL32 frame as the *only* thing under the faulting instruction is the
`BaseThreadInitThunk` shape [I], i.e. **a freshly created thread faulting on the FIRST instruction
of its start routine.** `rax/rcx/rsi/r12-r15` are all zero, which fits a thread entry.

⇒ **Working characterisation: a thread is created with entry point `0x7FFA42600001`, an address in
no loaded module, and dies immediately.** [I]

## What this is NOT

- ⛔ **Not our S121 backend work.** Run 1 died **before the game issued a single HTTP request**
  (`capture.log` for that run holds exactly one line — the launcher's own probe). The same fault
  then recurred after a full normal menu load. A payload cannot cause a crash in a process that
  never fetched it.
- ⛔ **Not the STATS page or the `Placements` change.** [M] The last UI navigation before run 5's
  death is `WBP_UI_LobbyCarousel_LaunchBanner` at 01:05:38; the crash is at 01:06:32, **54 s later,
  with no CAREER/STATS widget activation in between.** The page was never opened.
- ⛔ **Not the S120 family** (READ fault at `SUPERVIVE base + 0x1000`, `0x1000`-stride registers —
  the `catalog_store_fix` image-scan). Different exception information, different address.
- ⛔ **Not FK-32's `0x0000DEAD` silent kill** — this raises a real access violation and leaves a
  full crashpad minidump.

## ✅ ANSWERED: IT IS **NOT** ONE OF OUR SHIMS [M]

Manual mapping — how this project injects every shim — produces exactly this "executing from memory
with no module entry" signature, so this had to be measured, not assumed. It was, three independent
ways, with `tools/re/exec_regions.py` (read-only `VirtualQueryEx`; pass a faulting address and it
reports the containing region or none):

1. **Our manual maps live in the HEAP range and MOVE with ASLR.** [M] The shim-sized private
   `RWX` regions (0x2E000 / 0x29000 / 0x26000 / 0x6A000 / 0x8D000 — our DLLs are 135–190 KB) sit at
   **`0x1A3…`/`0x1A4…`** in the crashed process and at **`0x0269…`/`0x026A…`** in the live one.
   Different process, different addresses. The fault is at `0x7FFA426…`, a different part of the
   address space entirely.
2. **The fault address is in NO committed executable region** — not in the crash dump's 19, not in
   the live process's 20. Nearest exec region below ends `0x7FFA423ED000`, a **0x213001** gap.
3. **The injector never unmaps.** No `VirtualFree` / `MEM_RELEASE` / `MEM_DECOMMIT` anywhere in
   `tools/inject/main.go`, so a mapped shim cannot vanish and leave a dangling thread entry.

⚠ **State the discriminator precisely.** "The address is identical across two processes" is
explained by `ntdll` and `kernel32` having the **same base in both dumps** — Windows fixes
system-DLL bases per BOOT, not per process. So address stability is not itself mysterious and is
*not* the strong part of the argument. The strong part is (1): **our maps demonstrably move and this
does not, and they are in a different range.**

**Where it actually is:** `ntdll.dll` spans `0x7FFA422D0000 .. 0x7FFA424C9000`; the fault is
`ntdll_base + 0x330001`, i.e. **0x137000 past ntdll's end** — reserved-but-uncommitted space inside
the system-DLL region.

[I] **Leading hypothesis: a protector-created thread.** FK-10 measured `NtCreateThreadEx` as the 4th
entry of a pointer table at `packer0 0x1831c0`, so the protector does create threads; a thread whose
start address is computed into uncommitted space in that zone produces exactly this fault, on its
first instruction, with a bare `BaseThreadInitThunk` frame beneath it. **Not established.**

⚠⚠ **THE INSTRUMENT THAT COULD NOT ANSWER IT, recorded because it nearly produced a wrong claim.**
The fault page is absent from the minidump, which looks like "unmapped" — and a first pass here
concluded exactly that. The **positive control refutes the reading**: the game's own `ImageBase`
also returns "not captured" from the same dump, and that page is certainly mapped. ⇒ **absence from
a crashpad dump says nothing about whether an address was mapped.** Always control a dump read
against an address you know is mapped. The question was settled instead by live `VirtualQueryEx`
(`tools/re/exec_regions.py`), which reports actual region state rather than capture coverage.

## Why this matters

FK-7's corpus was built from deaths that could not be told apart. This one is **reproducible, has a
constant signature, and now has a named frame under it** — the first menu-idle death in this project
with all three. It is a better starting point than any of the artifact-less deaths.

⚠ Frequency, stated honestly: **2 deaths in 5 launches today**, both at the menu around T+80 s. That
is consistent with the project's recorded ~25–30 % per-launch hazard and is **not** a new regression
— but the fixed T+78/81 s window and the identical registers are new information about *what* that
hazard is.

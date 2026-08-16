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

★★ **The faulting address is IDENTICAL across two processes despite ASLR.** That makes it
deterministic, not a wild pointer.

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

## ⚠ What is NOT established, and an instrument that cannot answer it

**Whether the faulting page was mapped.** Manual mapping — how this project injects every shim —
produces exactly this "executing from memory with no module entry" signature, so **"is this one of
our own shims?" is a live and unanswered question.**

⚠⚠ **A dump-capture read CANNOT settle it, and a first pass here got that wrong.** The fault page is
absent from the minidump, which looks like "unmapped" — but the **positive control refutes that
reading**: reading the game's own `ImageBase` from the same dump ALSO returns "not captured", and
that page is certainly mapped. ⇒ **absence from a crashpad dump says nothing about whether an
address was mapped.** Always control a dump read against an address known to be mapped.

**How to actually settle it:** the manual mapper knows where it placed each shim. Log the mapped
base of every injected DLL (`tools/inject`) and compare against `0x7FFA426xxxxx`. A fixed address
across two processes is *itself* mild evidence against a heap manual-map [S], since those are
normally ASLR-scattered — but `NtCreateThreadEx` appears in the protector's own function table
(FK-10, `packer0 0x1831c0`, 4th entry), so a protector-created thread is at least as plausible.

## Why this matters

FK-7's corpus was built from deaths that could not be told apart. This one is **reproducible, has a
constant signature, and now has a named frame under it** — the first menu-idle death in this project
with all three. It is a better starting point than any of the artifact-less deaths.

⚠ Frequency, stated honestly: **2 deaths in 5 launches today**, both at the menu around T+80 s. That
is consistent with the project's recorded ~25–30 % per-launch hazard and is **not** a new regression
— but the fixed T+78/81 s window and the identical registers are new information about *what* that
hazard is.

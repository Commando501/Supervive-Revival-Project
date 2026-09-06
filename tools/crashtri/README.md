# crashtri — offline triage of the SUPERVIVE crash corpus

Stdlib-only Python. **READ-ONLY** on `%LOCALAPPDATA%\SUPERVIVE\Saved\Crashes` (every file is opened
`'rb'`; nothing is ever written into that tree). No live process, no injection.

The corpus is 86 crash folders, each with `CrashContext.runtime-xml` (unwound `PCallStack` +
`SecondsSinceStart`), `UEMinidump.dmp` (~14 MB: exception record, 124 thread contexts, ~7 MB of
memory, and the unwind table in stream 13) and its own `Loki.log`.

```powershell
python harvest.py                        # -> crash_census.csv + family classification of all 86
python mdctx.py   <dump.dmp> [--read=0xADDR,LEN ...]
python deadobj.py <dump.dmp> [<dump.dmp> ...]
python ptrhunt.py <dump.dmp> 0xVALUE [0xVALUE ...]
```

| tool | what it gives you |
|---|---|
| `harvest.py` | every crash's `SecondsSinceStart`, PID, module base, `ErrorMessage`, and the game-relative RVA chain; groups the corpus by chain prefix |
| `mdctx.py` | exception code/address/operands, the faulting thread's full `CONTEXT_AMD64` (GPRs + xmm), module list, and a byte-addressable view of every dumped memory range (`MD.read/q`) |
| `deadobj.py` | for the camera-crash family: the camera manager, `&ViewTarget`, the target pointer, and a scan of the captured window for UObject headers (`vtable@0x00, InternalIndex@0x10, UClass*@0x18, FName@0x20, Outer@0x28`) |
| `ptrhunt.py` | every place in the dump holding a given 8-byte value, split into 8-aligned pointer slots vs unaligned coincidences, each classified stack / heap / module |

`mdctx.MD` is importable; the other three use it.

## ⚠ Bug this replaces

`tools/re/parse_minidump.py` reads `MINIDUMP_THREAD` at the wrong offsets — it takes `Teb@+16` as the
stack base and `StartOfMemoryRange@+24` as `{DataSize, Rva}`. The correct layout is
`Tid@0, Susp@4, PriCls@8, Pri@12, Teb@16, Stack{Start@24, DataSize@32, Rva@36}, Context{DataSize@40, Rva@44}`.
With the wrong offsets 123 of 4009 ranges come back multi-gigabyte, `read()` returns bytes from
arbitrary file offsets, and per-thread `CONTEXT` pointers are garbage. `mdctx.py` uses the correct
offsets and its range table validates clean (0 ranges past EOF, ~6.8 MB total).

The exception-stream context (`stream 6 + 160`) is unaffected and was correct in the old script.

## Self-checks worth keeping

The camera-family register state validates itself three ways before you trust it: `rbx - rdi == 0x420`,
`[rdi]` equals the `.rdata` address `vtables.py` independently names `APlayerCameraManager`, and
`r8 == rbx + 0x10` matches the `lea r8,[rbx+0x10]` in the faulting instruction.

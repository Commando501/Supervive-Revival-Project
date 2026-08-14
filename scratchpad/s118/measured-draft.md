# S118 — measured facts owned by the main session (draft)

All measurements 2026-08-13, local time; `Loki.log` timestamps are **UTC = local + 5 h**.

## 0. The live window (this is what made route A possible)

The game was **still running from the S117 sitting**:

| property | value | source |
|---|---|---|
| PID | 29856 | `Get-Process` |
| start | 2026-08-13 15:16:57 local | `Get-Process` |
| uptime at first read | 02:18:25 | ” |
| module base | **`0x7FF7C7EF0000`** | ” |

`0x7FF7C7EF0000` is **byte-identical to the base recorded in
`fk15-handlenotif-jumptable-20260813.md`**, and `dumps/lobby-dispatch-decrypted/` was
written at 16:13 — i.e. **the same process instance**, so every S117 heap address is
still valid and the decrypted `.text` pages are live. [M]

★ **Reusable:** before re-deriving an ASLR-dependent address, check whether the process
that produced it is still alive. Two hours of "re-derive per launch" work was avoidable
here by one `Get-Process`.

## 1. Positive control — the live `Lobby` object is intact [M]

`Lobby = 0x1D251AA1C80`. Read `+0x88..+0xD8`, and all four validation offsets — **none of
which is part of any search** — reproduce exactly:

| offset | expected | read |
|---|---|---|
| `+0x88` | FString Num=19 (`X-Ab-EnvelopeStart`) | Data=`0x1D2176A1810` **Num=0x13=19** ✓ |
| `+0x98` | FString Num=17 (`X-Ab-EnvelopeEnd`) | Data=`0x1D2176A17B0` **Num=0x11=17** ✓ |
| `+0xA8` | envelope-start value `"LbS"` | Data=`0x1D20C44E140` **Num=4 Max=8** ✓ |
| `+0xB8` | envelope-end value `"LbE"` | Data=`0x1D20C44E120` **Num=4 Max=8** ✓ |

## 2. The dispatcher, disassembled LIVE — mechanism confirmed, one address corrected

`Lobby::HandleNotif` RVA `0x4B02C80`:

```
0x4B02CD8  call 0x8E904F0                       ; hash
0x4B02CE0  lea  rcx, [rip+0x54fb5e9]            ; -> RVA 0x9FFE2D0   (map object)
0x4B02CE9  call 0x8ED6520                       ; Find -> eax = element index | -1
0x4B02CF3  movsxd rcx, eax
0x4B02CF6  shl  rcx, 5                          ; element stride = 32   [M]
0x4B02CFA  add  rcx, qword ptr [rip+0x54fb5cf]  ; -> qword AT RVA 0x9FFE2D0 = element base
0x4B02D01  lea  rcx, [rcx+0x10]                 ; enum byte at element+0x10  [M]
0x4B02D0E  movzx r15d, byte ptr [rcx]
0x4B02D16  dec eax / cmp eax,0x20 / jnbe default
0x4B02D2A  mov  ecx, dword[rdx + rax*4 + 0x4b04978]   ; jump index = enum-1  [M]
```

Both rip-relative displacements resolve to **RVA `0x9FFE2D0`** (verified twice, two
independent arithmetic methods — the first attempt mis-transcribed a digit pair and
produced `0x9FFE270`, which is wrong; recompute, never eyeball).

⚠ **UNRESOLVED COMPLICATION.** `qword[RVA 0x9FFE2D0]` reads **`0x1D255EF1B00`**, and that
memory does **not** decode as `{FString, uint8}` at stride 32. It decodes as **UObjects**:
`+0x00` = `0x7FF7CF5EE7B0`, which I peeked and confirmed is **a vtable (all code
pointers)** [M]; `+0x0C` flags `0x41`; `+0x10` InternalIndex **consecutive** `0x2130,
0x2131, 0x2132, 0x2133, 0x2134`; `+0x18` class ptr; `+0x20` FName. Under investigation.
**Do not write up "the map is at 0x9FFE2D0" as settled until this is explained.**

## 3. ★ The 16 BOUND delegates — COMPLETE (the S117 list was truncated at 12)

Slot = 16 bytes `{void* Data; int32 Num; int32 tail}`; bound = heap ptr + Num>0.
Harness `scratchpad/s118/delegates.py` **self-tests** against 3 known-bound and 2
known-unbound offsets and aborts if they do not reproduce (rules 10/13). Self-test PASSED.

```
+0x12c0  +0x12d0  +0x12e0  +0x1570  +0x1590  +0x15a0  +0x15c0  +0x15d0
+0x15f0  +0x1600  +0x1610  +0x1630  +0x1640  +0x1650  +0x1660  +0x1670
```

**The four the S117 print dropped are `+0x1640 +0x1650 +0x1660 +0x1670`.** [M]
Every one has `Num == 3` and an invocation-list pointer in one tight pool,
`0x1D21663DBA0 .. 0x1D21663F430` (span 0x1890).

★ **Strengthening beyond S117:** S117 scanned ~`+0x12a0..+0x1670` (62 slots = its
"16 bound, 46 unbound"). I scanned **`+0x10c0..+0x19f0`** and the bound set is still
exactly those 16 — so the count is complete over a window ~2.4× wider, not just inside
the original one.

**Newly measured:** `+0x11b0` — the delegate broadcast by **case 8** — is **UNBOUND**,
joining case 19 (`+0x1510`) and case 23 (`+0x1550`). All three known case→delegate
mappings are unbound. [M]

### 3a. Stability control — the reading is not a transient [M]

Re-read at **22:52:21Z**, ~7 min after the first capture (~22:45Z): the delegate bytes are
**identical**, all 16 bound slots reproduce at the same offsets with the same pointers and
`Num=3`, and `+0x1550` re-reads UNBOUND as the internal negative control.
`qword[0x9FFE2D0]` is likewise **byte-identical** (`0x1D255EF1B00`) — so the UObject-shaped
value in §2 is a **stable** datum, not a torn read or a moment of garbage. Whatever
explains it has to explain a stable pointer.

## 4. An instrument artifact I committed and caught (37th instance candidate)

My first extent-finder grew the table through any all-zero slot and reported
**"17 bound, table +0x10c0..+0x1a00"**. The 17th (`+0x1a00`) is **not a delegate**: its
pointer `0x1D2176A1840` lies in a different pool, immediately adjacent to the *known
FString buffers* at `+0x88`/`+0x98` (`0x1D2176A1810`, `0x1D2176A17B0`) — it is a string.

⇒ **All-zero memory is indistinguishable from an unbound delegate slot, so a zero-run
cannot bound this table.** The allocation pool can: the 16 genuine delegates cluster in
0x1890 bytes, the false positive is 17 MB away. **Discriminate by pool, not by run.**

## 5. The push channel is live and can be acted on in this same session [M]

`GET /api/ws/sockets`:

| handle | kind | uptime | pushes |
|---|---|---|---|
| ws1 | messenger | 7171 s | 0 (stable — no reconnect churn; the TEXT heartbeat reply is holding) |
| ws2 | **/lobby** | 7171 s | **36**, last `fk15-dsNotif-fullfidelity` |

`Loki.log`: `Type: ` **41**, `Raw Lobby Response` 61, `Message fragmented` 19.
⇒ the mapping can be tested end-to-end against this very process.

## 6. ⚠ The running server binary is ONE COMMIT STALE

`server/ags.exe` built **15:50 local**; `b926d8f` (which empties `AlreadyProbed`) landed
**16:02 local**. The live `/api/ws/vocabulary` still annotates `matchmakingNotif` as
probed, while `vocabulary.go` at HEAD has `AlreadyProbed = map[string]string{}`.
Functionally harmless (the envelope fix landed earlier in `1f2b06e` and is empirically
present — 41 dispatches), but **reasoning about server behaviour from HEAD source while
this binary runs would give a false reading.** Rebuild before any server-side conclusion.

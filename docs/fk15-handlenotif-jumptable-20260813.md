# `HandleNotif`'s jump table — all 33 cases are real, and the sweep decrypted them

**S117, 2026-08-13.** Answers the question left open by the payload probe: does
`dsNotif` reach a bound handler case, or fall to the default?

## Answer: every one of the 33 has a real case body. None folds to the default.

Dispatch mechanics, decoded from `Lobby::HandleNotif` (`.text 0x04B02C80`):

```
0x4b02d21  lea rdx, [rip - 0x4b02d28]          ; rdx = image base (RVA 0)
0x4b02d2a  mov ecx, dword [rdx + rax*4 + 0x4b04978]  ; table of dword RVAs
0x4b02d31  add rcx, rdx
0x4b02d34  jmp rcx
0x4b02d18  cmp eax, 0x20 / ja 0x4b048f9        ; index = enum-1, 0..32, default 0x4b048f9
```

Reading the 33 dwords at RVA `0x4b04978`:

| property | value |
|---|---|
| entries pointing into `.text` | **33 / 33** |
| entries equal to the default `0x4b048f9` | **0** |
| distinct targets | 32 (idx 17 and 18 share `0x4b03d29` — the banned/unbanned pair) |

⇒ **`dsNotif` has a real case body**, whichever index it occupies. The "does it
reach a bound case" question is answered YES at the dispatcher level.

## ★★ The sweep decrypted the case bodies — 9/33 → 33/33

These pages are demand-decrypted and had **never executed** in any of the 68
existing dumps (`0x4b03000`, `0x4b05000`, `0x4b06000` were 100 % zero). Pushing
all 33 types executed all 33 cases, so a fresh `dumpimage` taken immediately
afterwards captures them:

```
old dumps/tutorial-hero  :  9/33 case bodies non-zero
new dumps/lobby-dispatch-decrypted : 33/33
```

★ **Reusable technique, and it generalises well beyond FK-15: driving a code path
from the backend is a way to FORCE `.text` decryption for offline RE.** The
project's standing framing is that coverage rises with "what the game has run";
this makes that steerable — push the messages, then dump. Banked in
`dumps/lobby-dispatch-decrypted/` (git-ignored, 65.74 % readable).

## The case shape (verified by LIVE disassembly, not by the extractor below)

idx 23, read from the running process:

```
lea rdx, [rdi+0x1550]        ; a delegate member on the Lobby object
lea rcx, [rip -> 0x9FFE6F0]  ; static descriptor (a populated reflection table)
call 0x4b06020               ; shared deserialize + broadcast helper
jmp  0x4b04955               ; epilogue
```

So a case = {delegate, type descriptor} handed to one common helper. Three cases
carry a descriptor of this shape: idx 8 (`Lobby+0x11b0`, desc `0x9FFE810`),
idx 19 (`Lobby+0x1510`, desc `0x9FFE860`), idx 23 (`Lobby+0x1550`, desc
`0x9FFE6F0`).

⚠ **A bulk extraction over all 33 produced several junk rows** (e.g.
`Lobby+0x2d394a4`, `Lobby+0x3aaa351` — rip-relative displacements misparsed as
member offsets, and a uniform-looking `+0x50`/`+0x40` that is probably a
different `lea`). **Only the three rows above, and idx 23 specifically, were
confirmed by live disassembly.** Do not quote the bulk table as measured.

## ⚠ Index → type mapping is NOT established

The enum comes from a runtime `TMap<FString,uint8>` at `.data 0x9FFE2D0`. The
mapping used above ("idx 23 = dsNotif") is inferred from the `.rdata` name order
and is **unconfirmed**. It does not affect the headline result — *all* 33 cases
are real, so `dsNotif`'s is real regardless — but any per-index claim needs the
map read live before it is trusted.

## What remains for `dsNotif`

The case deserializes and broadcasts a delegate. Whether **anything is bound to
that delegate** is the open question, and it needs the live `Lobby` object
address (which resisted the earlier string-scan approach: the FString points at
the buffer start, not at our message, so `findptr` on the message finds nothing).
Options: locate the object via the descriptor tables at `0x9FFE6F0`/`0x9FFE810`/
`0x9FFE860`, or via a vtable scan.

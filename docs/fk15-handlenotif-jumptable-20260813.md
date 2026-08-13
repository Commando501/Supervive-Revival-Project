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
call 0x4ad6020               ; shared deserialize + broadcast helper
jmp  0x4b04955               ; epilogue
```

⚠ **ADDRESS CORRECTION (same day):** this doc first recorded the helper as
`0x4b06020`. That was a transcription slip — the live call is `0x7ff7cc9c6020`
and the module base is `0x7FF7C7EF0000`, so the RVA is **`0x4AD6020`**.
`0x4b06020` is a real but unrelated address, which is exactly why the error was
not self-evident: disassembling it produced plausible-looking code mid-function.
**Verified:** `0x4AD6020` has a proper prologue (security cookie, then a large
stack struct zeroed) — the "zero-init model → deserialize → broadcast" shape.
**Always recompute an RVA from the live VA and the module base; never retype it.**

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

---

## Locating the live `Lobby` object — attempted, NOT achieved

To answer "is anything bound to the delegate", the object's address is needed.
Two routes were tried and both failed; recording them so the next attempt does
not repeat them.

**Route 1 — via the accumulate buffer (`Lobby+0xC8`).** Push a unique sentinel,
find it with `wstrings`, then `findptr` to the FString that owns it. **Failed by
construction:** the FString's Data pointer addresses the *buffer start*, not our
message inside it, so `findptr` on the message address correctly returns 0.

**Route 2 — via the envelope markers (`Lobby+0xA8` = "LbS", `+0xB8` = "LbE").**
This one is self-validating: any `P` where `[P]` points to "LbS" **and**
`[P+0x10]` points to "LbE" is `Lobby+0xA8` by the struct layout. `wstrings "LbS"`
returned 12 candidates; `findptr` was run against the 7 outside the
`0x1D24F130xxx` cluster (that region holds the descriptor-table pointer
`0x1D24F130B20`, so it is a static arena, not the object).

**Result: 0 aligned pointers to any of the 7.** [M]

That negative is informative rather than empty. It means the marker strings we
can see are **not** the allocation an `FString` at `Lobby+0xA8` points at — they
are transient copies (the HTTP header parse, request buffers, log formatting).
Either the object holds a different allocation not among the 12 hits (the search
was capped at 12 — **rerun uncapped first, it is the cheapest next step**), or
the markers are not stored where this analysis assumes.

⚠ Note the assumption still carrying weight: `Lobby+0xA8/+0xB8` being the two
markers is INFERRED from `0x4b35a80`'s two "is this FString empty" tests plus the
observed `envelope=["LbS".."LbE"]` handshake. It is consistent and probably right,
but it has not been confirmed by reading either FString.

**Untried routes, in order of expected cost:**
1. `wstrings "LbS"` **uncapped**, then `findptr` the remaining candidates.
2. The descriptor globals `0x9FFE6F0` / `0x9FFE810` / `0x9FFE860` already hold
   live heap pointers; walk what references them.
3. `usmapdump vtslot` if `AccelByte::Api::Lobby` has a vtable.
4. A shim that captures `rdi` inside `HandleNotif` — decisive, but it is an
   injection and this whole surface has been driven backend-only so far.

# S118 handoff — map the 16 BOUND lobby delegates to their notif types

**Use max 3 subagents.** Copy everything between the rulers as the opening prompt.

---

## THE TASK

`/lobby` server→client push now works end to end (S117). The last measurement showed **16 of the
Lobby object's ~62 delegates are BOUND and 46 are not**, and the two probed so far
(`+0x1550`, `+0x1510`) are **unbound** — which is why pushing `dsNotif` parsed, routed, deserialized
and then did nothing.

**Map those 16 bound delegate offsets back to their notification type names.** They are the only
notif types that can move this client, and they are currently unknown.

Chain: `bound delegate offset` → `jump-table case body that broadcasts it` → `case index` →
`type name`. The first two hops are solved and offline. **The third hop is the open problem.**

---

## READ FIRST (in this order)

1. `CLAUDE.md` → the "Before touching anything WebSocket- / notification- / server-push-shaped"
   block. It is current and dense; everything below expands on it.
2. `docs/method-rules.md` — **rules 10-13 were all added on 2026-08-13 because I broke them that
   same day.** Read them as live hazards, not history.
3. `docs/fk15-delegate-binding-20260813.md` — the delegate result and how the live object was found.
4. `docs/fk15-handlenotif-jumptable-20260813.md` — the jump table + the decrypted-pages win.
5. `docs/fk15-ws-push-audit.md` — why FK-15 was refuted (context; skim).

---

## FACTS YOU CAN BUILD ON (all measured 2026-08-13)

**Jump table** — `Lobby::HandleNotif` `.text 0x04B02C80`:
```
rdx = image base (RVA 0);  table = 33 dword RVAs at .text 0x4b04978
index = enum-1, bounded 0..0x20;  default = 0x4b048f9
```
All 33 entries point into `.text`; **none** is the default. idx 17/18 share `0x4b03d29`.

**Case body shape** — each case is `{delegate, type descriptor}` → one shared helper:
```
lea rdx, [rdi + <DELEGATE OFFSET>]     <-- this is the mapping key
lea rcx, [rip -> <descriptor>]
call 0x4AD6020                          <-- shared deserialize+broadcast helper
```
⚠ The helper is **`0x4AD6020`**. An earlier note said `0x4b06020`; that was a retyped RVA and is
wrong (corrected in `a75cdc5`). Recompute RVAs as `liveVA - moduleBase`; never retype one.

**Decrypted dump** — `dumps/lobby-dispatch-decrypted/SUPERVIVE-Win64-Shipping.dump.exe`.
All 33 case bodies are readable there (**9/33 → 33/33**) because the S117 sweep executed them.
Older dumps have those pages 100 % zero. ★ Use this dump for the jump-table work; no live process
needed for hops 1-2.

**Finding the live Lobby (only needed for hop 3, route A):**
`Lobby = 0x1D251AA1C80` was the S117 address — **ASLR-dependent, re-derive every launch.**
Signature: an `FString` whose data is `"LbS"` with, 16 bytes later, an `FString` whose data is
`"LbE"`, **in the heap range `0x1D2…`** (a module-`.data` match is the static default pair, not the
object — both exist). Validate on offsets that were *not* part of the search before trusting it:
```
+0x88  FString Num=19 -> "X-Ab-EnvelopeStart"     +0x98  Num=17 -> "X-Ab-EnvelopeEnd"
+0xA8  Num=4  -> "LbS"                            +0xB8  Num=4  -> "LbE"
```
Delegate slot = 16 bytes; **bound = non-null heap ptr + non-zero count; unbound = all zero.**

⚠ **Only 12 of the 16 bound offsets were recorded** (`+0x12c0 +0x12d0 +0x12e0 +0x1570 +0x1590
+0x15a0 +0x15c0 +0x15d0 +0x15f0 +0x1600 +0x1610 +0x1630`). **Re-enumerate to get all 16** — the
print was truncated at 12, which is exactly the class of error rule 13 is about.

---

## THE OPEN PROBLEM: index → type name

The enum comes from a **runtime `TMap<FString,uint8>` at `.data 0x9FFE2D0`**, populated at init.
`.rdata` name order (`0x8601A20`..`0x8602730`, 33 names, enumerated in
`server/internal/lobby/vocabulary.go`) *probably* matches the enum, but **that is INFERRED and has
never been verified.** Every per-index claim in the S117 docs carries that caveat.

Two routes:
- **A (live):** read the `TMap` at `.data 0x9FFE2D0` — pairs are 32 bytes with the `uint8` at
  `+0x10` (from `mov ecx,[rcx+rax*8]`… see `0x04b02cf3-0x04b02d0e`). Needs a running client.
- **B (offline):** find the code that populates it and read the literal order.

⚠ **Do not simply assume `.rdata` order and proceed.** If it is wrong, every type name in the
output is wrong and looks fine.

---

## SUGGESTED 3-AGENT SPLIT (all offline except where noted)

- **A — jump-table extraction.** From the decrypted dump, disassemble all 33 case bodies and emit
  `case index → delegate offset → descriptor address`. ⚠ A crude bulk extractor already produced
  junk rows once (rip displacements misparsed as member offsets, e.g. `Lobby+0x2d394a4`); verify
  each row decodes as a real `lea rdx,[rdi+imm]` and report a confidence column.
- **B — the index→type map.** Resolve route A or B above. Deliver the 33-entry mapping **with its
  evidence**, and say explicitly whether it confirms or refutes `.rdata` order.
- **C — subscriber identity.** For each bound delegate, what bound it and what does the subscriber
  do? Each bound slot holds a heap ptr + `entries=3`. Also pull each type's
  `AccelByteModels*Notice/Notif` field list from `tools/usmapdump/schema.txt` (reflected structs =
  ground truth; ⚠ FK-14: container inner + enum underlying types are untrustworthy, scalars and
  names are fine).

Then combine: **the 16 bound offsets → type names → their exact payload structs** = the shortlist
of notifs that can actually drive this client, ready to push.

---

## HAZARDS THAT COST TIME ON 2026-08-13 — DO NOT REPEAT

1. **Self-test every harness before believing it.** A `findptr` sweep reported "0 hits [M]"; it was
   a grep that missed the leading `@` in `    @0xADDR`. Published, then retracted. Feed the harness
   something you have already proved is present.
2. **`rg` is NOT on PATH in the background shell** (it is in the foreground one). Use `grep`, and
   `command -v` first.
3. **`Loki.log` is UTC; `ags`/PowerShell are local (UTC = local + 5 h).** State the timezone
   whenever correlating a log line with a deploy.
4. **An absent error line is only evidence if it can be printed.** The `Error; Detected of type
   notif but no specific handler case assigned` strings go through a virtual on `Lobby+0x218`, not
   `UE_LOG`. Their absence proves nothing. `Type: %s` is logged **before** the handler lookup — a
   bogus type produces the identical trace. **Send an impossible input to test any detector.**
5. **Don't conclude before the falsifying search returns.** Two claims ("only one candidate
   matched", "adjacency is not real") were written early and both were wrong.
6. **Count tokens, not substrings.** `dsNotif` "appears 10×" — 9 are inside `…FriendsNotif`.
   `rematchmakingNotif` contains `matchmakingNotif`.
7. Don't uncap-forget: `wstrings` defaults hid 15 of 27 hits and sent a whole scan down a hole.

---

## CURRENT STATE

- Branch `dedicated-server-stub`, pushed through `eefedf5`. Working tree clean apart from
  untracked `docs/relaunch*.log` scratch (delete once the game is closed).
- `server/internal/lobby/`: envelope wrapping in `ws.Conn.WriteText`, `enableTextHeartbeatReply=true`,
  `enableTargetedResync=true`, push console (`/api/ws/{sockets,preview,push,sweep,vocabulary,drop}`
  + admin "WS Push" tab), `vocabulary.go` (33 types), 58 tests green.
- Logging: `configs/set-log-verbosity.ps1 -Preset Ws` — **`LogAccelByteLobby=VeryVerbose` is what
  makes the lobby narrate itself**; `LogAccelByte` alone is NOT a substitute.
- To relaunch with shims: elevated PS, `.\configs\launch-redirect.ps1`. ⚠ Quote the script path in
  `Start-Process` (paths contain spaces; unquoted args split silently — bit twice).
- ⚠ `AlreadyProbed` in `vocabulary.go` is deliberately EMPTY: the historical `matchmakingNotif`
  record was void (unwrapped, never dispatched). **`matchmakingNotif` is fully re-testable.**

## THE INVERSION THIS ENABLES

Every probe in this project's history — the five from 2026-06-29 and the S117 33-type sweep —
picked notif types out of a string table and hoped. **The 16 bound delegates are the ones with a
listener.** Finish this mapping and the next push is chosen from evidence instead of a name list.

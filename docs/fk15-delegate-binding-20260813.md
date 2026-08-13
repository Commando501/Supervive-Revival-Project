# The `dsNotif` delegate is UNBOUND — nothing listens

**S117, 2026-08-13.** Closes the last question of the FK-15 chain: the notif is
received, envelope-stripped, parsed, routed to a real case, deserialized and
broadcast — into a delegate with no subscribers.

## Finding the live `Lobby` object

`Lobby = 0x1D251AA1C80` (this session; ASLR-dependent, re-derive per launch).

Located by the structural signature the constructor guarantees: an `FString`
whose data is `"LbS"` with, exactly 16 bytes later, an `FString` whose data is
`"LbE"`. Only one candidate of 26 matched. **Validated on four independent
offsets before use** — none of which were part of the search:

| offset | expected (from the ctor at `.text 0x4AF2270`) | read |
|---|---|---|
| `+0x88` | `FString "X-Ab-EnvelopeStart"` (18+1 chars) | Num=**19**, data → `…elopeStart` ✓ |
| `+0x98` | `FString "X-Ab-EnvelopeEnd"` (16+1) | Num=**17**, data → `…elopeEnd` ✓ |
| `+0xA8` | envelope-start VALUE | Num=4, data = `4C 00 62 00 53 00 00 00` = `"LbS"` ✓ |
| `+0xB8` | envelope-end VALUE | Num=4, data = `4C 00 62 00 45 00 00 00` = `"LbE"` ✓ |

⚠ The earlier failed hunt was **not** because the object was hard to find — it was
a grep bug in the harness (see method rule 13). The same scan, with a parser
self-test, found it on the first pass.

## The delegate table: 16 bound, 46 unbound

A delegate slot is 16 bytes; **bound** = non-null heap pointer + a non-zero count,
**unbound** = all zero. Over the region scanned:

```
BOUND   : 16   (every one with entries=3)
          +0x12c0 +0x12d0 +0x12e0 +0x1570 +0x1590 +0x15a0 +0x15c0 +0x15d0
          +0x15f0 +0x1600 +0x1610 +0x1630 ...
UNBOUND : 46   including +0x1550 and +0x1510
```

★ **The 16 bound slots are the internal positive control.** They sit on the same
object, read at the same instant, through the same tool — so "all zeros" is a real
unbound reading and not a failed peek. This is the control the earlier work in
this session kept omitting.

## Result

- **`Lobby+0x1550` — the delegate broadcast by jump-table case 23 — is UNBOUND.** [M]
- **`Lobby+0x1510` — case 19's delegate — is UNBOUND.** [M]

⇒ Pushing that notif can never produce an effect in this build. The route is
closed at the client's **subscription** layer, not at routing, parsing or
deserialization — all of which were proven working earlier in this chain.

⚠ **Scope:** "case 23 == `dsNotif`" is still INFERRED from `.rdata` name order.
What is measured is that *the delegate case 23 broadcasts* is unbound. The
`dsNotif` label rests on the ordering assumption; the unbound fact does not.

## ★ The actionable inversion

The 16 **bound** delegates are the notification types Loki actually subscribes to,
and they are exactly the ones worth pushing. Mapping those offsets back to their
case indices (each case body does `lea rdx,[rdi+<offset>]`, already extractable
from the now-decrypted `dumps/lobby-dispatch-decrypted/`) yields the shortlist of
notifs that can actually move the client.

**That is the next step, and it inverts the whole approach**: stop pushing types
chosen from a string table, and push the ones with a listener.

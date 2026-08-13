> ⚠⚠ **PARTIALLY SUPERSEDED (S118, same day) — read
> [fk15-bound-delegate-map-20260813.md](fk15-bound-delegate-map-20260813.md) first.**
> The headline **STANDS**: `dsNotif`'s delegate is unbound and nothing listens. Three things
> below are wrong or incomplete:
> 1. **"16 BOUND … 46 UNBOUND" is wrong on both counts.** The scan stepped **0x10**, but
>    members also sit at offsets ≡ 8 (mod 16). At 8-byte stride there are **23** bound
>    slots, and one of the missed ones (`+0x228`) is `disconnectNotif` — a real notif
>    delegate, so the miss changed a conclusion, not just a tally.
> 2. **The printed bound list is truncated at 12 of 16 and ends in a literal `…`.** Four
>    of the hidden offsets are four of the seven answers.
> 3. **"entries=3" is NOT a subscriber count.** The record is single-cast `FDelegateBase`
>    `{void* Alloc; int32 DelegateSize; pad}`; `3` is an allocation size in 16-byte units,
>    identical on every bound slot. `+0xC` is padding holding stale heap garbage.
>
> Also: "case 23 == `dsNotif`" is no longer inferred — S118 **measured** it.

# The `dsNotif` delegate is UNBOUND — nothing listens

**S117, 2026-08-13.** Closes the last question of the FK-15 chain: the notif is
received, envelope-stripped, parsed, routed to a real case, deserialized and
broadcast — into a delegate with no subscribers.

## Finding the live `Lobby` object

`Lobby = 0x1D251AA1C80` (this session; ASLR-dependent, re-derive per launch).

Located by the structural signature the constructor guarantees: an `FString`
whose data is `"LbS"` with, exactly 16 bytes later, an `FString` whose data is
`"LbE"`.

⚠ **CORRECTION to this document's first draft:** it said "only one candidate of 26 matched" — written
before the scan finished. **Two** matched. They are trivially separable, and the separation is the
point:

| P | region | verdict |
|---|---|---|
| `0x1D251AA1D28` | **heap** (`0x1D2…`) | a live object's field ⇒ **the Lobby** |
| `0x7FF7D1EF1A18` | **module `.data`** (RVA `0xA001A18`) | a static default LbS/LbE pair ⇒ not an instance |

Both genuinely point at `"LbS"` and, 16 bytes on, `"LbE"` (both buffers read and confirmed). The
discriminator is the **address range**, not the structure. **Do not assert a unique match before the
search that could falsify it has finished.**

★ This also corrects a note in `fk15-handlenotif-jumptable-20260813.md` claiming the LbS/LbE
**adjacency is not real** — generalised from one sample (`0x9FFEBD0`, whose next FString is
`"friends"`). At RVA `0xA001A18` the pair *is* adjacent. Adjacency holds in some tables and not
others; neither direction is a rule.

**Validated on four independent offsets before use** — none of which were part of the search:

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

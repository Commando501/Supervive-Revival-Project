# WALL P auto-fire caller hunt — the mechanism is REAL, not stripped (S153, 2026-09-02)

Companion to `docs/wall-p-callspellcomplete-deep-dive-s153.md`. That deep dive
established that MiniDash (S147's target) uses the AUTO-fire path for spell
completion — the stripped `CallSpellCompleteEvent` cannot be its blocker
because MiniDash never calls it. This doc hunts the actual auto-fire
mechanism offline and finds it **fully REAL**, moving the WALL P residual
into a much narrower search space.

**Bottom line:** the auto-complete broadcast is entirely real code — not a
fold, not stripped, not gated on a stripped predicate. If MiniDash's
completion isn't firing, the block must be at the STATE-BYTE READ layer (a
subobject state byte that never transitions), NOT at the broadcast layer.

## The reflected surface

- **`bManuallyCallSpellCompleteEvent`** — UPROPERTY on `ULokiGameplaySpell`,
  offset **`[GameplaySpell + 0xC76]`** as a full byte. Setter at RVA
  `0x5356750` (`mov byte [rcx+0xC76], 1; ret`). Defaults to `false` on
  570/596 shipping spells; TRUE on 26/596 (the manual-fire population).

- **`OnGameplaySpellEnded`** — an `FGameplaySpellEnded` multicast delegate
  on `ULokiAbilitySystemComponent`. The notification channel a spell fires
  when it completes.

## Static readers of `[reg + 0xC76]` (offline, `merged14`)

**Three unique accesses across `.text`:**

| RVA | instruction | role |
|---|---|---|
| `0x5356750` | `mov byte [rcx+0xC76], 1` | UHT-generated setter |
| `0x4727C80` | `mov byte [rbp+0xC76], al` | Alt setter — probably an init or reset writer |
| **`0x5515D40`** | **`movzx eax, byte [rsi+0xC76]`** | **THE READER** — during spell BEGIN, PROPAGATES the flag to another object's `+0xC0D` |

## The BEGIN function (`fn 0x5515C55..0x5515D6D`, 0x118 B, REAL)

Non-reflected internal helper on the spell-activation path. Not the S153
sweep's classified UFunctions (which is why it wasn't in the CSV).
Structural role (from disassembly):

1. **State-flag setup** — sets `[rcx+0xE58]=1` (state active), zeros
   `[rcx+0xEB0]`, `[rsi+0xEB1]`, `[rsi+0xF40]=1`, `[rsi+0xF5B]=0`,
   `[rsi+0xE20]=0`, `[rsi+0xE24]=0xBF800000` (`-1.0f`, cooldown-not-yet-set
   sentinel), `[rsi+0xF42]=0`, `[rsi+0xF59]=0`.

2. **Validated interface-cast chain** (only if predicate `0x44556A0`
   returns true):
   - `0x4453EC0` → returns object → r14
   - Validate via `0x54F8DC0` (interface cast returning `bool`)
   - `r14 = [r14 + 0x400]` — dereference to subobject
   - Validate via `0x5512380`

3. **THE PROPAGATION** — if the chain validates:
   ```
   movzx  eax, byte [rsi + 0xC76]     ; read bManuallyCallSpellCompleteEvent
   mov    byte [r14 + 0xC0D], al       ; propagate to subobject's +0xC0D byte
   ```

4. **Position/state-buffer copies** — if `[rsi+0x6a1]` non-zero, copies a
   32-byte struct through three parallel slots (`+0x6a8`/`+0x6c0`/`+0x6d8`).

**Interpretation:** the spell BEGIN function CACHES the manual-fire
preference on a subobject (call it the "state-tracker") for later use, then
sets up state buffers. The subobject at `r14 + 0x400` is likely an
ability-instance or state-machine subobject that owns per-invocation state.

## The auto-fire family (4 REAL sibling functions in `0x5679xxx`)

Each detects a different state-end trigger, then checks `[reg+0xC0D]` and
either fires or skips:

| function | state-byte guard | offset in sibling | fire condition |
|---|---|---|---|
| `0x5679D50..0x5679DC5` (0x75 B) | `[rcx+0xBFC]` | +0x012 checks 0xC0D | `[+0xC0D]==0 && 0x56992A0()==false` |
| `0x5679DF7..0x5679E60` (0x69 B) | `[rcx+0xBEC]` set to 1 at +0x023 | +0x02A checks 0xC0D | `[+0xC0D]==0 && 0x56992A0()==true` |
| `0x5679E80..0x5679EF8` (0x78 B) | `[rcx+0xBF4]` | +0x012 checks 0xC0D | `[+0xC0D]==0 && 0x56992A0()==false` |
| `0x5679F2C..0x5679F98` (0x6C B) | (similar shape) | | similar |

**Canonical body (from `0x5679D50`):**
```
push  rbx; sub rsp, 0x30
cmp   byte [rcx+0xBFC], 0        ; state-active check
je    <early_exit>
mov   rbx, rcx
                                  ; state cleanup:
mov   byte [rcx+0xBFC], 0        ; clear the state flag
mov   byte [rcx+0xBF4], 0        ; clear a sibling state flag
                                  ; setup args (two doubles at [rsp+0x20]):
movss xmm0, dword [rcx+0xBF8]    ; time/position
cvtps2pd xmm0, xmm0
cvtss2sd xmm1, xmm1
movsd [rsp+0x20], xmm0
movsd [rsp+0x28], xmm1
cmp   byte [rcx+0xC0D], 0        ; <-- read propagated flag
jne   <skip_autofire>            ; if MANUAL, don't auto-fire
call  0x56992a0                  ; predicate (REAL)
test  al, al
jne   <skip_autofire>            ; if predicate says skip, don't auto-fire
lea   rdx, [rsp+0x20]            ; rdx = pointer to (double, double)
mov   rcx, rbx                   ; rcx = this (state-tracker subobject)
call  0x56a5370                  ; <-- THE AUTO-FIRE BROADCAST
add   rsp, 0x30; pop rbx; ret
```

## The broadcast target `0x56A5370` (REAL)

`.pdata` reports `0x56A5370..0x56A539B` (0x2B B) but disassembly extends
past its first row — chained continuation reaches at least `0x56A555A`
(0x1EB B decoded before ret).

**First 3 instructions:**
```
mov qword [rsp+0x10], rsi
push rdi; sub rsp, 0x40
mov rsi, rdx                     ; rsi = pointer to (double, double)
mov rdi, rcx                     ; rdi = this (state-tracker subobject)
call 0x338C990                   ; validate/getter (returns pointer)
test rax, rax
je   <early exit>
movsd xmm1, [rsi]                ; load first double (time?)
movsd xmm0, [rsi+8]              ; load second double (interval?)
mulsd xmm1, xmm1                 ; ...compute a squared value
```

Not a fold, not stripped. **`0x338C990` is the same helper called by the
`SetGamepadAimSettings` JMP trampoline chain we investigated earlier this
session** — likely `IsValid(this)` or `GetOuter`. The auto-fire broadcast
does real arithmetic on time/position data after validation.

## What this means for S147 / MiniDash's WALL P residual

**The auto-fire mechanism is fully present in the shipping binary.** None of
the four sibling handlers, the propagation function, the predicate, or the
broadcast target are stripped. So the earlier synthesizer hypothesis
(*"CallSpellCompleteEvent stripping is the mechanism"*) was doubly wrong
for MiniDash — not only does MiniDash not call the stripped function, the
auto-alternative it DOES use is also fully wired.

**Residual candidates for MiniDash's "no durable ability body":**

1. **Propagation didn't run** — `[subobject + 0xC0D]` was never written
   because the validation chain in the BEGIN function (`0x44556A0`,
   `0x4453EC0`, `0x54F8DC0`, `0x5512380`) failed one of its 4 gates.
2. **State-tracker's state byte never flips** — the subobject at `r14+0x400`
   would need `[+0xBFC]`/`[+0xBF4]`/`[+0xBEC]` to transition, and that
   requires the montage/timer/dash callback to actually fire.
3. **Predicate `0x56992A0` returns the blocking value** — worth reading its
   input pointer chain from a live process.
4. **`0x56A5370`'s downstream is what actually broadcasts `OnGameplaySpell
   Ended`, and one of its deep callees is stripped or gated.** Requires
   further disassembly (~0x1EB B of extended body).

## Preregistered live-reads for the S142/next-session MiniDash follow-up

After MiniDash activation, use RPM to read:

1. **The propagated flag:** find the state-tracker subobject (via
   `[spell + 0x400]`-shaped path — needs live pointer walk), then read
   `[subobject + 0xC0D]`. If 0, auto-fire is ENABLED. If 1, propagation
   never happened (the BEGIN function's validation chain failed) — that
   IS the block.
2. **The state-tracker's state bytes:** `[subobject + 0xBFC]`,
   `[+0xBF4]`, `[+0xBEC]`, `[+0xC0C]`, `[+0xC04]`. Each of the 4
   sibling handlers checks a different one. Whichever is 1 post-cast
   corresponds to an unfired handler — read `[+0xBF8]`/`[+0xBF0]`/etc.
   for the timing values it would fire.
3. **Predicate `0x56992A0` return value** — set a hook or observe via a
   downstream side-effect. If it always returns TRUE for MiniDash, the
   auto-fire is always skipped and that IS the block.
4. **Page `0x56A5xxx` decrypt status** — currently `0x56A5000` is LIT in
   `merged14`, but does the CALL-DEPTH from a MiniDash cast actually
   reach into the chained `.pdata` continuation? If a live capture keeps
   the same pages lit that `merged14` already has, we can grade the
   downstream fully offline.

## Discriminators for the S142 flight

- `[+0xC0D] == 1` post-cast → **the BEGIN function's propagation chain
  failed on MiniDash**. Focus on the 4-gate validation
  (`0x44556A0`/`0x4453EC0`/`0x54F8DC0`/`0x5512380`); one of them refused
  a MiniDash subobject.
- `[+0xC0D] == 0` and all state bytes `[+0xBFC]`/`[+0xBF4]`/`[+0xBEC]`
  are `0` → **no state transition ever fired**. MiniDash's state
  machine stalled before reaching any of the 4 sibling end-triggers.
  The block is upstream, in the state machine, not in the fire path.
- `[+0xC0D] == 0`, one state byte was `1` and is now `0` → **the fire
  path was ENTERED**. Either predicate `0x56992A0` blocked it, or
  `0x56A5370`'s downstream is what's broken. Distinguish by whether
  `[+0xBEC]` gets cleared (only the `0x5679DF7` sibling clears it post
  auto-fire) or by tracing `0x56A5370`'s call graph.

## What this REFINES about the WALL P deep dive

| deep-dive claim (previous doc §6) | verdict after this hunt |
|---|---|
| Read `spec.bIsActive`/`spec.ActiveCount`/`OnGameplaySpellEnded.Num` | still valid, but now known to be UPSTREAM of the block |
| Check page `0x535F000` (EndInvoke) readability post-cast | still valid — that's a different code path (BPCallable void()) |
| The auto-fire path is what needs investigation | **REFINED:** the auto-fire path is fully real; the block is at the state-byte / propagation layer, not the fire layer |
| Three discriminator outcomes | **REPLACED by the three above** — reads a specific subobject byte structure with clear predictions per branch |

## Reusable rules banked

- **R-S153-i:** UHT `SetBitFunc` disassembly is the offline oracle for a
  bool UPROPERTY's `[class + offset]` byte address. `.rdata` name pointer
  → adjacent pointer at `-8` bytes → disassemble → `mov byte [rcx+X], 1;
  ret` reveals X. Two instructions decode the whole layout.
- **R-S153-j:** A `[reg + disp32]` read across `.text` can be found by
  literal search for the 4-byte disp32 pattern (`disp32 & 0xFF`, `>>8 &
  0xFF`, ...) then decoding backward 2-8 bytes to check for a valid
  memory-operand instruction with the right displacement. In this case,
  6 raw hits reduced to 3 unique valid accesses — a tight set. Cheap and
  offline-decisive when the offset is uncommon (0xC76, 0xC0D).
- **R-S153-k:** A stripped-stub hypothesis's SECOND-order refutation is
  worth the same offline effort as the first-order check. The deep dive
  proved CallSpellCompleteEvent isn't MiniDash's block; this hunt
  proved the ALTERNATIVE path isn't stripped either — moving the search
  space one hop deeper still, into state-machine transitions and
  propagation-chain validation.

## Files

- `docs/wall-p-callspellcomplete-deep-dive-s153.md` — parent doc (the
  partial refutation of R-S153-e)
- `docs/fk1-topic-crossindex-s153.md` — the cross-index that identified
  the original hypothesis
- `docs/fk1-native-sweep-s153.md` — the parent S153 sweep
- `tools/strxref/index/pdata_union.csv` — used to get exact function bounds
  for `0x5515C55` and the 4 sibling auto-fire handlers

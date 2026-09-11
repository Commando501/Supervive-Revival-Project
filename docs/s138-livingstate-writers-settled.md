# S138 — the writers of `LivingState`: nothing can set Alive, and the bridge is a stripped fold

Written 2026-08-23. Offline: zero launches, zero injections, zero `.text` writes. Two lanes, each
adversarially verified by independently-written tooling. Predecessor:
`docs/s138-livingstate-sweep-settled.md` (the live sweep that produced the question).

---

## 0. HEADLINE

**[M] `ALokiCharacter::LivingState` cannot become `Alive` on this client.** Three independent
closures, each with controls:

1. **Only TWO native writers exist in the decrypted image, and BOTH write literal `0` = Dead** —
   the constructor's zero-init and a reset/recycle virtual. Nothing writes `1`.
2. **The bridge from the state machine to the character is a STRIPPED VOID FOLD.**
   `ULivingStateMachine::RequestMoveTowardAlive` is **REAL** — but
   `ALokiCharacter::OnLivingStateMachineStateChanged`, the callback that would carry the machine's
   result onto the character's byte, has impl **`0x0F7EC20`** = `C2 00 00` = `ret 0`.
3. **The reflection-side writer is replication, and there is no NetDriver.** The property is
   `CPF_Net | CPF_RepNotify | CPF_NativeAccessSpecifierPrivate` with **no** Blueprint access and no
   config, so the only reflected writer is `FRepLayout` on the receive path — which never runs here
   (`World NetMode = Standalone` in **9/9** client logs; `NetDriver` **0** occurrences, against a
   passing control where it *does* appear 42-files'-worth in the `ds-server-backup` logs).

★★ **The honest prior was confirmed but NOT where it was expected.** The `TeamStates` precedent
predicted "the writer is a stripped server-authority stub". The *writer* isn't stripped — the
**state machine is fully real** and the **bridge out of it** is the fold. That is a different and
more informative shape than the prior, and it is why the prior had to be tested rather than assumed.

---

## 1. THE PROPERTY [M]

UHT `FEnumPropertyParams` at `.rdata 0x088D90B0`, byte-identical in both images:

| field | value |
|---|---|
| `NameUTF8` | `LivingState` |
| `RepNotifyFuncUTF8` | **`OnRep_LivingState`** |
| `PropertyFlags` | **`0x0040000100000020`** = `CPF_Net \| CPF_RepNotify \| CPF_NativeAccessSpecifierPrivate` |
| `GenFlags` | `0x1E` = Enum · underlying **`uint8`** (paired `FBytePropertyParams` names `UnderlyingType`) |
| `Offset` | **`0x1090`** |

**No `BlueprintVisible`, no `BlueprintReadOnly`, no `Edit`, no `Config`/`GlobalConfig`. `private`.**

Owner is `ALokiCharacter`, index 148 of its 216-entry `PropPointers` array — and the refuter pinned
that by a **stronger route than the lane used**: the owning `FClassParams 0x088DC130`'s
`ClassNoRegisterFunc 0x052F01E0` literally loads `L"/Script/Loki"` + `L"LokiCharacter"`.

★ **The flag decoder is proven discriminating, not printing a constant** — over the same 216
records: 58 distinct flag words, `BlueprintVisible` 76, `Edit` 100, `Config` **0**,
`Net∧RepNotify` 9 of which exactly **1** also has `BlueprintVisible`. Sibling controls in the same
pass: `OutOfBoundsBufferTimeRemaining` (Net|RepNotify **+BlueprintVisible|ReadOnly**),
`CustomAnimationState` (Net **without** RepNotify), `Experience` (Net|RepNotify|**Protected**).

**The enum, settled three independent ways.** Live (`FEnumProperty::Enum` → `ELivingState`), the
UHT record, and — best — **the shipped state classes writing their own tag** into
`ULivingState::LivingState @ +0x30`:

    ULokiCharacterLivingStateDead::ctor    0x0559F540  c6 43 30 00   -> 0
    ULokiCharacterLivingStateAlive::ctor   0x0559F510  c6 43 30 01   -> 1
    ULokiCharacterLivingStateKnocked::ctor 0x0559F570  c6 43 30 02   -> 2

⇒ **Dead = 0, Alive = 1, Knocked = 2.** A three-way, two-sided control that needs no live process.

---

## 2. THE WRITER TABLE [M, floor]

Method: `0x1090 > 0x7F` so every reference must contain the literal bytes `90 10 00 00`. Byte-scan
the union `.text` → **147 hits**, resolve each instruction boundary by consensus over long backward
linear decodes → **140 genuine references (130 memory + 10 immediate)**, 7 correctly rejected
(4 rel32 displacements + 3 copies of `mov dword [rbp-0x70],0x10`).
Of the 130 memory references, **53 are writes; exactly 5 are byte-width** — the only width that can
touch a `uint8`:

| # | address | instruction | containing function | writes | grade |
|---|---|---|---|---|---|
| **W1** | `0x0559E93C` | `mov byte [r14+0x1090], bpl` | `ALokiCharacter::ALokiCharacter` `0x0559E180` | **literal 0 = Dead** (`xor ebp,ebp`) | REAL |
| **W2** | `0x055B75E9` | `mov byte [rcx+0x1090], sil` | vtable slot 244, entry `0x055B75C0` (reset/recycle) | **literal 0 = Dead** (`xor esi,esi`) | REAL |
| — | `0x04840CBE`, `0x04858B36`, `0x0485D955` | `mov byte [rbp+0x1090], sil` | **stack frames, not this object** | 0 | — |

⇒ **NOTHING IN THE DECRYPTED IMAGE EVER WRITES `1`.** There is also **no read-modify-write** byte op
at `+0x1090` anywhere (no `or byte [x+0x1090],N` setter) — a check the lane did not claim and the
refuter added.

★ W1 is the mechanism behind the live sweep: it is why all 6 live characters **and all 30 CDOs**
read Dead. Dead is not "set"; it is the constructor's zero and nothing ever changes it.

★ The refuter independently followed the **31 pointer-producing sites** (`lea`/`add` yielding
`&obj+0x1090`) that appear in no table — all escape into CoreUObject helpers, **no byte store** —
and checked all 20 non-stack wide writes per-site: none is on an `ALokiCharacter` surface page.

⚠ **This is a FLOOR, not a census.** `.text` is only **55.49 %** decrypted in the union image
(16,802 / 30,281 pages). A writer could exist in the dark 44.5 %. Both the lane and its refuter
inherit exactly this bound and both say so.

---

## 3. `OnRep_LivingState` WRITES NOTHING [M]

    0x055B7EE0  mov   rax,[rcx]                  ; vtable
    0x055B7EE3  movzx r8d, dl                    ; OldState (param)
    0x055B7EE7  movzx edx, byte [rcx+0x1090]     ; the ALREADY-STORED new value
    0x055B7EEE  jmp   qword [rax+0xC60]          ; tail-call (this, New, Old)

⇒ the byte is written **before** `OnRep` runs, by the replication receive path. `[vtable+0xC60]` is
`ALokiCharacter` slot **396** = `0x055B3650`, which calls the Blueprint event
`OnNewLivingState 0x052F67A0`.

⚠ **REFUTED sub-grade, and it is the exact error class the brief warned about:** the lane graded
`OnRep_LivingState` **REAL**. It is a **virtual-dispatch shim** — the real body is at disp `0xC60`.
The conclusion is unaffected (the lane resolved `0xC60` separately and correctly), but the grade was
wrong, and "9 bytes of `mov rax,[rcx]; jmp qword [rax+disp]` is a SHIM, not an implementation"
remains the standing rule.

---

## 4. THE BRIDGE IS THE FOLD — the actual answer

| class | function | thunk | impl | grade |
|---|---|---|---|---|
| `ULivingStateMachine` | `RequestMoveTowardAlive` | `0x53C3870` | `0x55E3D70` | **REAL** |
| `ULivingStateMachine` | `RequestMoveTowardDeath` | `0x53C3970` | `0x55E3E50` | REAL |
| `ULivingStateMachine` | `FullyDie` | `0x53C2420` | `0x55D4410` | REAL |
| `ULivingState` | `CanEnter` / `EnterWithContext` / `Exit` | — | `0x53C0080`/`0x53C00D0`/`0x53C03A0` | REAL |
| `ALokiCharacter` | `GetLivingState` | `0x5300620` | `0x55AC7A0` | REAL |
| **`ALokiCharacter`** | **`OnLivingStateMachineStateChanged`** | `0x5289020` | **`0x0F7EC20`** | **FOLD (void)** |
| `ALokiBotController` | `HandleLivingStateChanged` | `0x52EDFE0` | `0x5560910` | REAL |
| `ALokiBotController` | `UpdateCharacterControllable` | `0x52EEDB0` | `0x5570B80` | REAL |
| `ALokiBotController` | `SetForceCharacterNotControllable` | `0x52EE680` | `0x556BB40` | **DARK** |

**The living-state machine is entirely real. The one thing that is stripped is the callback that
would tell the character about it.** Registrar decoder validated against two recorded answers
(`GoToPhase {0x5457200, 0x5601020}` and FK-1's `SpawnPlayer → 0x0F7EB50`).

⚠ **[I, strong], not [M], on the NAMING** — `0x0F7EC20` has **371** registrar records sharing it
(the refuter's count); a folded RVA names nothing. What is [M] is that the record for *that name*
carries that impl, and that the impl is the void fold.
⚠ The refuter notes the thunk `0x5289020` is itself **shared by 3 records** — so reading the
thunk's call target cannot attribute the fold to one name either. That is the folded-address error
*one level up*, and it is why the `.data` record is the right instrument. All three fold members
share the same impl, so the conclusion is unchanged.

---

## 5. ⚠⚠ WHAT THE REFUTERS OVERTURNED — do not carry these forward

**R-a. "The only engine writer is `FRepLayout`" is FALSE.** Native C++ writes `+0x1090` directly —
W1 and W2 above. **Corrected: the only writer *through the reflection system* is `FRepLayout`.**
Both native writers write Dead, so the verdict is untouched, but the sentence as written is wrong.

**R-b. `SetTowardAliveState` / `SetTowardDeadState` DO exist** (`{0x53C3F40, 0x0112E760}`,
`{0x53C3FD0, 0x01588FB0}`), refuting "zero functions named `Set*`". They are ICF-shared trivial
pointer setters (`mov [rcx+0x40],rdx; ret`) writing the `AliveState`/`DeadState` **object**
properties, not the enum byte. **Conclusion survives; the support does not.**
⚠ And a **type-based sweep on `ELizvingState` is NOT a completeness argument** — it cannot see a
setter that takes no `ELivingState` parameter. The lane called it "stronger than a name regex";
it is differently blind, not strictly stronger.

**R-c. There are TWO reflected `GetLivingState` functions**, and the second
(`{0x5424F20, 0x5693CA0}`) is `ALokiPlayerState`'s: it reads `[rcx+0x3f8]`, **not** `+0x1090`, and
returns a **different enum** — `EPlayerLivingState`, where **`Alive = 3`, not 1**.
⚠⚠ **Carrying "Alive == 1" to a PlayerState-side value is wrong by two.** Keep the two apart.

**R-d. A hand-arithmetic error** — the enum-constructor RVA was reported as `0x33BEA20`; it is
**`0x053BEA20`** in both images (off by `0x2000000`). The repo's recorded "recompute with a machine"
rule, again.

**R-e. The "91.7 % of the `ALokiCharacter` surface is decrypted" bound excludes its own evidence.**
Page `0x0559E000` — which contains **W1, one of the two writers the verdict rests on** — is not in
that surface, nor is `RequestMoveTowardAlive`. The figure is correctly computed but bounds only
*reflected + virtual entry points*. **The null's real support is the image-wide 55.49 % sweep.**

**R-f. Minor:** `OnRep_LivingState` is **21** bytes, not 15 (hex printed as decimal); the class has
**250** validated UFunction entries, not 251; `disp 0xC60` indirect calls are **8** on lit pages,
not 3 (exactly one in the Loki band, so the band argument carries it, not the count); and an
Angelscript control was quoted from a different population than the sweep (re-run in-scope, the
negatives hold).

---

## 6. WHAT THIS BUYS — and the lever it exposes

**The Q2 chain is now complete, end to end:**

    nothing writes LivingState=Alive  ->  every character reads Dead  ->
    bCharacterControllable = (LivingState==Alive) && !IsStunned  is FALSE for everyone  ->
    ALokiBotController::Tick's only motion driver never runs  ->  the bot does not move

Every link is measured except the last, which was measured in flight (`+0x6A0 = 0`, n=3 clients).

★★ **AND THE LEVER IS THE SAFEST WRITE CLASS THIS PROJECT HAS.** `LivingState` is **one aligned
byte at `hero+0x1090`**, with `GetLivingState` (`movzx eax,[rcx+0x1090]; ret`) as a free readback
and the live sweep tool as an external second instrument. Writing `1` is a **DATA poke** — the class
this project measures at **0 deaths in 22 armed windows**, versus 7/8 for a standing `.text` patch.
The notifier can additionally be driven through vtable slot **396** (`0x055B3650`) if the state
change needs to be announced rather than merely stored.

⚠⚠ **BUT DO NOT OVER-READ IT.** Nothing here shows that a character reading `Alive` *behaves*
alive. `bCharacterControllable` also depends on `!IsStunned`, which was **never measured** (no such
property surfaced; it is likely a function or gameplay-tag query). And `ServerSetHeroClass` /
`SetPlayerTeam` remain stripped folds regardless. **The honest prediction is narrow: poking the byte
should flip the gate's first conjunct, and nothing more is promised.**

---

## 7. STATE

**Closed [M, floor over 55.49 % of `.text`]:** nothing writes Alive; the state-machine→character
bridge is a void fold; the replication route has no NetDriver; no Blueprint, Angelscript, config or
reflected setter can touch it.

**Open:** `IsStunned` (unmeasured, second conjunct). Whether an Alive character behaves alive.
Whether a writer hides in the dark 44.5 %. `SetForceCharacterNotControllable` is **DARK** and
ungraded. And the whole result is offline — **nothing here has been flown.**

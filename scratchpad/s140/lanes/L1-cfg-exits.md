# L1 — SOUND EXIT ENUMERATION over engine `UCharacterMovementComponent::PerformMovement` `0x035E9EC0`

**Verdict up front: THE SIX SURVIVE — exactly, with no additions and no subtractions.**
There is **no backward bail**, **no indirect jump**, **no jump table**, **no non-returning callee**,
**no gap byte**, and **exactly one** call to vtable displacement `0x720` in the whole function.
But the enumeration being complete is a *negative* result: it removes the "missing exit" explanation
and pushes the whole weight of the contradiction elsewhere. Section 12 ranks the survivors.

---

## 0. Instrument — written from scratch, as instructed

`scratchpad/s140/l1/l1img.py`. **I did NOT import `scratchpad/s140/tools/cfg.py` or `peimg.py`.**
It contains my own PE parser and my own recursive-descent CFG (capstone 5.0.7, `CS_MODE_64`,
`detail=True`). I read `tools/cfg.py` only *after* producing every number below; design comparison
in section 11.

Differences from the shared tool that could have mattered and did not:

- I read 24 bytes per decode (it reads 16).
- I **follow** direct `jmp`s of any distance and only *record* ones more than `0x2000` away as tail
  jumps. Over this function **zero** such jumps exist (whole span is `0x1985` bytes), so the
  difference is moot.
- My successor sets are ordered lists, not `set()`s — no collapsing.

### Controls run on the image (all PASS)

| control | expected | got |
|---|---|---|
| all 10 sections VirtualAddress == PointerToRawData | flat | **flat, 10/10** |
| ImageBase | `0x7FF608F40000` | `0x7ff608f40000` |
| fold `0x00F7EC20` | `c2 00 00` | `c20000` PASS |
| fold `0x00F7EB50` | `33 c0 c3` | `33c0c3` PASS |
| fold `0x00F7EB60` | `32 c0 c3` | `32c0c3` PASS |
| fold `0x00B9E1F0` | `b0 01 c3` | `b001c3` PASS |
| fold `0x00FC6CF0` | `0f 57 c0 c3` | `0f57c0c3` PASS |
| **known-DARK** `0x5A6AC40` page | 0/4096 | **0** PASS |
| known-LIT `0x035E9EC0` page | greater than 0 | 3454/4096 |
| brief Super-call bytes `0x055B85C1` | `e8 fa 18 03 fe` | PASS, rel32 `-0x1fce706` gives **`0x035E9EC0`** (machine-recomputed) |
| brief `+0x12B0` writer#2 `0x055C2483` | `f3 0f 58 81 b0 12 00 00` | PASS |
| brief `+0x12B0` writer#3 `0x055A74D6` | `f3 0f 11 b6 b0 12 00 00` | PASS |

Every RVA below was recomputed by machine (struct-unpacked rel32, or capstone's own operand),
never by hand.

---

## 1. Recursive descent — **1461 instructions** [M]

```
insns          : 1461
calls          : 148   (115 direct sites / 31 distinct direct targets ; 33 indirect sites)
indirect jumps : 0
rets           : 1     -> 0x035eb1ca
decode failures: 0
int3/ud2/hlt   : 0
tail jmps      : 0
addr range     : 0x035e9ec0 .. 0x035eb845   span 0x1985
```

Independently reproduces the session lead's tool **and** S139 (1461 / 148 / 0 / 0). A linear sweep
gets 1074 and is unsound. **[M]**

### Gap analysis — a stronger soundness check than the count [M]

Marking every byte covered by a decoded instruction over `[0x035E9EC0, 0x035EB84A)`:

```
total span 6538 bytes, covered 6538, gaps 0 regions / 0 bytes
```

**Zero uncovered bytes — not even int3 padding.** So there is no undecoded island a missed edge
could be hiding, and the decode never desynced. This is the control that rules out
"my walk missed a block".

---

## 2. Backward reachability and the TRUE bail set

`R` = instructions that can reach `0x035EB13A` following successor edges: **|R| = 1075 of 1461**.

A bail = an edge `u -> v` with `u` in `R`, `u != CALL`, `v` not in `R`. Excluding the call node
itself as a source is what removes the lead's 7th edge — `0x035EB13A -> 0x035EB140` is the call's
own fallthrough, i.e. the *normal continuation*, not a bail. I confirm `0x035EB140` is NOT in `R`,
so the lead's artifact diagnosis is exactly right.

```
0x035e9f1f  0f8482120000  je   0x35eb1a7   -> 0x035eb1a7  [FORWARD]
0x035e9f28  0f8479120000  je   0x35eb1a7   -> 0x035eb1a7  [FORWARD]
0x035e9f97  0f8432180000  je   0x35eb7cf   -> 0x035eb7cf  [FORWARD]
0x035e9fa4  0f8525180000  jne  0x35eb7cf   -> 0x035eb7cf  [FORWARD]
0x035e9fbd  0f850c180000  jne  0x35eb7cf   -> 0x035eb7cf  [FORWARD]
0x035ea25d  0f84ed0e0000  je   0x35eb150   -> 0x035eb150  [FORWARD]
total bail edges: 6
```

- **Nodes in `R` with no successors: ZERO.** No `ret`, no `ud2`, no indirect jump inside `R`.
- **All six bails are the TAKEN edge of a conditional branch.** No bail is a fallthrough edge.
- **No BACKWARD bail exists.** The "target greater than call" predicate the brief flags as
  structurally blind happens to have been *correct* here — but that is now a measurement, not
  luck. **[M]**

### Diff against the prior six

`0x035E9F1F, 0x035E9F28, 0x035E9F97, 0x035E9FA4, 0x035E9FBD, 0x035EA25D` — **identical set.
Nothing missed. Nothing of theirs is a false exit.** [M]

---

## 3. (a) Indirect jumps / jump tables — **NONE** [M]

- CFG: `indirect_jumps = 0`.
- Independent operand scan over all 1461 decoded instructions: of every `call`/`jmp` with a
  non-immediate operand, **all 33 are `call`; zero are `jmp`.** No `jmp reg`, no
  `jmp [table+idx*8]`, no `jmp [mem]`.
- Corroborating: the gap analysis found 0 uncovered bytes, so there is no orphan block a jump table
  would have to target.

Therefore reachability here is **not** a floor.

---

## 4. (b) Non-returning callees

### 31 distinct DIRECT targets — all REAL, all contain a `ret`, **zero noreturn candidates** [M]

Graded by first bytes against the five fold constants plus page-nonzero:

- **REAL 31 / FOLD 0 / DARK 0.** Page-nonzero 3628–3951 for every one.
- Bounded recursive descent on each: every one has at least one `ret`, or leaves via a tail
  construct.
- One needed adjudication: `0x037E6B70` (4410 insns, **0 rets**, 1 "indirect jump"). Read directly —
  `0x037E81AF jmp qword ptr [rax+0x38]` is preceded by full stack/nonvolatile restore
  (`mov rsp,r11 ; pop rbp`), so it is a **tail call through a virtual**, not a jump table and not a
  noreturn. It returns to *its* caller.
- `0x0751DEB0` is `__security_check_cookie` (`cmp rcx,[rip+..] ; jne ; rol rcx,0x10 ...`). Its
  failure arm (`__report_gsfailure`) genuinely is noreturn — **but it is not in `R`**: its single
  call site is `0x035EB1B1`, in the epilogue, downstream of the ret path. Irrelevant to the exit set.

### 33 INDIRECT sites — 19 in `R`, of which **9 dominate the call**

Resolved through the `ULokiCharacterMovementComponent` vtable at `.rdata 0x088F8570`
(slot = `*(u64*)(0x088F8570 + disp) - ImageBase`).

**Positive controls on that vtable, 4/4 PASS** — this is what makes the resolution a measurement:

| disp | expected (brief) | read |
|---|---|---|
| `0x720` | `ULokiCMC::StartNewPhysics 0x055C2430` | `0x055c2430` **PASS** |
| `0xAA8` | `ULokiCMC::PerformMovement 0x055B8370` | `0x055b8370` **PASS** |
| `0x3D0` | `ULokiCMC::TickComponent 0x055C2B90` | `0x055c2b90` **PASS** |
| `0x890` | `ULokiCMC::ControlledCharacterMove 0x055A7680` | `0x055a7680` **PASS** |

Resolved spine virtuals, each graded and noreturn-tested:

| site | disp | resolves to | page nz | grade | rets | verdict |
|---|---|---|---|---|---|---|
| `0x035E9F17` (gate 1) | `0x6B8` | **`0x035E64C0`** | 3628 | REAL (**engine impl, NOT a Loki override**) | 2 | returns |
| `0x035E9FB5` (gate 5) | `0x4C0` on UpdatedComponent | **`0x03C9B0A0`** | 3718 | REAL | 3 | returns |
| `0x035E9FD9` | `0x610` | `0x055B1EC0` | 3699 | REAL (Loki override) | 3 | returns |
| `0x035EA0A9` | `0x6F0` | `0x035E7760` | 3671 | REAL | 2 | returns |
| `0x035EA126` | `0x808` | `0x055A15B0` | 3723 | REAL (Loki override) | 1 | returns |
| `0x035EA136` | `0x818` | `0x036061D0` | 3596 | REAL | 1 | returns |
| `0x035EA160` | `0x750` | `0x055AEB60` | 3694 | REAL (Loki override) | 2 | returns |
| `0x035EA16C` | `0x810` | `0x035D8B70` | 3626 | REAL | 1 | returns |
| `0x035EB120` | `0xA08` on CharacterOwner | see below | — | REAL | — | returns |
| `0x035EA249` (gate-6 block) | `0xB68` | `0x03603640` | — | REAL | 1 | returns |
| **`0x035EB13A`** | **`0x720`** | **`0x055C2430`** | 3626 | **REAL** | 2 | — |

`disp 0x4C0` was pinned without knowing the exact capsule class: I scanned `.rdata` for qwords equal
to `ImageBase + 0x03C91C60` (`GetBodyInstance`, disp `0x810`, [M] from S139), took `hit - 0x810` as
a candidate vtable base — **90 candidate vtables, and all 90 hold the SAME `disp 0x4C0` target
`0x03C9B0A0`.** No class in the primitive-component family overrides it. **[M]**

`disp 0xA08` was pinned the same way against `ImageBase + 0x3BBF3C0`
(`APawn::SpawnDefaultController`, slot 280 / disp `0x8C0`, [M] in CLAUDE.md as *not* overridden
across APawn/ACharacter/ALokiCharacter/ALokiHeroCharacter): 13 hits, so 13 candidate pawn-family
vtables, giving **5 distinct `disp 0xA08` targets: `0x03520F00`, `0x055A6890`, `0x011E50C0`, and
the two folds `0xF7EB60` / `0xF7EC20`. All five return.** `0x03520F00` is stock
`ACharacter::ClearJumpInput` ([M] structure / [I, strong] name): `test byte [rcx+0x580],4`
(bPressedJump) then `addss xmm1,[rcx+0x584]` (JumpKeyHoldTime += DeltaTime) then `call [rax+0xa10]`
(GetJumpMaxHoldTime) then `comiss` then clear the bit. `0x055A6890` is the Loki override, same
shape. Which one the bot's class uses is not determined offline — **but it does not matter, because
every candidate returns.** [M] for "returns"; [I, strong] for the naming.

So: **no non-returning callee is reachable on any path into `0x035EB13A`.** The only residual is a
C++ **throw** or `longjmp` out of an indirect callee, which a CFG cannot see. Given this image's
`IMAGE_DIRECTORY_ENTRY_EXCEPTION` is RVA=0 / size=0 (CLAUDE.md, FK-10 section 4) a throw would not
unwind cleanly and the process would die — it has not. Grade: **[I, strong] no hidden exit via
noreturn.**

---

## 5. (c) The `ret` at `0x035EB1CA`

- **Exactly one `ret` in the function.** [M]
- Its only predecessor is `0x035EB1C9 pop rbp`.
- **`reach_backward(0x035EB1CA)` = 1461 of 1461** — *every* instruction in the function can reach
  the ret. No dead-end block, no non-terminating path. [M]
- All three bail targets funnel there: `0x035EB1A7` (cookie check, epilogue, ret),
  `0x035EB7CF` (the root-motion-consume plus `ClearAccumulatedForces` block, which rejoins), and
  `0x035EB150` (the `FScopedMovementUpdate` destructor `call 0x03786FA0`, register restore, falls
  into `0x035EB1A7`). All three: `in reach_backward(RET) = True`. [M]

The epilogue is shared, which is why gate 6's target `0x035EB150` is numerically *forward* of the
call yet is still a bail — it re-enters the shared teardown, skipping the call.

---

## 6. (d) DOMINANCE — **only FIVE of the six are mandatory** [M]

Cooper–Harvey–Kennedy iterative dominators over the instruction graph (RPO from `0x035E9EC0`).

| bail site | dominates `0x035EB13A`? |
|---|---|
| `0x035E9F1F` | **YES** |
| `0x035E9F28` | **YES** |
| `0x035E9F97` | **YES** |
| `0x035E9FA4` | **YES** |
| `0x035E9FBD` | **YES** |
| `0x035EA25D` | **NO** |

Dominance *among* the six is a total order in address sequence: 9F1F dominates 9F28 dominates 9F97
dominates 9FA4 dominates 9FBD dominates A25D; no later one dominates an earlier one.

**The mandatory spine is 128 instructions** — every execution that reaches `StartNewPhysics`
executed exactly these, in order. It contains 5 direct calls and 9 indirect calls (all enumerated
above) and the 5 mandatory gates.

**This changes which live measurements matter, in two ways:**

1. Gate 6 (`0x035EA25D`) is **optional** — it sits inside a conditionally-entered block (preceded by
   `call [rax+0xb68]` = `0x03603640` with `xmm1 = DeltaSeconds`, i.e. the root-motion region). Some
   executions never evaluate it.
2. Gate 6 is **also redundant**: its predicate is `[rax+0x6B8]` = the *same* `HasValidData()` as
   gate 1, and gate 1 dominates it. It can only fire if something between `0x035E9F1F` and
   `0x035EA25D` nulled `UpdatedComponent` / `CharacterOwner` or set `RF_Garbage`. **[M]**

---

## 7. (e) Is `0x035EB13A` the only route to `StartNewPhysics`? **YES** [M]

- Operand scan over all 1461 instructions for a memory displacement of `0x720`: **2 hits** —
  `0x035EB0B8 movsd xmm3, qword ptr [rbx+0x720]` (a data read, not a call) and
  `0x035EB13A call qword ptr [rax+0x720]`. **Exactly one call.**
- `0x03600990` (engine `StartNewPhysics`) and `0x055C2430` (Loki `StartNewPhysics`) are **not**
  among the 31 direct call targets, and there is no `jmp` to either.
- The dispatch object is unambiguous: `0x035EB126 mov rax, qword ptr [rbx]` with `rbx = this` (set
  at `0x035E9EFD mov rbx, rcx`), so `[rax+0x720]` is the CMC's own vtable slot.

---

## 8. Loop? **NO — at most one `StartNewPhysics` per `PerformMovement`** [M]

Forward reachability from the call's successors: **`0x035EB13A` is NOT reachable from its own
successors** (forward set size 358; the call is not in it). The call is not in any loop.

So the latch cannot be "set then re-cleared by a second iteration of the same call site".
Re-entry from `PhysWalking`/`PhysFalling` with `Iterations != 0` would take
`0x055C2436 jne 0x55C2475` and not touch the latch at all — and it is already 1 by then.

---

## 9. What each gate actually tests — and every one is covered by an S139 measurement

Register provenance verified: `rbx = this` (`0x035E9EFD`); `rcx = [rbx+0xD0] = UpdatedComponent`
(loaded `0x035E9F2E`, **not rewritten** anywhere on the path to `0x035E9FB5` — checked instruction
by instruction, including the `0x035E9F59` diamond); `r13 = [rbx+0xC0] = World` (`0x035E9EEE`, with
a null-fallback `call 0x035AFC40` at `0x035E9F05`); `xmm11 = DeltaSeconds` (`0x035E9EF5`).

| # | site | bails when | S139 live value | passes? |
|---|---|---|---|---|
| 1 | `0x035E9F1F je 0x35EB1A7` | `HasValidData() == false` | see below | **PASS** |
| 2 | `0x035E9F28 je 0x35EB1A7` | `World == NULL` | `CMC+0xC0` non-null | **PASS** |
| 3 | `0x035E9F97 je 0x35EB7CF` | `MovementMode(+0x231) == 0` | 3 | **PASS** |
| 4 | `0x035E9FA4 jne 0x35EB7CF` | `UpdatedComponent->Mobility(+0x1BB) != 2` | 2 | **PASS** |
| 5 | `0x035E9FBD jne 0x35EB7CF` | `UpdatedComponent->IsSimulatingPhysics() == true` | see below | **PASS** |
| 6 | `0x035EA25D je 0x35EB150` | `HasValidData() == false` (again) | same as #1 | **PASS** (and optional) |

### `HasValidData 0x035E64C0` — full body, 14 instructions, **new [M]**

```
0x035e64c0 cmp qword ptr [rcx + 0xd0], 0   ; UpdatedComponent
0x035e64c8 je  0x35e64e5                   -> false
0x035e64ca mov rax, qword ptr [rcx + 0x198]; CharacterOwner
0x035e64d1 test rax, rax
0x035e64d4 je  0x35e64e5                   -> false
0x035e64d6 mov eax, dword ptr [rax + 0xc]  ; ObjectFlags
0x035e64d9 shr eax, 0x1e                   ; >> 30
0x035e64dc not al
0x035e64de test al, 1
0x035e64e0 je  0x35e64e5                   -> false  (bail if bit30 SET = RF_Garbage)
0x035e64e2 mov al, 1 ; ret
0x035e64e5 xor al, al ; ret
```

`HasValidData()` is `UpdatedComponent != NULL && CharacterOwner != NULL &&
!(CharacterOwner->ObjectFlags & (1<<30))`.
S139 measured **all three**: UpdatedComponent non-null, `CMC+0x198 == pawn`, and
`pawn ObjectFlags+0x0C bit30 == 0`. The banked measurement was aimed at exactly the right bit. **[M]**

### `IsSimulatingPhysics 0x03C9B0A0` — the gate-5 chain closes on a byte S139 already read, **new [M]**

```
0x03c9b0be call [rax+0x810]      ; GetBodyInstance(BoneName=rdx, bGetWelded=r8b=1, Index=r9d=-1)
0x03c9b0c7 test rax,rax ; je 0x3c9b0f8      ; BI == NULL -> long welded-children fallback
0x03c9b0cf call 0x01e2f940 ; test al,al ; je 0x3c9b0ee   -> RETURN FALSE
0x03c9b0db call 0x03bad5c0 ; test al,al ; je 0x3c9b0ee   -> RETURN FALSE
0x03c9b0e4 mov al,1 ; ret
```

and the first predicate is, verbatim:

```
0x01e2f940 push rbx ; sub rsp,0x20
0x01e2f946 test byte ptr [rcx + 0x10], 1     ; <<< BodyInstance+0x10 mask 0x01 == bSimulatePhysics
0x01e2f94a je 0x1e2f9b7                      ; -> returns false
```

S139 measured `BodyInstance(+0x3F0)+0x10 mask 0x01 == 0` on the bot's capsule (with the decode
control that `bEnableGravity` reads 1 from the same byte under a different mask), and
`WeldParent(+0x5F0) == NULL` so `GetBodyInstance(bGetWelded=1)` returns the capsule's own body
(`lea rax,[rcx+0x3f0]`, S139). Therefore `0x01e2f940` returns false, `IsSimulatingPhysics` returns
**false** at `0x03C9B0EE`, and gate 5's `jne` is not taken. **The gate-5 chain is now closed end to
end from the bytes.** [M] The second predicate `0x03BAD5C0 = cmp qword [rcx+0x230],0 ; setne al`
is never reached.

### Bail-target semantics (matches stock UE5 `PerformMovement` exactly)

`0x035EB7CF` (gates 3/4/5) is the stock
`{ if (!bClientUpdating && !bServerMoveIgnoreRootMotion && IsPlayingRootMotion() && GetMesh()) {...}
ClearAccumulatedForces(); return; }` block. `0x035EB1A7` (gates 1/2) is the bare `return;`.
That correspondence is what lets the five be *named*, not just located.

The spine also decodes cleanly against stock source, an independent sanity control on the whole
reading: `0x035EA09A call 0x03785B10` = `FScopedMovementUpdate` ctor and `0x035EB157 call 0x03786FA0`
= its dtor; `0x035EA13C cmp byte [rbx+0x231], 2 ; jne` = `MovementMode == MOVE_NavWalking`;
`0x035EB120 call [rax+0xa08]` = `CharacterOwner->ClearJumpInput(DeltaSeconds)` immediately followed
by `0x035EB130 mov dword [rbx+0x3dc], r15d` = `NumJumpApexAttempts = 0`; then
`0x035EB129 xor r8d,r8d` plus `movaps xmm1,xmm11` plus `call [rax+0x720]` =
`StartNewPhysics(DeltaSeconds, 0)`; then `0x035EB146 call [rax+0x6b8]` plus `jne 0x35EB1CB` = the
stock `if (!HasValidData()) return;`.

---

## 10. Cross-check I ran because my negative shifts the weight (lane-L2 territory, reported honestly)

`ULokiCMC::PerformMovement 0x055B8370`, same instrument, same method:

```
insns=322  rets=1  calls=29  indirect jumps=0  tail jmps=0  decode failures=0
span 0x055b8370..0x055b88dd
|reach_backward(0x055B85C1)| = 142
BAIL EDGES that skip the Super call: 0
nodes in R with no successors: none
```

**Zero bails.** The Loki wrapper reaches its Super (`0x055B85C1 -> 0x035E9EC0`) on **every** path.
[M], subject to the same throw/noreturn caveat.

And the caller: `0x035DCDAC call qword ptr [rax + 0xaa8]` is a **virtual dispatch** (`rax = [rsi]`,
`rsi = the CMC`), resolving to `0x055B8370` on the ULokiCMC vtable, gated by
`0x035DCD97 movzx ecx, byte [rax+0x160]` / `0x035DCD9E cmp cl,3` on `CharacterOwner` =
`Role == ROLE_Authority`, measured **3**. So the Loki wrapper is on the path and is entered.

`ULokiCMC::StartNewPhysics` re-verified from raw bytes:
`0x055C2469 c6 81 c8 16 00 00 01` = `mov byte [rcx+0x16c8], 1`, then
`0x055C2470 e9 1b e5 03 fe`, rel32 `-0x1fc1ae5`, target **`0x03600990`** (machine-recomputed) — a
*tail jump*, so **the latch is set BEFORE the engine `StartNewPhysics` body even begins.** Nothing
inside the engine function can prevent the latch being 1 once `0x055C2469` retires.

---

## 11. Comparison with the shared `tools/cfg.py` (read only after the fact)

Same design (recursive descent, instruction-graph reachability, calls assumed to fall through,
indirect jumps recorded not swallowed). Independent code, independent PE parser. It reported
1461 / 148 calls / 0 indirect jumps / 0 decode failures / 0 noreturn candidates for this entry;
**I reproduce all five numbers.** Two agreeing instruments.

---

## 12. WHAT I COULD NOT ESTABLISH OFFLINE, AND THE EXACT LIVE READ THAT WOULD SETTLE EACH

1. **Is the live component's vtable actually `ImageBase + 0x088F8570`?**
   Everything about the latch depends on the live object dispatching `disp 0x720` to
   `ULokiCMC::StartNewPhysics 0x055C2430`. If the pawn's movement component is a *plain*
   `UCharacterMovementComponent`, `disp 0x720` dispatches straight to `0x03600990`, **`+0x16C8` is
   never written by anyone, and the latch reads 0 for a completely innocent reason.**
   None of the banked S139 fields (`+0xE8`, `+0x231`, `+0x328`, `+0xD0`, `+0xC0`, `+0x198`) is
   Loki-specific — they are all engine-class offsets valid on either class.
   **THE READ: one qword, `*(uint64_t*)CMC`, compared to `ImageBase + 0x088F8570`.**
   Weak counter-evidence already exists: `+0x12B0` advances at exactly 1.0x real time on both pawns,
   which is hard to get from adjacent heap. But that is [I], and this is one read.
   *Rank: FIRST. It validates or invalidates the entire latch instrument for near-zero cost.*

2. **Does anything clear `+0x16C8` after `0x055C2469`?** Explicitly assigned to lane A4; my result
   makes it the second-strongest survivor. Offline-answerable — enumerate every writer of `+0x16C8`,
   including 16/32-byte stores that *land* on it, from capstone operands, not a byte scan.

3. **Whether an indirect callee on the mandatory spine throws.** Not decidable from a CFG. Bounded
   by: all resolvable targets contain `ret`, and the image has no main-image exception directory, so
   an escaping throw should be fatal and is not observed. **[I, strong] excluded.**

4. **Which pawn class the bot uses, hence which `disp 0xA08` body runs.** Five candidates, all
   returning, so the exit set is unaffected. Settled by one live read of `*(uint64_t*)CharacterOwner`.

5. **`0x055B1EC0` / `0x055AEB60` / `0x055A15B0` / `0x03603640` / `0x035E7760` / `0x035D8B70` /
   `0x036061D0` are graded REAL and returning but NOT named.** Naming them from stock-source
   correspondence would be [I], and none of them is a gate.

---

## 13. PLAIN STATEMENT

**"The six" SURVIVES.** Redone with a sound method by an independent instrument:

- exactly **6** bail edges out of `R`, at exactly the 6 addresses S139 named;
- **0** backward bails, **0** indirect jumps, **0** jump tables, **0** decode failures,
  **0** uncovered bytes, **0** non-returning direct callees, **0** non-returning resolvable indirect
  callees, **1** `ret`, **1** call to `disp 0x720`, **no loop**;
- **5 of the 6 dominate the call** — gate 6 is optional *and* re-tests gate 1's predicate;
- every one of the 6 predicates is now traced to bytes, and **every one is covered by an S139 live
  measurement, and every one PASSES** — including gate 1/6 (`HasValidData`'s three terms) and gate 5
  (`IsSimulatingPhysics` reading `BodyInstance+0x10 & 1`), neither of which had been read out of the
  bytes before.

**The "incomplete enumeration" branch of the S140 contradiction is CLOSED.** There is no missing
exit inside engine `PerformMovement`, and none inside the Loki wrapper either. The contradiction is
therefore real, and its remaining explanations are: **(1) the latch instrument is invalid because
the live component is not a `ULokiCharacterMovementComponent`** — one qword read; **(2) `+0x16C8` is
cleared after being set** — lane A4, offline; **(3) an upstream assumption about which object is
being measured is wrong.** Nothing else is left standing on this path.

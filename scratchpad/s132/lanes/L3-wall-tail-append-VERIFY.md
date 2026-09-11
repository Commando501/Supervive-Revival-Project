# S132 LANE 3 — ADVERSARIAL VERIFICATION of `L3-wall-tail-append.md`

Target: `ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable`, impl `0x55CD510`.
All work OFFLINE against `dumps/merged4.dump.exe` (ImageBase `0x7FF6AF000000`, file offset == RVA).
Zero launches, zero injections.

**I did not use `fkdis.py` for any load-bearing decode.** I wrote an independent loader
(`scratchpad/s132/verify/v.py`) and drove **capstone** directly, so the disassembly, the
predecessor enumeration, the `regs_access` liveness and the disp32 scans are a second route,
not a re-run of the report's instrument. All address arithmetic was done with `python -c`.

**Score: 22 of 27 load-bearing items CONFIRMED. 5 REFUTED or UNSUPPORTED (section A).**

---

## A. THE FIVE THAT DO NOT SURVIVE

### A1. REFUTED — R3: "the increment-before-grow is a FUNCTIONAL PRECONDITION, not a style choice" (report §0 R3, §5 consequences 1 and 2, graded **[M]**)

The report's stated failure mode is:

> *"A mirror that increments after the grow would allocate for `old` elements and then write
> `Data[old]` out of bounds."* … *"It `int3`-aborts when `ArrayNum < PreviousNum`. Passing a
> stale pair is fatal, not lossy."*

**Both failure modes are disproved by the same bytes the report prints.** Re-disassembled
independently:

```
0x00F988DF  48635908          movsxd rbx, dword ptr [rcx+8]   ; rbx = ArrayNum (from the struct)
0x00F988E3  8bf2              mov    esi, edx                 ; esi = PreviousNum
0x00F988E8  3bda              cmp    ebx, edx
0x00F988EA  7c71              jl     0xf9895d                 ; ArrayNum <  PreviousNum -> int3
0x00F988EC  83790c00          cmp    dword ptr [rcx+0xc], 0   ; ArrayMax == 0 ?
0x00F988F0  b804000000        mov    eax, 4
0x00F988F5  7411              je     0xf98908
0x00F988F7  488d045b          lea    rax, [rbx+rbx*2]         ; Max != 0 branch:
0x00F988FB  48c1e803          shr    rax, 3                   ;   NewMax = ArrayNum
0x00F988FF  4883c010          add    rax, 0x10                ;          + 16
0x00F98903  4803c3            add    rax, rbx                 ;          + (3*ArrayNum)>>3
0x00F98906  eb07              jmp    0xf9890f
0x00F98908  483bd8            cmp    rbx, rax                 ; Max == 0 branch:
0x00F9890B  480f47c3          cmova  rax, rbx                 ;   NewMax = max(4, ArrayNum)
```

`ResizeGrow` **never allocates exactly `ArrayNum` elements.** It allocates
`max(4, ArrayNum)` when `ArrayMax == 0`, and `ArrayNum + 16 + (3*ArrayNum)/8` otherwise.
Simulating the increment-**after** ordering against these bytes:

| | increment-BEFORE (shipped) | increment-AFTER (the "fatal" ordering) |
|---|---|---|
| `ArrayNum` seen by ResizeGrow | `old+1` = 1 | `old` = 0 |
| `PreviousNum` in `edx` | 0 | 0 |
| `cmp ebx,edx; jl` int3 | 1 < 0 → **not taken** | 0 < 0 → **not taken** |
| `NewMax` (Max==0 path) | `max(4,1)` = **4** | `max(4,0)` = **4** |
| `Data[old]` in bounds? | yes (0 < 4) | **yes (0 < 4)** |

⇒ **For the arm's own measured state (`PlayersAttached` live = `Data=0 Num=0 Max=0`) the two
orderings produce a byte-identical, valid array: `Max=4`, one 32-byte game-heap allocation.**
The `int3` does not fire (`ArrayNum == PreviousNum`, and `jl` is strict), and the write is not
out of bounds. In the general `Max != 0` case the only difference is one element less of
headroom (`old+16+3*old/8` vs `(old+1)+16+3*(old+1)/8`) — never fatal for a single append.

The only construction under which increment-after over-runs is `ArrayMax == 0` **with**
`ArrayNum > 4`, which is a corrupt array by construction and cannot arise here.

**Correction:** R3a (*ResizeGrow sizes the allocation from `ArrayNum` read out of the struct*)
and R3b (*it `int3`s when `ArrayNum < PreviousNum`*) are **CONFIRMED [M]** as facts about the
function. The **derived** claim — that increment-after is a functional error — is **REFUTED**.
Mirror the shipped order anyway (fidelity, and it is free), but on this data it is a style
choice, not a precondition, and the report's "**Do not 'clean up' the ordering**" warning is not
carrying the weight it claims. Grade the ordering advice **[I]**, not [M].

### A2. REFUTED as stated — §8.3: "There is no store of RAX to memory, and no copy of RAX to any non-volatile register, anywhere in the function" (graded **[M]**, "RAX-family reads/writes enumerated over all 746 bytes")

capstone `regs_access` over all 746 bytes, every RAX-family read, my own run:

```
0x055CD5CB R   mov rsi, rax                    <-- RSI IS NON-VOLATILE
0x055CD61D R   mov rbx, rax                    <-- RBX IS NON-VOLATILE
0x055CD6BC R   mov qword ptr [rsp+0x50], rax   <-- STORE OF RAX TO MEMORY
0x055CD6C4 R   mov qword ptr [rsp+0x48], rax   <-- STORE OF RAX TO MEMORY
```

Four counter-examples. None of them holds the round game mode (all four are downstream of
`call 0x55C7DD0` @`0x55CD583`, `call 0x56BE0D0` @`0x55CD5C6`, and `xor eax,eax` @`0x55CD6BA`
respectively), so **the conclusion is untouched** — but the *evidence sentence* is false as
written, and it is exactly the kind of whole-function absolute the report's own §8 method note
warns about. It criticises the prior lane for a window scoped one instruction too late and then
replaces it with an unbounded claim that a 4-line grep of its own instrument refutes.

**Correct evidence (which I re-derived and which does support the conclusion):** the round game
mode's return is live for exactly three instructions —

```
0x055CD577  test rax, rax
0x055CD57A  je   0x55CD7B2
0x055CD580  mov  rcx, rax        ; the only copy, into a VOLATILE register
0x055CD583  call 0x55C7DD0       ; consumes rcx, redefines rax
```

⇒ one consumer, dead at `0x55CD583`. **PRECONDITION, not data dependency — CONFIRMED**, by the
narrow window only.

*Nit on the same section:* the report's §8.1 annotates `call` sites as "WRITES-RAX" and presents
the block as capstone `regs_access` output. capstone does **not** report `call` as an RAX writer
(my run lists no `call` in the RAX read/write census). The RAX-redefinition-on-return step is
Win64 ABI knowledge, correct but not what the instrument printed.

### A3. REFUTED — §10: "Every RVA in this document came out of a machine."

Counter-example in §5:

```
report:   0x00F9891C  e89fef0600    call   0x0B078C0   ; FMemory::QuantizeSize
measured: 0x00F9891C  e89fef0600    call   0x10078C0
          python: hex(0xF98921 + 0x6EF9F) -> '0x10078c0'
```

Off by `0x5000000`. Not load-bearing (the callee's identity plays no role in any conclusion),
but it is the precise error class the caveat claims to have eliminated, and it sits inside the
disassembly block that is the report's main product. **Anything downstream that quotes
`0x0B078C0` must be corrected to `0x10078C0`.**

### A4. UNSUPPORTED — §7 free finding: "`0xA035E80` has exactly two `lea` xrefs in the whole image"

I re-ran the disp32 scan myself over the entire `.text` section:

```
target 0xA035E80  raw disp32 hits: 2   -> 0x55CD7C2 (this fn), 0x55CD9A8 (AuthPlayerPreSpawnOnAddToPlane)
target 0xA036AC0  raw disp32 hits: 22  -> 21 real lea + 1 false positive (0x23FE774)
```

The **counts reproduce**, but "in the whole image" does not hold: a byte scan can only see
decrypted pages, and

```
merged4 .text pages: 16683 / 30281 decrypted = 55.09 %
```

⇒ **"exactly two" is a FLOOR over 55.09 % of `.text`, not a census.** The report applies its own
coverage discipline correctly to `LokiTeleportActor` in §7 and then drops it three paragraphs
later.

**Conclusion unaffected, and for a better reason than the one given:** `0xA035E80` =
`LogLokiRideable` does not need the xref count at all. This function's own bail-B record
(`.rdata 0x8B1CF08`, decoded below) carries the *exact string* S131 measured live **with the
category prefix printed** (`LogLokiRideable: Error: ULokiRideableComponent::AuthPlayerEnterWorld
AttachedToRidable failed to get the round game mode`). The identification is direct, not
triangulated. Re-grade the count as [M, floor] and the naming as [M] by the live line.

*Minor, same paragraph:* the prose cites the xrefs at **`0x55CD7C5`** and **`0x55CD9AD`**. Those
are the **disp32 field offsets** the tool prints, not instruction boundaries — the `lea rcx`
instructions start at **`0x55CD7C2`** and **`0x55CD9A8`**. The report's own §3.5 listing has
`0x55CD7C2`, so the document contradicts itself by 3 bytes.

### A5. UNSUPPORTED as [M] — §6 item 3: "UHT declaration order … property 8 `PlayersAttached` → next slot = 0x130"

`binds_members.csv` genuinely lists class 4540 properties 6/7/8 as `PlayersInsideCount` /
`PlayersInside` / `PlayersAttached` (re-read verbatim). But **declaration order is not layout
order**, and the step "property 7 is at 0x120, therefore property 8 is at 0x130" is an inference
about packing, graded [M]. That is a grade upgrade across an inference step. (Property 9 is
`TSet<ALokiPlayerState> PlayersThatExited`, so the class does not stop at 8 — nothing in the CSV
forces the next 16-byte slot to be `PlayersAttached` rather than a non-reflected member.)

**I settled it [M] by a different instrument the report did not use — the UHT `FPropertyParams`
oracle.** Independent read of the `.rdata` property-params records (`Offset` is the `uint16`
following `ArrayDim`):

```
.rdata 0x8A50030  name-> "PlayersInsideCount"  ... 01 00  1c 01   Offset = 0x011C
.rdata 0x8A500B0  name-> "PlayersInside"       ... 01 00  20 01   Offset = 0x0120
.rdata 0x8A50130  name-> "PlayersAttached"     ... 01 00  30 01   Offset = 0x0130
```

**Two positive controls in the same pass**: `0x011C` and `0x0120` are exactly S131's live
by-name reads of `PlayersInsideCount` / `PlayersInside`. ⇒ `PlayersAttached @ this+0x130` is now
**[M] by an instrument independent of both the instruction operand and the declaration order.**

**Free by-product the report missed, and it is a safety property for the arm:** the same records
carry `EPropertyFlags`. `PlayersInside` = `0x0020080000000034` (**`CPF_Net` 0x20 SET**, and
`PlayersInsideCount` additionally carries a **non-null `RepNotifyFunc` pointer**), while
`PlayersAttached` = `0x0020080000000014` — **`CPF_Net` CLEAR**. ⇒ appending to `PlayersAttached`
touches no replication and no RepNotify path. That was assumed, not shown.

---

## B. CONFIRMED — re-derived by a second route

| # | claim | verdict | how I re-derived it |
|---|---|---|---|
| 1 | Extent = 5 contiguous `.pdata` rows, sizes sum **746**, `0x55CD7FA-0x55CD510 = 0x2EA = 746` | **CONFIRMED** | grepped `pdata_union.csv` myself: `149+470+25+30+72 = 746`; capstone linear decode of 746 bytes ends **exactly** at `0x55CD7FA` (166 instructions, no straddle) — an independent corroboration the report did not claim |
| 2 | Rows 2-5 carry `UNW_FLAG_CHAININFO` chaining to `{0x55CD510, 0x55CD5A5, 0x97FCA98}` | **CONFIRMED** | decoded `UNWIND_INFO` at `0x97FCA98/AB0/AC8/AD8` myself; flags `0x0 / 0x4 / 0x4 / 0x4 / 0x4`, all four chained parents byte-identical |
| 3 | Unwind codes decode to `xmm6@+0x150`, `rsi@+0x170`, `r14/rdi/rbx@+0x188/0x180/0x178` | **CONFIRMED** | decoded UWOP opcodes: row2 `10 68 15 00` = SAVE_XMM128 xmm6 `21*16=0x150`, `08 64 2e 00` = SAVE_NONVOL rsi `46*8=0x170`; row1 = r14 `49*8=0x188`, rdi `48*8=0x180`, rbx `47*8=0x178`, **plus** ALLOC_LARGE `44*8=0x160` and PUSH_NONVOL rbp @prolog `0x19` — matching `sub rsp,0x160` / `push rbp` as well |
| 4 | Fully decrypted, one page `0x55CD000`, **63 zero bytes, longest run 3** | **CONFIRMED** | exact match on my own census; page nonzero count 3703/4096. Negative control: `0x5668000` is all-zero in the same image |
| 5 | The append `0x55CD738..0x55CD767`, instruction for instruction | **CONFIRMED** | capstone, byte-for-byte identical to the report's listing including all opcode bytes |
| 6 | R1 growth test is **UNSIGNED** (`cmp eax,[Max]` + `jbe` skip) | **CONFIRMED** | `760e jbe` = CF\|ZF; grows iff `(old+1) > Max` unsigned |
| 7 | R2 `old` read `movsxd` (i32→i64), `old+1` computed 32-bit | **CONFIRMED** | `49639e38010000` / `8d4301` |
| 9 | `rdi` written **exactly twice** (`mov rdi,rdx` @`0x55CD53E` + epilogue restore) ⇒ the stored element is the caller's raw `PlayerState` | **CONFIRMED** | my own `regs_access` write-census: RDI 2 writes, R14 2 writes, RBX 4 writes — identical to the report |
| 10a | Array base from the instruction operands (`lea rcx,[r14+0x130]`, `mov rax,[r14+0x130]`, `r14 = this`) | **CONFIRMED [M]** | bytes + the R14 write census (2 writes only) |
| 10b | `ResizeGrow` treats `rcx` as `TArray{Data@0, Num@8, Max@0xC}`, self-consistent with `+0x138`/`+0x13C` | **CONFIRMED [M]** | `movsxd rbx,[rcx+8]`, `cmp [rcx+0xc],0`, `mov [rdi+0xc],eax` |
| 11 | Success path order and names; `SetActorEnableCollision 0x339A550` (54 B), `SpawnAndMoveLokiCharacter_MoveStep 0x55C1B20` (120 B), `GetServerTime 0x37D9D40` (65 B); `LokiTeleportActor 0x56680F0` **COVERAGE-BLOCKED in all seven images** | **CONFIRMED** | I located the `.data` `{name,thunk,impl}` records myself by scanning `.data` for pointers to the ANSI name strings: `AuthPlayerEnterWorldAttachedToRidable thunk=0x5456380 impl=0x55CD510` @`0x9C1E5B8`; `AuthSetCurrentRideable impl=0xF7EC20`; `LokiTeleportActor thunk=0x537B570 impl=0x56680F0`. `.pdata` sizes `0x36/0x78/0x41` confirmed. Page `0x5668000` nonzero-byte count = **0 in all 7 dumps**, with page `0x55DC000` present in 6 of 7 as the positive control |
| 11b | `0x55C1B20` named **[M] from its own literal** | **CONFIRMED** | I decoded `.rdata 0x8B19038` myself: fmt = `ALokiCharacter::SpawnAndMoveLokiCharacter_MoveStep Null Character was given to move`, file `...\Loki\Character\LokiCharacter.cpp`, **line 5484**, verbosity 2 — and verified the `lea rdx,[rip]` referencing it sits **inside** `0x55C1B20..0x55C1B98` (at `0x55C1B46`) |
| 12 | Only `0x55CD760` branches into `0x55CD738..0x55CD76B` | **CONFIRMED and STRENGTHENED** | my predecessor table is byte-identical to the report's. I additionally ran a **whole-`.text`** direct-branch scan (E8/E9 rel32, `0F 8x` jcc32, `EB`/`7x` short) for any target in that range: **1 hit, `0x55CD750`** — so the append is unreachable from outside the function too, which the report's internal-only enumeration did not establish |
| 13a | The two bails use **different** log categories (`0xA035E80` vs `0xA036AC0`); `0xA035E80` = `LogLokiRideable`; `0xA036AC0` UNRESOLVED; grep the text, not the category | **CONFIRMED** | all 11 rip-relative targets in the function resolved with capstone. Records decoded independently: `0x8B1CF08` line **299**, `0x8B1CFF0` line **327** (the game's own "whithout" typo present), `0x8B1CE28` line **257** (PreSpawn). `FLogCategory` bytes `05 00 05 07 a0a40100` vs `05 00 05 07 e5a40100` ⇒ FName `0x1A4A0` vs `0x1A4E5` — the report's numbers exactly. I re-decoded 7 of `0xA036AC0`'s other sites: `LokiGameMode.cpp:2717/2740/1364`, `LokiDropInGameMode.cpp:121`, `LokiPlayerState.cpp:4221/4233` — matching "~20 xrefs across LokiGameMode.cpp / LokiPlayerState.cpp". I then grepped the 634-file archived log corpus for four of its distinctive messages and for `… failed to get a player state`: **zero hits**. UNRESOLVED stands |
| 14 | `fkdis lea` false positive at `0x23FE774` decodes to `add rbx, 7` | **CONFIRMED** | bytes `... 48 8b 5d 40 | 48 83 c3 07 ...`; `48 83 c3 07` = `add rbx,7`, and `0x23FE774+4+0x07C38348 = 0xA036AC0`. (Nit: the instruction boundary is `0x23FE774` itself, not `0x23FE773` — the preceding `48 8b 5d 40` starts at `0x23FE770`.) |
| 15 | `callxref`/`findptr` 200-row cap not hit; `callxref 0x55C1B20` = 2 | **CONFIRMED** | reproduced: `0x55C1B08`, `0x55CD719` |
| 16 | `pdata_union.csv` has no row for `0x56680F0` or `0x55DCAA0` | **CONFIRMED** | grepped both; neither present |
| 17 | The prior lane's `0x55CD590..` window measures the wrong value | **CONFIRMED** | `0x55CD580 mov rcx,rax` reads the GM one instruction before the window starts; `0x55CD583 call` redefines rax. Both facts reproduced from my own decode |
| 20 | `LokiTeleportActor` is not any of the **five known** folds; control `AuthSetCurrentRideable` **does** list `impl=0xF7EC20` | **CONFIRMED, control NOT degenerate** | I re-read all five fold constants out of merged4 (`c20000`, `33c0c3`, `32c0c3`, `b001c3`, `0f57c0c3`) and found the fold-valued record myself. The control genuinely demonstrates the table surfaces folds. Correctly hedged to "not one of the **known** stubs" — it cannot exclude an unknown sixth fold, and the report does not claim it does |
| 21 | The 13 `LokiTeleportActor` args map 1:1 (arg4 `xmm3`, args5-13 `[rsp+0x20]..[rsp+0x60]`) | **CONFIRMED** | `binds_members.csv` class 4335 method 112 re-read: 13 params with the reported defaults (`MaxAdjustDistanceZ=400`, `InitialZAdjustMultiplier=0.5`, `bRequireGround=true`, `bEndFollowingActorOnSuccess=true`, `bRequireTerrain=false`). Win64: 3 by-ref aggregates + a float in `xmm3`, then 9 stack slots ending at `0x20+8*8 = 0x60` — matching the nine stores exactly. Constants re-read: `.rdata 0x8B1D4C8 = 7500.0` (double), `.rdata 0x76A10E0 = 0.5f`, `.data 0x99C87B8 = (0,0,0)` |
| 22 | The ordering trap: poking `PlayersInside (+0x120)` first makes `HasEverContainedPlayer` hit and the wall return **silently** at `0x55CD555` | **CONFIRMED** | re-disassembled `0x55DCAA0`: `mov rax,[rcx+0x120]` / `movsxd r8,[rcx+0x128]` / linear `cmp [rax],r9` loop → `je <found>`. *Addendum:* on an **empty** `PlayersInside` it does not return false — it falls through to a hash lookup at `[this+0x148]`, which the UHT table identifies as property 9 **`TSet<ALokiPlayerState> PlayersThatExited`**. The report notes the fall-through but does not name the set; the arm should know the predicate is `PlayersInside ∪ PlayersThatExited` |
| 23 | First append necessarily grows: `old=0, 1 > Max=0` → `NewMax = max(4,1) = 4`, a 32-byte game-heap allocation | **CONFIRMED** | simulated against the `0xF988D0` bytes: `Max==0` branch taken, `cmova` not taken, `lea rcx,[rax*8]` = 32, `mov [rdi+0xc], 4` |
| 24 | Identity: `.data` record `{name, thunk=0x5456380, impl=0x55CD510}`; UHT sig `(ALokiPlayerState*, const FVector&)` | **CONFIRMED** | record found independently at `.data 0x9C1E5B8`; `binds_members.csv` class 4540 method 3 re-read verbatim. Siblings also reproduced: `AuthPlayerDetachPlayerFromRidable impl=0x55CCCB0`, `AuthPlayerPreSpawnOnAddToPlane impl=0x55CD800`, `AuthPlayerEnterWorld impl=0x55CCE70`, and **`AuthPlayerEnterWorldNew impl=0xF7EC20`** — a *second* fold in this class that the report's §7 free finding does not mention |

---

## C. NET EFFECT ON THE ARM

**The recipe in §9 is byte-correct and I would fly it unchanged.** Every instruction of the
append, the array base, the element identity, the reload-after-grow and the "first append must
grow" note re-derived clean. The five items in section A change grades and one piece of
operational advice; none of them changes a line of the mirror code.

The one substantive downgrade: **"do not clean up the ordering" is [I], not [M]** — on the arm's
own measured state both orderings produce an identical valid array, so if a future arm ever has a
reason to reorder, R3 is not the argument that forbids it.

Two corrections to carry forward verbatim:

* `0x00F9891C` calls **`0x10078C0`**, not `0x0B078C0`.
* `PlayersAttached @ ULokiRideableComponent+0x130` is **[M] from the UHT `FArrayPropertyParams`
  record at `.rdata 0x8A50130` (`Offset = 0x0130`)**, with `PlayersInsideCount 0x011C` and
  `PlayersInside 0x0120` as same-pass positive controls — not from `binds_members.csv`
  declaration order.

**Coverage caveat that applies to everything in both documents:** merged4's `.text` is
**16,683 / 30,281 pages = 55.09 % decrypted**. Every whole-image byte-scan count in the report
(`lea` xrefs, `callxref`, `findptr`) is a **floor**. The one function under study is 100 %
decrypted, so no conclusion *about it* is coverage-blocked.

# S130 session-lead thread — the pooled spawn logs its own decline, and it does NOT consult the gate

All offline, `dumps/s129-poolgate/SUPERVIVE-Win64-Shipping.dump.exe`, ImageBase `0x7FF7B86D0000`.
Zero launches, zero injections, zero `.text` writes.

## 0. The vtable resolved OFFLINE — the handoff budgeted a staged launch for this

`tools/strxref/vtables.py` already indexes this image's vtables by class name. Slot `0x2D0` = index 90:

| class | vtable (.rdata) | slots | slot 90 |
|---|---|---|---|
| `UActorPoolManager` (engine) | `0x07DE3618` | 95 | `0x0B9E1F0` = `b0 01 c3` = **`mov al,1; ret`** (always TRUE) |
| `ULokiActorPoolManager` (Loki) | `0x08877A80` | 95 | **`0x56363F0`** — a real 93-byte function |

⇒ [M] the engine base's gate is a hard TRUE; the LOKI OVERRIDE is what can return false.

## 1. The gate, fully decoded — it reads a byte on `ALokiGameState`

`0x56363F0` (93 B, `.pdata` EXACT, page present):
```
push rbx / sub rsp,0x20 / mov rbx,rcx        ; rbx = this (ULokiActorPoolManager)
call 0x0B9E1F0                               ; Super::  -> mov al,1; ret
test al,al / je FAIL
mov rcx,rbx / call 0x12C7260                 ; = vtable slot 49 (devirtualised) -> the World
test rax,rax / je FAIL
lea rbx,[rax+0x258]                          ; &World[0x258]
cmp qword ptr [rbx],0 / je FAIL
call 0x5380690                               ; ALokiGameState::GetPrivateStaticClass  [M]
mov rdx,rax / mov rcx,rbx / call 0x12C7DD0   ; IsA-style check -> bool
test al,al / je FAIL
mov rax,[rbx] / test rax,rax / je FAIL
movzx eax, byte ptr [rax + 0x898]            ; <== THE RETURNED VALUE
ret
FAIL: xor al,al / ret
```
**`0x5380690` is `ALokiGameState::GetPrivateStaticClass` [M]** — `strxref.py func 0x5380690` shows it
references exactly the `GetPrivateStaticClassBody` literal triple:
`0x08981C70 U 'ALokiGameState'`, `0x088152C0 U '/Script/Loki'`, `0x0769ABD8 U 'Game'`.

**`0x12C7DD0` (31 B) is an `IsA`/class-chain walk [M]** — `mov rbx,[rcx]` (the pointer), null-check,
`mov rbx,[rbx+0x18]` (the object's `UClass` — this build's `classOff` IS `0x18`), null-check, then walk.

⇒ **[M] the actor-pool feature flag is `byte [ALokiGameState + 0x898]`**, reached as
`this->GetWorld()->[0x258]` (the GameState) after an `IsA(ALokiGameState)` test.
⇒ [I, strong] `UWorld+0x258` is `UWorld::GameState` — two independent code sites read that offset and
   test the result against `ALokiGameState::StaticClass()`.

## 2. ★ A FREE PER-ATTEMPT RECEIPT THAT S128/S129 NEVER USED

The pooled spawn **logs its own failure**, and it did so in the S128 flight:
```
docs/Loki-s128-poolspawn.log
[2026.08.20-02.00.41:653][398] LogActorPooling: Warning: Failed to spawn actor of type
    BlueprintGeneratedClass /Game/Loki/Core/GameModes/Objectives/Tutorial/Basics/BP_DropPod_Tutorial.BP_DropPod_Tutorial_C.
[2026.08.20-02.02.10:059][486] (identical)
```
**Exactly 2 occurrences in the whole `docs/` corpus** (unit: log lines; 1 file), matching the two
pooled-spawn probe calls P1 and P2. The `PrimePools : Feature is not enabled` line occurs 68 times
across 69 files — i.e. it is ambient startup noise, whereas this warning is attributable per attempt.
⇒ **Grep `Failed to spawn actor of type` before any further inference about the pooled path.**

## 3. The pooled spawn chain, resolved end to end

`strxref.py native "SpawnPoolableActorFromClass"` -> exec thunk **`0x537EEE0`** (700 B);
its final call at `0x537F16B` stores to the return slot ⇒ impl = **`0x566FF50`**.
```
0x566FF50 (+ chained 0x566FF8B..0x5670085):
   [rdx] = UClass*, must be non-null and pass a TObjectPtr validity check
   call 0x3EDBE70                 ; GEngine->GetWorldFromContextObject(rcx, 1)
   test rax,rax / je NULL
   lea rbx,[rax+0x258] / cmp qword[rbx],0 / je NULL      ; <-- SAME +0x258 AS THE GATE
   call 0x5380690                                        ; <-- SAME ALokiGameState::StaticClass
   mov rdx,rax / mov rcx,rbx / call 0x12C7DD0 / test al,al / je NULL   ; <-- SAME IsA
   mov rcx,[rbx] / test rcx,rcx / je NULL
   call 0x3840490                 ; reads [GameState+0x428], creates it if null
   call 0x5647F00  -> returned into rbp, then returned
0x5647F00 (137 B):
   call 0x5648050                 ; THE ACQUIRE (1086 B)
   test rax,rax
   je  -> UE_LOG(LogActorPooling, Warning, 'Failed to spawn actor of type %s.') ; site 0x5648009
   else mov r10,[rax] / call qword ptr [r10+0x578]  ; a virtual on the new actor
```
The format string `0x08B06390 U 'Failed to spawn actor of type %s.'` has **exactly 2 code refs**
(both `ptr-tbl`, invisible to a byte scan): `0x56389A2` (fn `0x563882A`, chained from `0x5638740`)
and `0x5648009` (fn `0x5647FFD`, chained from `0x5647F00`).

## 4. ★★ THE §2 ANSWER — THE POOLED SPAWN DOES NOT CONSULT THE GATE

Machine scan of **eight** function extents in the chain (`0x566FF50`, `0x566FF8B`, `0x5647F00`,
`0x5647F89`, `0x5647FFD`, `0x5648050`, `0x5638740..0x5638AA8`, `0x56181E0`), all mapped and non-zero:
**ZERO direct calls to `0x56363F0` and ZERO `call qword ptr [reg+0x2D0]` anywhere.**
The only indirect calls are `[r10+0x578]` / `[rax+0x578]` — a virtual on the SPAWNED ACTOR, not the
pool manager.

⇒ **[M] "the pool feature is disabled" and "the pooled spawn returns null" are DIFFERENT mechanisms.**
   The gate blocks *priming*; the spawn path never reads it.
⇒ **[M] and every predicate the two paths SHARE passed in the live world** — the warning is emitted
   strictly downstream of them, so in the staged tutorial world: `GetWorldFromContextObject` returned
   a world, `[World+0x258]` was non-null, it **was** an `ALokiGameState`, and the pool manager was
   obtained. The decline happens *inside* `0x5648050`.

## 5. Trap caught in this thread

`0x5648050` calls `0x3355FC0` and `0x334E7A0`, which sit 0x40 and 0x7860 below `PrimePools`
(`0x3356000`) and initially read as "the acquire calls into the pool manager". They are NOT:
`0x3355FC0` is `lock and dword ptr [rcx+8], edx` (an atomic flag op, and only a MED-tier heuristic
entry with **no `.pdata` row**, so even its start is unproven), and `0x334E7A0` is a generic
`TSet`/`TMap` hash find (`[rcx+0x34]` num, `[rcx+0x40]` hash, `[rcx+0x48]` size, `cmp esi,-1`).
**Code-band adjacency is not identity.**

## 6. Open, and now sharply posed
1. What inside `0x5648050` (1086 B) returns null? Only the first ~25 % was read here.
2. Is `SpawnPoolableActorFromClassDeferred`'s impl the OTHER warn site (`0x5638740` family)?
3. What is the UPROPERTY name/flags of `byte [ALokiGameState+0x898]`, and is it `CPF_Config`,
   `CPF_Net`, or plain? That decides whether the gate is ini-drivable or a data poke.
4. Does anything OTHER than `PrimePools` read the gate — i.e. is priming the only thing it blocks?

---

## 7. Follow-ups run after the first write-up

### 7.1 The gate is overridden by exactly ONE class [M]
`fkdis.py findptr 0x56363F0` -> **exactly one** `.rdata` qword: `0x08877D50`, which is
`0x08877A80 (ULokiActorPoolManager vtable) + 90*8` — independently reproducing the slot arithmetic.
Zero rel32 callers (expected: virtual-only dispatch).
⚠ **`0x0B9E1F0` is a ≥200-way fold** (`findptr` hit its 200 cap). So it is the image's universal
`mov al,1; ret` stub and **must not be named "the engine's IsEnabled"** — the correct statement is
*"the engine base's slot 90 is a return-true stub"*, which is a behavioural fact, not an identification.

### 7.2 Both pooled entry points converge on the same acquire, and neither reads the gate [M]
`SpawnPoolableActorFromClassDeferred` exec thunk `0x537F1A0` (696 B); its final call at `0x537F427`
⇒ impl **`0x5670090`** — the immediate neighbour of the non-deferred impl's chain end (`0x5670085`).
Its callees, in order: `0x3EDBE70` (GetWorldFromContextObject) -> `0x5380690`
(`ALokiGameState::GetPrivateStaticClass`) -> `0x12C7DD0` (IsA) -> `0x3840490` (pool mgr from
`[GameState+0x428]`) -> **`0x5648050`** — the SAME acquire, called **directly**, not via `0x5647F00`.
⇒ [M] identical predicate chain, zero gate consultation, on BOTH entry points.
⇒ [I, strong] **the DEFERRED arm's null is SILENT** — only the non-deferred path routes through
`0x5647F00`, which owns the warning. Consistent with the observation: **exactly 2 warnings, ~89 s
apart** (02:00:41 / 02:02:10), i.e. **one per injection** (`poolspawn` then `poolspawn-collmatch`),
not two per injection. ⇒ **do not read "no warning" as evidence about a deferred attempt.**

### 7.3 Who writes the gate byte — scanned, and correctly bounded [M, bounded]
Anchored scan of the whole `.text` section for byte-sized memory operands at displacement `0x898`
(366 raw `98 08 00 00` occurrences -> **11** real instructions, unit: instructions):
* `0x05636438  movzx eax, byte ptr [rax+0x898]` — **the gate; the only such read in the Loki band.**
* five `mov byte ptr [rbp+0x898], sil` — **rbp-relative stack frames, not object writes.**
* `0x06AE0A6A mov byte ptr [rax+0x898], dil`, `0x06ADD7D6 cmp bpl,[rcx+0x898]`,
  `0x031CDAA4 cmp byte ptr [rdi+0x898], r12b` — unattributed functions in unrelated bands.
⚠⚠ **Displacement `0x898` is NOT class-specific** — any class with a byte member there matches, so
those three are **not** evidence about `ALokiGameState`.
⚠⚠ **BOUNDED, exactly as this repo already records for `CurrentPhase`:** ~47 % of `.text` is
undecrypted, and a **replicated or config-loaded** property is written by computed-offset code
(net serializer / `FProperty::ImportText`) that a literal-displacement scan **cannot** see.
The honest form is *"no compiled literal-offset store exists in the decrypted image"*, never
*"nothing writes it."*

### 7.4 A trap avoided
`0x5648050` calls `0x3355FC0` and `0x334E7A0`, which sit within 0x8000 of `PrimePools`
(`0x3356000`). They are **not** pool functions: `0x3355FC0` is `lock and dword ptr [rcx+8], edx`
(an atomic flag op, and only a MED-tier heuristic entry with **no `.pdata` row** — even its start is
unproven), and `0x334E7A0` is a generic `TSet`/`TMap` hash find. **Code-band adjacency is not identity.**

## 8. What this implies for the repair (session lead's reading)
The gate and the spawn are **two different locks**:
* **Lock A — priming.** `PrimePools` refuses unless `byte[ALokiGameState+0x898]`. `ALokiGameState` is a
  client-resident replicated actor already located live in the staged world by S124, so this is a
  **single aligned DATA poke** — the safest write class this project has measured
  (nothing 0/22 · bytecode 0/9 vs standing `.text` 7/8) — with `PrimePools` (**not** a reflected
  UFUNCTION; raw direct call to `0x3356000` with `this` = the pool manager) as the follow-up.
* **Lock B — the acquire.** `0x5648050` declines for a reason not yet read. If that reason is
  "no pool exists for this class", Lock A is upstream of it and the two-step fixes both. If it is
  anything else, poking the byte changes nothing — and **that is exactly the discrimination the next
  flight must be designed to make.**

### 7.5 ★ `UWorld+0x258` IS `UWorld::GameState` — [I] UPGRADED TO [M], third independent instrument
`strxref.py native "GetGameState"` -> `UGameplayStatics::GetGameState` exec thunk `0x38047F0`.
Its body ends:
```
0x03804862  mov  rcx, qword ptr [rip + 0x67b5207]   ; GEngine
0x03804869  call 0x3EDBE70                          ; UEngine::GetWorldFromContextObject
0x0380486E  test rax, rax / je -> return nullptr
0x03804873  mov  rax, qword ptr [rax + 0x258]       ; <<<< UWorld::GameState
0x0380487A  mov  qword ptr [rdi], rax               ; the UFUNCTION return slot
```
⇒ **[M] `UWorld+0x258` = `UWorld::GameState`**, and `0x3EDBE70` = `UEngine::GetWorldFromContextObject`
(the same helper both pooled entry points call). Three unrelated functions agree on the offset.

### 7.6 THE GATE, in one line [M]
```
ULokiActorPoolManager::vtable[90]  ==  ((ALokiGameState*)GetWorld()->GameState)->byte@0x898
```
guarded by: `Super::` (a return-true fold) · `GetWorld() != null` · `GameState != null` ·
`GameState IsA ALokiGameState`.

### 7.7 The acquire's null-return paths — 9 branches [M]
`0x5648050`'s real extent is **`0x5648050 .. 0x5648EC6` = 3,702 B across 3 chained `.pdata` rows**
(the 1,086 B figure is only the first row). 819 instructions decode; the null exit is `0x5648EA1`
(`xor eax,eax`), reached by **9** branches (unit: branch instructions):
`0x56480B8 · 0x56480C6 · 0x56480FE · 0x564810C · 0x5648119` (the class TObjectPtr-validity block)
then the substantive ones:
* `0x0564817A` — `test byte ptr [rax + 0xdc], 1` / `jne` (a flag bit on the class or CDO)
* `0x05648210` — `cmp byte ptr [rax + 0x6c], r14b(0)` / `jne`
* `0x5648D97` — not yet read
* `0x5648E6F` — `test r14, r14` / `je`: the final "did we actually get an actor" test.
Success path sets `byte[actor+0x374]` from `byte[actor+0x2d3]` / `byte[actor+0x2d8]` and returns the actor.
⚠ Not yet resolved which branch fired live. **That is the remaining question.**

⚠ **Honesty note on §7.7:** the four substantive branches were read from a **linear sweep** starting at
the function entry. That is normally correct but is not proof of instruction alignment throughout a
3,702-byte body, and one reading does not add up: `r14` is zeroed at `0x5648124` yet is used both as a
zero constant (`cmp byte ptr [rax+0x6c], r14b`) and as a live pointer (`test r14,r14` at `0x5648E6F`,
`byte[r14+0x374]`), so **r14 must be reassigned somewhere I did not read.** Treat the branch list as
[M] (they exist and target the null exit) and the per-branch *semantics* as **[I], unverified**.
Do not act on the semantics without a second, independent decode.

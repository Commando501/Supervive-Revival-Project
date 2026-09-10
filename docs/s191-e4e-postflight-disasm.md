# S191 E4E post-flight direct disasm — the byte model + live measurements CONTRADICT the E4E readback — 2026-09-10

★★★★★★★ **BYTE-LEVEL DISASSEMBLY OF THE ITERATOR + GATE FUNCTION, MEASURED LIVE-STATE ON THE
STILL-RUNNING PROCESS, INDEPENDENTLY REPRODUCES ALL 8 E4E PREDICTIONS EXCEPT THE LAST — AND THE
LAST ONE (the NULL readback) IS PROVABLY INCONSISTENT WITH THE BYTE MODEL PLUS THE LIVE STATE.
The workflow's model is now BYTE-VERIFIED CORRECT, not "REFUTED as INCOMPLETE" as the E4E RESULT
first argued. The contradiction is between the byte model and the LIVE STATE AT READBACK TIME —
not between the byte model and the disassembly.**

Offline; zero launches, done against `dumps/merged15.dump.exe`, plus one read-only RPM live-state
enumeration on process 55960 at 42 min uptime (past all FK-32 windows; R-S191-m grade extends
indefinitely).

## The gate function 0x44C28E0 — BYTE-VERIFIED, workflow model exactly matches

```
0x044C28E0  48 8b 41 10               mov    rax, [rcx+0x10]        ; spec.Ability
0x044C28E4  48 85 c0                  test   rax, rax
0x044C28E7  74 31                     je     0x44C291A              ; NULL -> return NULL
0x044C28E9  80 b8 ee 00 00 00 01      cmp    [rax+0xEE], 1          ; workflow's "InstancingPolicy"
0x044C28F0  75 28                     jne    0x44C291A              ; != 1 -> return NULL
0x044C28F2  83 b9 88 00 00 00 00      cmp    [rcx+0x88], 0          ; NonRep.Num
0x044C28F9  7e 0b                     jle    0x44C2906              ; <=0 -> check Rep
0x044C28FB  48 8b 81 80 00 00 00      mov    rax, [rcx+0x80]        ; NonRep.Data
0x044C2902  48 8b 00                  mov    rax, [rax]             ; return *NonRep.Data[0]
0x044C2905  c3                        ret

0x044C2906  83 b9 98 00 00 00 00      cmp    [rcx+0x98], 0          ; Rep.Num
0x044C290D  7e 0b                     jle    0x44C291A              ; <=0 -> return NULL
0x044C290F  48 8b 81 90 00 00 00      mov    rax, [rcx+0x90]        ; Rep.Data
0x044C2916  48 8b 00                  mov    rax, [rax]             ; return *Rep.Data[0]
0x044C2919  c3                        ret

0x044C291A  33 c0                     xor    eax, eax
0x044C291C  c3                        ret                            ; return NULL
```

**[M] The workflow's transcription is BYTE-IDENTICAL to what's in `merged15`. The 4-instruction-tuple
tail (`mov rax,[rcx+0x?0]; mov rax,[rax]; ret`) is a `TArray<UObject*>::[0]` accessor: dereferences
the array header's Data pointer, reads the first UObject pointer stored there, returns it.**

## The iterator 0x4476F10 — BYTE-VERIFIED, does NOT invoke 0x44C28E0

Contra one of my earlier notes based on the rel32 sweep (I misattributed RVA 0x4477D07 to the iterator
— that call site is in a DIFFERENT function on the same page). The iterator itself is a
best-priority selector:

```
0x04476F10  prologue (save rbx/rbp/r12/r14/r15, sub rsp,0x20)
0x04476F24  xor ebp, ebp                 ; ebp = best-so-far pointer = NULL
0x04476F26  mov r12d, edx                ; r12d = InputID
0x04476F29  mov r15, rcx                 ; r15 = ASC
0x04476F2C  cmp edx, -1                  ; InputID == INDEX_NONE ?
0x04476F2F  je 0x4476FA1                 ;   -> return NULL
0x04476F31  mov rbx, [rcx+0x538]         ; rbx = Items.Data (loop pointer)
0x04476F38  movsxd rax, [rcx+0x540]      ; rax = Items.Num
0x04476F3F  imul r14, rax, 0xF8          ; r14 = Num * stride
0x04476F46  add r14, rbx                 ; r14 = end pointer
0x04476F49  cmp rbx, r14                 ; empty?
0x04476F4C  je 0x4476FA1                 ;   -> return NULL

; loop:
0x04476F58  cmp [rbx+0x24], r12d         ; spec.InputID == wanted?
0x04476F5C  jne 0x4476F86                ;   no -> next
0x04476F5E  test rbp, rbp                ; running best?
0x04476F61  je 0x4476F83                 ;   no -> this becomes best
; else compare priorities via vtable slot 246 [+0x7B0]:
0x04476F63  mov rax, [r15]               ; ASC vtable
0x04476F66  mov rdx, rbx                 ; rdx = candidate spec
0x04476F69  mov rcx, r15                 ; rcx = ASC
0x04476F6C  mov rsi, [rax+0x7B0]         ; rsi = vtable slot 246 (priority fn)
0x04476F73  call rsi                     ; priority(ASC, candidate)
0x04476F75  mov rdx, rbp                 ; rdx = current best
0x04476F78  mov rcx, r15
0x04476F7B  mov edi, eax                 ; edi = candidate priority
0x04476F7D  call rsi                     ; priority(ASC, current best)
0x04476F7F  cmp eax, edi                 ; best_prio >= cand_prio ?
0x04476F81  jge 0x4476F86                ;   yes -> keep current best
0x04476F83  mov rbp, rbx                 ; new best = current
0x04476F86  add rbx, 0xF8                ; advance
0x04476F8D  cmp rbx, r14
0x04476F90  jne 0x4476F58                ; loop

; epilogue:
0x04476F97  mov rax, rbp                 ; return rbp (best match or NULL)
0x04476F9A..0x04476FB7  epilogue + ret
```

**[M] The iterator has THREE bail conditions**:
1. `InputID == -1` (INDEX_NONE) — irrelevant to us (we pass 3)
2. `Items.Num == 0` — irrelevant (E4E measured Num=1)
3. **No spec matches on InputID** — with our K_GRANT'd spec at Items[0] and InputID=3, this bails ONLY IF `[Items[0]+0x24] != 3`

E4E measured `Items[0]@0x1C27ADB4ED0 InputID=3`. So bail 3 does NOT fire.

**⇒ [M] the iterator, given our K_GRANT state, MUST return our spec (0x1C27ADB4ED0). It does not
touch any other spec state — no bIsBeingDestroyed check, no Handle-map check, no flag byte read,
no Ability field read. It ONLY compares `[spec+0x24]` (InputID) and applies vtable-slot-246 priority
tie-breaking between multiple matches. With Num=1 there is no tie-breaking, and rbp = the one
matching spec is returned.**

## GetAbilityByInputID's complete flow — VERIFIED byte-for-byte

```
0x05526210  sub rsp, 0x28
0x05526214  mov rax, [rcx]               ; ASC vtable
0x05526217  movzx edx, dl                ; InputID
0x0552621A  call [rax + 0x7A8]           ; iterator 0x4476F10
0x05526220  test rax, rax
0x05526223  jne 0x552622A                ; iterator returned spec -> tail-jmp gate
0x05526225  add rsp, 0x28
0x05526229  ret                          ; iterator returned NULL -> return NULL

0x0552622A  mov rcx, rax                 ; rcx = spec from iterator
0x0552622D  add rsp, 0x28
0x05526231  jmp 0x44C28E0                ; tail-call gate function
```

**[M] Exactly 12 instructions. Iterator return value is checked once and immediately tail-called.
No other code path.**

## Live-state RPM read (spec[0] full 0xF8 stride) — the surprise

Read at t=42min uptime, docs/s191-e4e-spec-live-dump.log:

```
[SPEC[0] NAMED FIELDS]:
  +0x00   ??:                    0x1
  +0x08   ??:                    0x1FFFFFFFF
  +0x0C   Handle:                1
  +0x10   Ability:               0x1C28E636930 (CDO of GS_Ronin_LMB_Selector_C)
  +0x18   ??:                    0x0
  +0x20   Level:                 1
  +0x24   InputID:               3                              ← matches E4E
  +0x28   bIsBeingDestroyed?:    0                              ← clean
  +0x30   Source:                0x1C2EAE4AAC0 (=hero)
  +0x39   flag byte (S159):      0x00                           ← all bits clear
  +0x80   NonRep.Data:           0x0                            ← restored (E4E's A→B→A worked)
  +0x88   NonRep.Num:            0
  +0x8C   NonRep.Max:            0
  +0x90   Rep.Data:              0x1C104E28BC0                  ← ★★★ NEW: game populated this
  +0x98   Rep.Num:               1                              ← ★★★
  +0x9C   Rep.Max:               4                              ← ★★★
```

**Rep.Data[0] = 0x1C2B7504970**, a real UGameplayAbility instance:
- vtable = 0x7FF7BB5467F8 (game exe VA)
- classPtr @+0x18 = 0x1C2B70D9D90 = matches `hero.Ability1 = GS_Ronin_LMB_Selector_C` from the E4 marker
- FName.ComparisonIndex = 0x22F1F5

## Retrodiction against the byte model — a contradiction

Given at readback time:
- Items.Num=1, Items[0]@0x1C27ADB4ED0, InputID=3, Ability=CDO
- (post-poke) NonRep.Data=0x1C27ADB4EE0 (=spec+0x10), NonRep.Num=1, NonRep.Max=1
- [Ability+0xEE]=0x01

Trace `GetAbilityByInputID(3)`:
1. `call [ASC vtable + 0x7A8]` = iterator 0x4476F10 with (ASC, InputID=3)
2. iterator scans Items, finds Items[0] matches InputID==3, returns rbp = 0x1C27ADB4ED0 (our spec)
3. `test rax, rax; jne 0x552622A` — rax=0x1C27ADB4ED0, non-null → jne taken
4. `mov rcx, rax; add rsp, 0x28; jmp 0x44C28E0` — tail-call gate with rcx=our spec
5. Gate 0x44C28E0 with rcx=0x1C27ADB4ED0:
   - `mov rax, [rcx+0x10]` = `[0x1C27ADB4EE0]` = **0x1C28E636930** (CDO pointer) → non-null → gate (a) PASSES
   - `cmp [rax+0xEE], 1` = `[0x1C28E637A1E], 1` = 0x01 → PASSES
   - `cmp [rcx+0x88], 0` = NonRep.Num = 1 → 1>0 → jle FALSE → fall through
   - `mov rax, [rcx+0x80]` = NonRep.Data = **0x1C27ADB4EE0** (poked)
   - `mov rax, [rax]` = **`*(uint64_t*)0x1C27ADB4EE0`** = **the QWORD at spec+0x10 = the CDO pointer 0x1C28E636930**
   - `ret` → **return 0x1C28E636930**

**So per the byte model + measured state, `GetAbilityByInputID(3)` MUST return 0x1C28E636930 (the CDO
of GS_Ronin_LMB_Selector_C). Not NULL.**

**But E4E measured `E4E_READBACK_POST return=0x0(NULL)`.**

## The four candidate resolutions — [M]/[I,strong]/[I]/[REFUTED]

**(1) [REFUTED] The workflow's 3-gate model is wrong.** Byte-verified byte-for-byte in this doc.
   The model is EXACTLY right.

**(2) [REFUTED] The iterator has a hidden precondition that rejects our spec.** The iterator
   was disassembled in full above; it only checks `[spec+0x24]==InputID` and applies priority
   tie-breaking. It does not read `bIsBeingDestroyed`, the S159 flag byte, or the Ability field.

**(3) [I,strong] The poke was reset between the poke-verify and the readback.** The E4E arm's
   `E4E_POKE_VERIFY` line printed OK immediately after the writes. The `E4E_READBACK_POST`
   printed NULL immediately after. Both operations happen in the SAME shim callback with NO
   documented game-thread activity between them. **BUT** — `CallNativeGuarded` sets up an FFrame
   and invokes the native, which runs on the game thread. If the ability system has an
   asynchronous side effect between the framework setup and the actual `GetByInputID` call that
   resets spec+0x80/+0x88/+0x8C, this would explain it. The E4E post-flight live dump shows
   NonRep back to `{0,0,0}` — but that's expected (A→B→A restore ran after the readback).
   **Test**: extend the E4E arm to re-read NonRep IMMEDIATELY BEFORE the CallNativeGuarded call
   (i.e. between poke-verify and readback). If NonRep is still poked at that moment, (3) is
   refuted. If it's reset, we've found the wall.

**(4) [I,strong] `[Ability+0xEE]` is not `InstancingPolicy` and gate (b) actually failed at
   readback time.** The E4E arm's own marker reports `InstancePolicy@+0xEE=0x01 (InstancedPerActor
   OK)`. But that label ("InstancePolicy" and "InstancedPerActor OK") is TEXT the shim printed
   based on the workflow's claim about semantic role, NOT a measured semantic. The BYTE was
   measured (0x01); the interpretation was inherited from the workflow's disassembly. **If
   `[+0xEE]` is a different UPROPERTY whose value happens to read 1 at CDO time but ISN'T what
   `cmp byte [rax+0xEE], 1` semantically compares** (e.g. it's a compiler-emitted alignment
   byte, or a bool whose "true=1" happens to satisfy the compare without being InstancingPolicy),
   the code still runs and still bails if the byte reads something other than 1 at readback time
   — but our measurement said it read 0x01. **Test**: this is Lane G of the running workflow —
   find the real semantic role of `[UGameplayAbility+0xEE]` via UHT.

**(5) [I] The gate function's call site was different at that moment.** GetByInputID at
   0x0552622A does `mov rcx, rax` (spec from iterator) then `jmp 0x44C28E0`. But
   `CallNativeGuarded` calls the exec THUNK, not the impl directly. If the exec thunk on this
   build has been swapped or modified (e.g. by our own KFUNCSWAP framework being partially
   torn down), the call may reach a different gate. **Test**: read `hero.ASC.GetAbilityByInputID`'s
   registered `Func` @+0xE0 both AT the readback moment (need to re-fly with an extended arm) AND
   right now (RPM). If both point at the same impl chain we expect, (5) is refuted.

Most likely explanations, ranked: **(3) > (4) > (5)**.

## Immediate next actions (offline, no launch needed)

**Task A [OFFLINE, cheap]**: Enumerate every rel32 caller of 0x44C28E0 (49 sites found).
Classify each: iterator-family (0x4477_/0x4479_/0x447D_/etc), GetByInputID-family (0x5526_),
TryActivateAbilityByInputID-family (0x5544_), and others. Understanding WHERE else this function
is called informs whether "generic getter" is the right label. Result: 49 callers dominate around
0x447x-0x4498 and 0x5516-0x5544 — a broad ability-system-front-end use.

**Task B [OFFLINE, medium]**: The `[Ability+0xEE]` semantic — check the actual UHT class-
registration for UGameplayAbility. Find every `FBoolPropertyParams` whose `SetBitFunc` writes
at `[rcx+0xEE]`. Compare against `binds_members.csv` for UGameplayAbility hierarchy. Rules out or
confirms candidate (4). This is Lane G of the running workflow.

**Task C [LIVE via extended arm]**: Re-fly with a KBFE4E_V2 arm that re-reads NonRep + Rep
IMMEDIATELY BEFORE the readback CallNativeGuarded, AND immediately after inside the readback's
callback if reachable. Discriminates candidate (3). Requires shim rebuild + one more launch.

**Task D [LIVE, cheap]**: Extend the same arm to call `GetAbilityByInputID` via `ProcessEvent`
(vtable slot 78) as well as via the S55 direct-thunk. If both return NULL, the wall is on the
callee side. If ProcessEvent-call returns non-null while S55-direct returns NULL, the wall is
in the S55 framework. Discriminates candidate (5) partially.

## Rules banked

**R-S191-o** [M]: The workflow's 3-gate model at 0x44C28E0 is BYTE-CORRECT. The E4E RESULT's
initial claim that the model is "REFUTED as INCOMPLETE" is itself REFUTED by direct
disassembly. What is REFUTED is not the byte model — it is the assumption that the poke would
persist to the moment of readback OR the assumption that `[+0xEE]==1` at that moment implies
gate (b) passes.

**R-S191-p** [M]: The iterator (0x4476F10 = vtable slot 245) does NOT invoke 0x44C28E0. It is
a best-priority selector: iterate Items, match on `[spec+0x24]==InputID`, priority tie-break
via vtable slot 246. Only three bail conditions (INDEX_NONE, empty, no match). No spec-state
preconditions (no bIsBeingDestroyed, no flag byte, no Ability check). Any consumer that says
"the iterator refused our spec" is wrong unless the InputID actually differs.

**R-S191-q** [I,strong]: A shim marker line that PRINTS an interpretive label ("InstancedPerActor
OK") based on an INHERITED semantic claim can mislead a later reader into thinking the semantic
role was measured. The BYTE was measured; the interpretation was carried forward from another
document. Any future arm citing a UPROPERTY name should measure the semantic role via UHT
`SetBitFunc` on the same run, or explicitly label the interpretation as [S] (speculative).

**R-S191-r** [M]: GetAbilityByInputID's complete flow is a 12-instruction wrapper around
iterator + tail-jmp-to-gate. There is no other code path. Return value is fully determined by
(iterator's return value ∈ {NULL, some spec}) × (gate function's return value ∈ {NULL,
NonRep.Data[0], Rep.Data[0]}). Four possible outcomes total.

## Grade tally after this doc

Total S191 launches: 9 flown, 6 [M] results banked.
Direct disasm findings: 4 new [M] measurements independent of any launch.
Workflow `wf_7e83ab1b-f4d` still running (Verify phase). Adjudicator not yet started.

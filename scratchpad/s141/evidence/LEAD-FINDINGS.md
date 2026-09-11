# S141 SESSION LEAD — independent findings, before the lanes reported

Instrument: `scratchpad/s141/tools/peimg.py` + `cfg.py` over `dumps/merged14.dump.exe`
(ImageBase 0x7FF608F40000, FLAT verified). Controls: DARK ctrl `0x5A6AC40` = 0/4096 PASS;
5/5 fold constants byte-exact; 4 LIT positive controls.

## 1. T3-A ANSWERED: **Velocity.Z is NOT zeroed.** [M]

    035ed973  movups xmm0,[rbp+0x168]   ; gravity-space X,Y (doubles)
    035ed97a  movsd  xmm1,[rbp+0x170]   ; Y
    035ed982  mulsd  xmm0,xmm0          ; X*X
    035ed986  mulsd  xmm1,xmm1          ; Y*Y
    035ed98a  addsd  xmm1,xmm0          ; SizeSq2D  <- Z at [rbp+0x178] NOT included
    035ed98e  comisd xmm1,[.rdata 0x077F5180]
    035ed996  ja 0x35ed9c8
    035ed998  xorps  xmm0,xmm0
    035ed9ac  movups [rbp+0x168],xmm0   ; **16 BYTES** -> zeroes gravity-space X and Y ONLY.
                                        ;   [rbp+0x178] (gravity-space Z) SURVIVES.
    035ed9b3  call 0x35f4620            ; grav->world quat rotate; `mov rax,rdx` early => returns OUT
    035ed9b8  movups xmm0,[rax] / 035ed9bb movups [rsi],xmm0
    035ed9be  movsd  xmm1,[rax+0x10] / 035ed9c3 movsd [rsi+0x10],xmm1

xmm1 at 0x035ED9C3 is loaded at 0x035ED9BE from the transform's OUTPUT, not from a zero.
Under default gravity the quat is identity so the round trip is a pass-through, and
**Velocity.Z is preserved.**

**Consequence: the fixed point is 2-D, not 3-D.** A purely VERTICAL kick is not protected by this
gate — but it also is not what is missing.

## 2. CORRECTION — the gate-constant identity in `docs/s140-t2-armj-THE-BOT-WALKS.md` 4b is WRONG

`.rdata 0x077F5180` = **0.00099999997473787516**.
  * `(double)(float)1e-3`      = 0.0010000000474974513   <- what the doc asserts. NOT this.
  * `(double)(float)1e-4 * 10` = 0.00099999997473787516  <- **this**, i.e. UE_KINDA_SMALL_NUMBER
    (float) times ten, matching stock UE's `SizeSquared2D() <= UE_KINDA_SMALL_NUMBER*10.f`.
Escape threshold sqrt(gate) = **0.03162277644...** (the doc's ~0.0316 stands).

## 3. THREE Velocity-zeroing sites found, and **ALL THREE PRESERVE Z**

  a. engine PhysFalling `0x035ED9AC..0x035ED9C3` — the 2-D SizeSq gate above.
  b. **ULokiCMC::PhysFalling `0x055B8FBE`** (NEW, in no repo doc): a lateral fall-speed limiter
     gated on the float at `CMC+0x1678` being >= 0. It explicitly SAVES `[rbx+0xf8]` (Vz) at
     0x055B8FB3 and RESTORES it at 0x055B8FC5. `0x055B9063` writes
     `[rbx+0x1678] = 0xbf800000 = -1.0f`, so **-1.0 is the disabled sentinel**.
  c. engine `CalcVelocity`'s input clamp zeroes all three — but engine PhysFalling brackets every
     CalcVelocity call with `mov [rdi+0xf8], r13` (r13 = 0) then `movsd [rdi+0xf8], xmm14`
     (restore OldVelocity.Z) at 0x035ECBD1/0x035ECBDE, 0x035ECFE2, 0x035ED5CE — the stock
     `Velocity.Z = 0; CalcVelocity(); Velocity.Z = OldVelocity.Z;` idiom. **Z is restored.**

## 4. `CMC+0x1A0` IS `GravityScale` [M], and it RESOLVES THE S132 DISMOUNT (T3-B)

  `035e3680  mulss xmm0, dword ptr [rbx + 0x1a0]`  in **engine `GetGravityZ 0x35e3650`**:
      GetGravityZ() = <physics-volume gravity, 0x3632e20> * [this+0x1A0]
  S132's dismount recipe includes **`[mv+0x1A0] = 1.0f`** (`0x55CCDC2`).
  So **[M] the dismount's "hero fell with X and Y FROZEN, Z accelerating" was a GravityScale
  RESTORE, not a velocity write.** Pure vertical escape — exactly that signature.

  Also [M]: engine `GetGravityZ` returns **0.0f** iff `[CMCvt+0xCE0]()` is true AND
  `byte [this+0x1001] == 0`. `vt+0xCE0` resolves to **`0x035E6810`** on BOTH CMC vtables
  (not overridden) — the repo already identifies `0x035E6810` as **`IsDashing`**
  (`cmp byte [rcx+0x231],6`). So on `MOVE_Falling(3)` that arm is not taken. **Gravity is not
  suppressed for a falling pawn.**

  `ULokiCMC::GetGravityZ 0x055AB8C0` and `ULokiCMC::NewFallVelocity 0x055B6AD0` are BOTH REAL and
  BOTH gate their Loki behaviour on `[this+0x231] == 7` (`MOVE_Custom` in this build). On
  `MOVE_Falling` both delegate to the engine unchanged. **Neither zeroes gravity.**

## 5. GRAVITY IS REACHED BY EXACTLY TWO MANDATORY GATES, NEITHER VELOCITY-DEPENDENT [M]

Sound CFG of engine `PhysFalling 0x035EC850`: **1482 insns, 79 calls, 0 indirect jumps,
0 decode failures.** Edge-removal (not node-removal) gate analysis for the `GetGravityZ` call
`0x035ECC21` and both `NewFallVelocity` calls `0x035ECCEF` / `0x035ED617` gives **exactly 2**
mandatory gate edges, identical for all three:

    0x035EC881  jb 0x35ee577   fallthrough MANDATORY   comiss DeltaTime, MIN_TICK_TIME
    0x035EC97C  jge 0x35ee507  fallthrough MANDATORY   cmp Iterations, [rdi+0x3E4] MaxSimulationIterations

`ULokiCMC::StartNewPhysics` passes Iterations through UNCHANGED (tail `jmp 0x3600990`, r8d
untouched) and engine SNP forwards it as `edi` then `r8d`. With Iterations==0 and
MaxSimulationIterations==1 (measured), **both gates pass.**

`rsi` has exactly ONE defining `lea rsi,[rdi+0xe8]` (0x035EC9AC) plus the epilogue restore
(0x035EE519) — the S140 dominance claim confirmed with the full def list.
**36 Velocity write instructions** in engine PhysFalling.

## 6. THE FRAMING CORRECTION: "StartNewPhysics runs" is NOT "the physics step runs"

`ULokiCMC::StartNewPhysics 0x055C2430`:

    055c2430 movaps xmm2,xmm1
    055c2433 test r8d,r8d / 055c2436 jne 0x55c2475
    055c2448 movups xmm0,[rcx+0xe8]        ; read Velocity
    055c244f movups [rcx+0x16b0],xmm0      ; <-- THE PAYLOAD WRITE S140 T2 MEASURED
    055c2456/5e  movsd [rcx+0x16c0], [rcx+0xf8]
    055c2469 mov byte [rcx+0x16c8],1
    055c2470 jmp 0x3600990                 ; <-- ONLY NOW is the ENGINE entered

**The payload write sits in the LOKI WRAPPER'S PROLOGUE, entirely upstream of the engine call.**
S140 Tier 2's own headline — "`ULokiCMC::StartNewPhysics 0x055C2430` RUNS" — is literally correct.
But `CLAUDE.md` and `docs/next-session-prompt-s141.md` restate it as **"the physics step runs
every frame"**, and that crosses a function boundary. Engine `StartNewPhysics 0x03600990` has
**four** early-outs downstream of the payload write:

    036009A8 comiss dt, MIN_TICK_TIME      / 036009AF jb  -> bail
    036009B5 cmp r8d,[rcx+0x3e4]           / 036009BC jge -> bail
    036009C5 call [rax+0x6b8] HasValidData / 036009CD je  -> bail
    036009E4 call [UpdatedComp vt+0x4c0] IsSimulatingPhysics / 036009EC je -> CONTINUE (true -> log + RET)

So **nothing measured so far establishes that `PhysFalling` ever ran on the untreated bot.**
Same class of error S139 committed in the opposite direction with `+0x12B0`, and the repo's own
rule ("do not cross a function boundary with an inference") names it.

## 7. THE PLAYER'S NO-FALL IS SELF-INFLICTED AND ALREADY ON RECORD [M]

`docs/s138-flight9-movement-not-simulating.md:17` — GravityScale: **BOT 1.000 / PLAYER 0.000
"(zeroed by `sp`'s LIFT step)"**. `sp` is OUR OWN staging shim.
So the PLAYER never falling in S140 flight 3, despite a 600 uu/s kick, is **fully explained and is
not evidence about the game.** `docs/s140-t2-armj-THE-BOT-WALKS.md` 2 presents it as an
unexplained observation and infers "a real GAS-treatment dependency in the MOVER" from it. The GAS
dependency on the **horizontal decay** stands (that is the `CalcVelocity` clamp, 3 of that doc);
the **no-fall** half of it does not — it is a GravityScale of zero that we set ourselves.

## 8. WHAT REMAINS OPEN — the BOT's no-fall

BOT: `MOVE_Falling(3)`, `GravityScale 1.000`, `Velocity` exactly (0,0,0), position frozen at
(600, 0, 13240) for 97 s. Gravity's two mandatory gates are velocity-independent; both Loki
gravity overrides delegate to the engine on mode 3; the engine's zero-gravity arm needs
`IsDashing`. **Nothing found offline explains it.**

The live discriminator is one read: **does engine `StartNewPhysics` bail?** Its three silent bails
are dt, Iterations, and `HasValidData`.

### 8a. A SELF-CORRECTION, made before publication

I first wrote here: *"`+0x12B0 TimeSinceFallingStart` has TWO writers —
`ULokiCMC::PerformMovement 0x055B8414` (once per frame) and `ULokiCMC::StartNewPhysics 0x055C248B`
(per substep re-entry from `PhysFalling`'s tail). S139 measured 1.0x, not 2.0x, so [I, strong] the
substep re-entry never happens and `PhysFalling` never reaches its tail."*

**REFUTED by my own follow-up check.** The two writers are real and are exactly those two
([M]: 2 hits each, 0 in either `PhysFalling`). But **[M] NEITHER `PhysFalling` EVER CALLS
`StartNewPhysics`**: vtable displacement `0x720` appears in neither function's call set, there is
no direct call to `0x3600990` or `0x055C2430` from either, and neither has any tail jump outside
its own body. So the `r8d > 0` writer is unreachable from `PhysFalling` on this route, and a
**1.0x** advance is exactly what `PerformMovement` alone produces **whether or not `PhysFalling`
runs**. The measurement does not discriminate, and the inference was worth nothing.

Kept, because the corrected form is still useful: **`TimeSinceFallingStart`'s 1.0x advance is
driven solely by `ULokiCMC::PerformMovement 0x055B8414`**, which independently re-confirms S139's
attribution of that observable — and it means `+0x12B0` can never be used as a `PhysFalling`
receipt.

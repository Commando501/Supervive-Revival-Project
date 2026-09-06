- ★★★★★★ **S141 TIER 3 (2026-08-23/24) — THE ENGINE MOVER CHAIN RUNS, AND THE WALL MOVED TO THE PAWN
  WITH INPUT. Read `docs/s141-tier3-settled.md`; its §4 and §6 govern. Then
  `docs/next-session-prompt-s142.md`.** Six offline lanes over `merged14` + ONE staged flight
  (`armk` RAW `8278c6031d05756c`, pre-registered at `docs/s141-t3-armk-PREREGISTERED.txt` BEFORE launch).
  ★★★★★ **[M] ONE 4-BYTE WRITE OF `GravityScale = 1.0f` AND THE PLAYER HERO FELL 23,189 uu** — from
  `Z = 13240` to `Z = -9935` in 10 s, `Velocity.Z` pinned at terminal `-4000`. It was given
  `Velocity = (0, 600, 0)`, i.e. **`Vz` EXACTLY ZERO** ⇒ **gravity integrates from `Velocity.Z == 0`,
  and `TickComponent → ControlledCharacterMove → PerformMovement → StartNewPhysics → PhysFalling` all
  execute on this client.** ⛔ **"`Velocity == 0` stops the mover" IS DEAD — do not re-open it.**
  ★★★★★ **[M] `CMC+0x1A0` IS `GravityScale`** (engine `GetGravityZ 0x035E3650` ends
  `035e3680 mulss xmm0,[rbx+0x1a0]`; three agreeing instruments incl. `binds_members.csv` property
  index 0), **and the PLAYER's non-fall was SELF-INFLICTED**: `sp`'s LIFT-TO-SEE block
  (`tutorial_launch.cpp:12877-12890`) sets it to `0.0f`, `[LIFT] gravity OFF` is line 24 of every
  staged `sp` marker, and `docs/s138-flight9-movement-not-simulating.md:17` recorded BOT 1.000 /
  PLAYER 0.000 the day before. ⇒ `docs/s140-t2-armj-THE-BOT-WALKS.md` §2's inference of "a real
  GAS-treatment dependency in the MOVER" survives for the **horizontal decay** and is **REFUTED for
  the non-fall.**
  ★★★★★ **AND IT RESOLVES S132's DISMOUNT [M]:** `0x55CCDC9 mov dword [r14+0x1a0], 0x3f800000` is
  `GravityScale = 1.0`, and an exhaustive write scan finds **no velocity write in that function** ⇒
  the hero fell with **X and Y frozen** because it was **pure gravity switched back on**, not a
  velocity write. Same for `docs/fk22-dropphase-reachability.md`'s `[mv+0x1A0]=1.0f`.
  ★★★★★ **[M] THE FIXED-POINT GATE IS 2-D: `Velocity.Z` IS NOT ZEROED** — the store at `0x035ED9AC`
  is `movups`, **16 bytes over a 24-byte `FVector` of doubles**, so gravity-space Z at `[rbp+0x178]`
  survives and is rotated back verbatim. Four independent derivations. ★ And **[M] gravity is
  integrated BEFORE that clamp on every iteration** (the clamp write is dominated by the gravity
  write, not vice versa) ⇒ the clamp can never suppress a fall.
  ⇒ ★★★★★ **THE BOT IS NOW THE ONLY THING THAT DOES NOT MOVE, AND IT IS THE PAWN WITH INPUT.** Same
  world, same frame, same pass, both `MOVE_Falling`, both `GravityScale 1.0`, both `GravityDirection
  (0,0,-1)` (**read live — this KILLS the zero-gravity hypothesis**), both ARM-G treated, both
  identity controls passing:

      BOT    |Accel| = 50000 (AI wander) · written (0,0,-600) · read (0,0,0) at +250 ms and EVERY
             sample to +10 s · moved **0.000 uu** five times
      PLAYER Accel = (0,0,0)             · written (0,600,0)  · fell to Z = -9935 · moved 23,189 uu

  **[M] the bot's zero is NOT self-inflicted:** `KBSPSARMS=0x1BA0` has ARM H2 (the re-write burst,
  bit 10) **OFF**, the only two `Velocity` writes are marker lines 218/219 (before the armed dump),
  and the restore is line 344 — **after** all five samples.
  ★★ **THE LEADING CANDIDATE, `[I, strong]` and UNVERIFIED:** engine `CalcVelocity`'s clamp
  `0x035D6511-0x035D652F` writes **ZeroVector to ALL THREE components**, guarded by
  `0x035D64F2 comisd xmm8, [.rdata 0x076B49E8 = (double)(float)1e-4]` / `0x035D650F jae`, on the
  **ACCELERATE** branch (downstream of `Velocity += Acceleration*dt` at `0x035D64C6..0x035D64EA`).
  `preds` are UNIQUE at both stores (independently confirmed). `xmm8` is selected by
  `IsExceedingMaxSpeed` (`[CMCvt+0x4D0] = 0x0363BA00`, byte-matched to stock, same on both CMC
  vtables) between `|Velocity|` and `xmm11 = max(MaxSpeed × [rbx+0x3D0], GetMinAnalogSpeed())`.
  **That is why the pawn WITH input reaches it and the pawn WITHOUT input does not.**
  ⚠⚠ **BUT IT DOES NOT YET EXPLAIN S140 T2 FLIGHT 3**, where the SAME bot with the SAME treatment
  and the SAME acceleration SUSTAINED 500 uu/s and walked 13,187 uu. **Find that discriminator or
  drop the candidate.** ⇒ **S142's first move is ONE READ: `AnalogInputModifier` / `[CMC+0x3D0]` /
  `GetMaxSpeed()` on both pawns.** ⚠ S141 added `GravityScale`/`GravityDirection`/`MovementMode`/
  `+0x1001`/`+0x1678` to the arm's free reads **and missed the one field the hypothesis turns on**
  (defect S141-d).
  ★★★★★ **T3-B ANSWERED — THE GAME'S OWN KICK IS `PendingLaunchVelocity` @ `CMC+0x5C8`.** Write 24
  bytes; `ULokiCMC::HandlePendingLaunch` (vtable disp `0x750`, Loki `0x55AEB60`; setter `Launch`
  disp `0x748` = `0x35E7340`) then sets `Velocity`, forces `MOVE_Falling`, sets
  `bForceNextFloorCheck` and **zeroes the field behind itself** — nothing to restore, no `.text`
  write, no PI hook, **no authority check on the path**. Its call site `0x035EA160` in engine
  `PerformMovement` **DOMINATES** the `StartNewPhysics` call `0x035EB13A` (1461 → 181 reachable with
  it removed). ⚠ ONE derivation, UNVERIFIED; settle doubles-vs-floats at `+0x5C8` and `[this+0xB2]&8`
  in `Launch()` first. ⚠ And on the BOT it changes the kick's SOURCE, not its SURVIVAL.
  ⚠⚠ **T3-C IS HALF-ANSWERED AND THE OTHER HALF WAS MIS-DESIGNED.** ARM K1 landed (`PLAYER storages
  written 3/3`), but the player's `Acceleration` read `(0,0,0)` at every sample — **it has no input
  driver at all** — so its 600 → 0 decay is correct physics and cannot discriminate "the clamp still
  fires" from "nothing sustains it". **NOT ESTABLISHED, by my design error, not by a null.**
  ⚠⚠ **SCOPE CORRECTION TO S140 T2 THAT MATTERS ON ITS OWN: "StartNewPhysics runs" ≠ "the physics
  step runs".** The payload write at `0x055C244F` is in the **Loki wrapper's prologue**, upstream of
  `jmp 0x3600990` at `0x055C2470`; engine `StartNewPhysics` has **four** further early-outs before
  its jump table. **The 23,189 uu fall is what establishes the chain runs** — not the payload.
  ⚠ **[M] `ULokiCMC::PerformMovement 0x055B8370` contains ZERO writes to `+0xE8/+0xF0/+0xF8`**, and
  the `0x055B8838/3E/4A` block writes `[rsi+0x12F0]`/`[+0x1300]`, not `Velocity`.
  ⚠ **`+0x12B0 TimeSinceFallingStart` can NEVER be a `PhysFalling` receipt** — [M] neither
  `PhysFalling` ever calls `StartNewPhysics` (disp `0x720` absent from both call sets), so its
  substep writer is unreachable and a 1.0× advance is expected either way. (My own [I, strong]
  inference from it, refuted by my own follow-up before publication — defect S141-c.)
  ★ **New offsets [M]:** `+0x1A0 GravityScale` · `+0x1D8/+0x1E8 GravityDirection` (offsets and
  arithmetic [M]; the NAME is [I, strong]) · `+0x1F0..0x208` / `+0x210..0x228` the two gravity quats
  (helpers `0x35F4620` grav→world, `0x35F4770` world→grav, both `mov rax,rdx` ⇒ return the out
  buffer) · `+0x5C8 PendingLaunchVelocity` · `+0x1678` `ULokiCMC::PhysFalling`'s lateral fall-speed
  limiter (`-1.0f` = DISABLED; ⚠ **SEVEN writers in the Loki CMC band ⇒ NOT a clean receipt**).
  ⚠⚠ **ALL S141 ADVERSARIAL VERIFICATION WAS LOST TO API `529 Overloaded`** — 7 of 12 agents (every
  verifier + the adjudicator) and then 4 of 4 in two focused retries. The five lane analyses are
  **un-refuted except where they converge**, which they do 4-ways on T3-A and the gate constant.
  ★ Partial recovery: the dead L1 verifier's own scripts (`scratchpad/s141/verify/V1/`) were re-run
  and confirmed §1/§3/§4.1's attribution from independently written code. **Anything marked "pending
  verification" in `docs/s141-tier3-settled.md` has ONE derivation — treat it as [I].**
  ⚠ **Instrument defects S141-a..f** are in `docs/s141-tier3-settled.md` §9. Two generalise:
  **a displacement scanner must be controlled on sites you already know, IN THE SAME RUN** (S141's
  first one had two off-by-ones and reported a clean-looking wrong answer, caught only because a
  known site came back MISSED); and **a marker line can name a value it does not write** (`[SNP] BOT
  sentinel Velocity = (2^-10,0,0)` was hardcoded while the arm wrote `(0,0,-600)` — fixed).
  ⚠ Health: staged on attempt 1; FK-32 at **~300 s on the 4th manual-map**, 0 crashpad / 0 `Fatal` /
  no artifact. The `0xDEAD` series is now **7/6/4/4/4/4/4** — no dose-response, 4 is the mode.
  ★ Nothing was lost; ⚠ **except the `dumpimage`, attempted after the samples when the client had
  already gone. TAKE THE DUMP EARLY.**
  ⚠⚠ **`sentinel-big 52fceb9be6de532f` and every `sentinel-*` / `gasattr-sentinel` digest HAS MOVED**
  — S141's new free reads live inside `#if (KBSPSARMS & 0x200)`. **Re-digest before reusing any of
  them as a gate or a control.** Gates `botai 5e47c13cf7f0a158` / `gasattr 2fcc2536e21f18e3` /
  `gasattr-ctrl 4465ebc4d7168c03` all reproduce EXACTLY.

# S137 session prompt

Copy everything below the line into a fresh Claude session.

---

Continue the SUPERVIVE revival project. Read `docs/next-session-prompt-s137.md` first — it is the
flight procedure — then `docs/s136-ai-controller-settled.md` for the evidence. ⚠ That file opens with
a **CORRECTIONS block that GOVERNS the rest of it**; read that block before anything below it.

**Goal this session: give the AI controller a PlayerState. Build and fly the `bWantsPlayerState` CDO
poke, then read TWO numbers — `controller+0x3C0` and `pawn+0x3D8`, both measured NULL in S136, both
expected non-null and equal after.**

**State.** An AI-controlled hero pawn now exists and is possessed — `SpawnAIFromClass` →
`APawn::SpawnDefaultController` (slot 280, `0x3BBF3C0`) → `AController::Possess` (`0x36E2B60`), with a
bidirectional handshake, reproduced twice in one client. ⚠⚠ **It is NOT a Loki bot**:
`AIControllerClass` reads the engine default on the spawned pawns *and on the player hero*, and
`obj_by_chain BotController` = **0 LIVE**. Do not write "the bot spawner works".

**Why the PlayerState is NULL is settled, offline, end to end — and it is not a stripped stub.**
`AController::InitPlayerState = 0x36DEE20` (AController vtable slot 273) is **REAL, 778 B, 14/14
callees REAL, zero folds** — it names itself in its own UE_LOG at `.rdata 0x8018A50`. It never runs
because `AAIController::PostInitializeComponents` gates on `bWantsPlayerState`:

    0x45D6D1E  f6 83 88 04 00 00 20   test byte [rbx+0x488], 0x20
    0x45D6D25  74 25                  je  0x45D6D4C            <== THE BLOCKER
    0x45D6D46  call qword [rax+0x888]                          <-- InitPlayerState (slot 273)

The bit is `0x20` at `+0x488`, from its own UHT `SetBitFunc` (`0x45CFA10 = 83 89 88 04 00 00 20 c3`),
and **stock UE clears it** in `AAIController`'s and `ALokiBotController`'s constructors. So the arm is
**one aligned CDO write** — `CDO(<pawn's AIControllerClass>) + 0x488 |= 0x20` before spawning — the
same risk class as S130's `bCanEverReplicate`. Details, byte-for-byte, in §1.2 of the handoff.

⚠⚠ **FIRST ACTION, and do not skip it: read `pawn CDO + 0x3D0` (`AIControllerClass`) LIVE** to learn
*which* controller CDO to poke. `APawn::APawn` re-reads that field from the `APawn` CDO chain, not
from a hard-coded `AAIController::StaticClass()`, and resolving it offline was attempted and failed.

⚠ **Do not promise a Loki bot from this.** A second wall sits past the gate: everything it protects
calls two stripped folds ([I, strong] `ServerSetHeroClass` / `SetPlayerTeam`). A PlayerState buys
*reachability* of that branch, not hero-class or team assignment. Both walls are real and sequential
(§1.3). ⛔ And there is **no "third gate"** — that was refuted in review; do not pre-register one and
do not zero `[PS+0x8C8]` (§1.4).

**Procedure is §2 of the handoff.** Set `AGS_ARM_QUEUE=arm` in the *same* PowerShell call as
`launch-redirect.ps1 -NoHook` (it restarts `ags`, inheriting your env); Steam must be running;
`forceTutorialMatch` stays **false** — the queue-armed MatchID satisfies the stager; `-AllowStale` is
required. ★ **Re-inject into the SAME client rather than relaunching** — S136 did three probe
injections into one process with 0 `Fatal` and 0 crashpad, and the world stays staged
(`tools\inject\inject.exe mmap <pid> <dll>`).

⚠⚠ **WAIT FOR `[BS] done`, AND THEN READ `called=`.** S136's first flight showed a clean `0/0/0`
census under a confident VERDICT line and was a **no-op** — the arm had been dead-code-eliminated.
`called=` is the only field that exposed it. A census delta with `called=0` is UNINTERPRETABLE, not a
null. The other traps that cost real time are in §3; the two most transferable: **a confident failure
string is an instrument** (the old verdict asserted a knob that was set correctly), and **an edit that
does not move `.text` is ambiguous** — insert a marker string to separate a cached build from a
semantic no-op. Also: `strings` is not installed here, so use python byte scans **with a positive
control**, and both `CLAUDE.md` and `tutorial_launch.cpp` are CRLF.

If the poke lands, the next question is behaviour, not spawning: pass a real `BehaviorTree` and see
whether the pawn moves (`PathFollowingComponent` is already live). A controller that exists but does
nothing is a behaviour result, not a spawn failure — do not let it re-open the settled part.

There is also a free offline queue in §5b if no client is available: which netmode is it (`!= NM_Client`
is measured, Standalone-vs-ListenServer is not — and if Standalone, engine `HasAuthority()` plausibly
passes, which would enlarge the reachable "server-only" surface), and can a `LokiBotController` be
instantiated at all (CDO exists, 0 live, one probe answers it).

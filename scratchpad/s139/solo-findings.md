# S139 solo findings (before the workflow returned)

## F1 [M] ControlInputVector IS consumed every frame -- the handoff's standing hypothesis is REFUTED
Computed over all 194 raw samples in `docs/s138-f8-motion.txt`:
    |CIV| min 0.0000  max 1.0001   (190 non-zero)
    |CIV| > 1.05      : 0 samples
    CIV == RandomMoveDirection exactly : 193/194
    RMD changes (runs): 44
`ControlInputVector += direction` (S137 transcription, stock UE `APawn::Internal_AddMovementInput`).
An UNCONSUMED `+=` predicts:
  per-frame @60fps -> |CIV| ~ 5820
  per-2s cadence   -> |CIV| ~ sqrt(44) = 6.6 (random walk), and NOT equal to the latest direction
MEASURED max = 1.0001.
=> something zeroes CIV between every write. => the pawn-side consume runs every frame.
=> REFUTES `docs/s138-flight9b-flymode-refuted.md` Sec2 "the controller ticks; the CMC does not"
   and `docs/s138-flight9-movement-not-simulating.md` Sec3 "ControlInputVector is never zeroed".
Caveat to close: WHO consumes it (must be `UPawnMovementComponent::ConsumeInputVector` ->
`APawn::Internal_ConsumeMovementInputVector`), and whether the consume sits BEFORE the
HasValidData()/ShouldSkipUpdate() early-outs (stock UE 5.4: it does). If it does, consumption
does NOT imply simulation -- which reconciles every observation.

## F2 [M, source] `play` moves the player WITHOUT enabling any tick
`tutorial_launch.cpp:1240` calls `DoWakeMove()` only under `kRunMode==RM_WAKEMOVE`.
`:1275` RM_PLAY calls `DoPlay()`. DoPlay's one-shot init (`:12328`+) is exactly:
  teleport (unless KNOTELE) / GravityScale=1.0 / ResetIgnoreMoveInput(PC) /
  SetMovementMode(KFLYMODE=5) / SetActorHiddenInGame(hero,false) / body build
It does NOT call SetActive, SetComponentTickEnabled or SetActorTickEnabled.
(DoWakeMove `:2983` DOES call all three -- that is a DIFFERENT run mode and was never in play.)
Per-tick, DoPuppet + the auto-walk block write `CMC+0xE8` (Velocity) and `CMC+0x328` (Acceleration).

## F3 [I, strong] therefore the PLAYER's PerformMovement runs
Velocity becomes displacement only inside PerformMovement/SafeMoveUpdatedComponent. `play` moves the
hero +2945.7 uu "WITH collision" (shim source `:365`, CLAUDE.md) having enabled no tick.
=> the player's CMC ticks AND reaches PerformMovement.

## F4 [M] the BOT's PerformMovement does NOT run -- and flight 9's own table is the discriminator
`docs/s138-flight9-movement-not-simulating.md` Sec0:
    BOT    GravityScale 1.000  MOVE_Falling  Velocity (0,0,0)  frozen 97 s
    PLAYER GravityScale 0.000  MOVE_Falling  Velocity (0,0,0)  frozen
The PLAYER's freeze is FULLY CONSISTENT with a running PerformMovement (gravity 0 -> nothing to
integrate, no input). The BOT's is NOT: gravity 1.0 in MOVE_Falling puts a large negative number in
Velocity.Z within one frame.
=> the asymmetry is REAL, and it is NOT MovementMode (both 3), NOT UpdatedComponent (both non-null),
   NOT bIsActive (both True), NOT tick enablement (play enables none).
=> the failure sits BETWEEN ConsumeInputVector and PerformMovement, in the early-out ladder.

## Consequence for the S139 handoff's plan
Sec1 said: "run `play` to get a MOVING control and diff the CMCs". Still the right experiment, but
NOT for the stated reason -- `play` does not fix an input path (S75 measured forced
AddMovementInput -> zero accel/velocity on the PLAYER too). It bypasses the input path entirely by
writing Velocity. The diff target is the EARLY-OUT LADDER, not the input path.
Sec1.2's `UpdatedComponent`-null candidate is ALREADY DEAD (flight 9 measured non-null on both).

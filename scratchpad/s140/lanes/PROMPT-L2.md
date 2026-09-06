# LANE L2 — TASK A1b: WHAT DOES EACH EXIT ACTUALLY TEST?

For each of the six candidate exits of engine `PerformMovement 0x035E9EC0` that skip the
`StartNewPhysics` call at `0x035EB13A`:

    0x035E9F1F  je  0x035EB1A7
    0x035E9F28  je  0x035EB1A7
    0x035E9F97  je  0x035EB7CF
    0x035E9FA4  jne 0x035EB7CF
    0x035E9FBD  jne 0x035EB7CF
    0x035EA25D  je  0x035EB150

determine, **from the bytes**:

1. **The exact predicate** — trace the flag-setting instruction and everything that feeds it,
   backwards through register definitions, as far as needed to name the SOURCE.

2. **The FIELD it reads**: offset, width, and **WHICH OBJECT** (the CMC itself? `UpdatedComponent`?
   `CharacterOwner`? a local? a return value from a virtual call?). Name the owning class and say how
   you know. **This is the single most important column** — S139's six were declared "measured
   passing" and one of them may be measuring a different object than we read.

3. If it is a **virtual call**, resolve the displacement and say which class's slot it lands in for
   `ULokiCharacterMovementComponent` specifically (vtable `.rdata 0x088F8570`). Grade the impl
   FOLD/REAL/DARK. Remember `.rdata` in a dumped image holds ABSOLUTE VAs — subtract ImageBase
   `0x7FF608F40000`.

4. Whether that field has **ALREADY been measured live** (the brief's table) — and if so, whether the
   measured object is **provably THE SAME OBJECT** the branch dereferences. Flag any where it is not.

## Orientation hypothesis (NOT an answer)

Stock UE's `UCharacterMovementComponent::PerformMovement` begins roughly:

    if (!HasValidData()) return;
    ... GetWorld() ...
    if (UpdatedComponent->IsSimulatingPhysics()) { ...; return; }
    if (CharacterOwner->GetLocalRole() > ROLE_SimulatedProxy) ...
    ... bDeferUpdateMoveComponent ... MovementMode ...

Use that to orient, **never as an answer** — this build is modified (`EMovementMode` has
`MOVE_Dashing` inserted at index 6, so `MOVE_Custom == 7`, `MOVE_MAX == 8`).

## The high-value extra: log literals on bail paths

Cross-check against `.rdata`: are there any log/assert literals reachable ONLY from a bail block
(`0x035EB1A7` / `0x035EB7CF` / `0x035EB150`)? **A shipped log string on a bail path is a FREE live
receipt** and would be the highest-value thing you can find. Search for string references from those
blocks and report the `.rdata` address, the literal text, and the log category + verbosity threshold
if determinable. Note `CharacterMovementComponent.cpp` literals live around `.rdata 0x07FC0670`.

## Output

For each exit produce a row: address | condition | field+offset | owning class | measured? | same
object? | what it would take to settle it.

# LANE L1 — TASK A1a: SOUND EXIT ENUMERATION over engine PerformMovement `0x035E9EC0`

**The claim under test:** "exactly six branches skip the single call to `StartNewPhysics` at
`0x035EB13A`, and all six have their inputs measured passing."

The prior enumeration used the predicate "branch target > `0x035EB13A`", which is **structurally
blind to a backward bail** (a jump to a LOWER address into a block that then exits). Your job is to
redo it soundly.

**WRITE YOUR OWN CFG BUILDER FROM SCRATCH.** Do NOT import `scratchpad/s140/tools/cfg.py` — the whole
value of this lane is being an independent second instrument. You may read it afterwards to compare.
Say explicitly that you wrote your own.

## Method

1. Recursive descent from `0x035E9EC0`. Report your instruction count. (The session lead's
   independent tool got **1461**; S139 also got 1461; a linear sweep gets 1074 and is unsound. If you
   get something else, that is a finding — investigate rather than adjusting.)
2. Compute `R` = set of instructions that CAN REACH `0x035EB13A` (backward reachability over the
   *instruction* graph, so the answer does not depend on basic-block construction).
3. Every edge from a node in `R` to a node NOT in `R` is a bail. That is the true exit set. Report
   each with address, mnemonic, and whether its target is FORWARD or BACKWARD of the call.
4. Diff against the prior six: `0x035E9F1F`, `0x035E9F28`, `0x035E9F97`, `0x035E9FA4`, `0x035E9FBD`,
   `0x035EA25D`. Report anything missed and anything of theirs that is NOT a real exit.

## You MUST explicitly handle and REPORT ON each of

(a) **indirect jumps / jump tables** inside the function — do not assume there are none, verify;

(b) **calls that may not return** (a noreturn callee is an exit your walk would treat as
fallthrough) — enumerate every call target in the function, grade each FOLD/REAL/DARK, and flag any
that could be noreturn (e.g. `__report_gsfailure`, throw helpers, `DebugBreak`). Say how you tested;

(c) the `ret` at `0x035EB1CA` and every path reaching it;

(d) **DOMINANCE** — is any of the six dominated by another (i.e. unreachable given the others)?
Compute dominators over the CFG. This changes which live measurements actually matter;

(e) whether `0x035EB13A` really is the ONLY call to vtable displacement `0x720` in this function —
scan every call/jmp operand for displacement `0x720` and for any other route to `StartNewPhysics`.

## Also report

Is the call at `0x035EB13A` inside a **loop**? If `PerformMovement` can call `StartNewPhysics` more
than once per invocation that matters for interpreting the latch.

**STATE PLAINLY whether "the six" survives.**

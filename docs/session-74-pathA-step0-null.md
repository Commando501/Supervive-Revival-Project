# S74 Path A / Step 0 — identify the deploy null (DONE, instruction-level)

Goal: at the SpawnSelect deploy crash, find the exact object→member that is null, to decide if Path A
(fill the null so the client's own deploy runs) is a shallow fix or a deep reconstruction.

## Method
The process-wide VEH does NOT fire for this crash (packer interferes with VEH ordering — same as S64).
Fix: wrap the `CallNative(GoToPhase)` in a direct **SEH `__try/__except`** (CallNativeGuarded in
tutorial_launch.cpp) that catches the AV at the call site and dumps: RIP+rva, accessed address, all GP
registers, the **class name of each pointer-register**, and the instruction bytes at RIP / RIP-24.
`EXCEPTION_EXECUTE_HANDLER` also let the game SURVIVE (thread corrupt but alive) → live disasm of the
committed crash code via usmapdump. Reusable: DumpCrashCtx + CrashVEH + SehDump + CallNativeGuarded.

## The capture (GoToPhase(4) = SpawnSelect)
```
[NULL] fatal 0xC0000005 RIP=0x7FF6BAAFF8AE rva=0x560F8AE access=READ addr=0x0
RAX=0 RBX=1 RCX=<PS+0x470> RSI=<gamemode> RDI=<GE_RoundReset_C class> R14=<GameState> R15=<PlayerState>
cls RSI=BP_LokiGameMode_Tutorial_C RDI=BlueprintGeneratedClass(GE_RoundReset_C) R14=BP_LokiGameState_Tutorial_C R15=BP_LokiPlayerState_C
```
Faulting instr: `mov rcx,[rax]` with RAX=0. Reconstructed source (live disasm):
```
lea  rcx,[r15+0x470]     ; r15 = local BP_LokiPlayerState_C ; rcx = an EMBEDDED sub-object at PS+0x470
mov  rdx,[rcx]           ; rdx = sub-object vtable (0x7FF6BDF1E020, in-exe = multiple-inheritance C++ obj, 4 vtables)
...
call [rdx+0x10]          ; virtual call vtable[2] on the sub-object -> the getter @rva 0x56BA9E0, returns NULL
lea  rdx,[rsp+0x70]
mov  rcx,[rax]           ; rax = getter result = NULL  -> CRASH
mov  r8,[rcx+0x6C8]; call r8   ; (the caller was about to virtual-call the returned object)
```
The getter @0x56BA9E0:
```
mov  rax,[rcx+0x88]     ; rcx = sub-object (PS+0x470) ; rax = *(PS+0x470+0x88) = *(PS+0x4F8)
test rax,rax
jz   ret_null          ; ← TAKEN: PS+0x4F8 is NULL -> return NULL
mov  rax,[rax+0x3E8]   ; else return (*(PS+0x4F8))->[0x3E8]
ret
```

## ★ THE NULL: `PlayerState + 0x4F8` (a deploy-state/link pointer inside a PlayerState sub-object) is NULL.
The SpawnSelect transition iterates players (applying GE_RoundReset) and, per PlayerState, calls a getter
on an embedded component (PS+0x470) that returns `*(PS+0x4F8)->[0x3E8]`. Because `PS+0x4F8` is null on the
local player, the getter returns null and the caller crashes dereferencing it.

## What this means for Path A (honest)
- It is NOT a single top-level singleton (my `ULokiServerPlatformInstance` hypothesis was WRONG for this
  crash). It is a **per-player PlayerState deploy-state pointer**, null because the local player's
  server-authoritative deploy/match-init state was never built.
- **No healthy reference exists to copy from:** the only `BP_LokiPlayerState_C` instance is the local
  player (17 "PlayerState" objects found are its COMPONENTS: Bark/ObjectiveTracking/HeroUIState/ArmoryReward/
  RoguelikeChoice/DeadHunterEmote/...). The AI bots that "spawned" do not have full player PlayerStates to
  mirror. So we can't just read what `PS+0x4F8` should be from a working player.
- The getter shape `X ? X->[0x3E8] : null` + the deploy context strongly implies `PS+0x4F8` is the player's
  **assigned hero/pawn (or deploy-record) link** — null because the player has no hero yet. That's the
  chicken-and-egg the real server breaks: deploy needs the hero, hero-spawn (SpawnPlayer, exp3) ALSO
  null-derefs. Both directions are gated on the server-authoritative match/deploy init.
- => Path A is a **deep, interdependent deploy-state reconstruction**, not a shallow "fill one pointer" fix.
  Filling PS+0x4F8 requires knowing what object it should be + constructing it + then the next null (onion).

## Verdict + next
Step 0 is DONE: the null is precisely `PlayerState+0x4F8`, a per-player deploy-state link. This confirms the
crash is the server-authoritative player-deploy init, seen at instruction level — a deep onion, not a
singleton. This is exactly what **Route B (decompile the Angelscript deploy/round logic)** should clarify:
what the SpawnSelect→deploy sequence populates on each PlayerState (what PS+0x4F8 is, what sets it), which
tells us whether reconstruction (Route D) is bounded. Proceed A→B as planned.
Reusable: the SEH crash-dump instrumentation (CallNativeGuarded/DumpCrashCtx) + usmapdump live disasm recipe.

# S150→S151 — three unflown arms ready, versus AI continuation

**Paste this whole file as the opening prompt of a fresh session.**

You are continuing the SUPERVIVE revival project at
`G:\git\Supervive Revival Project` on branch `dedicated-server-stub` (synced
with `origin/dedicated-server-stub` at `0fe28f0` as of this writing). Read
`CLAUDE.md` (auto-loaded); its "Current-frontier override" at the top is
partly stale — a prior session lifted it for versus AI work, and this doc
records where that lands.

---

## 0. What happened last session (this branch, one continuous session)

Four commits shipped on `dedicated-server-stub`:

| commit | subject |
|---|---|
| `048ac99` | policy: gitignore + pre-commit size gate to prevent >100 MB blobs |
| `e8e757f` | S149-fix: capture-generation gate closes the stale-reopen refusal |
| `852fbfd` | S147-move3: KBFBINDCENSUS arm built + AB_OFF pinned, unflown |
| `0fe28f0` | S148-move4: chain S149 bind-only + frozen S148 into one sitting, unflown |

Plus the DLP orchestrator commit `d2ebf30` from the prior session that
rebased onto this branch after the filter-repo history rewrite (see §7).

None of the three flight arms have been flown. All three preregistrations
exist. The scaffolding — capture-gen gate, bindcensus helpers, Move-4
verifier + flight helper — is committed and pushed.

Two things worth reading before touching anything:
- `docs/coop-vs-ai-roadmap-s142.md` — the versus AI roadmap; WALL P / WALL E
  status blocks are the ground truth.
- `CLAUDE.md`'s WALL P block (search "WALL P STEP 1 IS SOLVED") and the
  S147 block below it — records where activation state moves but the BP
  witness doesn't fire.

---

## 1. Three unflown arms, ranked by information yield

### Arm A — DLP (drop chain in one injection). `docs/dlp-flight1-PREREGISTERED.txt`

**Not versus AI directly** — this is the S150-drop chain. Composes
`dropplane_b1only → droppod-pe-cdopoke → dismount-landstart →
play-atlanding-walk` into ONE injection via `RM_DROPLANDPLAY` (enum 34).
Cuts flight-4b's 7 injections to 4 (gft + fo + sp + dlp).

- DLL: `tools/sigbypass-mod/build/tutorial_launch_droplandplay.dll`
- `.text` RAW `157795de805b8fbc`, file 398,848 bytes
- `verify_dll.py` PASS. All 9 recorded regression gates re-verified byte-
  identical after the edit.
- Diagnostic arm; NOT SHIPPING. Do not add to the default injection set.

### Arm B — Move 3 BINDCENSUS. `docs/s147-move3-flight1-PREREGISTERED.txt`

**WALL P discriminator.** S147 flight 5 saw a real activation receipt on
natural LeftShift (`ActiveCount 0→1`, Mana `10→0`) but the Ability3 BP
K2Node witness stayed 0. Two live hypotheses that offline analysis could
not falsify:
- **H1** — the valid-handle downstream body under `InternalTryActivateAbility`
  triggers the protector kill (0xDEAD ~51 s after activation); two DARK
  pages `0x446bc60` and `0x4480b30` on the valid arm.
- **H2** — input never reaches the BP K2Node; either (H2a) BP bind never
  installed, or (H2b) ASC delegate consumed the action before BP.

This arm reads BOTH the PlayerController's AND the possessed pawn's
`InputComponent → ActionBindings` TArray, plus a heartbeat emitted from
inside `FsDisarm` at phase transitions (`enter → done` or `enter → faulted`).
`KBFBINDCENSUS_AB_OFF = 0xd0` is pinned [M] (offline disassembly of
`UInputComponent::InternalConstructor` at RVA `0x3616740`). Per-entry
STRIDE + NAMEOFF are UNPINNED — the TArray metadata (num/max) alone is
enough for the H2a case ("PAWN Num >= 1 AND PC Num == 0 ⇒ BP never wired").

- DLL: `tools/sigbypass-mod/build/tutorial_launch_botfight_castalive_dash_mana10_cdocharge1_naturalinput_bindcensus.dll`
- `.text` RAW `f07e45f3c81cf948`, file 264,192 bytes
- `verify_dll.py` PASS. Single-variable A/B over the S147 flight-5 arm
  (RAW `366e8ef09afa8cb9`).
- Follow-up if flight 1 lands BOTH-WIRED (both PC and PAWN have Ability3):
  ONE live-process RPM pass to derive STRIDE (walk PAWN's ActionBindings
  data with candidate strides `{0x50, 0x58, 0x60, 0x68, 0x70}`; the stride
  that produces Num valid FName ComparisonIndex values is correct); then
  rebuild with `-DKBFBINDCENSUS_STRIDE=0x?? -DKBFBINDCENSUS_NAMEOFF=0x??`
  for a follow-up flight that disambiguates H2b from H1.

### Arm C — Move 4 self-damage (WALL E Phase 1a). `docs/s148-move4-flight1-PREREGISTERED.txt`

**First live AdjustHealth attempt on the force-open route.** S148 flight 4
refused (issues=0x3EC13F) because the fresh ASC read `AvatarActor@0x410 = 0x0`
— no bind step ran in front of it. Move 4 stages the S149-bind-only DLL
FIRST to force the AvatarActor bind (S143-proven path), runs a read-only
verifier to confirm the bind is live AND SpawnedAttributes is populated,
and only then injects the frozen S148 self-damage DLL.

- Bind-only DLL: `s149-bind-flight1-b2` in the codex worktree
  (`C:\Users\eastr\.codex\worktrees\78d0\...\build\s149-bind-flight1-b2\
  tutorial_launch_botfight_bind_only.dll`), sha256 `5B743B30...`.
- Frozen S148 DLL: `s148-flight4-a` in the codex worktree
  (`C:\Users\eastr\.codex\worktrees\78d0\...\build\s148-flight4-a\
  tutorial_launch_botfight_damage_self_cal.dll`), sha256 `C7204964...`.
- Both `verify_dll.py` PASS. Neither is rebuildable from
  `dedicated-server-stub` HEAD — their compile-time deps
  (`S148ClassChainRenderEnabled` + `S148ClassChainRenderCapacityRefuses`)
  live only in the codex worktree source.
- Flight helper: `configs/s148-move4.ps1` (SHA256-pins both DLLs).
- Verifier: `tools/re/move4_bind_verify.py` (read-only RPM; exit codes
  0/3/4/5/6/9 discriminate PASS / bind lost / no attrset / no ASC /
  bad hero arg / instrument fault).
- **Load-bearing unknown**: whether S149-bind-only leaves `SpawnedAttributes`
  populated on the ASC. If empty, the verifier catches it and skips the
  5th injection (exit 4) — preserving the FK-32 draw and yielding an
  informative partial result (bind persistence + attribute-set absence
  measured together for the first time).

---

## 2. Recommended ordering

**FLY C (Move 4) FIRST.** It has the highest information yield for versus AI
end-to-end (proves or refutes damage pipeline, then either advances WALL E
directly or names the exact missing step). It's also self-contained — one
sitting, four terminal exit codes, all pre-registered outcomes are
informative. Both DLLs are pre-built and pinned by sha256; the flight
helper does the coordination end-to-end.

**Then FLY B (Move 3 BINDCENSUS).** Its purpose is to fill the H1/H2
ambiguity that Move 4 doesn't touch. If Move 4 succeeds (Case H:
HEALTH_APPLIED), WALL E is proved; WALL P is still open and Move 3
answers what's left. If Move 4 lands in Case A (NO_ATTRSET), that names
the next WALL E arm; Move 3 continues WALL P work in parallel.

**A (DLP) is orthogonal** — it's the drop chain, not versus AI mechanics.
Fly it separately whenever you have interest.

---

## 3. Live-flight preconditions (all three arms)

- **ELEVATED PowerShell** (inject.exe manual-map + hosts file).
- **Steam running BEFORE launch** (else Auth Failure 14005).
- `server/internal/interactive/interactive.go` `forceTutorialMatch = true`
  (already set in prior sessions; verify with grep before launch).
- **Fresh docs\capture.log** — always launch with `-ResetCapture`:
  ```powershell
  .\configs\launch-redirect.ps1 -NoHook -ResetCapture
  ```
  This applies the S149-fix capture-gen gate (archives stale
  `docs\capture.log`, `CreateNew`s a fresh one, forces `CreationTimeUtc =
  UtcNow`, refuses if age > 5 s). Off by default (byte-identical to
  primary launch when `-ResetCapture` unset).

## 4. Environment / tooling context

- **Primary tree at `0fe28f0`**, synced with `origin/dedicated-server-stub`.
  Pre-existing dirty state (documented in prior session's status output —
  docs/*.md edits from before this session) is intact and untouched.
- **Codex worktree at `C:\Users\eastr\.codex\worktrees\78d0\Supervive Revival Project`**
  holds the S148/S149 pre-built DLLs Move 4 depends on. Its HEAD is
  `94e3b43` (S150 successor-neutral v2). Do NOT try to rebuild those DLLs
  from `dedicated-server-stub` — the source dependencies are absent.
- **git filter-repo was run this session.** It removed two >100 MB blob
  files (`scratchpad/s133/evidence/capture-emote-attempt1.log` 111 MB and
  `scratchpad/s134/laneb/mapdumps/LVL_Skylands_WP.json` 188 MB) from all
  history. Every commit hash from `38d96d9` forward got a new hash. If
  you're reading a doc that cites a specific commit hash and can't find
  it, that's why. The two blob files are still on disk (untracked; now
  covered by `.gitignore`) and backed up at
  `G:/git/SRP-largefile-backup-1788310593/`.
- **Pre-commit hook** (added this session) rejects any staged blob >= 90 MB
  and warns at 50 MB. Not installed automatically; install with:
  ```
  git config core.hooksPath configs/git-hooks
  ```
  Recommended one-time setup for a fresh clone.
- **Isolated clone at `G:/git/SRP-filter-repo/`** left over from the
  rewrite (~100 MB). Can be `rm -rf`'d anytime.

## 5. The current-frontier override situation

`CLAUDE.md`'s top says "Current-frontier override" and restricts live work
to the S150 successor-neutral offline plan in the codex worktree. The user
lifted this override for versus AI work last session ("get back to versus
AI"). That lift stands for as long as the user's directive is in play; it
does NOT stand automatically session-to-session. If the fresh session
wants to fly one of the three arms, that's live work — confirm with the
user first if they haven't reiterated the versus-AI direction in their
opening message.

## 6. Load-bearing risks per arm (from the workflow syntheses)

**DLP**: DLL size 398,848 bytes = 1.41x the largest historical FLOWN
manual-map (droppod-pe-cdopoke 283,648 B). Under the 2x heuristic
threshold — proceed, but note it's the largest arm ever attempted.

**Move 3 BINDCENSUS**: only decisive for H2a via metadata alone. If flight
1 lands BOTH-WIRED (both PC and PAWN have Ability3), a second flight is
needed with STRIDE + NAMEOFF pinned. One live RPM pass suffices to derive
them.

**Move 4**: 5 injections. FK-32 mode is 4 (per S141 series). ZERO
precedent for a 5-injection sequence surviving to RESULT. The exit-4
short-circuit (skip S148 when SpawnedAttributes is empty) is the design's
one place where the draw is preserved.

## 7. Not-yet-done items (offline-derivable, no launches)

- **Move 3 STRIDE + NAMEOFF live derivation** — deferred, only needed if
  Move 3 flight 1 lands BOTH-WIRED. Design in the preregistration doc.
- **Move 4 CASE A follow-up** — if S149-bind-only leaves `SpawnedAttributes`
  empty, next arm needs an attribute-set-populating step (probably via
  `WireAbilitySystem`'s `TryUpdateAbilitySystem` path,
  `tutorial_launch.cpp:20053` in codex source). Design belongs to whichever
  session receives that CASE A outcome.
- **DLP §6.9 CallBPGuarded FFrame+0x80 primitive fix** — long-term win
  (unblocks every `FUNC_HasOutParms` UFunction project-wide); recorded in
  the DLP block of CLAUDE.md as a future direction.

## 8. What NOT to do

- Don't try to rebuild S148 / S149-bind-only DLLs from `dedicated-server-stub`
  HEAD — the `S148ClassChainRender*` helper definitions live only in the
  codex worktree. Use the pre-built DLLs from
  `C:\Users\eastr\.codex\worktrees\78d0\...` verbatim.
- Don't run `botfight-bind-only` from a fresh `build.ps1` invocation — it
  will hit the same compile error. That variant is deliberately preserved
  in build.ps1 so its knob semantics stay tracked, but current source
  can't produce it. Use the codex-worktree pre-built.
- Don't push the DLP DLL (or any arm) as a default injection — all three
  are DIAGNOSTIC arms. `launch-redirect.ps1`'s default set stays as-is.
- Don't touch the two backed-up large files at
  `G:/git/SRP-largefile-backup-1788310593/` unless cleaning up
  intentionally. They're the recovery source if the on-disk copies are
  ever needed and untracking them via .gitignore was the point of the
  filter-repo.

---

**Suggested opening move for the fresh session** (unless the user directs
otherwise): read this doc, read `docs/s148-move4-flight1-PREREGISTERED.txt`,
confirm with the user that Move 4 flight is authorized, then walk them
through the flight recipe. If the flight lands, interpret the outcome
against the pre-registered cases and update
`docs/coop-vs-ai-roadmap-s142.md`'s WALL E block.

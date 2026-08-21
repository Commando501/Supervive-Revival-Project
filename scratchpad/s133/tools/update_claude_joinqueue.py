#!/usr/bin/env python3
"""S133: record the joinQueue/FIND MATCH result in CLAUDE.md and update the canonical image."""
import io

# ---------------- CLAUDE.md ----------------
P = 'CLAUDE.md'
s = io.open(P, encoding='utf-8').read()


def rep(a, b):
    global s
    assert a in s, 'NOT FOUND: ' + a[:70]
    s = s.replace(a, b)


# canonical image ladder -> merged7
rep("""  ★★★★★ **THE CANONICAL COLD IMAGE IS `dumps/merged6.dump.exe` — `.text` **16,694 / 30,281**
  decrypted pages (**55.13 %**), measured 2026-08-20, and it is EXACTLY the union of all 26 state
  images on disk""",
"""  ★★★★★ **THE CANONICAL COLD IMAGE IS `dumps/merged7.dump.exe` — `.text` **16,707 / 30,281**
  decrypted pages (**55.17 %**), measured 2026-08-20, and it is EXACTLY the union of all 32 state
  images on disk""")
rep("""  16,683 → `merged5` 16,689 → **`merged6` 16,694**.""",
    """  16,683 → `merged5` 16,689 → `merged6` 16,694 → **`merged7` 16,707** (the S133 queue sweep).""")
rep("""  **`dumps/merged6.dump.exe` (16,694 decrypted pages, 55.13 % — the union of all 26 states)** or""",
    """  **`dumps/merged7.dump.exe` (16,707 decrypted pages, 55.17 % — the union of all 32 states)** or""")

# new digest block, before the coverage section
anchor = '### Before touching anything coverage- / dump- / "that page is undecrypted"-shaped\n'
block = """### Before touching anything queue- / FIND MATCH- / matchmaking-shaped
★★★★★ **FIND MATCH WORKS (S133, 2026-08-20) — read `docs/s133-joinqueue-find-match.md`.** The client
enters a real queued state with a running timer and a working cancel. Backend-only; no shim, no
injection, no `.text` write. `server/internal/interactive/joinqueue.go`, knob **`AGS_JOIN_QUEUE=0`**.
- **[M] TWO ENDPOINTS, BOTH PREVIOUSLY UNSERVED:** `POST /party/parties/{p}/joinQueue` (FIND MATCH)
  and `POST /party/parties/{p}/leaveQueue` (cancel — a correct speculative guess, confirmed on the
  wire). Both fell to the `/` catch-all, which is *why* FIND MATCH did nothing and why the client
  **re-POSTed every ~10–35 s**. ★ **The retry IS the rejection symptom** — once accepted, `joinQueue`
  fires exactly ONCE. Use that as a free receipt.
- ★★★★★ **THE RESPONSE MUST BE AN `FParty` UNDER AN ADVANCED `Version`.** Read from the function
  itself: `TryJoinQueue 0x5875E90` passes callback `0x5859E10`, whose third instruction is
  `call 0x587BE90` = **`UPartyModel::SetParty`** — the S85 monotonic-Version gate
  (`cmp [PartyModel+0x568]; jge bail`). So the handler echoes the party through `store.update()`
  exactly like `handleSetTargetQueues`.
- ★★ **THE FIELD IS `state`, NOT `inQueue`.** `EPartyState = { Default, `**`Matchmaking`**`,
  CustomGame, Unknown }` (usmap enum VALUE table — the trustworthy part, FK-14).
  ⚠⚠ **`inQueue: true` ALONE IS MEASURED INSUFFICIENT, and its null was only interpretable because
  the disjunction was pre-registered:** `SetParty` **ran** (party-slot widgets rebuilt —
  `LogBlueprintUserMessages: MENUSPAWNER … Entering SetHero` at the exact timestamp), `LogJson` at
  Verbose logged **ZERO** import failures, and the UI still did not move ⇒ **wrong FIELD, not a dead
  route.** Write that disjunction down BEFORE the flight or "nothing happened" means nothing.
- ★ **`QueueJoinTime` / `MillisInQueue` are NOT needed — the client times the queue LOCALLY.** They
  were deliberately withheld (unconfirmed UE types; a wrong-typed matched key sinks the whole document
  and would have made `state` untestable too). **The restraint cost nothing.**
- ⚠⚠ **THIS IS THE SECOND CORRECTION TO THE S122 UNSERVED-ROUTE SWEEP, SAME BLIND SPOT.**
  `setTargetQueues` was missed because nobody clicked a tile; `joinQueue` because nobody clicked FIND
  MATCH. ⇒ **A passive capture-diff enumerates what the client HAPPENED to exercise. Drive the
  interaction, THEN diff — do not just capture for longer.**
- ⚠ **Nothing matches the player**: the queue is answered by no matchmaker. And FK-15's S118 map
  measured **`matchmakingNotif` as UNBOUND**, so there is no push route — a match-found signal has to
  be HTTP.
- ⚠ **No CUSTOM GAME entry point exists on this client** (`customGameModes` is served and
  `CustomGameList` is `IsEnabledByDefault=true`, so it is NOT toggle-gated — the entry point is
  elsewhere and unidentified). `UPartyManager`'s 7 custom-game impls on `0x5873000`/`0x5874000` and
  the 6 ready/fill/emote impls on `0x5879000` remain **DARK and unreached**.

"""
assert anchor in s
s = s.replace(anchor, block + anchor)

# coverage section: record the measured yield
rep("""- ★★ **THE MEASURED EXCHANGE RATE: 216 pages (0.71 pp of `.text`) for EVERYTHING from S107 to S132**""",
"""- ★★★ **AND THE FIRST TARGETED SWEEP CONFIRMS THE REFRAMING (S133):** the party/queue action sweep
  decrypted **183 pages in-process** but only **13 NEW TO THE CORPUS** (`merged6` 16,694 → `merged7`
  **16,707**). **13 pages is nothing as a percentage — and one of them, `0x5875000`, unblocked a
  shipped feature.** ⇒ **Stop measuring this work in coverage %. Target the specific dark function
  that blocks a specific question, then read it.** ★ 90 % of the newly-decrypted pages (129/144)
  carried no reflected UFunction — an independent re-confirmation of the ~86 % callee figure.
- ★★ **THE MEASURED EXCHANGE RATE: 216 pages (0.71 pp of `.text`) for EVERYTHING from S107 to S132**""")

# FK-31: the UECC module-list correction
rep("""⚠ **S131's evidence file calls `scratchpad/s131/tools/{ripfamily,ripdelta,modscan}.py` "read-only, re-runnable";""",
"""★★ **AND THE "unevaluatable from a minidump" RULE IS FALSE FOR THE UECC CORPUS (S133).** A fresh
  T+9 s FK-31 death (menu route, during D3D12 RHI init) produced
  `UECC-Windows-D1834DBF…/UEMinidump.dmp` whose **ModuleList NAMES `runtime.dll` at
  `0x7FFB57400000`** while the fault is at `0x7FFB57400001` — **literally `base + 1`, directly
  evaluated.** The "no module entry (0 of 14)" measurement is true of the **SENTRY crashpad** corpus
  and does not generalise. Same scope error as the `.rdata` instrument mix-up.
⚠ **S131's evidence file calls `scratchpad/s131/tools/{ripfamily,ripdelta,modscan}.py` "read-only, re-runnable";""")

io.open(P, 'w', encoding='utf-8').write(s)
print('CLAUDE.md updated')

# NEXT SESSION (S134) — FIND MATCH works. Nothing answers the queue. And the protector has been sitting in our own manifests, discarded, 52 times.

**One line: S133 settled FK-20 by inverting it — the capture side is saturated, the defect is that
coverage is EARNED AND NEVER SPENT — then proved the point by driving the UI to decrypt
`TryJoinQueue`, reading the decrypted function, and shipping the endpoint it named. Read
`docs/fk20-coverage-settled.md` §0 and `docs/s133-joinqueue-find-match.md` first.**

Written 2026-08-20 at the end of S133. Reproducible from commit `39c1325` (three S133 commits:
`96354c9` → `eb948b0` → `39c1325`, all pushed to `origin/dedicated-server-stub`).

---

## 0. WHAT S133 DID

1. **FK-20 SETTLED, and REFRAMED.** Ten images sat unmerged; folding them in bought **+5 pages**.
   `merged6` = 16,694/30,281 (55.13 %) **== the exact union of all 26 images**. 12 of 26 carry the
   whole union; the other 14 are worth **zero**; `tutorial-hero` alone is 96.5 % of it.
2. **[M] 125 crash lifetimes + our 26 captures only ever reached 55.27 %** — from the crashpad
   `MemoryInfoList` page-protection map (only `NOACCESS` and `EXECUTE_READ` ever appear over `.text`;
   6,757,306 + 5,173,408 = 394 × 30,281 exactly). ⇒ **the dark 45 % is dark BECAUSE THE GAME NEVER RAN
   IT.** Validated against the byte-page method: 5 exact equalities, 2 at +2, never fewer.
3. **67.91 % of the dark set is unreachable by ANY state** — UE's own Chaos ISPC kernels, editor
   modules, third-party libs. Reachable ceiling ≈ 4,361 pages. **The exchange rate for EVERYTHING from
   S107 to S132 is 216 pages (0.71 pp).**
4. **THE REAL DEFECT: 31 coverage-blindness claims in the repo name an address that is readable
   today**, and **~29 were already stale against `merged2`**.
5. Then flew FK-20's own top lever: clicking **FIND MATCH** decrypted **`TryJoinQueue 0x5875E90`**
   (the most-cited dark address in the repo). Target page lit, **three spatial controls held DARK**,
   monotonicity control passed, and the **wire attributed it by name**.
6. That click exposed **`POST .../joinQueue` with NO HANDLER** — and the decrypted function then
   supplied its own contract. **Shipped:** `joinQueue` / `leaveQueue` / `setIsOpen` / `emote`, plus
   331 granted emotes. **FIND MATCH works end to end**; emotes are visible, equippable and playing.

---

## 1. ★★★★★ START HERE — TWO OFFLINE READS, BOTH CHEAP, ONE OF THEM COULD OBSOLETE THE WHOLE COVERAGE PROBLEM

### 1.1 The shadow-exe lottery ticket — ONE `VirtualQueryEx` + TWO 4 KB READS

**[M] In 394/394 crashpad minidumps there is exactly one `MEM_IMAGE` allocation of `0xA9E1000` — the
game's own `SizeOfImage` — `READONLY`, a SINGLE region with no per-section protections, at a heap
address, 124 distinct bases (one per crash). ZERO bytes of it were ever captured.**
Control: **the game's real module is `MEM_MAPPED`, not `MEM_IMAGE` (0/394)**, so this is a *second,
hidden view of the exe*.

- **[I, strong]** its shape (`SEC_IMAGE`, uniform READONLY) is a raw section view ⇒ probably the
  **encrypted on-disk bytes**, in which case it is worthless.
- **[S] it could instead be the PLAINTEXT MASTER the fault handler decrypts from — in which case one
  read-only RPM read yields 100 % of `.text` in one shot** and §0's whole 55 % ceiling evaporates.

**Cost to settle: one `VirtualQueryEx` to find the base, then 4 KB at `base+0` and 4 KB at
`base+0x751EFD0` (the OEP), compared against the on-disk exe and `dumps/merged10.dump.exe`.** Three
outcomes, all informative: matches on-disk-encrypted ⇒ dead; matches merged10 ⇒ **jackpot**; matches
neither ⇒ a third thing worth naming. Not settleable offline — needs a live client.
⚠ Also recorded in `docs/s109-dump-forensics.md` §5 since 2026-08-04 and never acted on.

### 1.2 `dumpimage` HAS BEEN DISCARDING THE PROTECTOR — 52 TIMES

`tools/usmapdump/dumpimage.go:239-240`:
```go
case rg.typ != memPrivate:
    dumped = "(skip: " + regionKind + " — other module)" // other DLLs / mapped, not our unpacked code
```
It skips **every `MEM_IMAGE` executable region by design**, on the false premise in its own comment.
A **manually mapped, module-list-hidden** `MEM_IMAGE` region is not "another DLL" — **it is the
protector**.

**[M] The protector signature appears in 26/26 manifests, TWICE each = 52 mappings, every one
skipped.** `SizeOfImage 0x4066000`, 48,136,192 executable bytes — both matching S131 and
`runtime.dll` on disk. Verified straight from the manifests: `0xFF767000 0x1000 Image` and
`0xFFF2F000 0x170000 Image` are exactly LOW`+0x7000` and LOW`+0x7CF000` of the predicted region map.

**Proposed patch (NOT applied — it adds ~48 MB per dump to an already-16 GB tree, so make it a flag):**
skip `MEM_IMAGE` only when `AllocationBase` resolves to a real `ModuleList` entry; otherwise dump it.
Pure RPM, no injection, no `.text` write. Because FK-10 measured `packer0` as **94.8 % encrypted on
disk**, this plausibly yields **plaintext `packer0`** — where the kill vtable (`packer0 RVA 0x1831C0`)
and its installer (`RVA 0x7F86F0`) live. **That is FK-10 Wall #7's target.**

★ **Free by-product already banked:** the manifests' HIGH bases group into **four** eras —
`0x7FF90E000000` (9 dumps) · `0x7FFD3B400000` (1) · `0x7FFA42600000` (6) · `0x7FFB57400000` (10).
**The last three are exactly S131's three FK-31 kill addresses minus 1**, and the fourth is one
S131's minidump-only corpus could not see.

---

## 2. ★★★★ NOTHING MATCHES THE PLAYER — the gameplay frontier, and the door is HTTP

`joinQueue` puts the client into a real queued state (widget, running timer, working cancel) and then
**no matchmaker ever answers**.

- ⚠ **There is no push route.** FK-15's S118 bound-delegate map measured **`matchmakingNotif` as one
  of the 26 UNBOUND notif types** — broadcast into a delegate with no subscriber. **A match-found
  signal has to be HTTP.**
- ★ The obvious candidate is the path S61/S62 already built: `/core-game/players/{id}` is the
  "do I have a match to rejoin?" heartbeat, and setting a real `MatchID` there drives the client to
  fetch `/core-game/matches/{matchId}` and escalate. `forceTutorialMatch` is the existing switch.
  **The open question is whether a QUEUED client takes that path, or whether it wants the match
  delivered through the party document** (`FParty.state` has `Matchmaking` — is there a terminal
  value, or does `state` return to `Default` with a match id elsewhere?).
- ★ **Free receipt while iterating: the client RETRIES an unaccepted party verb.** `joinQueue` was
  re-POSTed every ~10–35 s until the response was accepted; once accepted, exactly once. **A
  repeating verb in `capture.log` means your response is being rejected.**

---

## 3. THE UDP ECHO PACKET FORMAT IS READABLE OFFLINE TODAY (FK-5's open task)

`CLAUDE.md`'s standing next task is *"a UDP echo responder on `PingHost:PingPort`"*, and
`docs/fk5-battle-gate-settled.md` §6.4 plans a verbatim-echo + hexdump responder because it grades
`[M]` that *"the packet format is unreadable offline"*.

**That `[M]` is REFUTED (S133).** `0x1F8CFC0` is a ~300-byte **wrapper** — it reads `[Ping] StackSize`
from the ini, names a thread from the ANSI literal `"LokiPing"` (`.rdata 0x79C6E80`) and tail-calls
the real worker at **`0x1F8BE90`**, which is **LIT in `merged.dump.exe`, `merged2`, `menu`,
`tutorial-hero` — every image this project has ever taken.** A correction banner is on that file now.

⇒ **Read `0x1F8BE90` and siblings `0x1F8BB50` / `0x1F8B870` / `0x1F8B4F0` and write the responder
against a known format.** ⚠ Note `pingecho` already exists in `ags` and the region banner reads
`NA EAST (VIRGINIA) 0 ms`, so check what is already implemented before building.

★ **The rule this produced, and it is the one to carry:** *before recording "this page is dark,
therefore X is unreadable", CHECK THE CALLEE.* A zero wrapper says nothing about the function it
calls. This is `fk22-dropphase-reachability.md:675` recommitted in a different file.

---

## 4. SPEND THE COVERAGE — 31 STALE CLAIMS, AND TWO RE-GRADES NOW UNBLOCKED

`python scratchpad/s133/tools/regrade_blocked.py` re-runs the audit; the list is
`scratchpad/s133/evidence/dark_cited_functions.txt`.

- **FK-22 §2.5's 16 COVERAGE-BLOCKED keys**: page `0x5456000` (the five `AuthPlayer*` entry points and
  `GetLandingTeleportLocation`'s thunk `0x5456C80`) now reads **3,860/4,096 non-zero**. That file
  calls the re-grade *"free, offline and unstarted"* — it is now also **unblocked**. Banner added.
- Still genuinely dark, each naming its own experiment: **`0x5875E90`'s neighbours are done**, but
  **`0x560EE70`** (BR phase-4 body), **`0x5A6AC40`** (`ULokiRespawnComponent::Respawn` — FK-1's named
  deploy door), **`0x55A34E0`**, **`0x52FEF50`**.
- ⚠ **`0x5A6AC40` is not in the `.pdata` union at all**, because that index is built only from
  MATERIALISED functions — see §6.

---

## 5. WHAT SHIPPED, AND THE KNOBS

| endpoint | status | contract |
|---|---|---|
| `POST /party/parties/{p}/joinQueue` | ✅ | response must be an **`FParty` under an advanced `Version`**; the field is **`state="Matchmaking"`**, NOT `inQueue` |
| `POST /party/parties/{p}/leaveQueue` | ✅ | cancel; `cancelQueue` also registered, client uses `leaveQueue` |
| `POST /party/parties/{p}/setIsOpen/{value}` | ✅ | value in the PATH; client sends capitalised **`True`/`False`** — parse case-insensitively |
| `POST /party/parties/{p}/emote/{Emote:Name}` | 🧪 | id is the **PATH TAIL** as a full PrimaryAssetId; **body always empty**; changes no state, deliberately |

- **Knobs: `AGS_JOIN_QUEUE=0`** (restores the pre-S133 wire) and **`AGS_GRANT_EMOTES`** (`1` = all
  331; default empty = byte-identical to pre-S133).
- **Emotes need `catalog_store_fix.dll`.** Backend alone is NOT enough: `ULokiAssetLoader` has **no
  `EmoteAssets` map** (it has Hero/HeroCosmeticsBundle/SlotCosmetics/StoreOffer/LoginReward/
  MissionPool/Equipment/Power), so emotes are the one cosmetic type that cannot be enumerated without
  the shim's AssetManager scan. Skins/gliders/sprays populate fine on `-NoHook`; emotes never will.
- ⚠⚠ **`cosmetics.go:13` was WRONG and is fixed in place** — it said ACCESSORIES covers
  *"Gliders/**Emotes**/Wisps/Sprays/Avatars"* as `SlotCosmetics`. The live 536-name map has **zero**
  emotes (AVATAR 225 / SPRAY 146 / GLIDER 115 / WISP 40 / SPIKEVFX 2).
- **`docs/endpoints.md` now has a "Party ACTION verbs" section** — it was missing all of these,
  including `setTargetQueues` from **S122**.

**Untested / unreached:** `TrySetFillPreference`, `TrySendInvite`, `TrySendRequest`, `TrySetIsReady`
produced **no traffic** (no reachable affordance in a solo party). **`0x5873000` / `0x5874000` — the
7 custom-game impls — remain DARK: this client has NO CUSTOM GAME entry point at all**, and it is not
toggle-gated (`customGameModes` is served, `CustomGameList` is `IsEnabledByDefault=true`).

---

## 6. TRAPS THIS SESSION PAID FOR — read before reusing any of these instruments

1. ⚠⚠ **`tools/strxref/index/pdata_union.csv` IS AN EXECUTION-TRACKING INSTRUMENT, NOT A FUNCTION
   MAP.** `pdataunion.py` keeps only slots with `End-Begin > 1`; a size-1 slot is the packer's
   placeholder for a function **not decrypted in that process**. It is **blind by construction on
   exactly the dark code you are asking about**, and any filter built on it can only admit LIT code.
   **Two independent agents built that filter in the same hour and both were caught only by a positive
   control.** Placeholder `BeginAddress` is also **not stable across processes** (737,978 distinct
   values over 524,439 slots) — it is not a free complete function map either.
2. ⚠ **A zero from `Invalid asset path for` is not evidence unless you show that log point fires on
   your surface.** It fired 197× for missions; it fires **0×** for cosmetics, and nothing establishes
   it is on that path at all.
3. ⚠ **An unconditional `+1` for a partial trailing page is wrong when the size divides evenly.**
   `.text` VSize `0x7649000` is an exact multiple of 4096, so `NP = V//P + 1` reads one page **past**
   `.text` into `.rdata` and inflates every count by exactly 1. Use the vetted tools
   (`queue_verdict.py`, `dump_coverage_ledger.py`); never re-implement a measurement inline.
4. ⚠⚠ **DO NOT PROPAGATE A LANE BEFORE ITS VERIFIER LANDS.** S132-f wrote that rule down; S133 broke
   it and paid **ten corrections — every one of which flattered the finding**. That asymmetry is the
   tell: an unverified lane's errors are not random noise, they drift toward the conclusion the lane
   was hired to reach. **If you will not wait, re-derive the load-bearing number yourself.**
5. ⚠ **Publish a share of a whole, check its complement.** Two complementary percentages that do not
   sum to 100 % is a free arithmetic-only self-check. S133 shipped 73.4 % + 32.09 % = **105.54 %**.
6. ⚠ **`launch-redirect.ps1` starts `ags` with its OWN environment** — a knob exported in your shell
   does not reach it. Verify the SERVED DOCUMENT, not the knob.
7. ⚠ **Grep for `emote` matches `remote`.** It produced three false shim hits
   (`Process**Remote**Function`, "treat this as a **remote** URL") and a wrong conclusion.

**`docs/method-rules.md` is now 85 rows** (re-derive, never retype:
`grep -cE '^\| \*\*[^|]*S[0-9]+-[a-z]+\*\*' docs/method-rules.md`).

---

## 7. REPO STATE

- ✅ **Pushed** at `39c1325`, branch level with `origin/dedicated-server-stub`.
  `forceTutorialMatch` is **`false`**. Build + all package tests green.
- **New canonical cold image: `dumps/merged10.dump.exe` — `.text` 16,755 / 30,281 pages (55.33 %)**,
  the exact union of all 40 state images. Verify with `python tools/re/dump_coverage_ledger.py`
  (reads BYTES not manifests, exits 1 on an orphan; validated both directions).
- ⚠⚠ **RUN THAT LEDGER AFTER EVERY CAPTURE.** Ten images sat unmerged for six days because
  `mergedumps` manifests name donors by BASENAME only — `merged2.dump.exe.txt` lists
  `SUPERVIVE-Win64-Shipping.dump.exe` twelve times, which identifies nothing.
- **New backend files:** `server/internal/interactive/joinqueue.go`, `partyactions.go`;
  `server/internal/menu/emotegrant.go`, `data/emotes.txt` (331 names, read live from the client's own
  FNamePool by scanning interned `/Game/Loki/Personalization/Emotes/<Name>/` paths).
- **Evidence:** `scratchpad/s133/{tools,evidence,out}/`. ⚠ The raw `capture-*.log` backups (~270 MB)
  and the binary analysis caches are **git-ignored on purpose**; their generating scripts are
  committed, so the outputs rebuild.
- ⚠ **`scratchpad/s133/evidence/fnmap_dark_entries.txt` was DELETED, not committed** — 170k lines
  derived from placeholder `BeginAddress` values this session's own control refuted. Do not
  regenerate it and treat it as a function map.
- **I cleared two USER-LEVEL env vars I had set** (`AGS_GRANT_EMOTES`, `AGS_PROBE_FRIEND`). They
  persist across reboots and would silently alter every future `ags` launch —
  **`AGS_PROBE_FRIEND` injects a FAKE FRIEND into the social surface.** If a future session sets one
  at user level for convenience, clear it in the same session.
- ⚠ **A client (PID 50192) and `ags` may still be running.** S118's lesson: check `Get-Process`
  before relaunching — a live process is worth a lot.

⚠ **Operational gotchas, each of which cost minutes:** `usmapdump dumpimage` needs the **`.exe`
suffix** (without it, `ERROR: process … not found` while the client is alive); `usmapdump` has **no
`assetmgr` subcommand** despite CLAUDE.md listing one; `extractor bpdump` takes
**`<assetSubstring> <functionName>`** and silently falls through to the enumerate default if the
subcommand is unrecognised; and **`ags` truncates `docs/capture.log` on restart — and
`launch-redirect.ps1` restarts `ags`.** Back it up first.

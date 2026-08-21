# S133 — FIND MATCH works: the queue sweep, and the endpoint it found

**2026-08-20. One `-NoHook` menu client, alive throughout. Zero injections, zero `.text` writes.**
Evidence: `scratchpad/s133/evidence/capture-*.log`, dumps `dumps/s133-queue-*`.

---

## 0. Headline

FK-20's top-ranked next lever was a **party/queue action sweep** to decrypt `UPartyManager`'s 20
dark impls, chief among them **`TryJoinQueue 0x5875E90`** — the most-cited dark address in the repo
(11 citations). It ran, and it turned into a shipped feature:

- ★ **The target page lit, with three controls holding.** `0x5875000` DARK → LIT; `0x5873000`,
  `0x5874000`, `0x5879000` all stayed DARK; **0 pages lost** (monotonicity control).
- ★★ **The click exposed an unserved endpoint: `POST /party/parties/{p}/joinQueue`** — no handler,
  falling to the `/` catch-all, which is *why* FIND MATCH did nothing.
- ★★★★★ **The decrypted function then told us how to serve it**, and after a two-probe bisect
  **FIND MATCH now works**: the client enters a real queued state with a running timer and a
  working cancel.
- ⚠ **Corpus yield was small and that is the honest headline for FK-20:** 183 pages decrypted
  *in this process*, but only **13 new to the corpus** (`merged6` 16,694 → `merged7` **16,707**,
  55.17 %). **Coverage-for-its-own-sake is saturated; targeted decryption of a specific blocking
  function is what pays.** One of the 13 is `0x5875000`, and that one page unblocked a feature.

---

## 1. The decryption experiment

**Pre-registered before any click** (`scratchpad/s133/tools/party_targets.py`): 20 `UPartyManager`
dark impls sit on exactly FOUR dark pages, partitioned by which UI action reaches them. Every phase
therefore has a target page AND three built-in spatial controls.

| page | contains | phase-1 prediction | result |
|---|---|---|---|
| **`0x5875000`** | `TryJoinQueue` + 6 | **DARK → LIT** | **LIT** ✅ |
| `0x5879000` | ready/fill/emote/invite | stays DARK | DARK ✅ |
| `0x5873000` | custom-game team/desc | stays DARK | DARK ✅ |
| `0x5874000` | custom-game password | stays DARK | DARK ✅ |

**Baseline 15,260 pages → 15,404 after the click: +144 pages (576 KB)**, against lane 4's estimate of
25–60. Tab navigation (BATTLE / PRACTICE / TUTORIALS) added **+35** more; the queued state **+2**;
the cancel **+0**. Session total **+183**.

⚠ **The page test alone could not attribute.** `0x5875000` hosts SEVEN functions, so lighting it
proves one of seven ran. **The wire settled it:** `POST .../joinQueue` ×2, and **none** of the other
six functions' endpoints (custom-game, decline-invite/request, join-party) appear anywhere in the
capture. Two independent instruments, one conclusion.

★ **90 % of the newly decrypted pages (129 of 144) carry no reflected UFunction at all** — they are
callees. That independently reproduces the ~86 % figure from `docs/fk20-coverage-settled.md` §2e and
re-confirms that the ≤394-page *reflected-anchor* ceiling is not a ceiling on what driving reflected
code decrypts. Among the callees: `APartyBeaconClient::ServerCancelReservationRequest` — real netcode.

---

## 2. The endpoint, and why the sweep never found it

```
POST /party/parties/party-<id>/setTargetQueues  {"queueIds":["bots"]}   <- tile select  (served)
POST /party/parties/party-<id>/joinQueue                                <- FIND MATCH   (NOT served)
POST /party/parties/party-<id>/joinQueue                                <- retry, +10.4 s
```

⚠⚠ **This is the SECOND correction to the S122 unserved-route sweep, with the same cause
`handleSetTargetQueues` already names.** That sweep parsed a 74-minute capture and reported
"56 client routes, 8 unserved". `setTargetQueues` was missed because nobody clicked a tile;
`joinQueue` was missed because **nobody clicked FIND MATCH**.
⇒ **The fix is not "capture for longer". It is "drive the interaction, THEN diff."** Two endpoints,
one blind spot, two sessions apart.

---

## 3. ★★★★★ The decrypted function supplied its own contract

This is the part worth keeping. Two hours earlier `0x5875000` was all-zero in **all 26** images this
project owns, so none of the following was readable:

```
TryJoinQueue 0x5875E90 … 0x5875F8F  lea r9, [0x5859E10]      <- response callback
callback     0x5859E10 … 0x5859E51  mov rcx,[rbx+0xf8]
                                     mov rdx, rdi
                                     call 0x587BE90          <- UPartyModel::SetParty
```

**[M] `0x587BE90` is `UPartyModel::SetParty`**, which S85 already characterised: it gates the whole
party document on a strict monotonic `FParty.Version` (`cmp [PartyModel+0x568]; jge bail`).

⇒ **`joinQueue`'s response IS an `FParty`, fed straight into `SetParty`.** So the handler must echo
the party under an advanced version — which is why it goes through `store.update()` exactly like
`handleSetTargetQueues`.

★ **Drive the code → decrypt it → READ it → serve the endpoint.** The experiment that found the gap
supplied the fix. That is the whole argument for the coverage work: not the percentage, but being
able to read the function at the moment you need it.

---

## 4. The two-probe bisect

**PROBE 1 — `inQueue: true` (party + member booleans).** Type-safe, no enum risk, correct first
probe. **MEASURED INSUFFICIENT — and the null was interpretable because the disjunction was
pre-registered:**

- the response **was** adopted — `SetParty` ran and the party-slot widgets rebuilt
  (`LogBlueprintUserMessages: MENUSPAWNER … Entering SetHero`) at the exact joinQueue timestamp, so
  the Version gate passed;
- **`LogJson` at Verbose logged ZERO import failures** — the document typed cleanly;
- the UI did not move, and the client **re-POSTed 35 s later**.

⇒ **wrong FIELD, not a dead route.** Without that pre-registration, "nothing happened" would have
been indistinguishable from "this endpoint is a dead end."

**PROBE 2 — `state: "Matchmaking"`.** The shipped data named the answer: the usmap's enum value table
gives **`EPartyState = { Default, Matchmaking, CustomGame, Unknown }`** (FK-14: enum VALUE tables are
the trustworthy part of a usmap; container-inner and underlying types are not). The adjacent `FParty`
field block also names `QueueJoinTime` and `MillisInQueue`.

**RESULT: FIND MATCH WORKS.** Screenshot-confirmed — the bottom bar becomes a queue widget reading
`CO-OP VS. AI` with a running timer and a cancel control, and **`joinQueue` is POSTed ONCE, not
twice**: the retry was the rejection symptom and it is gone.

★ **The timer runs WITHOUT `QueueJoinTime`/`MillisInQueue`** being served — the client times locally.
Those two were deliberately withheld (unconfirmed UE types; a wrong-typed matched key sinks the whole
document and would have made `state` untestable too). **The restraint cost nothing and the fields
turned out to be unnecessary.**

★ **`leaveQueue` was a correct speculative guess.** Three spellings were registered blind
(`leaveQueue`, `cancelQueue`, plus the join route); the cancel click POSTed exactly
`/party/parties/{p}/leaveQueue`. ⚠ The cancel path decrypted **0** new pages — it is entirely
already-lit code. An honest zero.

---

## 5. What shipped

`server/internal/interactive/joinqueue.go` — `handleJoinQueue`, `handleLeaveQueue`,
`partyPathPlayerID`, `writeParty`, `applyQueueState`; `playerState.InQueue` (transient, `json:"-"`,
same reasoning as `SoloMode`: a persisted queued flag would make a fresh boot claim it is already
searching with no matchmaker to clear it); three routes; and **all five party echoes routed through
one `writeParty`** so the GET poll cannot snap the flag back — precisely the defect
`handleSetTargetQueues` exists to remove. Knob **`AGS_JOIN_QUEUE=0`** restores the pre-S133 wire.

Backend controls both passed: `joinQueue` on a throwaway id returns the full document with
`inQueue: true` and `state: "Matchmaking"`; an unregistered sibling verb still returns `{}`.

---

## 6. By-product: a fresh FK-31 kill, and a rule that is not unevaluatable after all

Run 1 of this session (default shim set) died at **T+9 s**, during D3D12 RHI init, before login:

```
<ErrorMessage>Unhandled Exception: EXCEPTION_ACCESS_VIOLATION 0x00007ffb57400001
```

[M] FK-31 family match — `0xC0000005`, `ExceptionInformation[0] == 8` (EXECUTE), `addr & 0xFFF == 1`,
and **exactly the era-4 constant `0x7FFB57400001`**, confirming per-boot constancy again on a fresh
crash.

★★ **AND ITS `UEMinidump.dmp` ModuleList NAMES `runtime.dll` AT `0x7FFB57400000`** — the faulting
address is literally `base + 1`. `CLAUDE.md` records the rule *"detect the kill by
`RIP == runtime.dll base + 1`"* as **unevaluatable from a minidump** because `runtime.dll` has no
module entry (0 of 14 sampled). That is true of the **Sentry crashpad** corpus; it is **false for the
UECC corpus**, where the rule is directly evaluatable — and here it evaluated TRUE. Same scope error
this session already caught in `docs/fk20-coverage-settled.md` §3.2.

⚠ Run 2 used `-NoHook` (S111: 0/11 deaths vs ~30 % injected) and stayed alive for the whole sitting.

---

## 7. Phase 2 — `0x5879000` LIT, and two more unserved endpoints

Run on the SAME live client, after `joinQueue` shipped.

**RESULT: `0x5879000` DARK → LIT.** Controls held: `0x5873000` and `0x5874000` (custom game) stayed
DARK, **all five `UChatManager` pages** stayed DARK, `UStorefrontManager` and
`UPlatformInventoryManager` stayed DARK. **0 pages lost.**

⚠⚠ **THE BASELINE FOR THIS PHASE IS CONFOUNDED AND I AM NOT GOING TO PRETEND OTHERWISE.** The
intended phase-2 baseline dump never ran — the command was moved to the background and its `&&`
chain broke — so the diff is taken against `s133-queue-CANCEL`, which predates an `ags` restart and
an `AGS_PROBE_FRIEND` injection. **Three variables, not one.**
⇒ **The page result survives that only because the WIRE attributes it directly**, and because the
untouched-control set is large and clean (7 pages that a resync or a friend list could plausibly have
lit, all still DARK).

**[M] ATTRIBUTION, from the capture (User-Agent `Loki/UE5-CL-0`):**

| endpoint | count | function on `0x5879000` | served? |
|---|---:|---|---|
| `POST /party/parties/{p}/emote/` | **5** | **`TrySendEmote`** | **NO — catch-all** |
| `POST /party/parties/{p}/setIsOpen/True` | **1** | **`TrySetIsOpen`** | **NO — catch-all** |

⇒ **two of the six functions on that page are attributed by name.** The other four
(`TrySetFillPreference`, `TrySendInvite`, `TrySendRequest`, `TrySetIsReady`) produced no traffic and
are **NOT** shown to have run — the operator reported being unable to find those controls, which is
consistent with a solo party having no READY and no reachable fill/invite affordance.

★ **TWO MORE UNSERVED ENDPOINTS, both with a distinctive value-in-path URL shape**
(`.../setIsOpen/True`, `.../emote/` with a trailing slash). Same discovery mechanism as `joinQueue`:
**invisible to any passive capture-diff until somebody clicks the control.** That is now THREE
endpoints from one afternoon of driving the UI, against a sweep that had declared the surface mapped.

★ `0x5865000` (`USocialManager`) also lit — the `AGS_PROBE_FRIEND` injection populating the friends
list. Expected, and it is part of the confound, not part of the result.

**Corpus effect: `merged7` 16,707 → `merged8` 16,714 (55.20 %), +7 pages.**

⇒ **13 of `UPartyManager`'s 20 dark impls are now readable offline** (7 on `0x5875000`, 6 on
`0x5879000`). The remaining **7 are the custom-game functions on `0x5873000`/`0x5874000`, and they
stay dark because this client has no CUSTOM GAME entry point at all** — not a toggle, not a
permission; the affordance does not exist on screen.

---

## 8. Still open

- **Phase 2 (`0x5879000` — ready/fill/open/emote) and phase 3 (`0x5873000`/`0x5874000` — custom
  game) were NOT reached.** Phase 2 was blocked by the `joinQueue` gap, which is now fixed, so a
  queued party may expose READY/FILL next sitting. **Phase 3 has no entry point: there is no CUSTOM
  GAME tile on this client.** `GET /party/matchmaking/customGameModes` is served and `CustomGameList`
  is `IsEnabledByDefault=true`, so the surface is not toggle-gated — the entry point is elsewhere and
  is unidentified.
- **Nothing matches the player.** `joinQueue` puts the client in a queue that no matchmaker ever
  answers. The next question is what a match-found response looks like — and note FK-15's S118 map
  measured **`matchmakingNotif` as UNBOUND**, so there is no push route; it has to be HTTP.
- `QueueJoinTime` / `MillisInQueue` remain unserved and untyped.

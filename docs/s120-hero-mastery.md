# Hero Mastery — the surface, the gates, and the one missing feed (S120, 2026-08-14)

Status: ★★★★★ **SOLVED END TO END, SCREENSHOT-CONFIRMED, SHIM-FREE.**
The HUNTERS → MASTERY page **renders and is UNLOCKED**, driven entirely by the backend.
Missions 323 → 330 (225/225 mastery refs resolve), `FPlayerProgression.HeroMastery` populated,
`Hero:<name>` confirmed as the consumed id form, and the game-feature gate identified **and opened**.

**Shipping configuration** (currently live): `AGS_SERVE_HEROMASTERY=hero`, no probe delta, no
diagnostic floor, `AccountPass.Level = 10`. Verified: `PM+0x1E0` Num = **25**, `PM+0x17C` = **10**,
`PM+0x100` = **330**, `Invalid asset path` = **0**, `LogJson` errors = **0**.

Everything below is labelled **[M]** measured / **[I]** inferred / **[S]** speculative.

---

## ★★★★★ THE PAGE RENDERS (screenshot, 2026-08-14)

**HUNTERS → MASTERY draws the full surface for ELLUNA (`reshealer`)**: 3 mission rows × 3 tiers,
exactly the 3 `MissionSets` × 3 `Missions` shape predicted from the asset.

| rendered row | total | mission | our served max |
|---|---|---|---|
| **YOU CARRY THIS** — "Throw Moonlight Blessing onto Allies" | 0 / **3,000** | `ResHealerETossToAllies_3` | 3000 ✓ |
| **COMBAT MEDIC** — "Knock enemies shortly after rooting them" | 0 / **1,200** | `ResHealer_RootKnocks_3` | 1200 ✓ |
| **DIVINE AID** — "Resurrect allies with your Divine Intervention" | 0 / **800** | `ResHealer_ResWithR_3` | 800 ✓ |

Each row draws its 3 tier pips and its per-tier `EntitlementReward` PlayerTitles with `XPReward`
values — Lunar / Priestess / Backpack, Battle / Bunny / Biologist, Support / Savior / Resuscitator at
10,000 / 20,000 / 20,000 XP. The bar spans the whole family with the tiers as milestones, which is
exactly `UpdatePip` + `ProgressBar_Left/Mid/Right` driven by `GetProgressForMission(0|1|2)`.
⚠ Honest scope: our catalog max and the asset max are identical **by construction** (both derived
from the same DA), so this confirms the derivation is faithful — it does **not** discriminate whether
the number on screen came from our payload or from the asset.

### ★★ [M] `Hero:<name>` IS THE FORM THE UI CONSUMES — §5 resolved

The hero badge reads **3**. We served `Hero:reshealer` Level **3** and `HeroMastery:reshealer` Level
**10**. ⇒ the UI took the `Hero:` entry. That matches `GetHeroMastery`'s **linear first-match** scan
(our array orders `Hero:` before `HeroMastery:` per hero) and **confirms the disassembly over the
log-line inference**. The `Progress Notif` pair (tier 3 *and* tier 10) is `CheckMasteryChanges`
iterating every element, not the UI's choice — so "last wins" was **wrong**; first match wins.
⇒ **Ship `AGS_SERVE_HEROMASTERY=hero`.** `both` lets one hero carry two levels and is diagnostic only.

### [M] THE UNLOCK GATE NAMES ITSELF — §6's biggest hole is closed

The page renders **`🔒 Hunter's Journey Level 10`** beside the hero. That is
`GetLevelGameFeatureUnlocked(MasteryGameFeature)` **= 10**, expressed against the ACCOUNT pass —
i.e. the gate is `(AccountPass.Level + 1) >= 10`, and we were serving `AccountPass.Level = 0`.
⚠ **The 10 is uncomfortably equal to the delta'd `HeroMastery:` Level we were serving**, so it was
NOT taken at face value; it is under a single-variable test (`AccountPass.Level` 0 → 10, every other
value held constant). See the test's outcome below.
★ Note the page renders its rows **while still locked** — the lock gates the *track*, not the list.

---

## THE UNLOCK TEST — and two method findings that nearly cost a session

Single variable: `AccountPass.Level` 0 → 10 via `PUT http://127.0.0.1:9210/api/progression/{id}`.
Every `HeroMastery` value held constant (`Hero:reshealer` 3, `HeroMastery:reshealer` 10).

[M] **Adopted, confirmed by exact match:** `PM+0x17C` (AccountPass.Level) `0 → 0x0A`, `PM+0xA0`
(adopted Version) `0x6A7EC502 → 0x6A7EC503` — precisely the served 1786692867. HeroMastery `Num`
held at 50 throughout, so the change really was single-variable. The gate arithmetic is now
`(10 + 1) >= 10`.

### ★★★★★ [M] RESULT: THE LOCK IS GONE — THE GATE IS CONFIRMED

Second screenshot, same page: **`🔒 Hunter's Journey Level 10` is replaced by a live tier bar
reading `0 XP TO NEXT TIER`.** The hero badge still reads **3** (`Hero:reshealer`), and the three
mission rows are unchanged.

⇒ **`GetLevelGameFeatureUnlocked(GameFeature_HunterMastery) = 10` [M]**, and the mastery surface is
gated by `PlayerHasGameFeature = (AccountPass.Level + 1) >= 10` exactly as the disassembly predicted.
★ **The "10 = 10" coincidence is RULED OUT**: the label was the genuine requirement, not our delta'd
`HeroMastery:` value leaking, because raising *only* `AccountPass.Level` removed the lock while every
`HeroMastery` value stayed put. That coincidence was flagged BEFORE the test and the test was
designed to break it — the right order.

⚠ **Side effect to keep in mind:** `AccountPass.Level = 10` is real persisted per-player state, so
the PASSES / Hunter's Journey page now shows tier 10 too. It is admin-editable
(`PUT http://127.0.0.1:9210/api/progression/{id}`) and reverting it re-locks mastery.
⚠ Cosmetic oddity, unexplained: with `Level = 3, XP = 0` the tier bar drew **full/green** with
"0 XP TO NEXT TIER" rather than empty against the 200,000 requirement. Serving a level with zero XP
is a synthetic state; not investigated.

### ⚠⚠ [M] THE CLIENT DOES **NOT** RE-POLL `/progression/players/{id}` EVERY ~61 s

`interactive.go`'s `progressionVersionFor` comment asserts *"the client re-polls this route every
~61s"* and the whole bump-every-change design rests on it. **MEASURED at the menu: it fetched the
route exactly ONCE per messenger connection** — 02:34:25, then nothing for eight minutes despite the
served Version advancing. Serving a new document is therefore **not sufficient**; something must
prompt the client.

★★ **THE LEVER: drop the messenger socket.** `POST /api/ws/drop/{handle}` (admin panel) — the S85
party/loadout mechanism, which **generalises to `/progression`**: the client reconnected and refetched
**within ~3 s** (fetch #2772 at 02:42:29). This is the cheap way to iterate on this document without
relaunching, and it needs no Version guesswork, unlike `NotifyResource`.

### ⚠⚠ [M] THE USER-AGENT TRAP FIRED AGAIN — 2nd recorded instance

Before finding the above, the evidence read as *"the client fetched twice after the change and
REFUSED to adopt"* — a real puzzle, since `867 > 866` passes the strict `>` gate. **All three of
those fetches were MY OWN `Invoke-WebRequest`.** `capture.log` records them identically to client
traffic; only `User-Agent` separates them (`Loki/UE5-CL-0` vs `Mozilla/…WindowsPowerShell`).
⇒ **Filter `capture.log` by `User-Agent` BEFORE counting anyone's requests.** A fabricated
"client ignores our document" finding was about two minutes away.

---

## FLIGHT RESULTS (2026-08-14, game PID 45848, base `0x7FF7C7EF0000`, ags PID 44844)

Two flights, cold client on the first. `AGS_SERVE_HEROMASTERY=both`, `AGS_HEROMASTERY_PROBE_DELTA=7`,
and on flight 2 `AGS_HEROMASTERY_BASE_LEVEL=3`.

### [M] The document was accepted — all three surfaces intact

| instrument | reading |
|---|---|
| `Invalid asset path for Mission:` | **0** |
| `Mission object is null` | **0** |
| `LogJson: Error/Warning` | **0** (category verified raised to Verbose, so silence is meaningful) |

⇒ adding the `HeroMastery` key did **not** reject `FPlayerProgression`. The blast-radius risk in §7
did not materialise.

### [M] Both feeds landed, with controls

Read live off `ProgressionManager 0x1BC00107A20`:

| address | value | meaning | before |
|---|---|---|---|
| `PM+0x1D8` | `0x1BCE677D180` | HeroMastery Data ≠ null | `0` |
| `PM+0x1E0/+0x1E4` | `0x0000003500000032` | **Num = 50**, Max = 53 | **Num = 0** |
| `PM+0x100` | `0x000001550000014A` | MissionData **Num = 330** | 323 |
| `PM+0x110` | `0x0000000900000009` | Pools Num = 9 | 9 |
| `PM+0xA0` | `0x6A7EC502` = 1786692866 | **exactly the Version served** | — |
| `PM+0x208` | `1` | progression valid | 1 |
| `PM+0x17C` | `0` | AccountPass.Level | 0 |

`obj_by_class.py` (parsing its `found N` line, never counting rows) reports **330 live
`UMissionModel`** and 9 `UMissionPoolModel` — so the 7 recovered missions became real models.

### ★★★★★ [M] THE TRACK IS DRIVEN BY OUR FEED

`LogLokiBattlepassProgressManager: … Progress Notif`, sequenced:

| time | track | currentTierIndex | requiredXP |
|---|---|---|---|
| 07:30:04.298 | `HeroMastery:reshealer` | 0 | 25,000 |
| **07:34:25.626** | `HeroMastery:reshealer` | **3** | **200,000** |
| **07:34:25.626** | `HeroMastery:reshealer` | **10** | **7,812,500** |

3 and 10 are **exactly** the Levels served for `Hero:reshealer` and `HeroMastery:reshealer` under
`base=3, delta=7`. They arrive in the **same millisecond**, in array order.

★★ **INDEPENDENT ARITHMETIC CONFIRMATION — the client is really computing from our data.**
`MasteryLevelProgression.XPAmounts = [25000, 50000, 100000, 200000, 400000, 600000, 1000000,
4000000]`, `PerLevelIncreasePercentage = 0.25`:
- tier 0 → `XPAmounts[0]` = **25,000** ✓
- tier 3 → `XPAmounts[3]` = **200,000** ✓
- tier 10 → past the 8-entry ladder, extrapolated at +25 %/level:
  `4,000,000 × 1.25³ =` **7,812,500** ✓ exact.

A six-digit exact match against an asset constant read by a different instrument is not coincidence.

### [M] BOTH `FPrimaryAssetId` forms are consumed — §5's question is answered

Both `Hero:reshealer` and `HeroMastery:reshealer` produced a notif, and **both notifs carry the same
`progressionTrackId: "HeroMastery:reshealer"`**. ⇒ the client **normalises `Hero:<n>` to
`HeroMastery:<n>`** before the track lookup, which is exactly what
`ULokiAssetStatics::GetHeroMasteryIdForHeroId` exists to do. Either form works; the later array entry
wins. ⇒ **for shipping, `hero` mode is the right default** — `HeroId` is the field's declared
semantic and the client converts — and `both` should be reverted so one hero cannot carry two levels.

⚠ Only `reshealer` emits notifs because it is the **currently-selected hero**. The other 24 are
served but unobserved. Do not read that as 24 failures.
⚠ The 07:30:04 `tier=0 / requiredXP=25000` line is the **pre-adoption default**, not evidence that
flight 1's `delta=7` was rejected.

### [M] A previously unrecorded endpoint

`POST /party/parties/{party}/members/{id}/refreshMastery -> 200` appears in the login sequence
(sibling of the known `refreshLevel`). Its body and effect are **untraced**.

### ⚠ Unrelated death worth logging

The **previous** game session (PID 64368) died on its own at **02:16:29**, during the read-only RPM
recon, leaving a 44 MB crashpad dump archived to `dumps/crashpad-20260814-022942`. Nothing was
injected or written by that recon — it was pure RPM — so this is another instance of the project's
known ~30 % per-launch injection-era hazard, **not** caused by anything in this session's changes.
It is unanalysed.

---

## ★★★★★ THE CLAIM PATH IS CLOSED END TO END — THE REAL CLIENT CLAIMED (S120 part 3, 2026-08-14)

**MEASURED, and it is the strongest kind of evidence available on this project: the GAME sent the
requests.** Preserved in `dumps/s120-claim-evidence/`.

    #231324 15:18:44.382 POST /progression/players/{id}/hero/rewards/claim -> 200
        User-Agent: Loki/UE5-CL-0 (http-legacy) Windows/10.0.19045...
        body: {"heroId":"Hero:reshealer","claimIds":["hm:reshealer:0"]}
    #231327 15:18:44.839  ... ["hm:reshealer:1"] -> 200
    #231331 15:18:45.346  ... ["hm:reshealer:2"] -> 200

ags granted all three (`mastery claim: … requested=1 granted=1 rejected=0` ×3) and the store
persisted `masteryClaimed = {"reshealer":[0,1,2]}`.

**EVERY inference in the trace was confirmed by the client's own bytes** — including the one flagged
[I] as "a single letter, never seen on the wire":

| predicted | client sent | was |
|---|---|---|
| `POST …/progression/players/{id}/hero/rewards/claim` | identical | [M] from `.rdata 0x08B4D3A0` |
| `heroId` (StandardizeCase) | `heroId` | [I] → confirmed |
| **`claimIds`** | **`claimIds`** | **[I] one letter → confirmed** |
| `"Hero:<name>"` not `HeroMastery:` | `"Hero:reshealer"` | [I] → confirmed |
| our minted ClaimIDs echoed verbatim | `hm:reshealer:0/1/2` | [M] |

⇒ **Serving `FPlayerProgression.HeroMastery[].UnclaimedRewards` IS sufficient.** No populate hop was
missing, no shim, no `.text` write. The client renders the reward, the user claims, we grant.

### ⚠⚠ RETRACTION — MY "CONTROLLED NEGATIVE" WAS NOT CONTROLLED

The previous revision of this section reported *"claimableRewards=[] ⇒ serving UnclaimedRewards is
necessary but NOT sufficient"* and called it a controlled negative because the notif was FRESH
(post-arming, tier actually changed). **That fixed staleness but not VALIDITY.**

`claimableRewards` occurs 30 times in the whole log corpus and is `[]` in **30 of 30** — including
the account pass at tier 10, and including runs where claiming demonstrably worked minutes later.
**There is no known-good case anywhere**, so the field has no positive control and cannot
discriminate "nothing is claimable" from "this payload field is simply never populated". I used a
payload field as an instrument without ever showing it could read non-empty.

★ Decisive counter-evidence: **the client fetched `/progression/players/{id}` exactly ONCE
(04:04:05, UA `Loki/UE5-CL-0`) and there were ZERO relaunches in the capture** — so the very
document I measured as "not claimable" is the one the client claimed from, 11 hours later. The
negative was false at the moment I published it.

This is the instrument-artifact pattern, 45th recorded instance, committed by the same session that
had just written the rule down twice. **A "fresh" reading of an uncontrolled field is still
uncontrolled.** Demand a positive control for the FIELD, not just recency of the sample.

### What this does NOT overturn

The disassembly stands: `GetAllClaimableHeroMasteryRewards` (impl `0x583F1F0`) really does go
`FindVM` → `0x57ABCC0` → walk `[VM+0xC8]`/`[VM+0xD0]`. That is what the *manager* API reads. It is
simply not evidence about whether the UI could offer a claim, and it was never in conflict with the
outcome — I over-read it as a blocker.

⚠ Still genuinely unknown: **what user action produced the claim**, and which widget offered it. No
Blueprint references the hero claim (controlled census: hero-claim symbols 0 vs `ClaimReward` 24), so
it is native-only — `BulkClaimAllProgressionTrackRewards` (thunk `0x5268FB0`) via the lobby
multi-claim remains the leading candidate, unconfirmed.

---

## Superseded first pass (kept for the record): endpoint TRACED and SERVED; claimable state believed NOT reached

### ★★★★ [M] THE ENDPOINT, traced with a passing positive control

    POST {progressionBase}/progression/players/{userId}/hero/rewards/claim

- literal `L"/hero/rewards/claim"` (UTF-16LE) at **`.rdata 0x08B4D3A0`**; exactly ONE rip-relative
  xref, `lea r8,[rip+0x3325588]` at **`.text 0x05827E11`**
- builder **`0x05827DA0`**: `"/progression/players/" + UserId` + `"/hero/rewards/claim"`, then
  `base = GetServiceAddress(key L"progression")` — the same key as all 11 progression call sites,
  and the client's real GET has no path prefix, so base is scheme+host only
- verb **POST** (`lea rdx,[0x8600824 ansi="POST"]` at `0x05827F24`); dispatch `call 0x057EC800`
- CONTROL: the same method re-found `L"/progression/players/"` at `.rdata 0x08B4D0D0` and its
  documented dispatcher (11 refs incl. `lea rdx` at `0x058454D2`) before any new claim was made.

**REQUEST** `FClaimHeroMasteryRewardsRequest` (UHT `0x09C42048`, SizeOf 0x20, 2 props):
`{"heroId":"Hero:reshealer","claimIds":["hm:reshealer:0"]}`.
Casing is `FJsonObjectConverter::StandardizeCase`, proven from a REAL client POST in
`capture.log` #479 (UA `Loki/UE5-CL-0`): `LastBattlepassIDSeen` → `lastBattlepassIdSeen`.
⚠ `ClaimIDs → "claimIds"` is that rule applied to `"IDs"` and has never been seen on the wire — [I],
one letter. The handler accepts every casing rather than betting on it.

**RESPONSE** `{"successfulClaimIds":[…],"unclaimedClaimIds":[…]}` — no
`ClaimHeroMasteryRewardsResponse` type exists, and `FClaimProgressionTrackRewardsResponse` /
`FClaimMissionRewardsResponse` are both SizeOf 0x20 with identical fields, so the JSON is the same
whichever is instantiated.

### ★★ [M] `UnclaimedRewards` SERVES AND INGESTES — 0 → 75

`{"0":{"ClaimID":"hm:reshealer:0","SKU":"Emote:SeraphHi"}}` — a JSON **object with int-parsable
keys**. Measured live: total `UnclaimedRewards` across the 25 heroes went **0 → 25** (level 0) and
then **→ 75** at level 2 (25 × 3), adopted Version exact, **LogJson errors 0**, `Invalid asset path`
0, MissionData still 330. **The blast radius did not fire** — the shape is right.

### ⚠⚠ [M] BUT IT DOES NOT REACH `claimableRewards`. THE PLAN'S PREMISE IS FALSIFIED.

With 75 rewards ingested, a tier change forcing a FRESH notif, and zero parse errors:

    09:04:05:969  track=HeroMastery:reshealer  tier=2  claimableRewards=[]

⇒ **Serving `UnclaimedRewards` is necessary but NOT sufficient.** This is a controlled negative: the
notif is fresh (post-arming, tier actually changed), the data is provably present, and nothing failed
to parse. Contrast the earlier reading of the SAME field, which was **uninterpretable** because the
last notif predated the change — that distinction is the whole reason this one counts.

**And the disassembly said so first.** `UClaimableRewardManager::GetAllClaimableHeroMasteryRewards`
(thunk `0x5269160` → impl **`0x583F1F0`**, fold 1) does NOT read `UnclaimedRewards`:

    mov rbx,[rcx+0x58]            ; the view manager
    call 0x558B110 / 0x12F4230    ; FPrimaryAssetId -> ToString
    call 0x57AB180                ; FindVM  (the SAME FindVM as the S83 account-pass fix)
    test rbx,rbx / je -> false
    call 0x57ABCC0(VM, outArray)  ; walks [VM+0xC8] / [VM+0xD0] = VM.Levels, bails when empty

⇒ claimables are built from the per-hero **BattlepassViewModel's Levels**, and `UnclaimedRewards`
could only reach them via `CheckMasteryChanges` (impl `0x5795510`) → populate. **That hop does not
happen** [M, by the null above].
★ The VMs themselves are fine: MEASURED 4 live `BP_BattlepassViewModel_C` with `Levels` Num =
**86** (Hunter's Journey), 11, **9**, **9** — the 9s match `WBP_HeroMastery_LevelIcon`'s `[0,8]`
clamp exactly, and they are created lazily per viewed hero. So `FindVM` can hit and there IS an
array to walk; the levels simply are not marked claimable.
★ The ACCOUNT PASS shows the identical symptom (`ProgressionTrack:HuntersJourney tier=10
claimableRewards=[]`), which lines up with S83's own still-open item. **Same gap, both tracks** —
worth attacking once rather than twice.

### [M] NO BLUEPRINT REACHES THIS ROUTE

A controlled census over all 69,142 extracted assets: `ClaimHeroMasteryRewards` 0 / `ClaimIDs` 0 /
`GetAllClaimableHeroMasteryRewards` 0, against passing positive controls `ClaimReward` 24 /
`HasClaimableMission` 2. The Claim button on `WBP_HeroMastery_Mission_v2` is the **MISSION** claim
(`/mission/rewards/claim`), NOT this one. ⇒ **do not use that button as this route's success
criterion.** The likely user-reachable path is the lobby multi-claim
(`BulkClaimAllProgressionTrackRewards`, thunk `0x5268FB0`).

### ★ FREE RECEIPT, STILL ARMED

The shared claim sender **`0x057EC800` is `PAGE_NOACCESS`** in the live process (negative control:
`CreateMissionsModel 0x56E0600` likewise unreadable, so the instrument discriminates). **No claim
POST of either kind has ever been dispatched this session.** If it flips to `EXECUTE_READ`, a real
claim went out. Zero-cost, valid while PID 45848 lives.

### Next lever, ranked

1. **What marks a VM Level claimable.** Disassemble the populate (`0x57DF4B0`) and the VM builder's
   Init (`0x57BB560`) — S83 already proved both run — and find the field `0x57ABCC0` tests per level.
2. **`GET /progression/players/{id}/tracks/rewards`** is a stub in `menu.go:70`. It is the only
   other reward-shaped route the client knows; it may be what actually carries claimable state.
3. `byte[PM+0x388]` is CLAUDE.md's recorded claim gate and reads **1** — so it is NOT the blocker.

---

## ★★★★★ THE BARS MOVE — CONFIRMED ON SCREEN (2026-08-14)

`YOU CARRY THIS` renders **1,500 / 3,000** with a half-filled bar, and the per-tier segments fill
independently across all three rows (COMBAT MEDIC tier 1 at 15/30; DIVINE AID tier 1 full 20/20 and
tier 2 half 100/200) — matching every value served, exactly.

### ⚠⚠ THE THING THAT MADE THIS LOOK BROKEN: A STALE WIDGET BINDING, NOT A DATA PROBLEM

Pushing progress to a client **already sitting on the page changes nothing on screen.** The bars only
picked it up after switching hunter and back, which forces the mastery screen to rebuild
(`WBP_HeroMastery_Screen_v2::ExecuteUbergraph` stmt [57] dedupes on same-hero, so away-and-back is a
genuine rebuild).

[M] The data was in the client the whole time — a `GUObjectArray` walk found **330
`UMissionObjectiveModel`** with **17 carrying our exact non-zero values** and 6 `Completed`, and 330
`UMissionModel` all with `MissionAsset` set and `Objectives` TMap Num=1. [I] The ingester rebuilds
the model objects on each adoption, so widgets built earlier hold pointers to a previous generation
that still reads 0.

⇒ **Do not diagnose this surface from a page that was already open.** Rebuild it (hunter switch, or
relaunch) before reading anything off it. Two separate surfaces were mis-diagnosed as broken feeds
because of this.

### ★ The row TEXT shows the LAST tier, because we serve all three as active

`GetProgressForMission(Index)` → `MissionsModel->GetCurrentAndTotalProgress(MissionAsset[Index],
&Current, &Total)` (both **int32**), and `ActiveIndex` comes from a loop gated on
`IsValid(GetActiveMissionModel(...)) || CompletionCounts[...] > 0`. Since we serve **every tier as
simultaneously granted**, that gate never fails and the index lands on the last tier — which is why
tier-1/tier-2 progress alone left the label reading `0 / 3,000`.

The SEGMENTS are per-tier and correct regardless. If the label should instead track the tier the
player is working on, the lever is `PrereqMissions` (161 of 330 DAs declare one): serve a tier only
once its prereq is complete. **Not done** — it changes what we serve on a route measured at 330/330,
and the segments already convey the full picture.

---

## MAKING THE BARS MOVE (S120 part 2, 2026-08-14)

The bars render but sat at 0 because **nothing could write a progress key the client reads**. Two
independent defects, both now fixed, both measured before and after.

### ⚠⚠ DEFECT 1 — the match-result fan-out wrote a DIFFERENT NAME SPACE

`missionInfo` READS `compositeKey(mission, objective)` built from **catalog** names.
`applyMatchResult` WROTE composite keys built from the **shim manifest's** names. MEASURED against
the live persisted manifest:

| | |
|---|---|
| catalog composite keys (read) | **330** |
| manifest composite keys (written) | 187 |
| **overlap** | **7** |
| manifest keys with no catalog match | **180** |

⇒ progress was written, persisted, and echoed by the API — and **invisible in game**. That is
exactly why it went unnoticed.

⚠ **An earlier reading of this as "the manifest is empty so it falls back to bare names" was WRONG.**
The manifest persists to `state/interactive.json` and survives ags restarts, so it long outlives the
retired `missions_fix` — 330 rows were still there. The fallback never fires. Measure before naming a
mechanism.

★ Live proof of the damage: of 14 keys in the store, **8 were orphaned** —
`Tournament_PlayAGame/PlayAGame` (store) vs `Tournament_PlayAGame_1/PlayAGame` (catalog), and
`Tournament_KnocksAssists/BR_Knocks_Assists` vs `Tournament_KnocksAssists_1/Knocks_Assists`, where
**both halves differ**.

**FIX:** `catalogManifest()` / `fanoutManifest()` — fan out over the catalog, the same source
`missionInfo` serves. The stored manifest survives only as a fallback for an empty catalog.

### ⚠⚠ DEFECT 2 — `objectiveRules` was keyed by the shim's names too

Even with the fan-out fixed, of **102** distinct catalog objective names exactly **2** had a rule.
Nearly every rule was a near-miss of the real name:

```
a2winarenagames  -> A2_WinArenaGames      BR_3Top4    -> Top3        BR_Knocks -> Knocks
BR_Knocks_Assists-> Knocks_Assists        BR_WinABR   -> WinABR      BR_Minions-> KillMinions
BR_KillBosses    -> BossKills             BR_Vaults   -> Vaults      BR_Boxes  -> Boxes
BR_Capture Bonfires -> CaptureBonfires    TopXWithFullArmory -> TopXWithFullArmoryInventory
Armory_PlayUniqueHunters -> PlayUniqueHunters   Onboarding_PlayTriosMatch -> PlayTrios
```

**FIX:** added the catalog names; kept the shim names as aliases for the `-WithMissionsShim` rollback
path. They cannot double-count — a mission's objective has exactly one name, so a given fan-out
source matches at most one rule per objective.

**MEASURED, coverage report:** `MissionsFullyTrackable` **3 → 22**, `ObjectivesMapped` **2 → 20**.

**MEASURED live:** one tournament-win POST now applies to **10 real servable keys**
(`ArmoryDaily_GetKnocks/Knocks +8`, `Tournament_KnocksAssists_1/Knocks_Assists +10`,
`Armory_WeeklyMinions/KillMinions +40`, …). Before the fix those increments landed on keys nothing
reads.

### ★ THE INVARIANT TEST — and its negative control

`TestMatchResultKeysAreServable`: **every key the match-result engine writes must be a key
`missionInfo` serves and reads back.** That is the property both defects violated.

It is controlled, not merely green: the servable set must ACCEPT a known-served composite and REJECT
both broken shapes (a bare objective name, and a shim-manifest composite). And the whole test was
verified to FAIL when the fan-out is reverted — it then names **33 unservable keys**. A test that has
never been seen to fail is not evidence.

### ⚠ WHAT STILL CANNOT MOVE FROM A MATCH, AND WHY IT IS NOT A TODO

The **293 hero-mastery objectives are unmappable from a match summary** — they are per-ability events
("heal allies with Cinnabar Cocktail", "knock enemies shortly after rooting them") that no
match-level stat expresses. That is a property of the data, not a missing rule. Moving those bars
needs per-ability telemetry the client never sends, or the explicit `objectives` passthrough.
Deliberately unmapped and recorded as decisions, not oversights: `TimeSurvive` (unit unverified —
inventing a field would bake a guess into the wire format), `ArmoryDaily_CompleteDailies` (a META
mission counting other completions), and the `NewOnboarding_*` / `CompleteAllTutorialMaps_Base`
tutorial completions.

⇒ **Mastery bars move today via the direct path**, which is measured working end to end:

```bash
curl -X POST http://127.0.0.1:8080/revival/missions/progress -d '{"objectives":{"ResHealerETossToAllies_1/ResHealer_ETossToAllies":80}}'
```

then force the client to re-read it with `POST http://127.0.0.1:9210/api/ws/drop/<handle>`.

---

## 0. The headline

**Hero Mastery is a SPLIT surface, and conflating the two halves is the trap.**

| half | source | backend involvement | status |
|---|---|---|---|
| row LIST (which missions, titles, descriptions, icons, tier maxes) | shipped `LokiDataAsset_HeroMastery` assets | **none** | [M] closed |
| PROGRESS / completion / active tier | the same `UMissionsModel` we already populate via `MissionInfo` | already served | [M] fed |
| per-hero LEVEL / XP / reward track | **`FPlayerProgression.HeroMastery`** | **was omitted — this was the gap** | implemented, unflown |

[M] Measured live before the change (game PID 64368, ProgressionManager `0x2601FB97A20`):
`PM+0x90+0x148` = `PM+0x1D8` read `Data=0 Num=0 Max=0`. The offset arithmetic was **controlled** in
the same pass — the identical chain read `MissionData Num=323` at `PM+0xF8` and `Pools Num=9` at
`PM+0x108`, the exact values we serve.

---

## 1. Why hunter missions render here and never in the modal

[M] **There is no pool filter on this surface.** `grep "Pool"` returns **0** across all Hero Mastery
bytecode dumps, against a control token `MissionSets` returning 6 in the same file. The missions
modal's categories are a hardcoded `PoolAsset[]` allowlist that omits `DA_MissionPoolHunterMissions`;
Hero Mastery has no equivalent. **Do not go looking for a mastery pool allowlist — it does not exist.**

[M] **Hero Mastery does NOT gate on `bAllMissionLoaded`.** Measured absent across all seven Hero
Mastery bpdump files, against a 17-hit `GetMissionsModel` control. Unlike the missions modal and the
news banner. Do not reason from that flag here.

[M] The allowlist that *does* exist is a per-hero **mission** allowlist living in the data asset:

```
LokiDataAsset_HeroMastery : LokiDataAsset_ProgressionTrack {
    PrimaryAssetId    Hero;
    Array<MissionSet> MissionSets;      // MissionSet { Array<PrimaryAssetId> Missions }
}
```

Uniformly **3 sets × 3 missions across all 25 heroes = 225 distinct mission ids.**

⚠ [M] **None of the 225 is one of the 75 abstract bases.** Serving the abstract bases (S119) did
nothing for this surface. This corrects the loose S119 statement that "~293 of the 323 are Hero
Mastery content": the correct figure is **225 named ids, of which 218 were served**; the 75 abstract
bases are templates that no mastery set references.

---

## 2. The 7 missing missions — our own bug, now fixed

[M] The 25 mastery assets name 225 missions. We served **218**. The 7 absent were:

```
Alchemist_UltMultihit_1   Beebo_RMBHitEnemies1   BountyHunter_UltKnockEnemies_1
Reaper_QSweetSpotHit_1    Void_BlackholeMultiples_1
burstcaster_rmbreturnhit_1   farshot_knockaftertp_1
```

[M] **Root cause was ours**, in `tools/re/gen_missions_catalog.py:125` — `if not objectives: skipped;
continue`. A `_1` tier variant that overrides nothing but its rewards has no `Objectives` key,
because CUE4Parse serializes only non-default properties; the engine resolves that through the CDO's
`Super` chain and we did not.

[M] **Exact closure, not a heuristic:** 330 mission DAs ship, 323 declare `Objectives`, **exactly 7
do not**, and those 7 are **set-identical** to the 7 unserved mastery refs.

**Fix:** a second pass resolves inherited `Objectives` via the `Super` link. Verified:
`323 → 330`, the 7 intended additions, **0 pre-existing entries changed, 0 removed**, and
**225/225 mastery refs now resolve**.

Scope was kept deliberately narrow (single-variable): objectives only, and only when the variant
declares none. **Pool is NOT inherited** — that would newly attach a pool to all 218 variants,
changing what the other 323 missions are served with, for no gain (`PoolId` was already disproven as
an acceptance filter and this surface has no pool filter).

### ⚠ Two traps this fix walked into

1. **Two of the 7 are findable only BY `InternalName`, never by file name** — the same rule that was
   worth 126 → 248 in S119. `DA_Mission_Void_UltMultiples_1` declares
   `InternalName "Void_BlackholeMultiples_1"`, and `DA_Mission_Beebo_RMBHitEnemies_1` declares
   `"Beebo_RMBHitEnemies1"` (no underscore). A filename search reports **both as absent from the
   shipped data**, which is false and would have written off 2 of the 7 as "dangling references in
   shipped data". A subagent did exactly that; searching by `InternalName` recovered them.
2. ★ **`extractor bpdump` leaves `<Name>_uasset.json` copies in the same flat `out/` directory.** For a
   variant those collapse harmlessly onto the same `InternalName` key, but an **abstract base has no
   `InternalName`, so it is keyed by file name and a stray copy becomes a WHOLE EXTRA MISSION.**
   Measured: an RE pass during this session left 4 such files behind and the catalog silently grew to
   **331**, the extra being `DA_Mission_Void_BlackholeMultiples_Base_uasset` — an id registered
   nowhere, which the client would reject with `Invalid asset path for Mission:`.
   **Caught only because 331 missed the pre-registered prediction of 330.** A run without that
   prediction would have shipped it. The generator now excludes `*_uasset.json`.

---

## 3. The measured schema of `FPlayerProgression.HeroMastery`

Recovered from UHT `FStructParams`/`FPropertyParams` over
`dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe` (`.rdata` 100 % readable).
**Positive control passed first:** the same decoder re-derived `FMissionInfo`'s 4 properties at their
4 known offsets with `SizeOf 0x80` before any new claim was trusted.

```
FPlayerProgression                                        SizeOf 0x178   (8 props, closes EXACTLY)
    ID                @0x000  FString                     served
    Version           @0x010  int32                       served
    Matches           @0x018  TMap<FString,FPlayerProgressionMatchXP>
    MissionInfo       @0x068  FMissionInfo                served
    AccountPass       @0x0e8  FProgressionTrackLevel      served
    HeroMastery       @0x148  TArray<FHeroMasteryProgress>    <-- THE GAP
    LoginReward       @0x158  TArray<FLoginReward>
    EventProgression  @0x168  TArray<FEventProgression>

FHeroMasteryProgress : FProgressionTrackLevel             SizeOf 0x70    (closes EXACTLY)
    <unreflected>     @0x000  1 byte, NOT a UPROPERTY, meaning UNIDENTIFIED, unreachable from JSON
    Level             @0x004  int32                       (inherited)
    XP                @0x008  int32                       (inherited)
    Cleared           @0x00c  bool                        (inherited; offset [M] from disasm)
    UnclaimedRewards  @0x010  TMap<int32,FHeroMasteryRewardClaimData>   (inherited)
    HeroId            @0x060  FPrimaryAssetId             <-- the ONLY own property

FHeroMasteryRewardClaimData  SizeOf 0x20 { ClaimID FString @0x0; SKU FPrimaryAssetId @0x10 }
```

Recursion terminates in scalars — **no enums, no `UObject*`, no `FDateTime`, no delegates, no nested
`TArray` anywhere under `HeroMastery`.** That is what makes this low-risk relative to
`FMatchHistoryEntry`.

**Three independent instruments agree** [M]: the UHT decode; `tools/asdump/out/binds_members.csv`
(a different pipeline entirely — AngelScript binds — agreeing on all 8 properties and all 5 flattened
members *including container inner types*); and disassembly of `UProgressionManager::GetHeroMastery`
(impl `base+0x5841D70`), which reads `[PM+0x90+0x148]`/`+0x150` and does `imul rdx,rax,0x70`.
⚠ The usmap was **not** used for any container inner type (FK-14).

---

## 4. The consumer chain — no shim, no `.text` write

```
GET /progression/players/{id}
  -> ingester base+0x585A570   copy-constructs the whole 0x178 struct into PM+0x90
                               (HeroMastery included, at no extra cost), sets PM+0x208/+0x388,
                               Broadcasts PM+0x48
  -> UBattlepassViewManager::CheckMasteryChanges
        exec thunk 0x5254220 -> impl 0x5795510
        walks HeroMastery at OutPlayer+0x148 with `imul rsi,rax,0x70`
        `cmp rdi,rsi; je` SKIPS THE WHOLE LOOP when Num == 0     <-- why we saw nothing
        -> FindVM 0x57AB180 -> Init 0x57BB560 -> populate 0x57DF4B0
  -> WBP_HeroMastery_Screen_v2 binds OnProgressionUpdated to
     UProgressionManager::OnUpdatedPlayerProgression
```

[M] `CheckMasteryChanges` impl `0x5795510` is **0x1090 from** `CheckAccountPassChanges` impl
`0x5794480` — the same translation unit. It is the mastery twin of the function S83 already solved,
and it reuses the *same* `FindVM`/`Init`/populate trio.

⚠ We never force-call `0x57DF4B0` — that was the S82 crash. The client calls it itself off the ingest.

[M] Decryption state measured **live with a working negative control**: `CheckMasteryChanges`,
`PlayerHasGameFeature`, `GetCurrentPlayerProgression`, `GetHeroMastery` all read fine, while
`CreateMissionsModel 0x56E0600` and `OnPSMissionsUpdated 0x56F51B0` are `PAGE_NOACCESS`.
⚠ Note `CreateMissionsModel` reads **non-zero in the offline dump** even though it is `PAGE_NOACCESS`
live — **the offline dump alone gives a FALSE positive here; only the live control discriminates.**

---

## 5. The open question: which `FPrimaryAssetId` type prefix

The two instruments disagree. **Do not pick by taste.**

- **`Hero:<name>`** — disassembly: the caller at `base+0x57B856E` does
  `movups xmm0,[MasteryDA+0xC0]`, and `0xC0` is where UHT places
  `ULokiDataAsset_HeroMastery::Hero`, then hands it to `GetHeroMastery`, which compares against
  `elem+0x60`. The field is also literally named `HeroId`. **Directly on-point.**
- **`HeroMastery:<name>`** — the client's own log line
  `Progress Notif: {"progressionTrackId":"HeroMastery:reshealer",...}`, plus
  `ULokiAssetStatics::GetHeroIdForHeroMasteryId`/`GetHeroMasteryIdForHeroId` existing at all, which
  proves the two ids are **distinct and mutually convertible**.
  ⚠ But that log line is the *progression track* id (the mastery asset's own `PrimaryAssetId`), which
  is not necessarily what the `HeroId` **field** holds. Weaker evidence, about a different thing.

[M] The **name** half is unambiguous either way: all 25 mastery DAs declare
`InternalName == Hero.PrimaryAssetName`.

**Resolved in one launch by `AGS_SERVE_HEROMASTERY=both`** — safe because `GetHeroMastery` does a
linear **first-match** scan and `CheckMasteryChanges` silently skips entries whose `FindVM` misses, so
surplus entries cannot break either consumer. Set `AGS_HEROMASTERY_PROBE_DELTA` to a nonzero integer
to offset the `HeroMastery:`-typed duplicate's `Level`, making the flight **self-discriminating**:
whichever `Level` the UI draws names the key the client actually consumed.

---

## 6. A THIRD gate that is not the array

[I] `PlayerHasGameFeature` (thunk `0x54D8460` → impl `0x585DB70`) drives
`WBP_HeroMastery_Screen_v2`'s `LockSwitcher`:

```
PlayerHasGameFeature = (AccountPass.Level + 1) >= GetLevelGameFeatureUnlocked(MasteryGameFeature)
   ... with -1 short-circuiting to "unlocked" in BOTH that function and 0x5665820
```

Live: `[PM+0x208]=1` (progression valid, so the gate is reached), `[PM+0x17C]` = **AccountPass.Level =
0**, `[PM+0x388]=0`.

⚠⚠ **`GetLevelGameFeatureUnlocked(GameFeature_HunterMastery)` has NO measured value** —
`GameFeature_HunterMastery` is not in `tools/extractor/out`. **This is the single biggest hole in the
unlock story** and it is why "serve HeroMastery and it renders" is a prediction, not a result.

⚠ Serving `AccountPass.Level = -1` would unlock every game feature — but CLAUDE.md records that same
`-1` as what made `CheckAccountPassChanges` bail. **A trade-off to test single-variable, not a free win.**

---

## 7. What was shipped

- `tools/re/gen_missions_catalog.py` — inherited-objectives pass + `*_uasset.json` exclusion.
  `missions_catalog.json` 323 → **330**.
- `server/internal/interactive/heromastery.go` — the feed, **off by default**.
- `server/internal/interactive/store.go` — `playerState.HeroMastery`.
- `server/internal/interactive/interactive.go` — one new top-level key, and the hero-mastery digest
  joins the `Version` key.
- `server/internal/interactive/heromastery_test.go` — 6 tests, all passing; full server suite green.

### Knobs

```
AGS_SERVE_HEROMASTERY = (unset)|off | hero | mastery | both
AGS_HEROMASTERY_PROBE_DELTA = <int>     # offsets the HeroMastery:-typed duplicate's Level in "both"
```

⚠⚠ **BLAST RADIUS IS THREE SURFACES, NOT ONE.** `FJsonObjectConverter` returns false for the WHOLE
struct on the first *matched* key it cannot import, so a wrong-typed `HeroMastery` would close the
missions page, the Hunter's Journey pass **and** news-banner gate 2 at once — and it would look
exactly like "no effect". That is why the default emits **no key at all** and the document stays
byte-identical to pre-S120.

★ **Arming the knob must move `Version`, and it does** (the digest includes the mode). The adoption
gate is a strict `>` on `dword[PM+0xA0]`; without that, a client that had already adopted the current
Version would ignore the new key and the run would read as "serving HeroMastery does nothing" — the
most expensive available failure. There is a test for exactly this.

---

## 8. Before the next flight — read this first

1. ★ **Grep `Loki.log` for `LogJson`.** It names the failing property verbatim:
   `JsonObjectToUStruct - Unable to import JSON value into property HeroMastery`, and
   `Unable to import Array element N for property HeroMastery`. Same class of free per-item readout as
   `Invalid asset path for Mission:`. **Do this before any statistical inference.**
   FK-11's user-`Engine.ini` `[Core.Log]` mechanism makes `LogJson` visible.
2. ★ **Also grep `Invalid asset path for Mission:`** — it should stay at **0**. The catalog just grew
   by 7; if any of those 7 is wrong, this is where it says so, by name.
3. **Acceptance must be measured on a COLD client and compared by SET IDENTITY, not by count** — the
   ingester MERGES into the existing model and never replaces, so an in-place re-push can only grow
   the number.
4. **`NotifyResource` on `/progression/players/{id}` drives a refetch in ~0.8 s** with no relaunch —
   pass **exactly** the Version the document will carry (too low is ignored; too high causes an
   unbounded refetch loop).
5. **Back up `docs/capture.log` before restarting `ags`** — it is truncated on restart.
6. **Check `User-Agent` on any captured request** before calling it client traffic: the game is
   `Loki/UE5-CL-0`, ours is `curl/…` or `WindowsPowerShell/…`.

---

## 9. Honest limits

- **NOTHING here has been verified against a running client.** Sections 3–5 are static/offline; the
  outcome of serving `HeroMastery` is a **prediction**.
- The **`Hero:` vs `HeroMastery:`** prefix is unresolved; `both` mode exists to settle it.
- `GetLevelGameFeatureUnlocked(GameFeature_HunterMastery)` is **unmeasured** (§6).
- `UnclaimedRewards` is deliberately **omitted**. Shape when wanted:
  `{"3":{"ClaimID":"…","SKU":"PlayerTitle:…"}}` — a JSON **object** whose keys parse as integers, with
  SKUs from each mastery DA's own 7-entry `LevelRewards` map (keys `"0"`..`"6"`).
- The **CLAIM path is unmapped** — `WBP_HeroMastery_Mission_v2`'s 14 functions
  (`Update Claimable State`, `OnClaimReward`) were not decompiled, and
  `FClaimHeroMasteryRewardsRequest { HeroID FPrimaryAssetId; ClaimIDs TArray<FString> }` implies a
  claim endpoint whose URL was not traced.
- **How the screen is navigated to / hosted was not examined.** A perfect feed is useless if the page
  is unreachable.
- The mastery level ladder is `MasteryLevelProgression`: `XPAmounts = [25000, 50000, 100000, 200000,
  400000, 600000, 1000000, 4000000]`, `PerLevelIncreasePercentage 0.25`, 7 `LevelRewards` keyed 0..6.

## 10. Corrections to earlier records

- **`CLAUDE.md`'s "roughly 293 of the 323 we serve are Hero Mastery content" is loose.** [M] The
  mastery assets name **225** ids; we served 218 (now 330 total served, 225/225 resolving). The 75
  abstract bases are referenced by **no** mastery set.
- **`WBP_UI_MissionModal`'s allowlist is bigger than recorded.** [M] Dailies and Weeklies each carry
  **four** pools, not two: Dailies = `DailyEasy, DailyChallenge, DailyEasy_Planbee,
  DailyChallenge_Planbee`; Weeklies = `Weekly, WeeklyChallenge, Weekly_Planbee,
  WeeklyChallenge_Planbee`. The Armory category instance is `MissionModalCategory_ArmoryTest_1`
  with header `"Armory Test "`.
- **`extractor wherefile` hard-caps at 20 results** (`Program.cs:842 .Take(20)`). It produced a false
  "no `LokiDataAsset_HeroMastery` assets are packaged" during this session; there are 26 files under
  `/Game/Loki/Core/HeroMastery`. **Treat 20 hits as truncation, never as a census.**
- **`CLAUDE.md`'s tooling list names `usmapdump` verbs that do not exist** — there is no `assetmgr`,
  `threads`, `findgametid` or `xref`. Real verbs: `info names objects extract dumpimage mergedumps
  reconstructiat deobfimports strings wstrings xrefstr callxref findptr peek disasm vtslot vtdump
  nameid poke pattern`.
- **The extracted `catalog/wbp/*.json` contain NO Kismet bytecode**, so a JSON-only reading of this
  surface cannot see a single gate — every gate in §1/§6 required re-running `bpdump`.

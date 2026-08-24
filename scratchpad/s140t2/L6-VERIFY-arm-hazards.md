# S140 Tier 2 — ADVERSARIAL VERIFICATION of `scratchpad/s140t2/L6-arm-hazards.md`

**Method:** every load-bearing claim re-derived with my own code and my own reads. No lane script
re-run. Sources: `tools/sigbypass-mod/tutorial_launch.cpp` (working tree), `build.ps1`, the shipped
markers in `docs/`, and my own PE section parser + byte scanner over
`tools/sigbypass-mod/build/*.dll`. No disassembly was done by the lane or by me, so the capstone
`regs_access` write-classification defect is **N/A** here, and no `.text` census over `merged13` was
taken by either of us — the "55.48 % is a floor" caveat does not apply to this lane.

**Bottom line: the lane's three headline findings all survive. Its analysis half is sound and in
two places under-sold. Its build/digest half contains one uniqueness claim that is FALSE, one
recommendation that was already implemented in the tree before the report was written, and one
"degenerate pair" that is not degenerate.** Separately, **the tree moved under the lane** — the
report's source line numbers are stale by ~+338 lines and three of the six DLLs it digested have
since been rebuilt.

---

## 0. THE TREE MOVED UNDER THE LANE (read this first)

| artifact | mtime | vs report (22:03:22) |
|---|---|---|
| `scratchpad/s140t2/L6-arm-hazards.md` | 22:03:22 | — |
| `tools/sigbypass-mod/build.ps1` | 21:59:06 | **before** |
| `tools/sigbypass-mod/tutorial_launch.cpp` | **22:06:28** | **after** (` M` in `git status`) |
| `build/tutorial_launch_driverecompute.dll` | **22:00:43** | before/at |
| `build/tutorial_launch_gasattr.dll` | **22:06:50** | after |
| `build/tutorial_launch_gasattr_ctrl.dll` | 22:06:53 | after |
| `build/tutorial_launch_botai.dll` | 22:06:55 | after |
| `build/tutorial_launch_gasattr_sentinel.dll` | 22:06:41 | after (NEW) |
| `build/tutorial_launch_sentinel_nogas.dll` | 22:06:59 | after (NEW) |

⇒ **[M] Line-number drift.** The `ONE-SHOT LADDER … [M] one hit is all this world state delivers`
comment cited by the lane as `:15883-15885` is **now `:16221-16223`**. Other cited anchors,
re-checked against the current tree: `Marker :405` OK · `Markerf :406` OK · `FaultStr :1004` /
`static char b[160] :1005` OK · `#ifndef KBSPSARMS :14178` OK · `LooksLikePtr` **:430** (lane said
:428) · `OnPI` **:1233**, early-out `:1234`, increment **:1237** (lane said :1238) · `CreateThread`
**:18059 / :17227-8 / :17492** (lane said :17715 / :16890-1 / :17155). **A successor following the
report's numbers lands inside ARM H.**

---

## 1. CONFIRMED — re-derived independently

| # | claim | my verification |
|---|---|---|
| C1 | §1 `BsLadderStep` runs on the game thread inside one `OnPI`; a `Sleep()` there stops frames | **[M]** `OnPI:1233` — `if(g_done||g_inHook) return;` then `if(GetCurrentThreadId()!=g_gameTid) return;` then `InterlockedIncrement(&g_hitsGT); g_inHook=1;` then `:1274 if(kRunMode==RM_BOTSPAWN){ DoBotSpawn(); … }`. Confirmed. |
| C2 | §1a census times | Verbatim in the files: s140f1 A0 **4046 ms** (line 17) / A1 **3625 ms** (line 30); s139f4 **4391** (17) / **3844** (30). |
| C3 | §1a the post-call `Sleep` is vacuous but harmless — the census still saw the spawns | **[M]** `[BS] done (step=4 … dCtl=3 dHero=3 …)` at **line 175 of BOTH** `s140f1-a1-1-gft.txt` and `s139f4-a1-1-gft.txt`, verbatim. |
| C4 | §2(a) `hitsGT` is structurally capped at 1 for a one-shot ladder | **[M]** increment sits after both early-outs; `g_inHook=1` blocks re-entry; `g_done=1` blocks everything after. |
| C5 | §2(b) `[BS] ---- A0` precedes `[FS] arm:` in 3/3 markers ⇒ the first hit landed during `FsScan` | **[M]** line 13 before line 14 in all three files. |
| C6 | §2(c) the s128 counter-example | **ALL verified verbatim.** `docs/fk24-s128-poolspawn-RESULT.txt:147` `[FS] cfg KFUNCSWAP=1 max=0 name='' profileMs=4000 watchMs=8000 reportMs=15000 rearmMs=60000` — **character-identical** to line 12 of all three bot markers. `:157 swapped=17563` identical. `:181 hot: 14 distinct`. `:183/184/185` = the three quoted `hits=41` rows. `:198 hitsGT=588 allThreadCalls=588 after 8016 ms (~73 …/s)`. `:200 t=+15s … called=587`. |
| C7 | §2(c) `RM_POOLSPAWN`'s census ran off the game thread | **[M] structurally**, and stronger than the lane argued: `[DP] P0-BEFORE` occupies lines 10–146 and `[FS] cfg` is line 147. `FsArm` prints `cfg`; before it **nothing is swapped**, so no game-thread hit can exist. The census cannot have been a game-thread hit. |
| C8 | §2 corroborator `t=+15s hitsGT=1 called=0 allThreadCalls=207` | Verified, byte-identical across `s137f4:127`, `s139f4:140`, `s140f1:141`. |
| C9 | §3 `FaultStr`/`DP_FAULT` NOT thread-safe | **[M]** `:1005 static char b[160]`; `:977 static uint64_t g_fltCode,g_fltRip,g_fltRva,g_fltAddr,g_fltAccess` written by the SEH filter at `:991-996` from any faulting thread. |
| C10 | §3 zero `CreateThread` precedent from a game-thread hit | **[M]** exactly 4 sites image-wide: `:18059` (DllMain) and `:17227,:17228,:17492`, all inside `Worker` (`:17215`). |
| C11 | §5 frames pass regardless of `g_done` | **[M]** `FsThunk` ends `OnPI(...); if(g_fsPi) ((PFN_THUNK)g_fsPi)(ctx,frame,result);` — the forward is unconditional. |
| C12 | §7a bit 9 (`0x200`) was unused | **[M]** pre-ARM-H bit usage is exactly `0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x100`. |
| C13 | §7b the `if(bit) …; else Marker("SKIPPED")` idiom dead-strips the body but leaves the skip literal | **Independently reproduced with my own byte scanner** (table in §4): `gasattr` `[GASX]`=22 / ARM-G body=1 / ARM-G skip=0; `gasattr_ctrl` `[GASX]`=0 / skip=**1**; `botai` all 0. |
| C14 | §7c `driverecompute a2a952babfed256b` is not a valid gate | **CONFIRMED BY PREDICTION — the strongest result in the lane.** The lane wrote *"A rebuild today yields `4465ebc4d7168c03`"*. `driverecompute.dll` was rebuilt at **22:00:43** and my own digest reads **RAW `4465ebc4d7168c03`, byte-identical `.text` to `gasattr_ctrl`**. CLAUDE.md's recorded gate is dead. |
| C15 | §7c CLAUDE.md's `lokibot 3119d75ae2ca1859` matches neither recipe | **[M]** my read: RAW `e123816b65d68e5e`, minVS `6748058e0aa4cd56`. Neither. |

---

## 2. REFUTED

**R1 — §7d "⇒ THE ONLY SAFE PATTERN: put ARM H behind a NEW compile-time knob defaulting to 0"
is FALSE as a uniqueness claim.**
`KBSPSARMS` is itself a `#define`, so `#if (KBSPSARMS & 0x200)` **with no `#else`** removes the arm
*and* its skip literal with zero new knobs. That is exactly what the current tree does
(`:15729`, `:16069-16077`, `:17894`), and its own comment says so:
`// * NOTE THE ABSENCE OF AN #else. Every other arm prints a "SKIPPED by KBSPSARMS bitN" line …`.
**And it is now MEASURED to work — a measurement the lane could not have taken:** `gasattr.dll`,
rebuilt at 22:06:50 from the ARM-H-bearing source, reads RAW **`2fcc2536e21f18e3`** = CLAUDE.md's
recorded S139 `gasattr` digest, unchanged; `botai` reads **`5e47c13cf7f0a158`**, unchanged.
**Positive control against the S136 "cached build vs semantic no-op" ambiguity, and it PASSES:**
`gasattr_sentinel.dll` (233,984 B) and `sentinel_nogas.dll` (228,864 B) were newly produced in the
same 22:06:41–22:06:59 batch, so the compiler demonstrably ran on the new source. "No change" for
`gasattr`/`botai` is therefore a semantic no-op, not a stale artifact. The lane's *thesis* is
vindicated; its *uniqueness* claim and its `KBSPSH` knob are unnecessary.

**R2 — §7d recommends adding a `'gasattr-sentinel'` variant to `build.ps1`. It already existed.**
`build.ps1:642 'gasattr-sentinel' = @(… '-DKBSPSARMS=0x3A0')`, mtime **21:59:06**, i.e. **before**
the report's 22:03:22 — and with *different* flags from the lane's proposal (no `-DKBSPSH`). The
lane recommended creating something already present in the file it cites three lines earlier
(`:625/:629/:635`).

**R3 — §7c "`driverecompute-ctrl` and `lokibot` … a second degenerate pair" — they are NOT a
degenerate pair.** My digests: `driverecompute_ctrl` RAW **`2a91f0aa7f3d521b`** (mtime Aug 23
02:43) vs `lokibot` RAW **`e123816b65d68e5e`** (Aug 23 01:00) — **different bytes**. My byte scan
shows why: `driverecompute_ctrl` carries the ARM-F skip literal (1) and no ARM-G literal; `lokibot`
carries neither. They are two builds from **two different source generations**. They *would* become
degenerate on rebuild, but today an A/B between them is **not** "against a copy of itself" — it is
between two stale artifacts, which is **uninterpretable, and worse**. The lane's fix (re-record or
delete) is right; its characterisation of the present state is wrong.

---

## 3. DOWNGRADES (claims stated stronger than their support)

**D1 — §6b: calling `CMC+0x12B0` a "FRAME CLOCK", and the rule "`Δ == 0` ⇒ NO FRAMES PASSED; the
sample is VOID", is [I] presented as a rule, and it is a cross-function inference.**
Per S139 (CLAUDE.md), `+0x12B0` is accumulated at `0x055B840C` **inside `ULokiCMC::PerformMovement`**,
immediately after the `xorps xmm6,xmm6` HitStop kill at `0x055B83FA`. So `Δ == 0` has at least
three causes — (a) no frames, (b) HitStop fired and zeroed dt, (c) the component stopped ticking —
and only (a) is "VOID". It is **not** a frame clock. It *is* a sound *"we reached the door"* control
for this specific test (the accumulate is upstream of the Super call and therefore upstream of
`StartNewPhysics`, so it is not circular here), but the negative branch is over-claimed and the
label will mislead the moment a future arm's wall moves upstream. **A genuinely independent clock
(a `UWorld` TimeSeconds / `GFrameCounter`-class global) was not considered.** Restate as:
*`Δ>0` ⇒ `ULokiCMC::PerformMovement` ran with dt>0; `Δ==0` ⇒ **uninterpretable**, three causes.*

**D2 — §2: "The 206 extra calls ARE our own nested BP dispatches from `SpawnAIFromClass` →
`SpawnDefaultController` → constructors" is stated as fact. It is [I, strong].** It is well-forced —
`called=0` at t=+15 s means `g_called` (incremented **after** `DoBotSpawn` returns, `:1274`) never
fired, so the game thread had not yielded by t+15 s, so those 207 cannot be free game frames — but
no per-call attribution was taken.

**D3 — §3: `Marker()` "THREAD-SAFE … `FILE_APPEND_DATA`-only access makes each `WriteFile` an atomic
append" is [I], not [M]**, and it is **load-bearing for §2(b)**, whose entire ordering argument is
*"marker writes are append-ordered, so file order is temporal order."* That inference is graded
nowhere in the report. (It is almost certainly right — documented Win32 behaviour — but it should
carry its grade, because §2(b) is one of the three headline findings.)

**D4 — §7b's positive control (`KERNEL32` = 1) cannot fail for the reason that matters.** It proves
the file opened and an ASCII byte search runs; it does not prove a *shim-authored* literal would be
found if present. The lane **had** a two-sided shim-literal control in its own table and did not
label it: `ARM F: drive Update…` reads **1** in `driverecompute`/`gasattr`/`gasattr_ctrl` and **0**
in `botai`/`lokibot`. Also unstated: byte-absence is a valid string test only for LONG literals
passed as pointers to a non-inlined call (CLAUDE.md S136) — it happens to be the valid case here.

**D5 — §4's "FsDisarm (~1–3.6 s)". Measured: 3468 / 3485 / 3641 ms** in the three bot markers
(and 3531 ms in s128). The low end of the quoted range has no support in this corpus.

**D6 — §1a's table reports s137f4's A1 census as "—". It is present:** `census A1 … **3750 ms**`
at line 33 of `docs/fk24-stage-s137f4-1-gft.txt`. Not load-bearing; a datum reported missing from
the file it cites.

**D7 — three transcription slips in §2(b)'s quoted line numbers.** s140f1 `census A0` is line **17**,
not 18. s139f4's tuple `(13/14/17/25)` should be **`13/14/17/22`** (`hot:` is line 22). s137f4's
`(13/14/20/25)` is correct. Conclusions unaffected.

---

## 4. MY OWN RAW MEASUREMENTS (so the next reader need not re-run anything)

`.text` digests — my own PE parser, both recorded recipes
(RAW = `sha256(.text[PointerToRawData, +SizeOfRawData))[:16]`; minVS uses `min(VirtualSize,SizeOfRawData)`):

```
variant                    RAW                minVS                rawsize  virtsize  mtime
botai                      5e47c13cf7f0a158   f34ab2bf31cb0b34      111104    110688  08-23 22:06
driverecompute             4465ebc4d7168c03   57629b389e6c4121      134656    134160  08-23 22:00
driverecompute_ctrl        2a91f0aa7f3d521b   053181ff036bcae3      131584    131120  08-23 02:43
gasattr                    2fcc2536e21f18e3   6ee3ee1d23c29550      137728    137376  08-23 22:06
gasattr_ctrl               4465ebc4d7168c03   57629b389e6c4121      134656    134160  08-23 22:06
lokibot                    e123816b65d68e5e   6748058e0aa4cd56      131072    130992  08-23 01:00
botspawn                   b2203efd62161182   213e0010ed8fd003      115200    114832  08-23 01:00
spawnbot_premade           6cb296bbf3c8c696   a100dc6283ea859a      138240    137952  08-23 01:00
botps                      445fb5ce5b902bc3   c9740aa49a14fae0      126464    126400  08-21 14:17
botteam                    160f067d697b545b   0c16652dc0338d33      115200    114704  08-21 02:36
```
- **`driverecompute` == `gasattr_ctrl` == `4465ebc4d7168c03` — a LIVE degenerate pair. Do not A/B them.**
- CLAUDE.md records `botteam 0c16652dc0338d33` — that is this file's **minVS**, while `botps
  445fb5ce5b902bc3` is its **RAW**. The two-recipe problem is reproduced here independently.

Byte-occurrence counts (my own scanner; unit = **occurrences of the token in the file**, not call
sites and not functions):

```
dll                       KERNEL32   [GASX]   [SNP]  ARMG_body ARMG_skip ARMF_body ARMF_skip  ARM H
botai                            1        0       0          0         0         0         0      0
driverecompute                   1        0       0          0         1         1         0      0   <- REBUILT 22:00
driverecompute_ctrl              1        0       0          0         0         0         1      0   <- stale 02:43
gasattr                          1       22       0          1         0         1         0      0
gasattr_ctrl                     1        0       0          0         1         1         0      0
lokibot                          1        0       0          0         0         0         0      0   <- stale 01:00
botspawn                         1        0       0          0         0         0         0      0
```

---

## 5. NEW FINDINGS the lane did not report

**N1 — The lane's own best evidence is one it never used: `allThreadCalls` is an UNGATED counter,
and `hitsGT` is not.** `g_fsCalls` is `InterlockedIncrement`ed on the **first line of `FsThunk`
(`:1708`)**, before every guard — thread id, `g_inHook`, `g_done`, `LooksLikePtr`. Its own
declaration comment (`:1699`) reads *"FsThunk entries, ALL threads (distinguishes 'swap took' from
'GT quiet')"*. At the **t+8 s watch line** it reads:

```
bot sittings (x3):  [FS] *** ARMED AND LIVE: hitsGT=1   allThreadCalls=1   after 8000 ms (~0  …/s)
s128 poolspawn:     [FS] *** ARMED AND LIVE: hitsGT=588 allThreadCalls=588 after 8016 ms (~73 …/s)
```
Same `[FS] cfg` flags, same `swapped=17563`. Because the one-shot ladder **cannot** cap
`allThreadCalls` (unlike `hitsGT`), this is the clean, non-circular refutation of *"one hit is all
this world state delivers"* — a 588x difference in an ungated counter, printed on the very line the
source comment cites. **§2(a) is correct but is a fact about the instrument, not evidence about the
world; N1 is the evidence.** The successor should quote N1, not §2(a).

**N2 — ARM H is ALREADY IMPLEMENTED in the working tree, and it adopted the lane's §9 design — so
most of the report is now a post-hoc justification of shipped code, not a design review.**
`:17894-17896` calls `ShSampleLoop()` on the **Worker**, between `FsDisarm()` and
`BsFinalReport()`, with a comment restating the lane's §4 argument almost verbatim (*"this is the
WORKER thread and the game thread has just been released, so Sleep() lets real frames pass … the
same loop inside BsLadderStep would … block the very frames the test needs — a guaranteed false
'StartNewPhysics did not run'. (RM_DROPPLANE B4 precedent.)"*). `ShHex24` prints the raw 24 bytes
first; `+0x12B0` is read per dump; and the payload is **poisoned with a distinct constant**
(`kShBotPoison = {-9876.5,-8765.25,-7654.125}` / `kShPlrPoison`) before the sentinel is written —
which is **stronger than the lane's §8.1 "record the before-value"**, because it discriminates
*stale-non-zero* from *never-written* by construction. §9 items 1–3 are DONE; item 4 is HALF done
(`driverecompute` rebuilt, `driverecompute_ctrl` and `lokibot` still stale); items 5–6 are NOT done
— the comment the lane calls *"an instrument-artifact generator"* is verbatim unchanged at
`:16221-16223`.

**N3 — The report's headline recommendation #1 ("Do not spawn a thread") is moot** — the tree never
spawned one. Its §3 thread-safety table and §8.5 (`FaultStr` off-thread) remain live constraints on
`ShSampleLoop`, which **does** run on the Worker: any fault reporting inside it must not go through
`FaultStr()`.

---

## 6. Circularity audit (asked for explicitly)

- **§2(c) s128 was selected because it shows a non-empty hot list** — selection-by-outcome. As an
  **existence proof** ("this staging pipeline can deliver 73 dispatches/s with identical `[FS]`
  flags") that is legitimate and not circular. As support for *"the bot world will deliver ~10
  ticks/s"* it is not sufficient, and the lane **correctly** demotes that to [I, strong] in §10 and
  names the confound (different injection sequence: `dropplane_b1only` + `droppod` staged first).
  **Accepted.**
- **§7b uses `gasattr_ctrl` both to establish the mechanism and, via the same instrument, to convict
  `driverecompute`.** Not circular: different files, and the conviction is independently
  corroborated by mtime **and** by the rebuild digest, which the lane predicted in advance.
- **§6b's `+0x12B0`** is the one place a control risks being non-independent of the system under
  test. For *this* test it is upstream and therefore valid; see D1 for when it stops being valid.
- No claim graded [M] rests on a fold-multiplicity-ambiguous address (no addresses were used) or on
  a census over dark pages (no `.text` census was taken).

---

## 7. What I could NOT check
- Nothing was run against a live process, and nothing was rebuilt. The R1 measurement rests on
  artifacts someone else built at 22:06 from source I read at 22:0x; I verified the source contains
  the `#if (KBSPSARMS & 0x200)` guard and that the batch produced two *new* DLLs, but I did not
  invoke the compiler myself.
- Whether `ShSampleLoop`'s sampling cadence, verdict logic or `+0x12B0` handling is correct is
  **out of scope** — I audited the lane report, not the shipped arm. **D1 applies to the shipped arm
  directly and should be checked by whoever owns ARM H.**
- `build/` holds **176** `.dll` (**101** named `tutorial_launch_*`); the lane's "174" was correct at
  its read time and is now +2 (`gasattr_sentinel`, `sentinel_nogas`).

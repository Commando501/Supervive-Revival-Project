#!/usr/bin/env python3
"""S133: record phase 2 in the settled doc, CLAUDE.md, and method-rules."""
import io

# ---------------- 1. docs/s133-joinqueue-find-match.md ----------------
P = 'docs/s133-joinqueue-find-match.md'
s = io.open(P, encoding='utf-8').read()
old = """## 7. Still open"""
new = """## 7. Phase 2 — `0x5879000` LIT, and two more unserved endpoints

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

## 8. Still open"""
assert old in s
s = s.replace(old, new, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('settled doc: phase 2 recorded')

# ---------------- 2. CLAUDE.md ----------------
P = 'CLAUDE.md'
s = io.open(P, encoding='utf-8').read()


def rep(a, b):
    global s
    assert a in s, 'NOT FOUND: ' + a[:70]
    s = s.replace(a, b)


rep("""- ⚠ **No CUSTOM GAME entry point exists on this client**""",
"""- ★★★★ **PHASE 2 ALSO LANDED — `0x5879000` DARK → LIT, and it found TWO MORE UNSERVED ENDPOINTS:**
  `POST /party/parties/{p}/emote/` (×5, **`TrySendEmote`**) and `POST /party/parties/{p}/setIsOpen/True`
  (×1, **`TrySetIsOpen`**), both still on the `/` catch-all. Note the value-in-path URL shape.
  ⇒ **THREE endpoints in one afternoon of driving the UI**, on a surface a passive sweep had declared
  mapped. ⚠ That phase's baseline was CONFOUNDED (an `ags` restart + `AGS_PROBE_FRIEND` sat between
  baseline and result); the page verdict survives only because **the wire attributes it by name** and
  7 plausible-alternative control pages stayed DARK. **13 of UPartyManager's 20 dark impls are now
  readable** (`merged7` 16,707 → `merged8` **16,714**, 55.20 %).
  ⚠ `TrySetFillPreference` / `TrySendInvite` / `TrySendRequest` / `TrySetIsReady` produced **no
  traffic** and are NOT shown to have run — no reachable affordance in a solo party.
- ⚠ **No CUSTOM GAME entry point exists on this client**""")

rep("""  **`dumps/merged7.dump.exe` (16,707 decrypted pages, 55.17 % — the union of all 32 states)** or""",
    """  **`dumps/merged8.dump.exe` (16,714 decrypted pages, 55.20 % — the union of all 33 states)** or""")
rep("""  16,683 → `merged5` 16,689 → `merged6` 16,694 → **`merged7` 16,707** (the S133 queue sweep).""",
    """  16,683 → `merged5` 16,689 → `merged6` 16,694 → `merged7` 16,707 → **`merged8` 16,714** (S133).""")
rep("""  ★★★★★ **THE CANONICAL COLD IMAGE IS `dumps/merged7.dump.exe` — `.text` **16,707 / 30,281**
  decrypted pages (**55.17 %**), measured 2026-08-20, and it is EXACTLY the union of all 32 state
  images on disk""",
"""  ★★★★★ **THE CANONICAL COLD IMAGE IS `dumps/merged8.dump.exe` — `.text` **16,714 / 30,281**
  decrypted pages (**55.20 %**), measured 2026-08-20, and it is EXACTLY the union of all 33 state
  images on disk""")
io.open(P, 'w', encoding='utf-8').write(s)
print('CLAUDE.md: phase 2 + merged8 recorded')

# ---------------- 3. method-rules ----------------
P = 'docs/method-rules.md'
s = io.open(P, encoding='utf-8').read()
anchor = '| **★★★★ S133-f** |'
i = s.index(anchor)
j = s.index('\n', i)
row = """| **★★★ S133-g** | a **throwaway inline page-counting script**, written in a `python -c` one-liner beside the vetted tool that already did the same job | it computed `NP = TEXT_VSZ//4096 + 1`. `.text` VSize is `0x7649000`, an **EXACT** multiple of 4096, so the unconditional `+1` reads **one page past `.text`, into `.rdata`** — which is non-zero, so every count came back **inflated by exactly 1**. The vetted tools (`queue_verdict.py`, `dump_coverage_ledger.py`) use `V//P + (1 if V%P else 0)` and were right throughout | it reported `merged7 = 16,708` and `merged8 = 16,715`; the true figures are **16,707** and **16,714**. An off-by-one that is invisible in isolation: the number is plausible, monotone, and moves in the right direction | **caught by cross-checking two of my own instruments** — the inline script disagreed with the ledger by exactly 1 on a value the ledger had already printed an hour earlier. ★★ **Rule: never re-implement a measurement inline "just to check" — call the vetted tool. A one-liner that agrees with itself is not a control, and a quantity that is off by one page will pass every plausibility test you can apply to it.** ★ The general form of the bug is worth naming too: **an unconditional `+1` for a partial trailing page is wrong whenever the size divides evenly** — guard it, or use `-(-V//P)`. |
"""
s = s[:j + 1] + row + s[j + 1:]
io.open(P, 'w', encoding='utf-8').write(s)
print('method-rules: S133-g added')

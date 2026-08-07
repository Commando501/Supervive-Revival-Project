# S111 — the `.text` patch is GONE from the shipping shim. Roster still renders.

**2026-08-06.** The `jz`-NOP that the bisect identified as the protector trigger has been **removed
from the default build**, and the roster was confirmed to still populate without it.

---

## 0. What changed

`KNOJZ` now **defaults to 1** in `catalog_store_fix.cpp`. The plain build performs **no `.text` write
of any kind**. Verified structurally: the `jz NOP'd` string literal is **absent** from the shipping
binary and present only in the `jzpatch` rollback build — the code is compiled out, not merely
skipped.

| build | `.text` sha256 | `.text` patch |
|---|---|---|
| **`catalog_store_fix.dll` (shipping)** | `2b0a5406fc20f0b5` | **none** |
| `catalog_store_fix_jzpatch.dll` (rollback) | `21e62f50f6d40c8d` | the old `jz`-NOP |

## 1. Why this is safe — the functional check

The `jz`-NOP existed to make `IsCatalogDataReady` ignore the never-set 5th flag. But the shim has
**always** also set that same condition as **data**, in its worker loop:

```cpp
// belt-and-suspenders data poke of [+0x354]=1 on the live instance
if(g_catMgr){ ... ((uint8_t*)(g_catMgr+kReadyOff))[4]=1; ... }
```

**VERIFIED LIVE (screenshot).** With `jz=0`, the **ALL HUNTERS grid renders the full roster** — the
whole hero tile wall, hero detail panel (EVA, abilities, MASTERY), hover tooltips, all of it. Marker
for that run:

```
[0] catalog_store_fix worker started … scan=SAFECOPY-S111 veh=1 slot=1 jz=0
[cm] live CatalogManager @0x25FFE1DCF00 (map Num=1339) — catalog loaded
[hb] catMgr=0x25FFE1DCF00 jz=0/0 unhook=1 purchIters=191 lastPurch=1339
```

and that same build cleared a **320 s hold with no death** (arm G).

### ⚠ Reconciling with S47, which said the poke does not work

`docs/session-47-tile-widget-FOUND.txt:385` records: *"In-place poke of `[+0x354]=1` on the
already-Constructed grid does NOT repopulate."* That is **still true** and is not contradicted here.
The distinction is timing:

- S47's failure case: grid **already Constructed** and waiting on the never-firing delegate → poking
  afterwards cannot wake it. The `jz` patch worked there because it caused the game's readiness check
  to **broadcast `OnCatalogDataReady`**.
- What happens now: the shim pokes `[+0x354]` **continuously from catalog-load onward**, which is
  long before the user navigates to HUNTERS. The grid Constructs *after* the flag is already set,
  sees `IsCatalogDataReady == true`, and calls `LoadCharacters` directly — S47's own option (B),
  which it described as requiring the poke to be "set at grid-Construct time".

⚠ **This is the fragile part, and it is the thing to watch.** The fix depends on the poke landing
**before first navigation to HUNTERS**. If a future change delays the scan (slower scan, later
injection, a user who opens HUNTERS within the first second or two), the roster could regress to
empty. Keep the poke early and continuous. If it ever regresses: rebuild with `-Variant jzpatch`.

## 2. Why it matters

The bisect measured the `jz`-NOP as the trigger for the protector kill: **patch standing 11/12 vs no
patch 0/5, p = 0.00097** (`docs/s111-bisect-jz-is-the-trigger.md`). The whole ladder is explained by
how long a `.text` modification stands:

| condition | patch standing | protector deaths |
|---|---|---:|
| `-NoHook` | never | 0/11 |
| inert mapped DLL | never | 0/11 |
| production, patch restored after catalog load | ~5–45 s | **25/90 (28 %)** |
| `KNOSCAN` controls, patch never restored | whole run | ~90 % |

Removing it entirely should take the shipping shim to the **0 %** row. That is worth roughly **one in
three launches** across every future experiment — including tutorial sittings, whose budgeted yield
is only ~2 armed windows per 4 launches.

## 3. ⚠ What is NOT yet established

- **The production death rate has not been re-measured with this build.** Arm G is **1 run** at 320 s
  plus the visual check. The claim "this takes production to ~0 %" is **INFERRED** from the bisect,
  not measured end-to-end. The obvious next step is a ~10–30 launch run of the *default set* (all
  five shims, this build as primary) counting protector deaths against the 25/90 baseline.
- **The other four shims still write.** `mainmenu_refresh_pi8`, `loadout_fix` and `missions_fix` all
  install `ProcessInternal` prologue patches — also `.text` writes, also transient. They were never
  bisected individually. If protector deaths persist at ~28 % with this build, they are the next
  suspects, and the same `-D` treatment applies.
- The store/cosmetics/passes surfaces were **not** re-checked visually; only HUNTERS was.

## 4. Variant registry, cleaned

`KNOJZ` defaulting to 1 made `noscan` and `noscan-nojz` the same binary, so every `KNOSCAN` control
arm now pins `-DKNOJZ=0` explicitly — arms C/E/E1/E2 were flown **with** the patch and their names
must keep meaning that. All six builds re-diffed: **6 distinct `.text` hashes, no duplicates.** The
`nojz` variant was retired (the plain build *is* the no-patch build; keeping it would be an
identical-DLL-under-another-name footgun).

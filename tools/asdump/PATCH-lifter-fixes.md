# asdump.py — three lifter/structurer defects found 2026-07-26

Found while decompiling `UAV/ Items/ Armory/ Domination/ MostWanted/ Minions/ Vault/
Interaction/ DayNightController/ UI/ Content/` (see `docs/angelscript-systems-rest.md` §13).

## Status against `asdump.py` — UPDATED 2026-07-26, final synthesis pass

| # | defect | state |
|---|---|---|
| 1a | `REFCPY` lhs/rhs swapped | **fixed** in `asdump.py` (core-gameplay pass) |
| 1b | `COPY` lhs/rhs swapped | **MERGED into `asdump.py`** — see below |
| 2 | script structs not treated as returning on stack | **MERGED into `asdump.py`** — see below |
| 3 | structurer hides a shared join block in the `else` arm | **diagnosed, NOT fixed** — the 46-function audit list below stands |

**1b and 2 are now folded into the canonical `tools/asdump/asdump.py`** and the whole
`out/` corpus was regenerated from it. Verified after the merge:

```
byte accounting  1,184,817 / 1,184,817   UNACCOUNTED 0   (unchanged)
decode           1,463 / 1,463  100.00%                  (unchanged)
symbols          all classes 100%                        (unchanged)
dword-depth audit  1,449/1,463 (99.04%) -> 1,458/1,463 (99.66%)
`nullptr = <expr>;` inversions in out/modules   32 -> 0
ULokiGameStateUAVComponent::ExecuteUAV   now reads Config/TeamIndex/SourceLocation correctly
```

`tools/asdump/asdump_patched.py` is retained only as the pre-merge reference copy; it is
now behaviourally identical to `asdump.py`. **Use `asdump.py`.**

```
python tools/asdump/asdump_patched.py --out <dir> --usmap tools/usmapdump/mappings.usmap
```

Validation of the rebased fork: `PrecompiledScript.Cache` 1,184,817/1,184,817 B
(UNACCOUNTED 0), both `Binds.Cache` files 100 %, 1,463/1,463 streams decoded,
**depth audit 1458/1463 = 99.66 %** (was 99.04 %).

---

## 1. `COPY` / `REFCPY` emit `lhs` and `rhs` swapped — 235 statements in 42 of 78 modules

*(`REFCPY` is fixed upstream; `COPY` is not. The measurement below was taken before either
fix, so it covers both opcodes.)*

AngelScript's VM takes the **destination from the top of the stack** (the pointer pushed
*last*):

```c
case asBC_REFCPY: { void **d = (void**)*(asPWORD*)l_sp; l_sp += AS_PTR_SIZE;
                    void  *s = (void*) *(asPWORD*)l_sp;  ...  *d = s; }
case asBC_COPY:   { void  *d = (void*) *(asPWORD*)l_sp; l_sp += AS_PTR_SIZE;
                    void  *s = (void*) *(asPWORD*)l_sp;  memcpy(d, s, n); }
```

Ground truth from the cache itself — `FLokiUsableData`'s default constructor:

```
0000  PshNull
0004  PshVPtr   this
0008  ADDSi     0 134230883      ; .Actor
0010  REFCPY                      ==> this.Actor = nullptr
```

which the unpatched tool renders as `nullptr = this.Actor;`. The literal string
`"nullptr = "` occurs **32 times** in `out/modules/`; total inverted statements measured by
diffing patched vs unpatched output: **235, across 42 of the 78 modules**.

```python
# --- op_REFCPY ---------------------------------------------------------------
-    def op_REFCPY(self, i, a):
-        rhs = self.pop()
-        lhs = self.pop()
-        self.emit("%s = %s;" % (lhs, rhs))
+    def op_REFCPY(self, i, a):
+        # asBC_REFCPY: `void **d = *(l_sp); l_sp += PTR; void *s = *(l_sp);`
+        # -- the DESTINATION is the pointer pushed LAST (top of stack).
+        lhs = self.pop()
+        rhs = self.pop()
+        self.emit("%s = %s;" % (lhs, rhs))

# --- op_COPY -----------------------------------------------------------------
-    def op_COPY(self, i, a):
-        rhs = self.pop()
-        lhs = self.pop()
-        self.emit("%s = %s;" % (lhs, rhs))
-        self.push(lhs)
+    def op_COPY(self, i, a):
+        # asBC_COPY: `void *d = *(l_sp); l_sp += PTR; void *s = *(l_sp);`
+        # -- destination is the LAST pushed, and it is what stays on the stack.
+        lhs = self.pop()
+        rhs = self.pop()
+        self.emit("%s = %s;" % (lhs, rhs))
+        self.push(lhs)
```

Note `op_RefCpyV` (the `RefCpyV vN` form) was already correct — it takes its destination
from the instruction operand, not the stack.

---

## 2. Script-declared **structs** are not treated as returning on the stack

`returns_on_stack()` excludes every script-declared type:

```python
if n in cache.script_enums or n in cache.script_classes:
    return False
```

But **34 of the 110 script-declared types are AngelScript value types** (`asOBJ_VALUE`) —
every `F…` struct and every script delegate. A value-type return consumes the hidden
return pointer slot, so every declared parameter sits one slot (2 dwords) further down;
without this, `param_offsets()` mis-attributes every parameter name in those functions.

The cache states it directly. `FAngelscriptPrecompiledClass.BehaviorRefs` has 7 slots
(`factory, listFactory, copyfactory, construct, copyconstruct, destruct, copy`):

```
value type  <=>  BehaviorRefs[3] (construct) != 0  AND  BehaviorRefs[0] (factory) == 0
```

Measured: `FActiveUAV`, `FLokiUAVConfig`, `FUAVCharacterGrouping`, `FLokiUsableData`,
`FLokiPodDetachData`, `FMinionWave`, `FLaserTraceResult`, the 12 script delegates, … = 34
types; every `U…`/`A…` script class registers a factory and does not qualify.

```python
# --- Cache._index() ----------------------------------------------------------
     self.script_classes = set(c.name for _, c in self.classes)
+    # A script-declared type is a VALUE type (asOBJ_VALUE) when it registers a
+    # `construct` behaviour and NO `factory`; the 7 BehaviorRefs slots are
+    #   0 factory 1 listFactory 2 copyfactory 3 construct
+    #   4 copyconstruct 5 destruct 6 copy
+    # 34 of the 110 script types classify this way (every F-struct and every
+    # script delegate); they DO return on the stack.
+    self.script_value_types = set(
+        c.name for _, c in self.classes
+        if len(c.behavior_refs) == 7 and c.behavior_refs[3]
+        and not c.behavior_refs[0])

# --- returns_on_stack() ------------------------------------------------------
-    if n in cache.script_enums or n in cache.script_classes:
-        return False
+    if n in cache.script_enums:
+        return False
+    if n in getattr(cache, "script_value_types", ()):
+        return True
+    if n in cache.script_classes:
+        return False
```

**Independent corroboration.** The tool's own dword-depth audit shares no code with the
lifter, and this fix alone moves it from **1449/1463 (99.04 %) to 1458/1463 (99.66 %)**.
Residual unbalanced after the fix: `FLaserTraceResult`, `FAimingLaserSettings`,
`UpdateGroundLaserAtLocation`, `FLokiUsableData` ×2.

Worked example, `ULokiGameStateUAVComponent::ExecuteUAV(const FLokiUAVConfig& Config,
const FVector& SourceLocation, const int TeamIndex = -1)` returning `FActiveUAV`:

| | before | after |
|---|---|---|
| | `v68.Config = SourceLocation;` | `v68.Config = Config;` |
| | `v68.TeamIndex = arg_m8;` | `v68.TeamIndex = TeamIndex;` |
| | `v68.SourceLocation = TeamIndex;` | `v68.SourceLocation = SourceLocation;` |

It also stops `CancelActiveUsable(const ELokiUsableInteractionEndResult ResultType)` from
binding `ResultType` to the hidden return temp, which in turn lets the enum-naming pass
resolve `ELokiUsableInteractionEndResult::Interrupted / RepressRestart / UsableRemoved /
InstigatorLivingStateChange` at all four of its call sites.

---

## 3. NOT FIXED — the structurer can put a shared join block inside the `else` arm

When two conditional jumps target the **same** label (two guard clauses falling into common
code), `structure()` sometimes emits an `if / else` whose `else` arm holds the *join* block,
so code that runs on both paths appears to run on only one. **This is the dangerous one: the
output looks perfectly reasonable and states the opposite of the truth.**

Confirmed instance — `ALokiGem::OnComponentBeginOverlap`:

```
010C  CMPIi  v13 -2
0114  JZ            -> L0154        ; TeamIndex == -2   -> join
013C  CMPi   v13 v14
0144  JNZ           -> L0154        ; TeamIndex != mine -> join
014C  JMP           -> L029C        ; else: return
L0154: <grant "Gems", fire cue, DestroyActor>
```

Real rule: *"the owning team may not collect; everyone else may."*
Rendered as: `if (v13 != -2) { if (v13 == v14) return; } else { <grant …> }` — i.e. "only
unowned gems ever pay out."

**Audit set.** Scanning for the risk shape — *a label reached by ≥2 conditional jumps that
is not the function's last instruction* — flags **46 of 1,463 functions (3.1 %)**. The
shape is necessary but not sufficient, so each needs a look. The 17 in the modules covered
by `docs/angelscript-systems-rest.md`:

```
Armory/LokiArmoryGlobals            GetArmoryUniqueEffectTextForItemClass
Armory/…ArmoryComponent             OnAssetLoadComplete, CanBuyItem
Domination/LokiDominationUtilities  GetDominationSpawnForPlayer
Interaction/…PlayerComponent        Tick_Implementation, OnSpawnedCharacterChangedCalled,
                                    UpdateSelectedUsable, ProcessActiveInteraction
Items/LokiGem                       OnComponentBeginOverlap        <-- CONFIRMED WRONG
Items/LokiTeamElimBoxComponent      DropWipedTeamInventories, FindLocationForBox
Minions/LokiNodePathingComponent    MoveToActor, FindClosestPathingActor
MostWanted/…MostWantedComponent     HandleMostWantedEvent
UAV/LokiGameStateUAVComponent       PulseUAV, PulseIndividual, IsValidUAVTarget
                                        (last two CONFIRMED WRONG — the `Radius` guard
                                         body lands in the `else`)
```

Suggested fix: when both arms of a conditional reach a common successor, emit the successor
**after** the `if`, not inside either arm.

Detection script (stdlib only), run against the emitted `.txt` files:

```python
import os, re, collections
RE_F = re.compile(r"/\* ---- (\S+): (\d+) dwords")
RE_J = re.compile(r"^\s*([0-9A-F]{4})\s+(J\w+)\s+(-?\d+)\s+->\s+L([0-9A-F]{4})")
RE_A = re.compile(r"^\s*([0-9A-F]{4})\s+(\S+)")
for root, _, fs in os.walk("out/modules"):
    for f in (x for x in fs if x.endswith(".txt")):
        fn = last = None; cond = collections.Counter()
        def flush():
            if fn and [t for t, c in cond.items() if c >= 2 and t != last]:
                print(os.path.join(root, f), fn)
        for line in open(os.path.join(root, f), encoding="utf-8", errors="replace"):
            m = RE_F.search(line)
            if m: flush(); fn = m.group(1); cond = collections.Counter(); last = None; continue
            if not fn: continue
            a = RE_A.match(line.rstrip("\n"))
            if a: last = a.group(1)
            j = RE_J.match(line.rstrip("\n"))
            if j and j.group(2) != "JMP": cond[j.group(4)] += 1
        flush()
```

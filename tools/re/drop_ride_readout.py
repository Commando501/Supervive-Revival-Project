# drop_ride_readout.py -- S150-drop. Read-only RPM. The staged-flight instrument for RM_MOUNT.
#
# WHAT IT MEASURES (the pre-registered receipts of docs/drop-sequence-status-s150.md §6.5):
#   R1  PlayersAttached.Num on the pod's rideable      (the append landed)
#   R2  pod ComponentVelocity vs (CurrPodDestination - pod loc)   (descent/flight direction)
#   R3  hero X TRACKS pod X during flight   <-- THE DECISIVE ONE
#         mount-ride   (treatment) MUST show the hero following the pod.
#         mount-noride (control)   MUST show a FROZEN hero while the pod flies  (confirms the
#                                  offline verdict that a poke rider does not co-move).
#   PB  pod bHasStartedGameplay (0->1) + DropPodState   (StartPodGameplay ran; descent is
#         timer-deferred ~6.5s, so velocity ~0 immediately after is EXPECTED, not failure).
#
# WHY START IT BEFORE THE INJECTION. motion_watch.py's lesson: a mount+ride window can be seconds
# long and the client can die (FK-32) right after. This polls until a flying pod exists, then
# tight-samples, and prints each sample as it goes so nothing is lost if the process dies.
#
#   usage: drop_ride_readout.py <PID> <BASE-hex> [--pod 0xADDR] [--hero 0xADDR] [--secs N]
#
#   Auto-discovers the pod (BP_DropPod* actor) and lists BP_HERO_* candidates. The RM_MOUNT arm's
#   marker prints the exact pod/hero addresses it used ([RD] resolve: pod=... / [RD] hero ...);
#   pass them with --pod/--hero for an unambiguous read. All offsets [M] and match
#   scratchpad/s131/tools/pod_live_read.py and tools/re/motion_watch.py.
import ctypes
import math
import struct
import sys
import time
from ctypes import wintypes

# ---- args ------------------------------------------------------------------------------------------
if len(sys.argv) < 3:
    print("usage: drop_ride_readout.py <PID> <BASE-hex> [--pod 0xADDR] [--hero 0xADDR] [--secs N]")
    sys.exit(2)
PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)
POD_ARG = HERO_ARG = 0
MULTI_HERO = False
SECS = 60.0
_a = sys.argv[3:]
i = 0
while i < len(_a):
    if _a[i] == "--pod":
        POD_ARG = int(_a[i + 1], 16); i += 2
    elif _a[i] == "--hero":
        HERO_ARG = int(_a[i + 1], 16); i += 2
    elif _a[i] == "--secs":
        SECS = float(_a[i + 1]); i += 2
    else:
        i += 1

# ---- constants (same image layout as motion_watch.py / pod_live_read.py) ----------------------------
NAMEPOOL = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18
CLASS_OFF, NAME_OFF, SUPER_OFF = 0x18, 0x20, 0x48

POD_DEST, POD_HSG, POD_STATE, POD_RIDE, POD_ROOT = 0x478, 0x4B8, 0x540, 0x6C8, 0x1B0
RIDE_PIN, RIDE_PA = 0x120, 0x130          # PlayersInside / PlayersAttached (Data;Num@+8;Max@+0xC)
SC_LOC, SC_VEL = 0x158, 0x1A0
STATE_NAME = {0: "None", 1: "Intro", 2: "Attached", 3: "Descending", 4: "Outro", 5: "Destroying"}

# ---- RPM -------------------------------------------------------------------------------------------
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x0010 | 0x0400, False, PID)     # VM_READ | QUERY_INFORMATION
if not h:
    print("OpenProcess(%d) failed -- err %d. Elevated? Process alive? RUN IS VOID."
          % (PID, ctypes.get_last_error()))
    sys.exit(1)


def rpm(a, n):
    b = (ctypes.c_ubyte * n)()
    r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)


def u32(b, o=0):
    return int.from_bytes(b[o:o + 4], "little")


def u64(b, o=0):
    return int.from_bytes(b[o:o + 8], "little")


def lp(v):
    return 0x10000 < v < 0x7FFFFFFFFFFF


def p(a):
    b = rpm(a, 8)
    return u64(b) if b else 0


def v3(a):
    b = rpm(a, 24)
    return struct.unpack("<ddd", b) if b else None


def b1(a):
    b = rpm(a, 1)
    return b[0] if b else None


def alive():
    return rpm(OBJOBJECTS, 0x18) is not None


_nc = {}


def fname(idx):
    if idx in _nc:
        return _nc[idx]
    blk, off = idx >> 16, (idx & 0xFFFF) << 1
    bp = rpm(NAMEPOOL + blk * 8, 8)
    r = "?"
    if bp:
        bp = int.from_bytes(bp, "little")
        if lp(bp):
            hd = rpm(bp + off, 2)
            if hd:
                hd = int.from_bytes(hd, "little")
                ln, wide = hd >> 6, hd & 1
                if 0 < ln < 250:
                    s = rpm(bp + off + 2, ln * (2 if wide else 1))
                    if s:
                        r = ("".join(chr(s[k * 2] | (s[k * 2 + 1] << 8)) for k in range(ln))
                             if wide else s.decode("latin1", "replace"))
    _nc[idx] = r
    return r


def oname(o):
    b = rpm(o + NAME_OFF, 4)
    return fname(u32(b)) if b else "?"


def chain_has(cls, needle):
    cur, g = cls, 0
    while lp(cur) and g < 24:
        if needle in oname(cur):
            return True
        cur = p(cur + SUPER_OFF)
        g += 1
    return False


def chain_ends_at(cls, exact):
    """S150-drop mount-flight 2 fix: exact leaf-name walk of the SuperStruct chain.
    Mirrors the shim's DPV_ACTOR test (strcmp(n,"Actor")==0). Substring `chain_has`
    is not enough — an AnimInstance/UUserWidget with 'DropPod' in the class name
    passes substring but has no Actor ancestor, and the reader would then read
    stale bytes off the wrong object. Use this to gate discovery."""
    cur, g = cls, 0
    while lp(cur) and g < 24:
        if oname(cur) == exact:
            return True
        cur = p(cur + SUPER_OFF)
        g += 1
    return False


# S150-drop offsets [M] from the shim's RdResolve + PdPodDump — same offsets the
# working RM_MOUNT arm reads. Never diverge from these.
POD_TEAM_INDEX = 0x460   # IntProperty; class default -1; == 0 means InitializeDropPod ran
POD_CUR_DEST   = 0x478   # StructProperty Vector (24 B, LWC doubles)


def pod_qualifies(o):
    """S150-drop: apply the shim's RdResolve gate to reject non-Actor/uninitialised
    'DropPod'-named UObjects. Returns (True, "why") for a real mountable pod, else
    (False, "why-not") so discovery is self-attributing.

    Gate:
      (a) class chain contains 'DropPod' (name family)
      (b) class chain EXACT-terminates at 'Actor' (kills AnimInstance/UUserWidget)
      (c) RootComponent @pod+0x1B0 is non-null (kills DEFERRED-never-finished pool templates)
      (d) PodTeamIndex @pod+0x460 == 0 (kills class-default -1 = never went through InitializeDropPod)
    """
    cls = p(o + CLASS_OFF)
    if not lp(cls):
        return (False, "no class")
    if not chain_has(cls, "DropPod"):
        return (False, "not DropPod-named")
    if not chain_ends_at(cls, "Actor"):
        return (False, "not Actor-derived (AnimInstance/UUserWidget/Component with DropPod in name)")
    root = p(o + POD_ROOT)
    if not lp(root):
        return (False, "RootComponent null (deferred/template pod)")
    b = rpm(o + POD_TEAM_INDEX, 4)
    if not b:
        return (False, "PodTeamIndex unreadable")
    ti = int.from_bytes(b, "little", signed=True)
    if ti != 0:
        return (False, "PodTeamIndex=%d (class default -1; expect 0 from InitializeDropPod)" % ti)
    return (True, "actor-derived, root=0x%X, PodTeamIndex=0" % root)


def hero_qualifies(o):
    """S150-drop: same discipline for hero discovery. Reject non-Actor 'BP_HERO_'-named
    UObjects (e.g. widgets, animation blueprints)."""
    cls = p(o + CLASS_OFF)
    if not lp(cls):
        return (False, "no class")
    if not chain_ends_at(cls, "Actor"):
        return (False, "not Actor-derived")
    if not lp(p(o + POD_ROOT)):
        return (False, "RootComponent null")
    return (True, "actor-derived, has RootComponent")


def actor_loc(actor):
    root = p(actor + POD_ROOT)
    return v3(root + SC_LOC) if lp(root) else None


def actor_vel(actor):
    root = p(actor + POD_ROOT)
    return v3(root + SC_VEL) if lp(root) else None


def discover():
    """One GUObjectArray pass -> (pods[], heroes[], rejected).

    S150-drop mount-flight 2 fix: apply the shim's RdResolve gate so we never
    pick a non-Actor UObject whose class name contains 'DropPod' or 'BP_HERO_'.
    Rejected candidates are returned so the caller can print WHY discovery failed.
    """
    hdr = rpm(OBJOBJECTS, 0x18)
    if not hdr:
        return [], [], []
    objptr, numEl = u64(hdr, 0), u32(hdr, 0x14)
    if not lp(objptr) or not (0 < numEl < 8000000):
        return [], [], []
    pods, heroes, rejected = [], [], []
    for ci in range((numEl + PERCHUNK - 1) // PERCHUNK):
        chunk = p(objptr + ci * 8)
        if not lp(chunk):
            continue
        for j in range(min(PERCHUNK, numEl - ci * PERCHUNK)):
            o = p(chunk + j * STRIDE)
            if not lp(o):
                continue
            nm = oname(o)
            if nm.startswith("Default__") or "_GEN_VARIABLE" in nm:
                continue
            # Pod candidacy: object name starts with BP_DropPod (fast prefilter)
            # AND class chain passes the mount gate.
            if nm.startswith("BP_DropPod"):
                ok, why = pod_qualifies(o)
                if ok:
                    pods.append((o, nm))
                else:
                    rejected.append(("pod", o, nm, why))
            elif nm.startswith("BP_HERO_"):
                ok, why = hero_qualifies(o)
                if ok:
                    heroes.append((o, nm))
                else:
                    rejected.append(("hero", o, nm, why))
    return pods, heroes, rejected


def read_num(comp, arr_off):
    """TArray Num at comp+arr_off+8, with a plausibility guard."""
    if not lp(comp):
        return None
    b = rpm(comp + arr_off, 16)
    if not b:
        return None
    data, num, cap = struct.unpack("<QII", b)
    if num < 0 or num > 64 or cap < 0 or cap > 4096 or num > cap:
        return -1   # implausible header
    return num


# ---- resolve pod + hero ----------------------------------------------------------------------------
print("drop_ride_readout  PID=%d BASE=0x%X  %s" % (PID, BASE, time.strftime("%Y-%m-%d %H:%M:%S")))
if not alive():
    print("*** process not readable at start -- RUN IS VOID ***")
    sys.exit(1)

pod = POD_ARG
hero = HERO_ARG
if not pod or not hero:
    print("waiting for a flying pod (BP_DropPod*) to appear (stage droppod-pe-cdopoke first)...")
    t0 = time.time()
    while time.time() - t0 < SECS:
        if not alive():
            print("*** process gone while discovering -- NOT OBTAINED (not a null) ***")
            sys.exit(3)
        pods, heroes, rejected = discover()
        if pods:
            print("\npod candidates (PASSED the RdResolve gate: Actor-derived + PodTeamIndex==0 + Root!=null):")
            for a, nm in pods:
                loc = actor_loc(a)
                print("  0x%X  %s  loc=%s" % (a, nm, ("(%.1f,%.1f,%.1f)" % loc) if loc else "?"))
            print("hero candidates:")
            for a, nm in heroes:
                loc = actor_loc(a)
                print("  0x%X  %s  loc=%s" % (a, nm, ("(%.1f,%.1f,%.1f)" % loc) if loc else "?"))
            # S150-drop mount-flight 2 fix: name the REJECTED candidates so a wrong
            # pick is impossible to hide. Mount-flight 2 picked a stale template because
            # the reader lacked this gate.
            if rejected:
                print("rejected candidates (would have been picked by the old startswith-only filter):")
                for kind, a, nm, why in rejected[:12]:
                    print("  [%s] 0x%X  %s  -- %s" % (kind, a, nm, why))
                if len(rejected) > 12:
                    print("  ... %d more rejected" % (len(rejected) - 12))
            if not pod:
                pod = pods[0][0]
            if not hero and heroes:
                hero = heroes[0][0]
                if len(heroes) > 1:
                    MULTI_HERO = True
            break
        time.sleep(1.0)
    if not pod:
        print("\n*** no qualifying BP_DropPod* appeared within %.0fs. This may mean the pod actor" % SECS)
        print("    was never created (staging incomplete) OR only non-Actor 'DropPod'-named UObjects")
        print("    exist (§6.8 substring hits: AnimInstance/UUserWidget/Component templates).")
        print("    STAGING statement, not a result.")
        sys.exit(3)

if not hero:
    print("\n*** no hero resolved. Pass --hero 0xADDR (read it from the arm's [RD] hero marker). ***")
    sys.exit(3)
if MULTI_HERO:
    print("\n⚠ MULTIPLE BP_HERO_ candidates -- using the first (0x%X). If the ride reads wrong, re-run"
          " with --hero from the arm's [RD] hero marker (bots are BP_HERO_ too)." % hero)

ride = p(pod + POD_RIDE)
ride_ok = lp(ride) and chain_has(p(ride + CLASS_OFF), "Rideable")
print("\nusing  pod=0x%X  hero=0x%X  rideable=0x%X%s" % (pod, hero, ride, "" if ride_ok else " (⚠ +0x6C8 is not a Rideable -- R1 unavailable; PlayersAttached.Num will read '?')"))
dest = v3(pod + POD_DEST)
print("CurrPodDestination = %s\n" % (("(%.1f,%.1f,%.1f)" % dest) if dest else "?"))

# ---- sample loop -----------------------------------------------------------------------------------
print("%-9s %-4s %-11s %-24s %-24s %-9s %s"
      % ("time", "HSG", "state", "pod loc", "hero loc", "|h-pod|xy", "pod vel"))
t0 = time.time()
pod0 = hero0 = None
pod_disp = hero_disp = 0.0
max_gap = 0.0
num_seen = -2   # -2 = never read, -1 = implausible, >=0 = value
hsg_seen = 0
n = 0
while time.time() - t0 < SECS:
    if not alive():
        print("\n*** PROCESS GONE at t=+%.1fs -- samples above are still valid. ***" % (time.time() - t0))
        break
    pl = actor_loc(pod)
    hl = actor_loc(hero)
    pv = actor_vel(pod)
    hsg = b1(pod + POD_HSG)
    st = b1(pod + POD_STATE)
    num = read_num(ride, RIDE_PA) if ride_ok else None
    if num is not None:
        num_seen = num
    if hsg == 1:
        hsg_seen = 1
    gap = None
    if pl and hl:
        gap = math.hypot(hl[0] - pl[0], hl[1] - pl[1])
        max_gap = max(max_gap, gap)
        if pod0 is None:
            pod0, hero0 = pl, hl
        else:
            pod_disp = math.hypot(pl[0] - pod0[0], pl[1] - pod0[1])
            hero_disp = math.hypot(hl[0] - hero0[0], hl[1] - hero0[1])
    print("%-9s %-4s %-11s %-24s %-24s %-9s %s"
          % ("+%.1fs" % (time.time() - t0),
             hsg if hsg is not None else "?",
             ("%d:%s" % (st, STATE_NAME.get(st, "?"))) if st is not None else "?",
             ("(%.0f,%.0f,%.0f)" % pl) if pl else "?",
             ("(%.0f,%.0f,%.0f)" % hl) if hl else "?",
             ("%.0f" % gap) if gap is not None else "?",
             ("(%.0f,%.0f,%.0f)" % pv) if pv else "?"))
    n += 1
    time.sleep(0.5)

# ---- verdict (computed from OBSERVED samples; never a hardcoded conclusion) -------------------------
print("\n" + "=" * 100)
print("VERDICT   (from the %d observed samples above)" % n)
print("=" * 100)
print("  R1 PlayersAttached.Num                 : %s" % (
    "UNAVAILABLE (rideable not resolved)" if num_seen == -2 else
    "IMPLAUSIBLE header (not the array?)" if num_seen == -1 else
    ("%d  %s" % (num_seen, "*** APPEND LANDED ***" if num_seen >= 1 else "(0 -- append not present)"))))
print("  PB bHasStartedGameplay reached 1       : %s" % ("YES  (StartPodGameplay ran)" if hsg_seen else "no"))
print("  pod horizontal displacement over window: %.0f uu" % pod_disp)
print("  hero horizontal displacement           : %.0f uu" % hero_disp)
print("  max |hero-pod| horizontal              : %.0f uu" % max_gap)
print()
print("  R3 RIDE (the decisive receipt):")
if pod_disp < 500:
    print("    -- POD DID NOT FLY (moved %.0f uu). Can't judge the ride. Check state/HSG above: if"
          " StartPodGameplay ran, the mover is deactivated and descent is timer-deferred ~6.5s." % pod_disp)
elif hero_disp > 0.5 * pod_disp and max_gap < 3000:
    print("    ***** HERO TRACKS THE POD -- THE RIDE WORKS. *****  (hero moved %.0f uu vs pod %.0f, gap<=%.0f)"
          % (hero_disp, pod_disp, max_gap))
    print("    If this was mount-RIDE: the arm-driven co-move works. If it was mount-NORIDE (poke-only),")
    print("    this REOPENS the offline verdict -- something repositions the rider natively; re-derive.")
elif hero_disp < 0.05 * pod_disp:
    print("    HERO IS FROZEN while the pod flew (hero %.0f uu vs pod %.0f)." % (hero_disp, pod_disp))
    print("    If mount-NORIDE (poke-only): CONFIRMS the offline verdict (a poke rider does not co-move).")
    print("    If mount-RIDE: the per-hit reposition did NOT take -- check the arm markers (MoveStep fault,")
    print("    wrong hero, or the hook stopped firing i.e. KFSNAME/funcswap starvation).")
else:
    print("    PARTIAL: hero moved %.0f uu, pod %.0f, gap<=%.0f -- inconclusive; read the per-sample rows."
          % (hero_disp, pod_disp, max_gap))

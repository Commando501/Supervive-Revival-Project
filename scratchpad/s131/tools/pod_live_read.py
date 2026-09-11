#!/usr/bin/env python3
"""
S131 -- read raw fields off a live drop-pod actor. Pure ReadProcessMemory, no injection, no writes.

  usage: pod_live_read.py <PID> <POD-ADDR-hex> [more pod addrs...]

Offsets come from the Angelscript bytecode operands, which S131 lane 1 confirmed [M] are byte
offsets from `this` (50/50 ordered match against the AOT-compiled x86 ctor, replicated 12/12 across
classes / 214 pairs). Every value is printed with the offset it came from so a wrong offset shows up
as a wrong-looking number rather than a silent one.
"""
import ctypes, ctypes.wintypes as w, struct, sys, time

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.OpenProcess.restype = w.HANDLE
k32.ReadProcessMemory.argtypes = [w.HANDLE, w.LPCVOID, w.LPVOID, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]


def rpm(h, addr, n):
    buf = (ctypes.c_char * n)()
    got = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
        return None
    return bytes(buf[:got.value])


# (offset, size, kind, name)  -- kind: i32 u8 f64 ptr vec3
FIELDS = [
    (0x3C0, 8, 'ptr', 'PilotPlayerState        (LokiDropPodBase, UHT +0x3C0)'),
    (0x3E0, 8, 'f64', 'InitialDropPodSpeed'),
    (0x3E8, 8, 'f64', 'IntroSequenceTotalTime'),
    (0x45C, 1, 'u8',  'bPilotHasPodControl'),
    (0x45D, 1, 'u8',  'bIsTeamLeaderPod        <== discriminator'),
    (0x460, 4, 'i32', 'PodTeamIndex            <== discriminator'),
    (0x464, 1, 'u8',  'bIsLocalPlayerPilot'),
    (0x468, 8, 'ptr', 'ImpactIndicator'),
    (0x470, 8, 'ptr', 'GroundLaserIndicator'),
    (0x478, 24, 'vec3', 'CurrPodDestination      <== discriminator'),
    (0x490, 16, 'arr', 'AttachedCrewPods        (TArray)'),
    (0x4A0, 1, 'u8',  'bSteeringEnabled'),
    (0x4A8, 8, 'f64', 'SteeringStartTime'),
    (0x4B0, 8, 'ptr', 'LeaderPod'),
    (0x4B8, 1, 'u8',  'bHasStartedGameplay     <== StartPodGameplay guard (NOT a UPROPERTY)'),
    (0x540, 1, 'u8',  'PodStateEvent.DropPodState  (0 None 1 Intro 2 Attached 3 Descending 4 Outro 5 Destroying)'),
    (0x570, 1, 'u8',  'CrewDetachEvent.DetachState'),
    (0x5F0, 1, 'u8',  'bIsHidingDropPhaseHiddenActors'),
    (0x5F1, 1, 'u8',  'bPodIsDestroying'),
    (0x638, 8, 'ptr', 'PodMeshComponent        (set only by StartPodGameplay)'),
    (0x648, 16, 'arr', 'PlayersToSpawnCrewPodFor (TArray)'),
    (0x06C, 1, 'u8',  'AActor::bCanEverReplicate'),
    (0x150, 8, 'ptr', 'AActor::Owner'),
    (0x1B0, 8, 'ptr', 'AActor::RootComponent'),
]


def show(h, pod):
    print("=" * 96)
    print("POD 0x%X" % pod)
    print("=" * 96)
    for off, size, kind, name in FIELDS:
        b = rpm(h, pod + off, size)
        if b is None or len(b) < size:
            print("  +0x%03X %-56s UNREADABLE" % (off, name)); continue
        if kind == 'i32':   v = "%d" % struct.unpack('<i', b)[0]
        elif kind == 'u8':  v = "%d" % b[0]
        elif kind == 'f64': v = "%.3f" % struct.unpack('<d', b)[0]
        elif kind == 'ptr':
            p = struct.unpack('<Q', b)[0]
            v = "null" if p == 0 else ("0x%X" % p)
        elif kind == 'vec3':
            x, y, z = struct.unpack('<3d', b); v = "(%.1f, %.1f, %.1f)" % (x, y, z)
        elif kind == 'arr':
            data, num, cap = struct.unpack('<QII', b); v = "Data=0x%X Num=%d Max=%d" % (data, num, cap)
        else: v = b.hex()
        print("  +0x%03X %-56s %s" % (off, name, v))
    # root component + its velocity-ish fields
    b = rpm(h, pod + 0x1B0, 8)
    if b:
        root = struct.unpack('<Q', b)[0]
        if root:
            loc = rpm(h, root + 0x158, 24)
            vel = rpm(h, root + 0x1A0, 24)
            att = rpm(h, root + 0x1D0, 8)
            print("  ROOT 0x%X" % root)
            if loc: print("    +0x158 RelativeLocation   (%.1f, %.1f, %.1f)" % struct.unpack('<3d', loc))
            if vel: print("    +0x1A0 ComponentVelocity  (%.1f, %.1f, %.1f)  [offset is [I] from lane 3]" % struct.unpack('<3d', vel))
    print()


def main():
    if len(sys.argv) < 3:
        print(__doc__); return 2
    pid = int(sys.argv[1], 0)
    h = k32.OpenProcess(0x0010 | 0x0400, False, pid)   # VM_READ | QUERY_INFORMATION
    if not h:
        print("OpenProcess failed (err %d) -- is the process alive and are you elevated?" % ctypes.get_last_error())
        return 1
    for a in sys.argv[2:]:
        show(h, int(a, 16))
    return 0


if __name__ == "__main__":
    sys.exit(main())

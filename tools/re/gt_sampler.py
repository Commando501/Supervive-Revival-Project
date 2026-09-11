# Live game-thread SAMPLING profiler (S81). No minidump, no injection.
# Suspends ONLY the game thread for a few ms per sample (anti-tamper hooks thread CREATION,
# not NtSuspendThread/NtGetContextThread/RPM, so this is as invisible as usmapdump's RPM),
# grabs RIP+RSP, reads the stack, resolves return-addresses that fall in the game exe to
# exe+RVA, and appends a timestamped line per sample.
#
# Purpose: the DS client freezes its game thread ~20s (silent in Loki.log) then the
# NetConnection times out. A ~3Hz sample stream over that window shows the common deep
# exe frame = the function that is blocking. This is a poor-man's sampling profiler.
#
# usage: gt_sampler.py <pid> <out.txt> [seconds=800] [hz=3] [gameTid=0(auto)] [exeBase=0(auto)]
#   auto game thread = earliest-created thread of the pid (UE runs the game loop on the main thread)
import sys, time, ctypes as C
from ctypes import wintypes as W

pid      = int(sys.argv[1])
outpath  = sys.argv[2]
seconds  = float(sys.argv[3]) if len(sys.argv) > 3 else 800.0
hz       = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0
force_tid= int(sys.argv[5], 0) if len(sys.argv) > 5 else 0
force_base= int(sys.argv[6], 0) if len(sys.argv) > 6 else 0

k = C.WinDLL('kernel32', use_last_error=True)

PROCESS_ALL          = 0x1F0FFF
THREAD_QUERY_INFO    = 0x0040
THREAD_GET_CONTEXT   = 0x0008
THREAD_SUSPEND_RESUME= 0x0002
TH32CS_SNAPTHREAD    = 0x00000004
TH32CS_SNAPMODULE    = 0x00000008
TH32CS_SNAPMODULE32  = 0x00000010

k.OpenProcess.restype = W.HANDLE
k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k.OpenThread.restype = W.HANDLE
k.OpenThread.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k.SuspendThread.argtypes = [W.HANDLE]
k.ResumeThread.argtypes = [W.HANDLE]
k.CloseHandle.argtypes = [W.HANDLE]
k.CreateToolhelp32Snapshot.restype = W.HANDLE
k.CreateToolhelp32Snapshot.argtypes = [W.DWORD, W.DWORD]

class THREADENTRY32(C.Structure):
    _fields_ = [("dwSize", W.DWORD), ("cntUsage", W.DWORD), ("th32ThreadID", W.DWORD),
                ("th32OwnerProcessID", W.DWORD), ("tpBasePri", C.c_long),
                ("tpDeltaPri", C.c_long), ("dwFlags", W.DWORD)]

class MODULEENTRY32(C.Structure):
    _fields_ = [("dwSize", W.DWORD), ("th32ModuleID", W.DWORD), ("th32ProcessID", W.DWORD),
                ("GlblcntUsage", W.DWORD), ("ProccntUsage", W.DWORD),
                ("modBaseAddr", C.c_void_p), ("modBaseSize", W.DWORD),
                ("hModule", W.HMODULE), ("szModule", C.c_char * 256),
                ("szExePath", C.c_char * 260)]

def filetime_to_int(ft):
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime

# ---- enumerate threads of pid ----
def list_threads(pid):
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    te = THREADENTRY32(); te.dwSize = C.sizeof(te)
    out = []
    if k.Thread32First(snap, C.byref(te)):
        while True:
            if te.th32OwnerProcessID == pid:
                out.append(te.th32ThreadID)
            if not k.Thread32Next(snap, C.byref(te)):
                break
    k.CloseHandle(snap)
    return out

def thread_creation(tid):
    h = k.OpenThread(THREAD_QUERY_INFO, False, tid)
    if not h: return None
    c = W.FILETIME(); e = W.FILETIME(); kt = W.FILETIME(); ut = W.FILETIME()
    ok = k.GetThreadTimes(h, C.byref(c), C.byref(e), C.byref(kt), C.byref(ut))
    k.CloseHandle(h)
    if not ok: return None
    return filetime_to_int(c)

# ---- exe module base/size ----
def all_modules(pid):
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    me = MODULEENTRY32(); me.dwSize = C.sizeof(me)
    out = []
    if k.Module32First(snap, C.byref(me)):
        while True:
            nm = me.szModule.decode('ascii', 'replace')
            out.append((me.modBaseAddr or 0, me.modBaseSize, nm))
            if not k.Module32Next(snap, C.byref(me)):
                break
    k.CloseHandle(snap)
    return out

def exe_module(pid):
    for b, s, nm in all_modules(pid):
        low = nm.lower()
        if 'supervive' in low and low.endswith('.exe'):
            return b, s
    return 0, 0

hproc = k.OpenProcess(PROCESS_ALL, False, pid)
if not hproc:
    print("OpenProcess failed err=%d" % C.get_last_error()); sys.exit(1)

if force_base:
    exebase, exesize = force_base, 0x8000000
else:
    exebase, exesize = exe_module(pid)
if not exebase:
    print("could not find game exe module; pass exeBase explicitly"); sys.exit(1)

# pick game thread = earliest creation
if force_tid:
    gtid = force_tid
else:
    tids = list_threads(pid)
    best = None
    for t in tids:
        ct = thread_creation(t)
        if ct is None: continue
        if best is None or ct < best[1]:
            best = (t, ct)
    gtid = best[0] if best else 0
    print("threads=%d  earliest-created(gameThread guess)=tid %d" % (len(tids), gtid))

print("pid=%d gameTid=%d exeBase=0x%X exeSize=0x%X out=%s dur=%.0fs hz=%.1f"
      % (pid, gtid, exebase, exesize, outpath, seconds, hz))

# ---- CONTEXT (x64), 16-byte aligned ----
CONTEXT_CONTROL = 0x00100001
CONTEXT_INTEGER = 0x00100002
CTXSZ = 1232
raw = (C.c_ubyte * (CTXSZ + 16))()
ctx_addr = (C.addressof(raw) + 15) & ~15
OFF_FLAGS = 0x30
OFF_RSP   = 0x98
OFF_RIP   = 0xF8

k.GetThreadContext.argtypes = [W.HANDLE, C.c_void_p]
k.ReadProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]

stackbuf = (C.c_ubyte * 0x1000)()
nread = C.c_size_t(0)

def u32(a, o): return C.cast(a + o, C.POINTER(W.DWORD)).contents.value
def u64(a, o): return C.cast(a + o, C.POINTER(C.c_uint64)).contents.value

def sample():
    h = k.OpenThread(THREAD_GET_CONTEXT | THREAD_SUSPEND_RESUME | THREAD_QUERY_INFO, False, gtid)
    if not h: return None
    if k.SuspendThread(h) == 0xFFFFFFFF:
        k.CloseHandle(h); return None
    # set ContextFlags
    C.memset(ctx_addr, 0, CTXSZ)
    C.cast(ctx_addr + OFF_FLAGS, C.POINTER(W.DWORD)).contents.value = CONTEXT_CONTROL | CONTEXT_INTEGER
    rip = rsp = 0; frames = []
    if k.GetThreadContext(h, ctx_addr):
        rip = u64(ctx_addr, OFF_RIP)
        rsp = u64(ctx_addr, OFF_RSP)
        if k.ReadProcessMemory(hproc, C.c_void_p(rsp), stackbuf, 0x1000, C.byref(nread)):
            n = nread.value
            seen = set()
            for off in range(0, n - 8, 8):
                v = u64(C.addressof(stackbuf), off)
                if exebase <= v < exebase + exesize:
                    rva = v - exebase
                    if rva not in seen:
                        seen.add(rva); frames.append(rva)
                        if len(frames) >= 16: break
    k.ResumeThread(h)
    k.CloseHandle(h)
    return (rip, rsp, frames)

interval = 1.0 / hz
end = time.time() + seconds
f = open(outpath, 'w', buffering=1)
f.write("# pid=%d gameTid=%d exeBase=0x%X exeSize=0x%X\n" % (pid, gtid, exebase, exesize))
for b, s, nm in sorted(all_modules(pid)):
    f.write("# MOD 0x%X 0x%X %s\n" % (b, s, nm))
count = 0
while time.time() < end:
    t0 = time.time()
    s = sample()
    if s is None:
        # thread gone (process exited / travel) -> keep trying a bit
        f.write("%.3f GONE\n" % t0)
        time.sleep(interval);
        # if process handle invalid, stop
        if not k.OpenProcess(PROCESS_ALL, False, pid):
            break
        continue
    rip, rsp, frames = s
    ripin = "EXE+0x%X" % (rip - exebase) if exebase <= rip < exebase+exesize else "0x%X" % rip
    fr = " ".join("+0x%X" % r for r in frames)
    f.write("%.3f RIP=%s RSP=0x%X | %s\n" % (t0, ripin, rsp, fr))
    count += 1
    dt = interval - (time.time() - t0)
    if dt > 0: time.sleep(dt)
f.close()
print("done, %d samples -> %s" % (count, outpath))

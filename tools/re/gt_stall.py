# Controlled game-thread STALL experiment (S81). Suspends ONLY the game thread for N seconds,
# then resumes — reproducing exactly what a shim's heavy game-thread work (ForEachObject sweep,
# per-line file I/O) does. If the DS client then logs "Connection TIMED OUT ... Real: ~N" and
# travels to the menu, it proves a ~N-second game-thread stall is SUFFICIENT to cause the drop
# (i.e. the drops are game-thread-stall-induced, not an inherent DS-connection failure).
#
# usage: gt_stall.py <pid> <stall_seconds> [gameTid=0(auto)]
import sys, time, ctypes as C
from ctypes import wintypes as W

pid   = int(sys.argv[1])
stall = float(sys.argv[2])
ftid  = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0

k = C.WinDLL('kernel32', use_last_error=True)
THREAD_QUERY_INFO = 0x0040
THREAD_SUSPEND_RESUME = 0x0002
TH32CS_SNAPTHREAD = 0x00000004
k.OpenThread.restype = W.HANDLE
k.OpenThread.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k.CreateToolhelp32Snapshot.restype = W.HANDLE

class THREADENTRY32(C.Structure):
    _fields_ = [("dwSize", W.DWORD), ("cntUsage", W.DWORD), ("th32ThreadID", W.DWORD),
                ("th32OwnerProcessID", W.DWORD), ("tpBasePri", C.c_long),
                ("tpDeltaPri", C.c_long), ("dwFlags", W.DWORD)]

def ftint(ft): return (ft.dwHighDateTime << 32) | ft.dwLowDateTime

if not ftid:
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    te = THREADENTRY32(); te.dwSize = C.sizeof(te); best = None
    if k.Thread32First(snap, C.byref(te)):
        while True:
            if te.th32OwnerProcessID == pid:
                h = k.OpenThread(THREAD_QUERY_INFO, False, te.th32ThreadID)
                if h:
                    c=W.FILETIME(); e=W.FILETIME(); kt=W.FILETIME(); ut=W.FILETIME()
                    if k.GetThreadTimes(h, C.byref(c), C.byref(e), C.byref(kt), C.byref(ut)):
                        ct = ftint(c)
                        if best is None or ct < best[1]: best = (te.th32ThreadID, ct)
                    k.CloseHandle(h)
            if not k.Thread32Next(snap, C.byref(te)): break
    k.CloseHandle(snap)
    ftid = best[0] if best else 0

h = k.OpenThread(THREAD_SUSPEND_RESUME, False, ftid)
if not h:
    print("OpenThread failed err=%d" % C.get_last_error()); sys.exit(1)
print("%.3f suspending gameTid=%d for %.1fs ..." % (time.time(), ftid, stall))
prev = k.SuspendThread(h)
print("%.3f SuspendThread returned prevCount=%d" % (time.time(), prev))
time.sleep(stall)
r = k.ResumeThread(h)
print("%.3f ResumeThread returned prevCount=%d (thread running again)" % (time.time(), r))
k.CloseHandle(h)

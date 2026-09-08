"""S182 Rank 4 extension: snapshot every thread's RIP once, categorize by module + ntdll export.

Since Rank 4 established the game thread is NOT stuck (ticks at 29ms Sleep), the PI dispatch
halt must be elsewhere. Enumerate every thread and see which are in waits that could be
companion-related (named event, pipe read, mutex acquire, etc.).
"""
import sys, ctypes, argparse, os, re
from ctypes import wintypes, windll, byref, c_size_t
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gt_inspect import (find_pid, open_process, enum_modules, get_ntdll_exports, attribute,
                        read_gameTid_from_memory, parse_gameTid_from_marker,
                        CONTEXT, CONTEXT_FULL, THREAD_GET_CONTEXT, THREAD_SUSPEND_RESUME)

k32 = windll.kernel32

def enum_threads(pid):
    TH32CS_SNAPTHREAD = 4
    class THREADENTRY32(ctypes.Structure):
        _fields_ = [('dwSize', ctypes.c_ulong), ('cntUsage', ctypes.c_ulong),
                    ('th32ThreadID', ctypes.c_ulong), ('th32OwnerProcessID', ctypes.c_ulong),
                    ('tpBasePri', ctypes.c_long), ('tpDeltaPri', ctypes.c_long),
                    ('dwFlags', ctypes.c_ulong)]
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    te = THREADENTRY32(); te.dwSize = ctypes.sizeof(te)
    tids = []
    if not k32.Thread32First(snap, byref(te)):
        k32.CloseHandle(snap); return tids
    while True:
        if te.th32OwnerProcessID == pid:
            tids.append(te.th32ThreadID)
        if not k32.Thread32Next(snap, byref(te)): break
    k32.CloseHandle(snap)
    return tids

def sample_rip(tid, h_proc, modules, ntdll_exports):
    th = k32.OpenThread(THREAD_GET_CONTEXT | THREAD_SUSPEND_RESUME, False, tid)
    if not th: return None
    prev = k32.SuspendThread(th)
    if prev == 0xFFFFFFFF: k32.CloseHandle(th); return None
    try:
        ctx = CONTEXT(); ctx.ContextFlags = CONTEXT_FULL
        if not k32.GetThreadContext(th, byref(ctx)): return None
        return (ctx.Rip, ctx.Rsp, attribute(ctx.Rip, modules, ntdll_exports) or f'0x{ctx.Rip:x}', ctx.Dr7)
    finally:
        k32.ResumeThread(th); k32.CloseHandle(th)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', type=int, default=None)
    args = ap.parse_args()
    pid = args.pid or find_pid('SUPERVIVE-Win64-Shipping.exe')
    if not pid: print('ERR: game not running', file=sys.stderr); sys.exit(2)
    h = open_process(pid)
    modules = enum_modules(h)
    ntdll_exports = get_ntdll_exports()
    gameTid = read_gameTid_from_memory(h, modules) or parse_gameTid_from_marker() or 0
    tids = enum_threads(pid)
    print(f'[AT] pid={pid} threads={len(tids)} gameTid={gameTid}')
    rows = []
    for tid in tids:
        r = sample_rip(tid, h, modules, ntdll_exports)
        if r is None: continue
        rip, rsp, attr, dr7 = r
        rows.append((tid, attr, rsp, dr7))
    # group by rip_attr (normalize numeric suffix on ntdll exports)
    from collections import Counter
    def normalize(a):
        # drop the +0xNN suffix on ntdll exports so 'NtWaitForSingleObject+0x14' groups with '+0x28'
        return re.sub(r'\+0x[0-9a-fA-F]+$', '', a) if '!' in a else re.sub(r'\+0x[0-9a-fA-F]+$', '', a)
    counts = Counter(normalize(a) for _, a, _, _ in rows)
    print(f'[AT] --- top RIP sites (thread count) ---')
    for a, n in counts.most_common():
        print(f'    {n:3d}  {a}')
    print(f'[AT] --- game thread ---')
    for tid, a, rsp, dr7 in rows:
        if tid == gameTid:
            print(f'    tid={tid} rip={a} rsp=0x{rsp:x} dr7=0x{dr7:x}')
    print(f'[AT] --- non-Wait threads (interesting non-idle sites) ---')
    for tid, a, rsp, dr7 in rows:
        if any(w in a for w in ('NtWait', 'NtDelayExecution', 'NtRemoveIoCompletion', 'NtSignalAnd',
                                 'ZwWait', 'ZwDelay', 'KiUserApcDispatcher')):
            continue
        print(f'    tid={tid:6d} dr7=0x{dr7:016x}  {a}')
    print(f'[AT] --- threads with DRs armed (dr7 != 0) ---')
    for tid, a, rsp, dr7 in rows:
        if dr7 != 0:
            print(f'    tid={tid:6d} dr7=0x{dr7:016x}  {a}')
    k32.CloseHandle(h)

if __name__ == '__main__':
    main()

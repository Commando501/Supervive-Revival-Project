"""S187: sample the 6 candidate frame-counter qwords in the live game process to
(a) identify which is GFrameCounter (highest delta rate ~29ms tick period),
(b) discriminate FEngineLoop::Tick vs UGameEngine::Tick as the S181 halt gate.

If any counter advances at ~30-60 Hz baseline and FREEZES post-companion-kill, then
FEngineLoop::Tick is halted (gate is at or above the frame pump). If all counters
continue advancing post-kill, then the frame pump runs but UGameEngine::Tick or
downstream is gated.

Usage:
  python scratchpad\\s187\\frame_probe.py [--iters N] [--interval SEC]
"""
import sys, ctypes, argparse, time
from ctypes import windll, byref, c_size_t

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
k32 = windll.kernel32

# S187 candidates from offline hunt (docs/s186 §"Files preserved" + inc-qword scan):
# each is a qword in .data reached by an INC qword [rip+X] site in .text.
CANDIDATES = [
    # (label, rva, containing_fn_extent_bytes)
    ('C1', 0xa075ea8, 164),
    ('C2', 0x9d49138, 293),
    ('C3', 0x9f527a0, 841),
    ('C4', 0x9f52790, 1543),   # largest containing fn — most likely GFrameCounter
    ('C5', 0x9f85208, 86),
    ('C6', 0x9faa5b0, 1070),
]

def find_pid(name):
    TH32CS_SNAPPROCESS = 2
    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [('dwSize', ctypes.c_ulong), ('cntUsage', ctypes.c_ulong),
                    ('th32ProcessID', ctypes.c_ulong), ('th32DefaultHeapID', ctypes.c_void_p),
                    ('th32ModuleID', ctypes.c_ulong), ('cntThreads', ctypes.c_ulong),
                    ('th32ParentProcessID', ctypes.c_ulong), ('pcPriClassBase', ctypes.c_long),
                    ('dwFlags', ctypes.c_ulong), ('szExeFile', ctypes.c_char * 260)]
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    pe = PROCESSENTRY32(); pe.dwSize = ctypes.sizeof(pe)
    if not k32.Process32First(snap, byref(pe)):
        k32.CloseHandle(snap); return None
    while True:
        if pe.szExeFile.decode('ascii', errors='replace').lower() == name.lower():
            k32.CloseHandle(snap); return pe.th32ProcessID
        if not k32.Process32Next(snap, byref(pe)): break
    k32.CloseHandle(snap)
    return None

def find_module_base(h_proc, name):
    """Enumerate loaded modules, return base of the named one."""
    psapi = windll.psapi
    hMods = (ctypes.c_void_p * 4096)()
    cbNeeded = ctypes.c_ulong()
    if not psapi.EnumProcessModulesEx(h_proc, hMods, ctypes.sizeof(hMods), byref(cbNeeded), 0x03):
        return None
    n = cbNeeded.value // ctypes.sizeof(ctypes.c_void_p)
    for i in range(n):
        mod_raw = hMods[i]
        if not mod_raw: continue
        mod = ctypes.c_void_p(mod_raw)
        name_buf = (ctypes.c_char * 260)()
        if psapi.GetModuleBaseNameA(h_proc, mod, name_buf, ctypes.sizeof(name_buf)):
            if name_buf.value.decode('ascii', errors='replace').lower() == name.lower():
                return mod_raw
    return None

def rpm_qword(h_proc, addr):
    buf = (ctypes.c_ubyte * 8)()
    nread = c_size_t(0)
    if not k32.ReadProcessMemory(h_proc, ctypes.c_void_p(addr), buf, 8, byref(nread)):
        return None
    if nread.value != 8: return None
    return int.from_bytes(bytes(buf), 'little')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', type=int, default=None)
    ap.add_argument('--iters', type=int, default=10)
    ap.add_argument('--interval', type=float, default=0.5)
    args = ap.parse_args()

    pid = args.pid or find_pid('SUPERVIVE-Win64-Shipping.exe')
    if not pid: print('ERR: game not running', file=sys.stderr); sys.exit(2)

    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h: raise ctypes.WinError(ctypes.get_last_error())

    base = find_module_base(h, 'SUPERVIVE-Win64-Shipping.exe')
    if not base: print('ERR: game module base not found', file=sys.stderr); sys.exit(3)
    print(f'[FP] pid={pid} SUPERVIVE base=0x{base:x} iters={args.iters} interval={args.interval}s')

    # Take iterations of samples, print raw + delta per candidate
    prev = None
    for i in range(args.iters):
        t0 = time.time()
        row = []
        for (label, rva, fn_size) in CANDIDATES:
            v = rpm_qword(h, base + rva)
            row.append(v)
        line = f'[{i+1:2d}/{args.iters}] t+{int((time.time()-t0)*1000)}ms'
        for j, (label, rva, fn_size) in enumerate(CANDIDATES):
            v = row[j]
            if prev is not None and v is not None and prev[j] is not None:
                delta = v - prev[j]
                line += f'  {label}={v}(+{delta})' if delta >= 0 else f'  {label}={v}({delta})'
            else:
                line += f'  {label}={v}'
        print(line)
        prev = row
        if i < args.iters - 1: time.sleep(args.interval)

    print(f'[FP] done')
    k32.CloseHandle(h)

if __name__ == '__main__':
    main()

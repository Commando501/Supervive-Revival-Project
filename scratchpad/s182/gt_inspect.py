"""S182 Rank 4 (docs/s181-companion-kill-halts-reflection-settled.md §"Mechanism"): identify
the specific wait state the game thread enters after the runtime.dll companion is killed.

Suspends the game thread, samples RIP + module attribution + stack chain, resumes it. Runs
N iterations at spaced intervals so a transient wait resolves into a stable one.

Preconditions:
  1. Game must be running (SUPERVIVE-Win64-Shipping.exe).
  2. F9 must have fired: DR install (hwbp_movei.py) + companion killed (companion-watch).
  3. Optional: fo-verbose injected — script picks up its gameTid from the marker automatically.

Usage:
  python scratchpad\\s182\\gt_inspect.py [--iters N] [--interval SEC] [--tid TID]
  Defaults: --iters 6 --interval 3   (30s total sampling window; fits inside fo-verbose 60s wait)

Attribution: RIP is compared against the ntdll base + a lookup of exported wait syscalls
(NtWaitFor*, NtDelayExecution, NtSignalAndWait, NtRemoveIoCompletion, ZwWait*), and RIP - base
is bucketed. The stack walk reads RSP + 32 qwords, filters for pointers into loaded modules,
and prints module!offset for each.

Design constraint: SuspendThread on the game thread is disruptive; the Sleep(interval) between
samples lets the game run in-between. The suspend window per sample is <5ms.
"""
import sys, os, argparse, ctypes, time, re, glob
from ctypes import wintypes, windll, byref, c_size_t

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_SUSPEND_RESUME = 0x0800
THREAD_GET_CONTEXT = 0x0008
THREAD_SUSPEND_RESUME = 0x0002
CONTEXT_AMD64 = 0x00100000
CONTEXT_FULL = CONTEXT_AMD64 | 0x1 | 0x2 | 0x4 | 0x8 | 0x10  # control + integer + segment + fp + debug regs
MEM_COMMIT = 0x00001000
MEM_IMAGE = 0x1000000

k32 = windll.kernel32
k32.GetModuleHandleW.restype = ctypes.c_void_p
ntdll = ctypes.WinDLL('ntdll.dll')

class MODULEINFO(ctypes.Structure):
    _fields_ = [('lpBaseOfDll', ctypes.c_void_p),
                ('SizeOfImage', ctypes.c_ulong),
                ('EntryPoint', ctypes.c_void_p)]

class M128A(ctypes.Structure):
    _fields_ = [('Low', ctypes.c_uint64), ('High', ctypes.c_int64)]

class XMM_SAVE_AREA32(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('ControlWord', ctypes.c_uint16), ('StatusWord', ctypes.c_uint16),
                ('TagWord', ctypes.c_uint8), ('Reserved1', ctypes.c_uint8),
                ('ErrorOpcode', ctypes.c_uint16), ('ErrorOffset', ctypes.c_uint32),
                ('ErrorSelector', ctypes.c_uint16), ('Reserved2', ctypes.c_uint16),
                ('DataOffset', ctypes.c_uint32), ('DataSelector', ctypes.c_uint16),
                ('Reserved3', ctypes.c_uint16), ('MxCsr', ctypes.c_uint32),
                ('MxCsr_Mask', ctypes.c_uint32), ('FloatRegisters', M128A * 8),
                ('XmmRegisters', M128A * 16), ('Reserved4', ctypes.c_uint8 * 96)]

class CONTEXT(ctypes.Structure):
    _pack_ = 16
    _fields_ = [('P1Home', ctypes.c_uint64), ('P2Home', ctypes.c_uint64),
                ('P3Home', ctypes.c_uint64), ('P4Home', ctypes.c_uint64),
                ('P5Home', ctypes.c_uint64), ('P6Home', ctypes.c_uint64),
                ('ContextFlags', ctypes.c_uint32), ('MxCsr', ctypes.c_uint32),
                ('SegCs', ctypes.c_uint16), ('SegDs', ctypes.c_uint16),
                ('SegEs', ctypes.c_uint16), ('SegFs', ctypes.c_uint16),
                ('SegGs', ctypes.c_uint16), ('SegSs', ctypes.c_uint16),
                ('EFlags', ctypes.c_uint32),
                ('Dr0', ctypes.c_uint64), ('Dr1', ctypes.c_uint64),
                ('Dr2', ctypes.c_uint64), ('Dr3', ctypes.c_uint64),
                ('Dr6', ctypes.c_uint64), ('Dr7', ctypes.c_uint64),
                ('Rax', ctypes.c_uint64), ('Rcx', ctypes.c_uint64),
                ('Rdx', ctypes.c_uint64), ('Rbx', ctypes.c_uint64),
                ('Rsp', ctypes.c_uint64), ('Rbp', ctypes.c_uint64),
                ('Rsi', ctypes.c_uint64), ('Rdi', ctypes.c_uint64),
                ('R8', ctypes.c_uint64), ('R9', ctypes.c_uint64),
                ('R10', ctypes.c_uint64), ('R11', ctypes.c_uint64),
                ('R12', ctypes.c_uint64), ('R13', ctypes.c_uint64),
                ('R14', ctypes.c_uint64), ('R15', ctypes.c_uint64),
                ('Rip', ctypes.c_uint64),
                ('FltSave', XMM_SAVE_AREA32),
                ('VectorRegister', M128A * 26),
                ('VectorControl', ctypes.c_uint64),
                ('DebugControl', ctypes.c_uint64), ('LastBranchToRip', ctypes.c_uint64),
                ('LastBranchFromRip', ctypes.c_uint64), ('LastExceptionToRip', ctypes.c_uint64),
                ('LastExceptionFromRip', ctypes.c_uint64)]

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

def open_process(pid):
    access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | PROCESS_SUSPEND_RESUME
    h = k32.OpenProcess(access, False, pid)
    if not h: raise ctypes.WinError(ctypes.get_last_error())
    return h

def enum_modules(h):
    """Return list of (base, size, name) tuples for loaded modules."""
    psapi = windll.psapi
    ret = []
    hMods = (ctypes.c_void_p * 4096)()
    cbNeeded = ctypes.c_ulong()
    if not psapi.EnumProcessModulesEx(h, hMods, ctypes.sizeof(hMods), byref(cbNeeded), 0x03):
        return ret
    n = cbNeeded.value // ctypes.sizeof(ctypes.c_void_p)
    for i in range(n):
        mod_raw = hMods[i]
        if not mod_raw: continue
        mod = ctypes.c_void_p(mod_raw)
        info = MODULEINFO()
        if not psapi.GetModuleInformation(h, mod, byref(info), ctypes.sizeof(info)):
            continue
        name_buf = (ctypes.c_char * 260)()
        if psapi.GetModuleBaseNameA(h, mod, name_buf, ctypes.sizeof(name_buf)):
            name = name_buf.value.decode('ascii', errors='replace')
        else:
            name = f'mod@0x{mod_raw:x}'
        ret.append((info.lpBaseOfDll, info.SizeOfImage, name))
    return ret

def attribute(rip_or_ptr, modules, ntdll_exports=None):
    """Given a pointer, return 'module!offset' or 'module!export_name+offset' or None."""
    for base, size, name in modules:
        if base is not None and base <= rip_or_ptr < (base + size):
            off = rip_or_ptr - base
            if ntdll_exports and name.lower() == 'ntdll.dll':
                # find closest export at or below offset
                best_name = None; best_delta = None
                for ename, eaddr in ntdll_exports.items():
                    if eaddr <= off:
                        d = off - eaddr
                        if best_delta is None or d < best_delta:
                            best_delta = d; best_name = ename
                if best_name is not None and best_delta < 0x1000:
                    return f'{name}!{best_name}+0x{best_delta:x}'
            return f'{name}+0x{off:x}'
    return None

def get_ntdll_exports():
    """Enumerate ntdll.dll exports by name (our own process's ntdll — same base as game's on x64
    Windows because ntdll is shared-image-baseline within a boot). Focus on wait-related exports."""
    from ctypes.wintypes import HMODULE
    hmod = k32.GetModuleHandleW('ntdll.dll')
    if not hmod: return {}
    hmod = int(hmod)  # k32.GetModuleHandleW.restype = c_void_p ensures this is unsigned
    # Parse the PE export directory manually
    dos = ctypes.string_at(hmod, 0x40)
    e_lfanew = int.from_bytes(dos[0x3c:0x40], 'little')
    nt = ctypes.string_at(hmod + e_lfanew, 0x108)
    # OptionalHeader is at nt+0x18; DataDirectory[0] = Export at nt+0x18+0x70 for PE32+
    export_rva = int.from_bytes(nt[0x18+0x70:0x18+0x74], 'little')
    export_size = int.from_bytes(nt[0x18+0x74:0x18+0x78], 'little')
    if not export_rva: return {}
    exp_dir = ctypes.string_at(hmod + export_rva, 0x28)
    n_funcs = int.from_bytes(exp_dir[0x14:0x18], 'little')
    n_names = int.from_bytes(exp_dir[0x18:0x1c], 'little')
    addr_of_funcs = int.from_bytes(exp_dir[0x1c:0x20], 'little')
    addr_of_names = int.from_bytes(exp_dir[0x20:0x24], 'little')
    addr_of_ords  = int.from_bytes(exp_dir[0x24:0x28], 'little')
    exports = {}
    for i in range(n_names):
        name_rva = int.from_bytes(ctypes.string_at(hmod + addr_of_names + i*4, 4), 'little')
        if not name_rva: continue
        name_bytes = ctypes.string_at(hmod + name_rva, 128)
        name = name_bytes.split(b'\x00', 1)[0].decode('ascii', errors='replace')
        ordinal = int.from_bytes(ctypes.string_at(hmod + addr_of_ords + i*2, 2), 'little')
        func_rva = int.from_bytes(ctypes.string_at(hmod + addr_of_funcs + ordinal*4, 4), 'little')
        exports[name] = func_rva
    return exports

def sample_thread(h_proc, tid, modules, ntdll_exports):
    """Suspend, GetContext, walk stack, resume. Return dict of findings."""
    th = k32.OpenThread(THREAD_GET_CONTEXT | THREAD_SUSPEND_RESUME, False, tid)
    if not th:
        return {'error': f'OpenThread({tid}) failed: {ctypes.get_last_error()}'}
    prev_susp = k32.SuspendThread(th)
    if prev_susp == 0xFFFFFFFF:
        k32.CloseHandle(th)
        return {'error': 'SuspendThread failed'}
    try:
        ctx = CONTEXT()
        ctx.ContextFlags = CONTEXT_FULL
        if not k32.GetThreadContext(th, byref(ctx)):
            return {'error': f'GetThreadContext failed: {ctypes.get_last_error()}'}
        rip = ctx.Rip; rsp = ctx.Rsp
        rip_attr = attribute(rip, modules, ntdll_exports) or f'0x{rip:x} (unattributed)'
        # If we're inside NtDelayExecution, rdx points to a LARGE_INTEGER delay.
        # Read it and decode: negative = relative (100ns units), positive = absolute time (UTC 100ns since 1601),
        # 0x8000000000000000 (INT64_MIN) = INFINITE.
        delay_info = None
        if 'NtDelayExecution' in (rip_attr or ''):
            dbuf = (ctypes.c_ubyte * 8)()
            dnread = c_size_t(0)
            if k32.ReadProcessMemory(h_proc, ctypes.c_void_p(ctx.Rdx), dbuf, 8, byref(dnread)):
                raw = int.from_bytes(bytes(dbuf), 'little', signed=True)
                if raw == -0x8000000000000000:
                    delay_info = 'INFINITE'
                elif raw < 0:
                    ms = abs(raw) / 10000.0
                    delay_info = f'relative {ms:.1f} ms ({abs(raw):#x} in 100ns units)'
                else:
                    delay_info = f'absolute UTC {raw:#x}'
        # Stack walk: read 32 qwords from RSP, attribute each
        buf = (ctypes.c_ubyte * 256)()
        nread = c_size_t(0)
        stack = []
        if k32.ReadProcessMemory(h_proc, ctypes.c_void_p(rsp), buf, 256, byref(nread)):
            for i in range(nread.value // 8):
                p = int.from_bytes(bytes(buf[i*8:i*8+8]), 'little')
                attr = attribute(p, modules, ntdll_exports)
                if attr:
                    stack.append((rsp + i*8, p, attr))
        return {
            'tid': tid, 'prev_suspend_count': prev_susp,
            'rip': rip, 'rip_attr': rip_attr,
            'rsp': rsp, 'rax': ctx.Rax, 'rcx': ctx.Rcx, 'rdx': ctx.Rdx,
            'r8': ctx.R8, 'r9': ctx.R9, 'r10': ctx.R10, 'r11': ctx.R11,
            'dr0': ctx.Dr0, 'dr1': ctx.Dr1, 'dr7': ctx.Dr7,
            'delay_info': delay_info,
            'stack': stack[:24],  # cap output
        }
    finally:
        k32.ResumeThread(th)
        k32.CloseHandle(th)

def parse_gameTid_from_marker():
    """Extract [0v] WaitTid gameTid from most recent tutorial-launch-marker.txt."""
    path = 'docs/tutorial-launch-marker.txt'
    if not os.path.isfile(path): return None
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                m = re.search(r'WaitTid ok gameTid=(\d+)', line)
                if m: return int(m.group(1))
    except Exception:
        pass
    return None

# tutorial_launch.cpp:43 kGGameTidRva=0x9D49158 (uint32 at this offset from game exe base is
# the game thread ID, written by UE at engine init and read by WaitTid).
K_GAME_TID_RVA = 0x9D49158

def read_gameTid_from_memory(h, modules):
    """Fallback: read the game's own GGameThreadId at SUPERVIVE-Win64-Shipping+0x9D49158."""
    for base, size, name in modules:
        if name.lower().startswith('supervive'):
            addr = base + K_GAME_TID_RVA
            buf = (ctypes.c_ubyte * 4)()
            nread = c_size_t(0)
            if k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, 4, byref(nread)):
                if nread.value == 4:
                    return int.from_bytes(bytes(buf), 'little')
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', type=int, default=None)
    ap.add_argument('--tid', type=int, default=None, help='override; else read from marker')
    ap.add_argument('--iters', type=int, default=6)
    ap.add_argument('--interval', type=float, default=3.0)
    args = ap.parse_args()

    pid = args.pid or find_pid('SUPERVIVE-Win64-Shipping.exe')
    if not pid:
        print('ERR: game not running', file=sys.stderr); sys.exit(2)

    h = open_process(pid)
    try:
        modules = enum_modules(h)
        # Prefer live RPM read of game exe +0x9D49158 over the marker (marker can be stale from
        # a previous session's dead PID). Marker is a fallback only.
        tid = args.tid or read_gameTid_from_memory(h, modules) or parse_gameTid_from_marker()
        if not tid:
            print('ERR: no --tid, RPM read of game exe +0x9D49158 failed, and no gameTid in marker', file=sys.stderr)
            sys.exit(3)
        src = ('--tid' if args.tid else 'RPM' if read_gameTid_from_memory(h, modules) else 'marker(stale?)')
        print(f'[GT] pid={pid} gameTid={tid} (from {src}) iters={args.iters} interval={args.interval}s')
        print(f'[GT] {len(modules)} modules loaded; ntdll base: '
              f'0x{next((b for b,s,n in modules if n.lower()=="ntdll.dll"), 0):x}')
        ntdll_exports = get_ntdll_exports()
        print(f'[GT] {len(ntdll_exports)} ntdll exports resolved (via our own ntdll — shared base per boot)')
        for i in range(args.iters):
            t0 = time.time()
            r = sample_thread(h, tid, modules, ntdll_exports)
            elapsed_ms = int((time.time() - t0) * 1000)
            if 'error' in r:
                print(f'[{i+1}/{args.iters}] ERR: {r["error"]}')
            else:
                print(f'[{i+1}/{args.iters}] t+{elapsed_ms}ms rip={r["rip_attr"]}')
                print(f'    regs: rax=0x{r["rax"]:016x} rcx=0x{r["rcx"]:016x} rdx=0x{r["rdx"]:016x}')
                print(f'          r8= 0x{r["r8"]:016x} r9= 0x{r["r9"]:016x} r10=0x{r["r10"]:016x}')
                print(f'    DRs:  dr0=0x{r["dr0"]:016x} dr1=0x{r["dr1"]:016x} dr7=0x{r["dr7"]:016x}')
                if r.get('delay_info'):
                    print(f'    delay: {r["delay_info"]}')
                if r['stack']:
                    print(f'    stack (module-attributed only, RSP=0x{r["rsp"]:x}):')
                    for addr, p, attr in r['stack']:
                        print(f'      [rsp+0x{addr-r["rsp"]:03x}] -> 0x{p:016x} = {attr}')
                else:
                    print(f'    stack: (no module-attributed pointers in top 32 qwords)')
            if i < args.iters - 1:
                time.sleep(args.interval)
    finally:
        k32.CloseHandle(h)
    print('[GT] done')

if __name__ == '__main__':
    main()

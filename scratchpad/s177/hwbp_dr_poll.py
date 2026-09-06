"""S177 Move I-4: DR-poll variant of hwbp_movei.

Purpose
-------
Move I / Move I-2 established that HW breakpoints on 6 kill-adjacent addresses
DO NOT FIRE during a real FK-32 kill (docs/s176-move-i2-4-alternate-ntdll-exports-ruled-out.md).
Two explanations remain:
  (B) the kill is kernel-mediated (protector driver invokes PsTerminateProcess)
  (C) the protector CLEARS the DR breakpoints before firing an otherwise-BP'd path

This script tests (C) directly. It:
  1. Installs a chosen set of DR breakpoints (default: same as Move I - Dr0
     on runtime.dll HIGH + 0x80F7F0, Dr1 on ntdll!NtTerminateProcess).
  2. Enters a poll loop, sampling Dr0..Dr3 + Dr7 on every thread every N
     seconds. Any DIFF from expected is logged (timestamp, tid, register,
     expected, observed).
  3. Optionally REINSTALLS the DRs after each drift is detected, so a
     successor can measure whether drift is bulk-cleared (protector sweeps
     all DRs periodically) vs targeted-cleared (only the kill thread's DRs
     are cleared just before firing).

Discriminator (per docs/next-session-prompt-s177.md Candidate C):
  drift observed AT MANY THREADS SIMULTANEOUSLY -> protector sweeps DRs
    periodically. Kills bypass BPs because DRs were already cleared. Candidate
    C strong. Next: --reinstall to see if drift returns; if it does, install
    frequency vs sweep frequency determines whether we can WIN the race.
  drift observed AT ONE THREAD JUST BEFORE FK-32 -> protector clears DRs on
    the kill thread only, on demand. Candidate C very strong. Next: identify
    that thread's TID pattern and check its call stack.
  NO DRIFT + FK-32 still fires with our DRs intact -> Candidate C REFUTED
    definitively. Kill really is bypassing the BP targets by other means
    (JIT stub, kernel-side). Combined with Move I-3 result, either A or B is
    left.
  NO DRIFT + FK-32 fires + no BP fires + our DRs still set at kill time
    -> Kill address is NOT among {DR0, DR1} targets. Candidate B (kernel-
    side) becomes strongly implicated by elimination.

Usage
-----
  # Install DR0 + DR1 (defaults, same as Move I), poll every 5s, log to stdout:
  python hwbp_dr_poll.py

  # Install just the runtime.dll kill primitive, poll every 2s, log to file:
  python hwbp_dr_poll.py --only-runtime --interval 2 --log dr_poll.log

  # Also REINSTALL DRs after each drift is detected:
  python hwbp_dr_poll.py --reinstall

  # Custom targets (useful for testing Move I-3's identified JIT stub):
  python hwbp_dr_poll.py --dr0 0x7FF... --dr1 0

  # Just clear all DRs (cleanup after an experiment):
  python hwbp_dr_poll.py --clear

Runtime notes
-------------
- Each poll costs approximately (thread_count * 1ms). At 137 threads this is
  ~140ms/poll. With --interval 5 that is ~3% CPU overhead on the polling side.
- SuspendThread + GetThreadContext + ResumeThread pauses each thread for tens
  of microseconds. On a game already under memory pressure this MAY perturb
  timing enough to shift FK-32's kill window - keep --interval low only if
  you need fine-grained drift measurements.
- GetThreadContext with CONTEXT_DEBUG_REGISTERS does NOT require SuspendThread
  on modern Windows, but SetThreadContext strictly does. The poller only reads
  by default; SuspendThread is only used when --reinstall re-writes DRs.
  (In practice we still Suspend for reads for safety — some poorly-written
  Windows kernel builds have race conditions on unsuspended reads. Cost is
  small.)
- BP install may itself be detected by the protector — Move I fired FK-32
  ~150s post-install (target: kill primitive); Move I-2 ~370s post-install
  (target: alternate exports). Note the elapsed times to your own install
  in each run; if drift begins right after install, the protector is
  actively responding to the DR write.

Blind spots (banked, S177):
- ThreadContext reads can lag on threads currently in kernel mode. We
  handle GetThreadContext failure by counting it separately from a real
  drift; a large "cx_fail" count is diagnostic of thread state, not of DR
  tampering.
- We enumerate threads at the START of each poll, so a thread that spawns
  and exits between iterations is invisible. This is fine: the protector
  isn't going to spin up an ephemeral thread just to clear DRs on another
  one.
- The poller cannot see DRs cleared then re-set within one poll interval
  (`--interval` sub-sampling). If the protector is that surgical, --interval
  1 (or 0.5 with sub-second sleeps) narrows the observable window.
"""
from __future__ import annotations
import sys, os, argparse, ctypes, time
from ctypes import wintypes, windll, byref, c_size_t

# --- constants (mirror hwbp_movei.py so both files use the same values) ---
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_SUSPEND_RESUME = 0x0800
THREAD_GET_CONTEXT = 0x0008
THREAD_SET_CONTEXT = 0x0010
THREAD_SUSPEND_RESUME = 0x0002
CONTEXT_AMD64 = 0x00100000
CONTEXT_DEBUG_REGISTERS = 0x00100010
MEM_IMAGE = 0x1000000
MEM_COMMIT = 0x00001000

KILL_RVA = 0x0080F7F0

k32 = windll.kernel32

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress",       ctypes.c_void_p),
        ("AllocationBase",    ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_ulong),
        ("__alignment1",      ctypes.c_ulong),
        ("RegionSize",        ctypes.c_size_t),
        ("State",             ctypes.c_ulong),
        ("Protect",           ctypes.c_ulong),
        ("Type",              ctypes.c_ulong),
        ("__alignment2",      ctypes.c_ulong),
    ]

class M128A(ctypes.Structure):
    _fields_ = [("Low", ctypes.c_uint64), ("High", ctypes.c_int64)]

class XMM_SAVE_AREA32(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("ControlWord", ctypes.c_uint16), ("StatusWord", ctypes.c_uint16),
        ("TagWord", ctypes.c_uint8), ("Reserved1", ctypes.c_uint8),
        ("ErrorOpcode", ctypes.c_uint16), ("ErrorOffset", ctypes.c_uint32),
        ("ErrorSelector", ctypes.c_uint16), ("Reserved2", ctypes.c_uint16),
        ("DataOffset", ctypes.c_uint32), ("DataSelector", ctypes.c_uint16),
        ("Reserved3", ctypes.c_uint16), ("MxCsr", ctypes.c_uint32),
        ("MxCsr_Mask", ctypes.c_uint32), ("FloatRegisters", M128A * 8),
        ("XmmRegisters", M128A * 16), ("Reserved4", ctypes.c_uint8 * 96),
    ]

class CONTEXT(ctypes.Structure):
    _pack_ = 16
    _fields_ = [
        ("P1Home", ctypes.c_uint64), ("P2Home", ctypes.c_uint64),
        ("P3Home", ctypes.c_uint64), ("P4Home", ctypes.c_uint64),
        ("P5Home", ctypes.c_uint64), ("P6Home", ctypes.c_uint64),
        ("ContextFlags", ctypes.c_uint32), ("MxCsr", ctypes.c_uint32),
        ("SegCs", ctypes.c_uint16), ("SegDs", ctypes.c_uint16),
        ("SegEs", ctypes.c_uint16), ("SegFs", ctypes.c_uint16),
        ("SegGs", ctypes.c_uint16), ("SegSs", ctypes.c_uint16),
        ("EFlags", ctypes.c_uint32),
        ("Dr0", ctypes.c_uint64), ("Dr1", ctypes.c_uint64),
        ("Dr2", ctypes.c_uint64), ("Dr3", ctypes.c_uint64),
        ("Dr6", ctypes.c_uint64), ("Dr7", ctypes.c_uint64),
        ("Rax", ctypes.c_uint64), ("Rcx", ctypes.c_uint64),
        ("Rdx", ctypes.c_uint64), ("Rbx", ctypes.c_uint64),
        ("Rsp", ctypes.c_uint64), ("Rbp", ctypes.c_uint64),
        ("Rsi", ctypes.c_uint64), ("Rdi", ctypes.c_uint64),
        ("R8", ctypes.c_uint64), ("R9", ctypes.c_uint64),
        ("R10", ctypes.c_uint64), ("R11", ctypes.c_uint64),
        ("R12", ctypes.c_uint64), ("R13", ctypes.c_uint64),
        ("R14", ctypes.c_uint64), ("R15", ctypes.c_uint64),
        ("Rip", ctypes.c_uint64),
        ("FltSave", XMM_SAVE_AREA32),
        ("VectorRegister", M128A * 26),
        ("VectorControl", ctypes.c_uint64),
        ("DebugControl", ctypes.c_uint64), ("LastBranchToRip", ctypes.c_uint64),
        ("LastBranchFromRip", ctypes.c_uint64), ("LastExceptionToRip", ctypes.c_uint64),
        ("LastExceptionFromRip", ctypes.c_uint64),
    ]

def open_process(pid: int) -> int:
    access = (PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | PROCESS_VM_WRITE
              | PROCESS_VM_OPERATION | PROCESS_SUSPEND_RESUME)
    h = k32.OpenProcess(access, False, pid)
    if not h:
        raise ctypes.WinError(ctypes.get_last_error())
    return h

def enum_threads(pid: int) -> list[int]:
    TH32CS_SNAPTHREAD = 4
    class THREADENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong),
            ("th32ThreadID", ctypes.c_ulong), ("th32OwnerProcessID", ctypes.c_ulong),
            ("tpBasePri", ctypes.c_long), ("tpDeltaPri", ctypes.c_long),
            ("dwFlags", ctypes.c_ulong),
        ]
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    te = THREADENTRY32(); te.dwSize = ctypes.sizeof(te)
    tids = []
    if not k32.Thread32First(snap, byref(te)):
        k32.CloseHandle(snap); return tids
    while True:
        if te.th32OwnerProcessID == pid:
            tids.append(te.th32ThreadID)
        if not k32.Thread32Next(snap, byref(te)):
            break
    k32.CloseHandle(snap)
    return tids

def find_pid(name: str):
    TH32CS_SNAPPROCESS = 2
    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong),
            ("th32ProcessID", ctypes.c_ulong), ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", ctypes.c_ulong), ("cntThreads", ctypes.c_ulong),
            ("th32ParentProcessID", ctypes.c_ulong), ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", ctypes.c_ulong), ("szExeFile", ctypes.c_char * 260),
        ]
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    pe = PROCESSENTRY32(); pe.dwSize = ctypes.sizeof(pe)
    if not k32.Process32First(snap, byref(pe)):
        k32.CloseHandle(snap); return None
    while True:
        if pe.szExeFile.decode("ascii", errors="replace").lower() == name.lower():
            k32.CloseHandle(snap); return pe.th32ProcessID
        if not k32.Process32Next(snap, byref(pe)):
            break
    k32.CloseHandle(snap)
    return None

def virtual_query(h: int, addr: int):
    mbi = MEMORY_BASIC_INFORMATION()
    if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), byref(mbi), ctypes.sizeof(mbi)):
        return None
    return mbi

def enum_regions(h: int):
    addr = 0
    while addr < 0x00007FFFFFFEFFFF:
        mbi = virtual_query(h, addr)
        if not mbi:
            break
        yield mbi
        addr = (mbi.BaseAddress or 0) + mbi.RegionSize

def rpm_bytes(h: int, addr: int, sz: int):
    buf = (ctypes.c_ubyte * sz)()
    nread = c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, sz, byref(nread)):
        return None
    return bytes(buf)[:nread.value]

def find_high_runtime_base(h: int):
    """Locate the HIGH runtime.dll mapping (the ACTIVE view per S169).

    Same heuristic as hwbp_movei.py's find_high_runtime_base:
      - MEM_COMMIT | MEM_IMAGE
      - region size 0xF0000..0x110000 (the header/section carrying the kill)
      - subtract 0x3f69000 to reach the module base
      - reject bases <= 0x100000000 (that's the LOW mapping)
      - verify the kill primitive bytes at base + 0x80F7F0
    """
    for mbi in enum_regions(h):
        if mbi.State != MEM_COMMIT: continue
        if mbi.Type != MEM_IMAGE: continue
        if not (0xf0000 <= mbi.RegionSize <= 0x110000): continue
        base = mbi.BaseAddress - 0x3f69000
        if base <= 0x100000000: continue
        pre = rpm_bytes(h, base + KILL_RVA, 16)
        if pre and (pre[:8] == bytes.fromhex("4c8b51104d85d274")
                    or pre[:8] == bytes.fromhex("4c8b51104d85d2eb")):
            return base
    return None

def resolve_ntdll_export(name: str):
    ntdll = ctypes.WinDLL("ntdll.dll")
    fn = getattr(ntdll, name, None)
    if fn is None:
        h = k32.GetModuleHandleA(b"ntdll.dll")
        if not h: return None
        addr = k32.GetProcAddress(h, name.encode("ascii"))
        return addr if addr else None
    return ctypes.cast(fn, ctypes.c_void_p).value

def read_dr(tid: int) -> tuple[dict, str | None]:
    """Read {Dr0, Dr1, Dr2, Dr3, Dr6, Dr7} of one thread.

    Returns ({}, error_string) on failure so the caller can distinguish
    "context read failed" (thread exited, permission denied) from "DRs
    match expected". We SuspendThread for the read because some Windows
    builds have race conditions on unsuspended CONTEXT_DEBUG_REGISTERS
    reads; the cost is a few microseconds per thread per poll.
    """
    th = k32.OpenThread(THREAD_GET_CONTEXT | THREAD_SUSPEND_RESUME, False, tid)
    if not th:
        return {}, f"OpenThread failed (WinError {ctypes.get_last_error()})"
    try:
        k32.SuspendThread(th)
        try:
            ctx = CONTEXT()
            ctx.ContextFlags = CONTEXT_AMD64 | CONTEXT_DEBUG_REGISTERS
            if not k32.GetThreadContext(th, byref(ctx)):
                return {}, f"GetThreadContext failed (WinError {ctypes.get_last_error()})"
            return {
                "Dr0": ctx.Dr0, "Dr1": ctx.Dr1, "Dr2": ctx.Dr2,
                "Dr3": ctx.Dr3, "Dr6": ctx.Dr6, "Dr7": ctx.Dr7,
            }, None
        finally:
            k32.ResumeThread(th)
    finally:
        k32.CloseHandle(th)

def install_hwbp(h: int, threads: list[int], addrs: dict[str, int]) -> tuple[int, int]:
    """Install DRs. addrs = {'Dr0': va, 'Dr1': va, 'Dr2': va, 'Dr3': va}.

    Absent keys / value 0 mean "leave that slot at 0 and DO NOT enable in Dr7".
    """
    ok = 0; fail = 0
    dr7 = 0
    for i, slot in enumerate(("Dr0", "Dr1", "Dr2", "Dr3")):
        if addrs.get(slot, 0):
            dr7 |= (1 << (i * 2))  # L{i} enable
    for tid in threads:
        th = k32.OpenThread(THREAD_GET_CONTEXT | THREAD_SET_CONTEXT | THREAD_SUSPEND_RESUME,
                            False, tid)
        if not th:
            fail += 1; continue
        k32.SuspendThread(th)
        try:
            ctx = CONTEXT()
            ctx.ContextFlags = CONTEXT_AMD64 | CONTEXT_DEBUG_REGISTERS
            if not k32.GetThreadContext(th, byref(ctx)):
                fail += 1
                continue
            ctx.Dr0 = addrs.get("Dr0", 0)
            ctx.Dr1 = addrs.get("Dr1", 0)
            ctx.Dr2 = addrs.get("Dr2", 0)
            ctx.Dr3 = addrs.get("Dr3", 0)
            ctx.Dr7 = dr7
            ctx.ContextFlags = CONTEXT_AMD64 | CONTEXT_DEBUG_REGISTERS
            if not k32.SetThreadContext(th, byref(ctx)):
                fail += 1
            else:
                ok += 1
        finally:
            k32.ResumeThread(th)
            k32.CloseHandle(th)
    return ok, fail

# Dr7 bit 10 is reserved-must-be-1 on x86-64 per AMD manual; Windows OR's it in
# on write, so a thread's post-install Dr7 reads back with (value | 0x400).
# S177 flight 3 measured 51 of 139 threads reading `expected 0x5 observed 0x405`
# from exactly this normalization — NOT protector tampering. Mask it out for
# meaningful drift detection. Bits we care about for a "did the BP get
# disabled" question are the L0-L3 enable bits (0/2/4/6) and the R/W + LEN
# fields (16-31). We compare the full value but ignore bit 10.
DR7_RESERVED_MASK = 0x400

def fmt_drift(expected: dict[str, int], observed: dict[str, int]) -> list[str]:
    """Return a list of 'Xreg: expected 0x.. observed 0x..' strings for each
    register that differs. For Dr7, we mask out reserved bit 10 which Windows
    always normalizes to 1 on write. A protector clearing a BP would zero the
    enable bits (0/2/4/6), which the mask leaves intact."""
    diffs = []
    for reg in ("Dr0", "Dr1", "Dr2", "Dr3"):
        e = expected.get(reg, 0)
        o = observed.get(reg, 0)
        if e != o:
            diffs.append(f"{reg}: expected 0x{e:X} observed 0x{o:X}")
    # Dr7 with reserved bit masked
    e7 = expected.get("Dr7", 0) & ~DR7_RESERVED_MASK
    o7 = observed.get("Dr7", 0) & ~DR7_RESERVED_MASK
    if e7 != o7:
        diffs.append(
            f"Dr7: expected 0x{expected.get('Dr7',0):X} "
            f"observed 0x{observed.get('Dr7',0):X} "
            f"(masked expected 0x{e7:X} vs observed 0x{o7:X})"
        )
    return diffs

class Sink:
    """Duplicate output to stdout and (optionally) an append-mode log file.

    Log file is opened line-buffered so a kill mid-write still preserves
    the drift record.
    """
    def __init__(self, path: str | None):
        self.path = path
        self.fp = None
        if path:
            self.fp = open(path, "a", encoding="utf-8", buffering=1)
    def __call__(self, msg: str) -> None:
        print(msg, flush=True)
        if self.fp:
            self.fp.write(msg + "\n")
    def close(self) -> None:
        if self.fp:
            self.fp.close()

def parse_va_arg(s: str | None):
    """Accept '0x1234', '1234', 'NtTerminateProcess', or a bare integer."""
    if not s: return 0
    s = s.strip()
    if s.lower() in ("0", "none", "off"): return 0
    if s.startswith("0x") or s.startswith("0X"):
        return int(s, 16)
    if s.isdigit():
        return int(s)
    # Treat as an ntdll export name.
    addr = resolve_ntdll_export(s)
    if addr is None:
        raise ValueError(f"could not resolve --dr* target {s!r} as hex, decimal, or ntdll export")
    return addr

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pid", type=int, default=None,
                    help="target PID (default: find SUPERVIVE-Win64-Shipping.exe)")
    ap.add_argument("--interval", type=float, default=5.0,
                    help="poll interval in seconds (default 5)")
    ap.add_argument("--log", type=str, default=None,
                    help="append log to this file in addition to stdout")
    ap.add_argument("--reinstall", action="store_true",
                    help="reinstall DRs on threads that drifted (measures drift rate)")
    ap.add_argument("--only-runtime", action="store_true",
                    help="Dr0 = runtime.dll HIGH + 0x80F7F0 only (skip ntdll Dr1)")
    ap.add_argument("--only-ntdll", action="store_true",
                    help="Dr1 = ntdll!NtTerminateProcess only (skip runtime Dr0)")
    ap.add_argument("--dr0", type=str, default=None,
                    help="override Dr0 target (hex '0x..', or ntdll export name)")
    ap.add_argument("--dr1", type=str, default=None,
                    help="override Dr1 target (hex '0x..', or ntdll export name)")
    ap.add_argument("--dr2", type=str, default=None,
                    help="Dr2 target (default off)")
    ap.add_argument("--dr3", type=str, default=None,
                    help="Dr3 target (default off)")
    ap.add_argument("--clear", action="store_true",
                    help="just clear all DRs on all threads and exit")
    ap.add_argument("--duration", type=float, default=0.0,
                    help="stop after N seconds; 0 = run until Ctrl+C")
    args = ap.parse_args()

    pid = args.pid or find_pid("SUPERVIVE-Win64-Shipping.exe")
    if not pid:
        print("ERR: game not running", file=sys.stderr); sys.exit(2)
    sink = Sink(args.log)
    sink(f"[MoveI4] target pid={pid}  interval={args.interval}s  reinstall={args.reinstall}")

    h = open_process(pid)
    try:
        expected: dict[str, int] = {"Dr0": 0, "Dr1": 0, "Dr2": 0, "Dr3": 0}

        if args.clear:
            threads = enum_threads(pid)
            ok, fail = install_hwbp(h, threads, expected)
            sink(f"[MoveI4] CLEAR: ok={ok} fail={fail} on {len(threads)} threads")
            return

        # Resolve Dr0 (runtime.dll HIGH kill primitive by default)
        if args.dr0 is not None:
            expected["Dr0"] = parse_va_arg(args.dr0)
        elif not args.only_ntdll:
            base = find_high_runtime_base(h)
            if not base:
                sink("ERR: HIGH runtime.dll mapping not found; supply --dr0 explicitly"); sys.exit(3)
            expected["Dr0"] = base + KILL_RVA

        # Resolve Dr1 (ntdll!NtTerminateProcess by default)
        if args.dr1 is not None:
            expected["Dr1"] = parse_va_arg(args.dr1)
        elif not args.only_runtime:
            addr = resolve_ntdll_export("NtTerminateProcess")
            if addr is None:
                sink("ERR: ntdll!NtTerminateProcess not resolved"); sys.exit(4)
            expected["Dr1"] = addr

        if args.dr2 is not None:
            expected["Dr2"] = parse_va_arg(args.dr2)
        if args.dr3 is not None:
            expected["Dr3"] = parse_va_arg(args.dr3)

        expected_dr7 = 0
        for i, slot in enumerate(("Dr0", "Dr1", "Dr2", "Dr3")):
            if expected.get(slot, 0):
                expected_dr7 |= (1 << (i * 2))
        expected["Dr7"] = expected_dr7
        sink(f"[MoveI4] targets:")
        for slot in ("Dr0", "Dr1", "Dr2", "Dr3"):
            sink(f"  {slot} = 0x{expected[slot]:X}")
        sink(f"  Dr7 = 0x{expected_dr7:X}")

        # Install DRs on every current thread once. Move I recorded that a
        # 150s "install -> kill" gap is a real signal (protector may detect
        # BP install); the poller therefore times its first sample right
        # after install so we have a clean 't=0' reference.
        threads_now = enum_threads(pid)
        ok, fail = install_hwbp(h, threads_now, expected)
        sink(f"[MoveI4] install: ok={ok} fail={fail} on {len(threads_now)} threads")

        # State the poller carries between iterations.
        stats = {
            "polls": 0,
            "reads_ok": 0, "reads_fail": 0,
            "threads_clean": 0, "threads_drifted": 0, "threads_new_no_dr": 0,
            "reinstall_ok": 0, "reinstall_fail": 0,
        }
        # Track per-thread state so we can print a compact "first drift" line
        # per thread instead of spamming every poll cycle.
        drifted_once: set[int] = set()
        install_time = time.monotonic()
        end_time = install_time + args.duration if args.duration > 0 else None

        sink(f"[MoveI4] entering poll loop @ t=0 (install complete)")
        try:
            while True:
                if end_time is not None and time.monotonic() >= end_time:
                    sink(f"[MoveI4] --duration reached; stopping cleanly.")
                    break
                # Sleep BEFORE polling so t=0 -> first observation at interval.
                # This gives the protector one full window to react before we
                # start counting drifts against it.
                time.sleep(args.interval)
                t_elapsed = time.monotonic() - install_time
                stats["polls"] += 1

                threads_now = enum_threads(pid)
                clean = drifted = read_fails = 0
                per_poll_drifts: list[str] = []

                for tid in threads_now:
                    observed, err = read_dr(tid)
                    if err is not None:
                        stats["reads_fail"] += 1
                        read_fails += 1
                        continue
                    stats["reads_ok"] += 1
                    diffs = fmt_drift(expected, observed)
                    if diffs:
                        drifted += 1
                        stats["threads_drifted"] += 1
                        # Only log the FIRST drift per tid to keep the stream
                        # readable across long runs. A tid that drifts, gets
                        # reinstalled, then drifts again is logged separately
                        # by the reinstall branch below.
                        if tid not in drifted_once:
                            per_poll_drifts.append(
                                f"    tid={tid}: " + " | ".join(diffs)
                            )
                            drifted_once.add(tid)
                    else:
                        clean += 1
                        stats["threads_clean"] += 1

                if per_poll_drifts:
                    sink(f"[MoveI4] t=+{t_elapsed:6.1f}s poll#{stats['polls']}: "
                         f"{drifted} DRIFTED (new), {clean} clean, {read_fails} read-fail")
                    for line in per_poll_drifts:
                        sink(line)
                else:
                    # Only print if something interesting changed vs last time.
                    # A run of "all clean" lines every N seconds gets loud;
                    # print one every 10 polls for a heartbeat.
                    if stats["polls"] % 10 == 1 or read_fails > 0:
                        sink(f"[MoveI4] t=+{t_elapsed:6.1f}s poll#{stats['polls']}: "
                             f"{clean} clean, {drifted} drifted this poll, "
                             f"{read_fails} read-fail, thread_count={len(threads_now)}")

                if args.reinstall and drifted > 0:
                    # Reinstall on drifted threads only. Reading them again
                    # afterwards would double the poll cost — trust SetThreadContext.
                    drifted_tids = []
                    for tid in threads_now:
                        obs, err = read_dr(tid)
                        if err is None and fmt_drift(expected, obs):
                            drifted_tids.append(tid)
                    r_ok, r_fail = install_hwbp(h, drifted_tids, expected)
                    stats["reinstall_ok"] += r_ok
                    stats["reinstall_fail"] += r_fail
                    sink(f"[MoveI4]   reinstalled DRs on {len(drifted_tids)} drifted: "
                         f"ok={r_ok} fail={r_fail}")
                    # Reset drifted_once so a re-drift on these tids is logged.
                    drifted_once -= set(drifted_tids)
        except KeyboardInterrupt:
            sink(f"[MoveI4] Ctrl+C; stopping")

        # Final summary.
        sink("")
        sink("=" * 60)
        sink("[MoveI4] SESSION SUMMARY")
        sink("=" * 60)
        for k, v in stats.items():
            sink(f"  {k}: {v}")
        sink(f"  drifted_tids_ever: {len(drifted_once)}")

        # Discriminator hint - a successor can grep for VERDICT
        sink("")
        if stats["threads_drifted"] == 0:
            sink("VERDICT: NO DR DRIFT observed over the poll window.")
            sink("  If FK-32 fired during this session and no BP was hit, Candidate C is")
            sink("  refuted for this poll interval. Kill mechanism is B (kernel-side) or an")
            sink("  as-yet-unmodeled path. Reduce --interval and re-fly before publishing.")
        elif len(drifted_once) == 1:
            sink("VERDICT: DRIFT observed on ONE THREAD.")
            sink("  Targeted DR clearing. That single tid is the FK-32 kill thread; check")
            sink("  its call stack via a follow-up snapshot. Candidate C strongly supported.")
        elif len(drifted_once) >= 3:
            sink("VERDICT: DRIFT observed on MULTIPLE THREADS.")
            sink("  Protector sweeps DRs periodically. Candidate C confirmed for the sweep;")
            sink("  race the poll interval against sweep frequency to determine feasibility of")
            sink("  keeping DRs installed long enough to catch a kill.")
        else:
            sink("VERDICT: DRIFT observed on a small number of threads.")
            sink("  Between targeted and swept - more data needed. Run longer or with --reinstall.")

    finally:
        try: k32.CloseHandle(h)
        except Exception: pass
        sink.close()

if __name__ == "__main__":
    main()

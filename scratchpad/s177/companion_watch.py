"""S177 Move next+1 — watch for runtime.dll companion process.

S177 established that FK-32 fires from a hidden companion process (runtime.dll
running as a PE, PID 19536 in flight 7) spawned as child of the game. Open
question: does the companion ALWAYS spawn, or only in response to our DR
install (or other tampering)?

This script watches for ANY child process of the game, prints it as soon as it
appears, and (optionally) terminates it immediately to see what the game does
when its child is killed.

Usage:
  # Passive monitor - just observe, don't touch anything:
  python companion_watch.py --duration 120

  # Aggressive: kill the child on sight (test whether game recovers)
  python companion_watch.py --duration 120 --kill-on-sight

  # Just print all children currently alive, then exit:
  python companion_watch.py --snapshot

Design notes
------------
- Uses Toolhelp32 snapshot + PROCESSENTRY32 (ParentProcessID field) to
  enumerate. No dependency on psutil.
- Filters for children of SUPERVIVE-Win64-Shipping.exe automatically. Any
  process whose ParentProcessID matches the game's PID is reported.
- On kill: uses TerminateProcess(handle, 0x1) — cause a clean exit code (0x1)
  so we can tell "we killed it" apart from "it killed the game and exited
  itself" (which per S177 exits with code 0, and its target dies with 0xDEAD).
- Watches on a tight interval (default 200 ms) because S177 measured the
  companion spawn → terminate → own-exit chain in ~4.15 seconds; the whole
  observation window is small.

Blind spots (banked, S177):
- Toolhelp32 snapshots are cheap but not free (~1-2 ms per call). At 200 ms
  cadence that's <1% CPU.
- The companion may spawn, kill the game, and exit BEFORE our poll observes it.
  For flight 7's timing (~4.1s alive) that's very unlikely at 200 ms polls
  (would take 20+ polls to miss). If the companion's lifetime is much shorter
  than expected, reduce --interval.
- A companion that hides its parent PID (e.g. via NtCreateUserProcess with
  ParentProcess = NULL) would not be detected as a child. If we see NO
  children spawn but FK-32 fires anyway, that's the case; then we widen the
  watch to any process whose image name is "runtime.dll" regardless of parent.
"""
from __future__ import annotations
import sys, os, argparse, ctypes, time
from ctypes import wintypes, windll, byref

k32 = windll.kernel32
psapi = windll.psapi

PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TH32CS_SNAPPROCESS = 0x00000002

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_ulong),
        ("cntUsage", ctypes.c_ulong),
        ("th32ProcessID", ctypes.c_ulong),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", ctypes.c_ulong),
        ("cntThreads", ctypes.c_ulong),
        ("th32ParentProcessID", ctypes.c_ulong),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_ulong),
        ("szExeFile", ctypes.c_char * 260),
    ]

def snapshot_processes() -> list[tuple[int, int, str]]:
    """Return [(pid, ppid, image_basename)] for every process alive right now."""
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == 0 or snap == -1:
        raise ctypes.WinError(ctypes.get_last_error())
    out = []
    pe = PROCESSENTRY32(); pe.dwSize = ctypes.sizeof(pe)
    try:
        if not k32.Process32First(snap, byref(pe)):
            return out
        while True:
            name = pe.szExeFile.decode("ascii", errors="replace")
            out.append((pe.th32ProcessID, pe.th32ParentProcessID, name))
            if not k32.Process32Next(snap, byref(pe)):
                break
    finally:
        k32.CloseHandle(snap)
    return out

def find_game_pid() -> int | None:
    for pid, _, name in snapshot_processes():
        if name.lower() == "supervive-win64-shipping.exe":
            return pid
    return None

def get_image_path(pid: int) -> str:
    """Full image path via QueryFullProcessImageNameW. Useful because Toolhelp's
    szExeFile is truncated to 260 chars AND is basename-only."""
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h: return "?"
    try:
        buf = (ctypes.c_wchar * 32768)()
        sz = ctypes.c_ulong(len(buf))
        if not k32.QueryFullProcessImageNameW(h, 0, buf, byref(sz)):
            return "?"
        return buf.value
    finally:
        k32.CloseHandle(h)

def kill_process(pid: int, exit_code: int = 1) -> bool:
    h = k32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if not h:
        return False
    try:
        return bool(k32.TerminateProcess(h, exit_code))
    finally:
        k32.CloseHandle(h)

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--interval", type=float, default=0.2,
                    help="poll interval in seconds (default 0.2)")
    ap.add_argument("--duration", type=float, default=180.0,
                    help="stop after N seconds; 0 = run until Ctrl+C or game dies")
    ap.add_argument("--kill-on-sight", action="store_true",
                    help="TerminateProcess() any newly-observed child of the game")
    ap.add_argument("--only-name", type=str, default="",
                    help="restrict --kill-on-sight to children whose image name "
                         "matches this exact string (case-insensitive). Default "
                         "empty = kill any child. For S177 use 'runtime.dll' to "
                         "leave EpicWebHelper etc. alone.")
    ap.add_argument("--snapshot", action="store_true",
                    help="print all children of the game right now and exit")
    ap.add_argument("--log", type=str, default=None,
                    help="append log to this file in addition to stdout")
    ap.add_argument("--wait-for-game", type=float, default=0.0,
                    help="if the game process is not running yet, wait up to this many "
                         "seconds for it to appear (polling every 1 s). Default 0 = "
                         "require the game to be running at start-up. Used by launch-"
                         "redirect.ps1 to auto-attach before the game finishes booting.")
    args = ap.parse_args()

    # Open log for tee'd output.
    log_fp = open(args.log, "a", encoding="utf-8", buffering=1) if args.log else None
    def out(msg):
        print(msg, flush=True)
        if log_fp:
            log_fp.write(msg + "\n")

    # Optionally wait for the game to appear. Purely additive — old callers pass
    # no flag and the behaviour is unchanged (fail fast if the game is missing).
    game_pid = find_game_pid()
    if not game_pid and args.wait_for_game > 0:
        out(f"[cw] game not running; waiting up to {args.wait_for_game:.0f}s for it to appear")
        deadline = time.monotonic() + args.wait_for_game
        while time.monotonic() < deadline:
            time.sleep(1)
            game_pid = find_game_pid()
            if game_pid:
                out(f"[cw] game appeared: pid={game_pid}")
                break
    if not game_pid:
        out("ERR: SUPERVIVE-Win64-Shipping.exe not running")
        sys.exit(2)
    out(f"[cw] game pid={game_pid}")

    if args.snapshot:
        procs = snapshot_processes()
        children = [(p, n) for (p, pp, n) in procs if pp == game_pid]
        out(f"[cw] {len(children)} children right now:")
        for pid, name in sorted(children):
            path = get_image_path(pid)
            out(f"    pid={pid:6}  name={name}  path={path}")
        sys.exit(0)

    # Passive/active watch loop
    seen_children: dict[int, str] = {}  # pid -> name
    start = time.monotonic()
    end = start + args.duration if args.duration > 0 else None
    poll = 0
    try:
        while True:
            if end is not None and time.monotonic() >= end:
                out(f"[cw] --duration reached, stopping cleanly. polls={poll}, children_seen={len(seen_children)}")
                break
            # Check game is alive; exit if not
            if find_game_pid() != game_pid:
                out(f"[cw] game process gone (t=+{time.monotonic()-start:.2f}s), stopping. polls={poll}")
                break
            time.sleep(args.interval)
            poll += 1
            procs = snapshot_processes()
            children_now = {p: n for (p, pp, n) in procs if pp == game_pid}
            new_children = {p: n for p, n in children_now.items() if p not in seen_children}
            for pid, name in new_children.items():
                path = get_image_path(pid)
                elapsed = time.monotonic() - start
                out(f"[cw] t=+{elapsed:6.2f}s NEW CHILD pid={pid}  name={name}  path={path}")
                seen_children[pid] = name
                if args.kill_on_sight:
                    # Filter: only kill children whose name matches --only-name.
                    # Empty --only-name = kill any child.
                    if args.only_name and name.lower() != args.only_name.lower():
                        out(f"[cw]     SKIP kill (name '{name}' != --only-name '{args.only_name}')")
                        continue
                    ok = kill_process(pid, exit_code=1)
                    out(f"[cw]     kill_process({pid}) -> {ok}")
            # Also detect exits of previously-seen children
            exited = [p for p in seen_children if p not in children_now]
            for pid in exited:
                elapsed = time.monotonic() - start
                out(f"[cw] t=+{elapsed:6.2f}s CHILD EXITED pid={pid} name={seen_children[pid]}")
                del seen_children[pid]
    except KeyboardInterrupt:
        out(f"[cw] Ctrl+C, stopping. polls={poll}, children_seen={len(seen_children)}")

    # Final summary
    if log_fp:
        log_fp.close()

if __name__ == "__main__":
    main()

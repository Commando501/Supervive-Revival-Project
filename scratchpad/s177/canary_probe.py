"""S177 Move next-3 — canary probe of runtime.dll +0x949000 self-modification.

Purpose
-------
S177 flight 5 measured that within 2 s of a DR install, the protector modifies
a specific hidden-image page inside runtime.dll HIGH: the region at HIGH+0x949000
fragmented from 0x3000 to 0x2000, spawning a new 0x1000 RW page at HIGH+0x94B000.
The scan of the new page found no code and no 0xDEAD bytes — it was zeros.

Zeros are ambiguous: either the protector deliberately zeroed the page, or the
Windows CoW split filled it with zeros first and the protector never touched
its content beyond that. To discriminate, we PRE-POISON the page with a canary,
then trigger the response, then read back.

Recipe
------
1. Find the game process + runtime.dll HIGH base.
2. WriteProcessMemory a distinctive canary pattern (0x00-terminated ASCII plus
   a magic dword) across the whole page HIGH+0x949000 (which at baseline is
   part of the larger 0x3000 region and IS accessible).
3. Verify the write with an immediate readback.
4. Install HW BPs (hwbp_movei-style) to trigger the same protector response
   we saw in flight 5.
5. Wait 3 seconds (well within the 2-s CoW-split observation window).
6. ReadProcessMemory the page back.
7. Diff: which bytes changed, what values were written.

Discriminator outcomes
----------------------
- No change to the canary                    -> the protector's response is
                                                elsewhere; this page just gets
                                                a CoW read that has no writer.
                                                Reduces (but does not refute)
                                                the "protector wrote here"
                                                reading from flight 5.
- Canary partially overwritten with 0x00s    -> protector zeroed the page. The
                                                page is a scratchpad it clears
                                                on integrity check.
- Canary overwritten with non-zero bytes     -> those bytes are the payload
                                                the protector writes. Disassemble
                                                them: if they contain code (any
                                                MSVC prologue, a syscall stub,
                                                a JMP), the interpretation of
                                                flight 5's "data page" changes.
                                                If they are data (hashes, pointer
                                                values, tag bytes), interpret
                                                per pattern.

Blind spots (banked, S177):
- If the page is PAGE_WRITECOPY at baseline, our WriteProcessMemory forces the
  CoW BEFORE the protector's response, and the protector then writes to OUR
  copy. That is still what we want to observe. WriteProcessMemory on a WRITECOPY
  page IS allowed (kernel bypasses the CoW protection for external writes).
- The exact offset 0x949000 was observed in ONE flight. In a different lifetime
  under ASLR, runtime.dll HIGH may map at a different base but the internal
  offset should stay constant (it's a runtime.dll page). We recompute the base
  live.
- If find_high_runtime_base fails (game reached a different phase), the probe
  aborts loudly rather than writing to a wrong VA. Never write to an
  unidentified address.
"""
from __future__ import annotations
import sys, os, argparse, ctypes, time
from ctypes import wintypes, windll, byref, c_size_t

# Reuse the shared plumbing from hwbp_dr_poll.py rather than re-defining every
# ctypes struct. The scripts live in the same dir so a plain import works.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hwbp_dr_poll import (
    open_process, enum_threads, find_pid, find_high_runtime_base,
    resolve_ntdll_export, install_hwbp, rpm_bytes, k32,
    KILL_RVA,
)

# The offset within runtime.dll HIGH where flight 5 saw the new RW page appear.
# Same page was the tail of the 0x3000 region at baseline; the protector's
# write inside that page caused the CoW split.
CANARY_OFFSET = 0x949000  # HIGH base + 0x949000 = the observed page VA in flight 5
CANARY_LEN    = 0x1000    # one page

def wpm(h, addr, data: bytes) -> tuple[bool, int]:
    """WriteProcessMemory helper. Returns (ok, nwritten). Uses VirtualProtectEx
    to temporarily make the page writable if the current protection blocks it —
    a WRITECOPY page will refuse an external write on some Windows builds
    despite the kernel-bypass reputation, so we belt-and-brace with a scoped
    protection change and restore afterwards."""
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    n = c_size_t(0)
    # Attempt the plain write first.
    if k32.WriteProcessMemory(h, ctypes.c_void_p(addr), buf, len(data), byref(n)):
        return True, n.value
    # If that failed, temporarily grant PAGE_READWRITE and retry.
    old = wintypes.DWORD(0)
    PAGE_READWRITE = 0x04
    if not k32.VirtualProtectEx(h, ctypes.c_void_p(addr), c_size_t(len(data)),
                                 PAGE_READWRITE, byref(old)):
        return False, 0
    ok = bool(k32.WriteProcessMemory(h, ctypes.c_void_p(addr), buf, len(data), byref(n)))
    # Restore original protection. Even if this fails, our data is written.
    junk = wintypes.DWORD(0)
    k32.VirtualProtectEx(h, ctypes.c_void_p(addr), c_size_t(len(data)),
                         old.value, byref(junk))
    return ok, n.value

def diff_bytes(a: bytes, b: bytes) -> list[tuple[int, int, int]]:
    """Return list of (offset, a_byte, b_byte) where they differ."""
    return [(i, a[i], b[i]) for i in range(min(len(a), len(b))) if a[i] != b[i]]

def hex_hexdump(data: bytes, offset_base: int = 0, per_line: int = 16, first_lines: int = 8) -> str:
    """Compact hex-dump for a small buffer (< 512 bytes recommended)."""
    lines = []
    for i in range(0, min(len(data), first_lines * per_line), per_line):
        chunk = data[i:i + per_line]
        hexed = " ".join(f"{b:02x}" for b in chunk)
        ascii_ = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"  0x{offset_base + i:04X}  {hexed:<48}  {ascii_}")
    if len(data) > first_lines * per_line:
        lines.append(f"  ... ({len(data) - first_lines * per_line} more bytes)")
    return "\n".join(lines)

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pid", type=int, default=None)
    ap.add_argument("--offset", type=lambda s: int(s, 0), default=CANARY_OFFSET,
                    help=f"offset within runtime.dll HIGH to probe (default 0x{CANARY_OFFSET:X})")
    ap.add_argument("--wait", type=float, default=3.0,
                    help="seconds between DR install and readback (default 3)")
    ap.add_argument("--no-install", action="store_true",
                    help="skip DR install (measure spontaneous drift only)")
    ap.add_argument("--canary", type=str, default="S177CANARY",
                    help="ASCII tag stamped every 16 bytes across the page")
    args = ap.parse_args()

    pid = args.pid or find_pid("SUPERVIVE-Win64-Shipping.exe")
    if not pid:
        print("ERR: game not running", file=sys.stderr); sys.exit(2)
    print(f"[canary] target pid={pid}")

    h = open_process(pid)
    try:
        # (a) Locate runtime.dll HIGH mapping. This uses the same heuristic as
        # hwbp_movei.py — MEM_COMMIT|MEM_IMAGE region of the right size that
        # sits above 0x100000000 and has the kill-primitive bytes at +0x80F7F0.
        # If that mapping isn't present we cannot proceed; better to abort loudly.
        high_base = find_high_runtime_base(h)
        if not high_base:
            print("ERR: runtime.dll HIGH mapping not found (game may be at wrong phase)",
                  file=sys.stderr)
            sys.exit(3)
        target_va = high_base + args.offset
        print(f"[canary] runtime.dll HIGH base = 0x{high_base:X}")
        print(f"[canary] target VA           = 0x{target_va:X} (HIGH + 0x{args.offset:X})")

        # (b) Read the page's initial content so we can measure change.
        pre = rpm_bytes(h, target_va, CANARY_LEN)
        if pre is None or len(pre) != CANARY_LEN:
            print(f"ERR: could not read {CANARY_LEN} bytes at 0x{target_va:X}", file=sys.stderr)
            sys.exit(4)
        print(f"[canary] pre-write page hash (first 32B): {pre[:32].hex()}")

        # (c) Build the canary. We use a repeating pattern with an offset field
        # so a partial overwrite is localisable — every 16 bytes carry the
        # ASCII tag followed by a 4-byte offset index in little-endian.
        tag = args.canary.encode("ascii")
        pattern = bytearray()
        stride = 16
        assert stride > len(tag) + 4, "tag too long for stride"
        for i in range(0, CANARY_LEN, stride):
            row = bytearray(stride)
            row[:len(tag)] = tag
            row[len(tag):len(tag)+4] = (i // stride).to_bytes(4, "little")
            # Fill remainder with 0xAA so a wipe-to-zero is unambiguous.
            for j in range(len(tag)+4, stride):
                row[j] = 0xAA
            pattern.extend(row)
        pattern = bytes(pattern[:CANARY_LEN])

        # (d) Write the canary. If this fails (e.g. the page's initial
        # protection doesn't permit external writes even via VirtualProtectEx),
        # abort — we do NOT want to install DRs without a canary in place, or
        # we'd learn nothing.
        ok, nwritten = wpm(h, target_va, pattern)
        if not ok or nwritten != CANARY_LEN:
            print(f"ERR: WriteProcessMemory failed (ok={ok}, wrote={nwritten}/{CANARY_LEN})",
                  file=sys.stderr)
            sys.exit(5)
        # Immediate readback to confirm the write landed.
        rb = rpm_bytes(h, target_va, CANARY_LEN)
        if rb != pattern:
            diffs = diff_bytes(pattern, rb or b"")
            print(f"ERR: canary readback mismatch ({len(diffs)} byte differences)",
                  file=sys.stderr)
            sys.exit(6)
        print(f"[canary] canary written and verified: {CANARY_LEN} bytes")

        # (e) Install DRs to trigger the protector response we saw in flight 5.
        # Skip only if the operator wants a spontaneous-drift measurement.
        if not args.no_install:
            addr0 = high_base + KILL_RVA
            addr1 = resolve_ntdll_export("NtTerminateProcess")
            if addr1 is None:
                print("ERR: could not resolve NtTerminateProcess", file=sys.stderr)
                sys.exit(7)
            threads = enum_threads(pid)
            ok_cnt, fail_cnt = install_hwbp(h, threads,
                                            {"Dr0": addr0, "Dr1": addr1, "Dr2": 0, "Dr3": 0})
            print(f"[canary] DR install: Dr0=0x{addr0:X} Dr1=0x{addr1:X} "
                  f"ok={ok_cnt} fail={fail_cnt} on {len(threads)} threads")

        # (f) Wait for the protector response window. Flight 5's diff was
        # taken 2 s after install; we wait a little longer to give time for
        # the write and to give ourselves headroom before FK-32 fires.
        print(f"[canary] waiting {args.wait}s for protector response...")
        time.sleep(args.wait)

        # (g) Read back and diff. The game may already be dead by now — that's
        # OK, the process handle is still open and RPM works until the process
        # goes fully teardown. If it's really gone we report and exit.
        post = rpm_bytes(h, target_va, CANARY_LEN)
        if post is None:
            print("[canary] READBACK FAILED — game is likely dead or page unmapped")
            print("[canary] this itself is informative: the protector may have unmapped")
            print("[canary] the region as part of its response.")
            sys.exit(0)
        diffs = diff_bytes(pattern, post)
        print(f"[canary] readback OK. {len(diffs)} bytes differ vs canary.")

        # (h) Report the delta. We keep the first 512 bytes of both for
        # eyeballing and print byte-diff histograms.
        if not diffs:
            print("VERDICT: NO CHANGE — canary intact.")
            print("  The protector did NOT write to this page while we held it.")
            print("  Flight 5's CoW split was NOT caused by a write into THIS specific")
            print("  page; the split may have been a Windows-side artifact of some other")
            print("  operation. Reduces (does not refute) the 'protector wrote here' reading.")
            return
        # Class the diff: all-zero writes vs non-zero.
        zeroed = sum(1 for _, _, b in diffs if b == 0)
        nonzero = len(diffs) - zeroed
        # Runs of contiguous differing bytes tell us if the write was
        # scattered (many small pokes) or bulk (one memset/memcpy).
        runs = []
        cur_start = diffs[0][0]; cur_end = cur_start
        for (o, _, _) in diffs[1:]:
            if o == cur_end + 1:
                cur_end = o
            else:
                runs.append((cur_start, cur_end))
                cur_start = cur_end = o
        runs.append((cur_start, cur_end))
        print(f"[canary] diff shape: zeroed={zeroed} non-zero-write={nonzero} runs={len(runs)}")
        for i, (s, e) in enumerate(runs[:8]):
            print(f"  run {i}: [0x{s:04X}..0x{e:04X}] len={e-s+1}")
        if len(runs) > 8:
            print(f"  ... {len(runs) - 8} more runs")

        # Show hexdumps of the biggest run, both sides.
        biggest = max(runs, key=lambda r: r[1] - r[0])
        s, e = biggest
        sz = min(e - s + 1, 128)  # cap for readability
        print()
        print(f"=== biggest changed run: [0x{s:04X}..0x{s+sz-1:04X}] ({sz} bytes) ===")
        print("CANARY (what we wrote):")
        print(hex_hexdump(pattern[s:s+sz], offset_base=s))
        print("POST-RESPONSE (what the protector left):")
        print(hex_hexdump(post[s:s+sz], offset_base=s))

        # Discriminator verdict.
        print()
        print("=" * 60)
        print("VERDICT (per S177 canary discriminator)")
        print("=" * 60)
        if nonzero == 0:
            print("ZEROED: the protector wiped canary bytes back to 0x00.")
            print("  This page is a scratchpad the protector clears on integrity")
            print("  check. Does NOT indicate the FK-32 mechanism directly, but")
            print("  confirms flight 5's split WAS caused by a protector write here.")
        elif zeroed == 0:
            print("OVERWRITTEN with non-zero bytes.")
            print("  Disassemble the biggest run above. If it decodes as x86-64,")
            print("  the page hosts code — first evidence of protector-written")
            print("  code in a data-classed page. If it decodes as data (hashes,")
            print("  pointer table, tag bytes), interpret per pattern.")
        else:
            print("MIXED: some bytes zeroed, some overwritten non-zero.")
            print("  Complex response — likely a structured write (header + body)")
            print("  or the write hit multiple times with different payloads.")
            print("  Read the biggest run's bytes above to characterize.")

    finally:
        try: k32.CloseHandle(h)
        except Exception: pass

if __name__ == "__main__":
    main()

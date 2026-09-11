// crashwatch.go — capture a full image dump from a process that is CRASHING.
//
// WHY. Crash-era processes are the highest-coverage states this project has ever observed: the
// best one had 62.68% of .text decrypted against merged2's 54.95%, and the crash-table union
// names ~2,334 .text pages that no image dump on disk has BYTES for. That is roughly 25x the
// yield of a tutorial sitting and 180x a menu dump — and it costs ZERO extra launches, because
// runs already die on their own (FK-31 alone kills 27% of tutorial launches). The catch is that
// nobody has ever captured one, because you have to dump the process while it is dying.
//
// THE WINDOW IS ~34 ms, SO RACING IT IS HOPELESS. Measured from the archived crash corpus
// (dumps/crashpad-20260804-181909-shimrun2-DEATH/session-Loki.log):
//
//     23.18.59:834  LogSentrySdk: flushing session and queue before crashpad handler
//     23.18.59:835  LogSentrySdk: Verbose: invoking `on_crash` hook
//     23.18.59:853  LogSentrySdk: Sentry HandleBeforeCrash End
//     23.18.59:868  LogSentrySdk: handing control over to crashpad     <-- last line in the file
//
// 34 ms from the first detectable line to handoff, and the log stops there. A full dumpimage is
// 178 MB of ReadProcessMemory plus a VirtualQuery walk plus export enumeration over ~221 modules
// — orders of magnitude slower. Polling faster does not fix that; the dump cannot finish inside
// the window no matter how early you notice.
//
// THE MOVE THAT MAKES IT WORK: SUSPEND THE DYING PROCESS. NtSuspendProcess is a single call and
// it freezes the target indefinitely, converting an unknown sub-second window into unlimited
// time. We then dump at leisure and RESUME, so crashpad still gets to write its own minidump and
// we keep the stream-13 function table too. The process is already crashing, so suspending it
// costs nothing that was not already lost.
//
// WHAT THIS CANNOT CATCH, stated plainly: the silent-kill class. FK-32 identified
// runtime.dll+0x80f7f0 as `mov edx,0xDEAD; syscall` = NtTerminateProcess(h, 0xDEAD) — the
// protector deliberately killing the process. That path writes no log line and leaves no
// artifact, so there is nothing to trigger on and no window to suspend into. Those deaths are
// out of reach here; the exit code is still captured, which is how you tell them apart.
//
// USAGE
//   usmapdump crashwatch <proc-name> <outDir> [-log <path>] [-poll <ms>] [-timeout <sec>]
//                                             [-nosuspend] [-dumpnow]
//
//   -dumpnow   dump immediately instead of waiting for a crash. This is how you MEASURE the dump
//              wall-clock, which was never measured before this file existed and which decides
//              whether -nosuspend is ever viable. Run it once on a healthy process.
//   -nosuspend skip the suspend. Almost certainly loses the race; kept as the control arm so the
//              suspend's necessity is demonstrable rather than assumed.
//
// The harness holds an OS handle across exit so GetExitCodeProcess still works after the process
// is gone: 0xC0000005 = access violation, 0x0000DEAD = protector kill, 0xFFFFFFFF = Stop-Process.
// An exit code of 259 (STILL_ACTIVE) as a real exit code is impossible, so it is used as the
// "still running" sentinel exactly as Windows intends.
package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

var (
	ntdllCW              = syscall.NewLazyDLL("ntdll.dll")
	procNtSuspendProcess = ntdllCW.NewProc("NtSuspendProcess")
	procNtResumeProcess  = ntdllCW.NewProc("NtResumeProcess")
	procGetExitCodeProc  = kernel32.NewProc("GetExitCodeProcess")
)

const (
	processSuspendResume = 0x0800
	stillActive          = 259
)

// Earliest-to-latest crash markers. The list is ordered by how early each one appears so the
// report can say which fired; any of them is enough to trigger. The Sentry "flushing session"
// line is the earliest observed (34 ms of lead), UE's own fatal banners can precede it on other
// death modes, and "handing control over to crashpad" is the last-chance backstop.
var crashMarkers = []string{
	"=== Critical error ===",
	"Fatal error",
	"flushing session and queue before crashpad handler",
	"invoking `on_crash` hook",
	"Sentry HandleBeforeCrash Begin",
	"handing control over to crashpad",
}

func cwExitCode(h uintptr) (uint32, bool) {
	var code uint32
	r, _, _ := procGetExitCodeProc.Call(h, uintptr(unsafe.Pointer(&code)))
	if r == 0 {
		return 0, false
	}
	return code, true
}

func cwLabelExit(code uint32) string {
	switch code {
	case 0x0000DEAD:
		return "PROTECTOR NtTerminateProcess(0xDEAD) — deliberate anti-tamper kill (FK-32)"
	case 0xC0000005:
		return "ACCESS VIOLATION (unhandled)"
	case 0xFFFFFFFF:
		return "killed by Stop-Process / TerminateProcess(-1)"
	case 0:
		return "clean exit"
	case stillActive:
		return "STILL_ACTIVE — not a real exit code"
	default:
		return "unclassified"
	}
}

// tailNew returns bytes appended to path since off, and the new offset. A missing or shrinking
// file resets the offset rather than erroring — the game truncates its log on relaunch.
func cwTailNew(path string, off int64) ([]byte, int64) {
	f, err := os.Open(path)
	if err != nil {
		return nil, off
	}
	defer f.Close()
	fi, err := f.Stat()
	if err != nil {
		return nil, off
	}
	if fi.Size() < off {
		off = 0
	}
	if fi.Size() == off {
		return nil, off
	}
	n := fi.Size() - off
	if n > 1<<20 {
		// Never read more than 1 MB per poll; on a log-heavy run this keeps the poll cheap.
		off = fi.Size() - (1 << 20)
		n = 1 << 20
	}
	buf := make([]byte, n)
	rd, err := f.ReadAt(buf, off)
	if rd <= 0 {
		return nil, off
	}
	_ = err
	return buf[:rd], off + int64(rd)
}

func cmdCrashWatch(args []string) {
	if len(args) < 2 {
		fmt.Println("usage: usmapdump crashwatch <proc-name> <outDir> [-log <path>] [-poll <ms>]")
		fmt.Println("       [-timeout <sec>] [-wait <sec>] [-nosuspend] [-dumpnow]")
		os.Exit(1)
	}
	procName, outDir := args[0], args[1]
	logPath := filepath.Join(os.Getenv("LOCALAPPDATA"), "SUPERVIVE", "Saved", "Logs", "Loki.log")
	pollMs, timeoutSec := 50, 0
	waitSec := 180 // how long to wait for the process to APPEAR (armed before launch)
	suspend, dumpNow := true, false
	for i := 2; i < len(args); i++ {
		switch strings.ToLower(args[i]) {
		case "-log":
			if i+1 < len(args) {
				i++
				logPath = args[i]
			}
		case "-poll":
			if i+1 < len(args) {
				i++
				pollMs, _ = strconv.Atoi(args[i])
			}
		case "-timeout":
			if i+1 < len(args) {
				i++
				timeoutSec, _ = strconv.Atoi(args[i])
			}
		case "-wait":
			if i+1 < len(args) {
				i++
				waitSec, _ = strconv.Atoi(args[i])
			}
		case "-nosuspend":
			suspend = false
		case "-dumpnow":
			dumpNow = true
		}
	}
	if pollMs < 5 {
		pollMs = 5
	}

	// WAIT for the process rather than requiring it. launch-redirect.ps1 arms crashwatch BEFORE
	// it starts the game, so an immediate findPID would always miss and the harness would be a
	// silent no-op -- the exact failure mode this tool exists to prevent. Poll until it appears.
	var pid uint32
	waitDeadline := time.Now().Add(time.Duration(waitSec) * time.Second)
	for {
		if p, err := findPID(procName); err == nil && p != 0 {
			pid = p
			break
		}
		if time.Now().After(waitDeadline) {
			fmt.Printf("ERROR: process %q never appeared within %ds — nothing to watch.\n",
				procName, waitSec)
			os.Exit(1)
		}
		time.Sleep(250 * time.Millisecond)
	}
	// SUSPEND_RESUME is the whole point; VM_READ/QUERY let us confirm liveness and exit code.
	h, _, e := procOpenProcess.Call(processVMRead|processQueryLimited|processSuspendResume, 0, uintptr(pid))
	if h == 0 {
		fmt.Println("ERROR: OpenProcess failed — run elevated (the game is elevated):", e)
		os.Exit(1)
	}
	defer procCloseHandle.Call(h)

	fmt.Printf("crashwatch: pid %d (%s)\n", pid, procName)
	fmt.Printf("  log     : %s\n", logPath)
	fmt.Printf("  outDir  : %s\n", outDir)
	fmt.Printf("  poll    : %d ms   suspend-on-trigger: %v\n", pollMs, suspend)
	if timeoutSec > 0 {
		fmt.Printf("  timeout : %d s\n", timeoutSec)
	}

	// Start from the CURRENT end of the log: markers already in the file are from earlier runs
	// and would fire instantly. (A stale trigger is the obvious failure mode of a log tailer.)
	var off int64
	if fi, err := os.Stat(logPath); err == nil {
		off = fi.Size()
	}
	fmt.Printf("  log tail starts at offset %d (older markers ignored)\n\n", off)

	start := time.Now()
	trigger := ""
	var tTrigger time.Time

	if dumpNow {
		trigger = "-dumpnow (no crash; this run exists to MEASURE the dump wall-clock)"
		tTrigger = time.Now()
	}

	for trigger == "" {
		if code, ok := cwExitCode(h); ok && code != stillActive {
			fmt.Printf("MISSED: process exited before any crash marker was seen.\n")
			fmt.Printf("  exit code %d (0x%08X) — %s\n", int32(code), code, cwLabelExit(code))
			fmt.Printf("  elapsed %.1fs\n", time.Since(start).Seconds())
			fmt.Printf("  If this was a silent kill (0xDEAD) there is nothing to catch — see the\n")
			fmt.Printf("  header of crashwatch.go. If it was 0xC0000005, the log markers may have\n")
			fmt.Printf("  been buffered; lower -poll or add the marker you saw to crashMarkers.\n")
			return
		}
		if timeoutSec > 0 && time.Since(start) > time.Duration(timeoutSec)*time.Second {
			fmt.Printf("timeout after %ds with no crash — process still alive. Nothing captured.\n", timeoutSec)
			return
		}
		if chunk, newOff := cwTailNew(logPath, off); len(chunk) > 0 {
			off = newOff
			s := string(chunk)
			for _, m := range crashMarkers {
				if strings.Contains(s, m) {
					trigger = m
					tTrigger = time.Now()
					break
				}
			}
		}
		if trigger == "" {
			time.Sleep(time.Duration(pollMs) * time.Millisecond)
		}
	}

	fmt.Printf("*** TRIGGER: %q  at T+%.1fs ***\n", trigger, tTrigger.Sub(start).Seconds())

	// --- SUSPEND. One call, and it is what buys the time to dump at all. ---
	suspended := false
	if suspend {
		t0 := time.Now()
		r, _, _ := procNtSuspendProcess.Call(h)
		lat := time.Since(tTrigger)
		if r == 0 {
			suspended = true
			fmt.Printf("  SUSPENDED %.0f ms after trigger (NtSuspendProcess took %.1f ms)\n",
				lat.Seconds()*1000, time.Since(t0).Seconds()*1000)
		} else {
			fmt.Printf("  WARN: NtSuspendProcess returned 0x%X — dumping a RUNNING, dying process;\n", r)
			fmt.Printf("        expect a torn or truncated image, and probably a lost race.\n")
		}
	} else {
		fmt.Printf("  -nosuspend: NOT suspending (control arm; the race is expected to be lost)\n")
	}
	if code, ok := cwExitCode(h); ok && code != stillActive {
		fmt.Printf("  LOST THE RACE: process already exited (0x%08X — %s) before the dump began.\n",
			code, cwLabelExit(code))
		return
	}

	// --- DUMP. cmdDumpImage re-resolves the process by NAME, which is correct here: we want the
	// module base of this same live process, and it is still alive because we suspended it. ---
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		fmt.Println("ERROR: creating outDir:", err)
	}
	tDump := time.Now()
	fmt.Printf("  dumping into %s ...\n", outDir)
	cmdDumpImage(procName, outDir)
	dumpDur := time.Since(tDump)
	fmt.Printf("  DUMP COMPLETE in %.1fs\n", dumpDur.Seconds())

	// --- RESUME so crashpad still writes its own minidump (stream 13 = the function table). ---
	if suspended {
		r, _, _ := procNtResumeProcess.Call(h)
		if r == 0 {
			fmt.Printf("  resumed — letting crashpad finish its own report\n")
		} else {
			fmt.Printf("  WARN: NtResumeProcess returned 0x%X; the process stays suspended.\n", r)
		}
	}

	// --- Hold the handle across exit so the exit code survives. ---
	fmt.Printf("  waiting for exit to capture the code ...\n")
	var finalCode uint32 = stillActive
	deadline := time.Now().Add(120 * time.Second)
	for time.Now().Before(deadline) {
		if code, ok := cwExitCode(h); ok && code != stillActive {
			finalCode = code
			break
		}
		time.Sleep(100 * time.Millisecond)
	}

	info := filepath.Join(outDir, "CRASHWATCH-INFO.txt")
	var b strings.Builder
	fmt.Fprintf(&b, "usmapdump crashwatch\n")
	fmt.Fprintf(&b, "captured   : %s\n", time.Now().Format("2006-01-02 15:04:05"))
	fmt.Fprintf(&b, "process    : %s (pid %d)\n", procName, pid)
	fmt.Fprintf(&b, "trigger    : %s\n", trigger)
	fmt.Fprintf(&b, "trigger at : T+%.1fs after watch start\n", tTrigger.Sub(start).Seconds())
	fmt.Fprintf(&b, "suspended  : %v\n", suspended)
	fmt.Fprintf(&b, "dump time  : %.1fs\n", dumpDur.Seconds())
	if finalCode == stillActive {
		fmt.Fprintf(&b, "exit code  : still alive after 120s (unexpected for a crash)\n")
	} else {
		fmt.Fprintf(&b, "exit code  : %d (0x%08X) — %s\n", int32(finalCode), finalCode, cwLabelExit(finalCode))
	}
	fmt.Fprintf(&b, "\nNOTE: a crash-era image is expected to hold MORE decrypted .text than any\n")
	fmt.Fprintf(&b, "healthy-process dump. Pre-registered prediction (docs/fk18-fk19-multistate-\n")
	fmt.Fprintf(&b, "merge-settled.md §12.2): ~18,900 non-zero .text pages, contributing ~2,300 to a\n")
	fmt.Fprintf(&b, "re-merge. If it lands near 15,700 like every healthy dump, the crash-path\n")
	fmt.Fprintf(&b, "hypothesis is WRONG and that is the more interesting result.\n")
	fmt.Fprintf(&b, "Fold in with:  usmapdump mergedumps dumps/merged2.dump.exe dumps\n")
	if err := os.WriteFile(info, []byte(b.String()), 0o644); err == nil {
		fmt.Printf("  wrote %s\n", info)
	}

	if finalCode != stillActive {
		fmt.Printf("EXIT %d (0x%08X) — %s\n", int32(finalCode), finalCode, cwLabelExit(finalCode))
	}
	fmt.Printf("done. Dump is in %s\n", outDir)
}

// inject — a minimal, transparent CreateRemoteThread+LoadLibraryW DLL injector.
//
// Why this exists: SUPERVIVE-Win64-Shipping.exe is a packed executable that imports
// only preloader.dll (the real UE engine is unpacked at runtime). Because of that, no
// proxy-DLL (dwmapi.dll etc.) is ever loaded, so UE4SS's normal proxy bootstrap never
// runs. There is NO EasyAntiCheat present (verified), so injecting UE4SS.dll directly
// into the running process is a clean way to load it. Once loaded, press Ctrl+NumPad6
// in-game (UE4SS DumpUSMAP keybind) to write Mappings.usmap.
//
// Usage (run ELEVATED — the game runs elevated):
//   inject.exe "SUPERVIVE-Win64-Shipping.exe" "G:\...\Loki\Binaries\Win64\ue4ss\UE4SS.dll"
//   inject.exe 12345 "C:\path\to\some.dll"        (numeric first arg = PID)
//
// Pure stdlib (kernel32 via LazyDLL) — no external modules.
package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"unsafe"
)

var (
	kernel32                 = syscall.NewLazyDLL("kernel32.dll")
	procOpenProcess          = kernel32.NewProc("OpenProcess")
	procVirtualAllocEx       = kernel32.NewProc("VirtualAllocEx")
	procWriteProcessMemory   = kernel32.NewProc("WriteProcessMemory")
	procCreateRemoteThread   = kernel32.NewProc("CreateRemoteThread")
	procWaitForSingleObject  = kernel32.NewProc("WaitForSingleObject")
	procGetExitCodeThread    = kernel32.NewProc("GetExitCodeThread")
	procCloseHandle          = kernel32.NewProc("CloseHandle")
	procCreateToolhelp32Snap = kernel32.NewProc("CreateToolhelp32Snapshot")
	procProcess32FirstW      = kernel32.NewProc("Process32FirstW")
	procProcess32NextW       = kernel32.NewProc("Process32NextW")
	procModule32FirstW       = kernel32.NewProc("Module32FirstW")
	procModule32NextW        = kernel32.NewProc("Module32NextW")
	procGetModuleHandleW     = kernel32.NewProc("GetModuleHandleW")
	procGetProcAddress       = kernel32.NewProc("GetProcAddress")
	procGetProcMitigation    = kernel32.NewProc("GetProcessMitigationPolicy")
	procReadProcessMemory    = kernel32.NewProc("ReadProcessMemory")
)

const (
	processAllAccess   = 0x1F0FFF
	memCommitReserve   = 0x3000
	pageReadWrite      = 0x04
	th32csSnapProcess  = 0x00000002
	th32csSnapModule   = 0x00000008
	th32csSnapModule32 = 0x00000010
	infinite           = 0xFFFFFFFF
)

type moduleEntry32 struct {
	Size         uint32
	ModuleID     uint32
	ProcessID    uint32
	GlblcntUsage uint32
	ProccntUsage uint32
	ModBaseAddr  uintptr
	ModBaseSize  uint32
	HModule      uintptr
	ModuleName   [256]uint16
	ExePath      [260]uint16
}

// moduleLoaded reports whether a module with the given base name (case-insensitive)
// is present in the target — definitive proof of a load, unlike the truncated thread
// exit code.
func moduleLoaded(pid uint32, baseName string) bool {
	snap, _, _ := procCreateToolhelp32Snap.Call(th32csSnapModule|th32csSnapModule32, uintptr(pid))
	if snap == 0 || snap == ^uintptr(0) {
		return false
	}
	defer procCloseHandle.Call(snap)
	var me moduleEntry32
	me.Size = uint32(unsafe.Sizeof(me))
	ret, _, _ := procModule32FirstW.Call(snap, uintptr(unsafe.Pointer(&me)))
	for ret != 0 {
		name := syscall.UTF16ToString(me.ModuleName[:])
		if strings.EqualFold(name, baseName) {
			return true
		}
		ret, _, _ = procModule32NextW.Call(snap, uintptr(unsafe.Pointer(&me)))
	}
	return false
}

type processEntry32 struct {
	Size            uint32
	Usage           uint32
	ProcessID       uint32
	DefaultHeapID   uintptr
	ModuleID        uint32
	Threads         uint32
	ParentProcessID uint32
	PriClassBase    int32
	Flags           uint32
	ExeFile         [260]uint16
}

func findPID(name string) (uint32, error) {
	snap, _, err := procCreateToolhelp32Snap.Call(th32csSnapProcess, 0)
	if snap == 0 || snap == ^uintptr(0) {
		return 0, fmt.Errorf("snapshot failed: %v", err)
	}
	defer procCloseHandle.Call(snap)

	var pe processEntry32
	pe.Size = uint32(unsafe.Sizeof(pe))
	target := name
	ret, _, _ := procProcess32FirstW.Call(snap, uintptr(unsafe.Pointer(&pe)))
	for ret != 0 {
		exe := syscall.UTF16ToString(pe.ExeFile[:])
		if exe == target {
			return pe.ProcessID, nil
		}
		ret, _, _ = procProcess32NextW.Call(snap, uintptr(unsafe.Pointer(&pe)))
	}
	return 0, fmt.Errorf("process %q not found (is the game running?)", name)
}

// mustPID resolves a numeric PID or a process name, exiting on failure.
func mustPID(arg string) uint32 {
	if n, err := strconv.Atoi(arg); err == nil {
		return uint32(n)
	}
	p, err := findPID(arg)
	if err != nil {
		fmt.Println("ERROR:", err)
		os.Exit(1)
	}
	return p
}

// diag characterizes what the OS will let us do to the target — which decides whether
// any injection technique (incl. manual mapping) or an injection-free external
// memory-read usmap dumper is viable. No injection performed.
func diag(name string) {
	pid, err := findPID(name)
	if err != nil {
		fmt.Println("ERROR:", err)
		os.Exit(1)
	}
	fmt.Printf("Target %q PID %d\n\n", name, pid)

	masks := []struct {
		n string
		m uintptr
	}{
		{"QUERY_LIMITED_INFORMATION", 0x1000},
		{"QUERY_INFORMATION", 0x0400},
		{"VM_READ", 0x0010},
		{"VM_WRITE|VM_OPERATION", 0x0020 | 0x0008},
		{"CREATE_THREAD", 0x0002},
		{"ALL_ACCESS", 0x1F0FFF},
	}
	fmt.Println("OpenProcess access rights the OS grants:")
	for _, a := range masks {
		h, _, e := procOpenProcess.Call(a.m, 0, uintptr(pid))
		if h != 0 {
			fmt.Printf("  %-26s GRANTED\n", a.n)
			procCloseHandle.Call(h)
		} else {
			fmt.Printf("  %-26s denied (%v)\n", a.n, e)
		}
	}

	// Mitigation policies that block injection. Needs a query handle.
	hq, _, _ := procOpenProcess.Call(0x1000, 0, uintptr(pid))
	if hq == 0 {
		hq, _, _ = procOpenProcess.Call(0x0400, 0, uintptr(pid))
	}
	if hq != 0 {
		defer procCloseHandle.Call(hq)
		var sig, dyn uint32
		// ProcessSignaturePolicy = 8, ProcessDynamicCodePolicy = 2.
		procGetProcMitigation.Call(hq, 8, uintptr(unsafe.Pointer(&sig)), 4)
		procGetProcMitigation.Call(hq, 2, uintptr(unsafe.Pointer(&dyn)), 4)
		fmt.Printf("\nSignaturePolicy   = 0x%X  (MicrosoftSignedOnly=%v StoreSignedOnly=%v)\n",
			sig, sig&1 != 0, sig&2 != 0)
		fmt.Printf("DynamicCodePolicy = 0x%X  (ProhibitDynamicCode=%v)\n", dyn, dyn&1 != 0)
	} else {
		fmt.Println("\n(could not open a query handle — cannot read mitigation policy)")
	}

	// Can we ReadProcessMemory? (decides external no-injection dumper viability)
	hr, _, _ := procOpenProcess.Call(0x0010|0x1000, 0, uintptr(pid))
	if hr != 0 {
		defer procCloseHandle.Call(hr)
		buf := make([]byte, 2)
		var read uintptr
		ok, _, e := procReadProcessMemory.Call(hr, 0x140000000,
			uintptr(unsafe.Pointer(&buf[0])), 2, uintptr(unsafe.Pointer(&read)))
		fmt.Printf("ReadProcessMemory test @0x140000000: ok=%v read=%d (%v)\n", ok != 0, read, e)
	}

	fmt.Println("\nVERDICT:")
	fmt.Println("  MicrosoftSignedOnly=true => LoadLibrary of unsigned DLLs blocked; only")
	fmt.Println("    MANUAL MAPPING could load UE4SS (use `inject probe` for ACG check).")
	fmt.Println("  ProhibitDynamicCode=true => manual mapping's exec also blocked => pivot")
	fmt.Println("    to an EXTERNAL ReadProcessMemory usmap dumper (no injection).")
	fmt.Println("  VM_READ granted + RPM ok => external dumper viable regardless of policy.")
}

func main() {
	if len(os.Args) == 3 && os.Args[1] == "diag" {
		diag(os.Args[2])
		return
	}
	// probe mode: report whether the target allows allocating EXECUTABLE memory.
	// If PAGE_EXECUTE_READWRITE alloc fails, Arbitrary Code Guard (ACG) is on and
	// manual mapping is also blocked; if it succeeds, manual mapping is viable
	// (it sidesteps the signed-image check that blocks LoadLibrary).
	if len(os.Args) == 3 && os.Args[1] == "probe" {
		probePID := mustPID(os.Args[2])
		h, _, e := procOpenProcess.Call(processAllAccess, 0, uintptr(probePID))
		if h == 0 {
			fmt.Println("ERROR: OpenProcess failed (elevated?):", e)
			os.Exit(1)
		}
		defer procCloseHandle.Call(h)
		const pageExecRW = 0x40
		addr, _, ae := procVirtualAllocEx.Call(h, 0, 0x1000, memCommitReserve, pageExecRW)
		if addr == 0 {
			fmt.Println("ACG: ON — cannot allocate executable memory. Manual mapping is BLOCKED too.")
			fmt.Println("  err:", ae)
			os.Exit(0)
		}
		fmt.Println("ACG: OFF — executable allocation succeeded. Manual mapping is VIABLE.")
		os.Exit(0)
	}

	if len(os.Args) != 3 {
		fmt.Println(`usage: inject <process-name-or-pid> <dll-path>`)
		fmt.Println(`       inject probe <process-name-or-pid>`)
		os.Exit(2)
	}

	// Resolve PID.
	var pid uint32
	if n, err := strconv.Atoi(os.Args[1]); err == nil {
		pid = uint32(n)
	} else {
		p, err := findPID(os.Args[1])
		if err != nil {
			fmt.Println("ERROR:", err)
			os.Exit(1)
		}
		pid = p
	}

	dllPath, err := syscall.UTF16FromString(os.Args[2])
	if err != nil {
		fmt.Println("ERROR: bad dll path:", err)
		os.Exit(1)
	}
	if _, err := os.Stat(os.Args[2]); err != nil {
		fmt.Println("ERROR: dll not found:", os.Args[2])
		os.Exit(1)
	}
	fmt.Printf("Target PID %d, injecting %s\n", pid, os.Args[2])

	hProc, _, err := procOpenProcess.Call(processAllAccess, 0, uintptr(pid))
	if hProc == 0 {
		fmt.Println("ERROR: OpenProcess failed (run elevated? game is elevated):", err)
		os.Exit(1)
	}
	defer procCloseHandle.Call(hProc)

	// Allocate + write the DLL path (wide string) into the target.
	size := uintptr(len(dllPath) * 2)
	remote, _, err := procVirtualAllocEx.Call(hProc, 0, size, memCommitReserve, pageReadWrite)
	if remote == 0 {
		fmt.Println("ERROR: VirtualAllocEx failed:", err)
		os.Exit(1)
	}
	var written uintptr
	ok, _, err := procWriteProcessMemory.Call(hProc, remote,
		uintptr(unsafe.Pointer(&dllPath[0])), size, uintptr(unsafe.Pointer(&written)))
	if ok == 0 {
		fmt.Println("ERROR: WriteProcessMemory failed:", err)
		os.Exit(1)
	}

	// LoadLibraryW lives in kernel32, which is mapped at the same base in every
	// process this boot — so its local address is valid in the target.
	hK32, _, _ := procGetModuleHandleW.Call(uintptr(unsafe.Pointer(syscall.StringToUTF16Ptr("kernel32.dll"))))
	loadLib, _, _ := procGetProcAddress.Call(hK32, uintptr(unsafe.Pointer(syscall.StringBytePtr("LoadLibraryW"))))
	if loadLib == 0 {
		fmt.Println("ERROR: could not resolve LoadLibraryW")
		os.Exit(1)
	}

	thread, _, err := procCreateRemoteThread.Call(hProc, 0, 0, loadLib, remote, 0, 0)
	if thread == 0 {
		fmt.Println("ERROR: CreateRemoteThread failed:", err)
		os.Exit(1)
	}
	defer procCloseHandle.Call(thread)

	procWaitForSingleObject.Call(thread, infinite)
	var exitCode uint32
	procGetExitCodeThread.Call(thread, uintptr(unsafe.Pointer(&exitCode)))

	// Definitive check: is the module actually present in the target now? The thread
	// exit code is only 32-bit (truncates the 64-bit HMODULE), so it's unreliable.
	base := filepath.Base(os.Args[2])
	if moduleLoaded(pid, base) {
		fmt.Printf("OK: %s is loaded in the target (verified via module list).\n", base)
		fmt.Println("Switch to the game and press Ctrl+NumPad6 to dump Mappings.usmap.")
		return
	}
	fmt.Printf("FAILED: %s did NOT load in the target (remote exit code 0x%X).\n", base, exitCode)
	fmt.Println("If a known MS-signed DLL also fails to load this way, the process is")
	fmt.Println("blocking non-system DLL injection (signature mitigation / packer).")
	os.Exit(1)
}

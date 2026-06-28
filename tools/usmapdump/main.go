// usmapdump — an EXTERNAL, read-only Unreal .usmap dumper for SUPERVIVE.
//
// Why external: SUPERVIVE-Win64-Shipping.exe runs with Code Integrity Guard (CIG) —
// only Microsoft-signed images load, so we cannot inject an unsigned dumper DLL
// (verified: signed mscms.dll injects, our canary.dll does not). Instead of injecting,
// this tool reads the live process's memory via ReadProcessMemory and reconstructs the
// mappings from outside. Nothing is ever loaded or executed in the game, so neither CIG,
// ACG, nor the packer's anti-debug can see us — we only hold a VM_READ handle (the same
// access the OS already grants; proven during the inject diag).
//
// Build:  go build -trimpath -o usmapdump.exe .
// Run (ELEVATED, game at main menu):
//   usmapdump.exe info "SUPERVIVE-Win64-Shipping.exe"
//
// MILESTONE R2.1 (this file): attach read-only, resolve the REAL module base/size,
// parse the PE + section table straight out of live memory, and map the executable
// regions that later milestones pattern-scan for GNames / GUObjectArray. No reflection
// walking yet — this proves the RPM substrate end to end.
package main

import (
	"encoding/binary"
	"fmt"
	"os"
	"strconv"
	"strings"
	"syscall"
	"unsafe"
)

var (
	kernel32                 = syscall.NewLazyDLL("kernel32.dll")
	procOpenProcess          = kernel32.NewProc("OpenProcess")
	procReadProcessMemory    = kernel32.NewProc("ReadProcessMemory")
	procVirtualQueryEx       = kernel32.NewProc("VirtualQueryEx")
	procCloseHandle          = kernel32.NewProc("CloseHandle")
	procCreateToolhelp32Snap = kernel32.NewProc("CreateToolhelp32Snapshot")
	procProcess32FirstW      = kernel32.NewProc("Process32FirstW")
	procProcess32NextW       = kernel32.NewProc("Process32NextW")
	procModule32FirstW       = kernel32.NewProc("Module32FirstW")
	procModule32NextW        = kernel32.NewProc("Module32NextW")
)

const (
	processVMRead         = 0x0010
	processQueryLimited   = 0x1000
	th32csSnapProcess     = 0x00000002
	th32csSnapModule      = 0x00000008
	th32csSnapModule32    = 0x00000010
	imageScnMemExecute    = 0x20000000
	imageScnMemWrite      = 0x80000000
	imageScnMemRead       = 0x40000000
)

// ---- process / module discovery -------------------------------------------------

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

func findPID(name string) (uint32, error) {
	snap, _, err := procCreateToolhelp32Snap.Call(th32csSnapProcess, 0)
	if snap == 0 || snap == ^uintptr(0) {
		return 0, fmt.Errorf("snapshot failed: %v", err)
	}
	defer procCloseHandle.Call(snap)
	var pe processEntry32
	pe.Size = uint32(unsafe.Sizeof(pe))
	ret, _, _ := procProcess32FirstW.Call(snap, uintptr(unsafe.Pointer(&pe)))
	for ret != 0 {
		if syscall.UTF16ToString(pe.ExeFile[:]) == name {
			return pe.ProcessID, nil
		}
		ret, _, _ = procProcess32NextW.Call(snap, uintptr(unsafe.Pointer(&pe)))
	}
	return 0, fmt.Errorf("process %q not found (is the game running?)", name)
}

// moduleBaseSize returns the live load address + size of the named module.
func moduleBaseSize(pid uint32, baseName string) (uintptr, uint32, error) {
	snap, _, _ := procCreateToolhelp32Snap.Call(th32csSnapModule|th32csSnapModule32, uintptr(pid))
	if snap == 0 || snap == ^uintptr(0) {
		return 0, 0, fmt.Errorf("module snapshot failed (elevated?)")
	}
	defer procCloseHandle.Call(snap)
	var me moduleEntry32
	me.Size = uint32(unsafe.Sizeof(me))
	ret, _, _ := procModule32FirstW.Call(snap, uintptr(unsafe.Pointer(&me)))
	for ret != 0 {
		if strings.EqualFold(syscall.UTF16ToString(me.ModuleName[:]), baseName) {
			return me.ModBaseAddr, me.ModBaseSize, nil
		}
		ret, _, _ = procModule32NextW.Call(snap, uintptr(unsafe.Pointer(&me)))
	}
	return 0, 0, fmt.Errorf("module %q not found in PID %d", baseName, pid)
}

// ---- the read substrate ----------------------------------------------------------

// reader wraps a process handle with region-aware ReadProcessMemory. Every later
// milestone (FName decode, object iteration, property walk) reads through this.
type reader struct {
	h uintptr
}

// read fills buf from the target at addr. Returns the number of bytes actually read;
// a short read (crossing into an unmapped page) is NOT fatal — callers decide.
func (r *reader) read(addr uintptr, buf []byte) (int, error) {
	if len(buf) == 0 {
		return 0, nil
	}
	var n uintptr
	ok, _, e := procReadProcessMemory.Call(r.h, addr,
		uintptr(unsafe.Pointer(&buf[0])), uintptr(len(buf)), uintptr(unsafe.Pointer(&n)))
	if ok == 0 && n == 0 {
		return 0, e
	}
	return int(n), nil
}

func (r *reader) u32(addr uintptr) (uint32, error) {
	var b [4]byte
	if _, err := r.read(addr, b[:]); err != nil {
		return 0, err
	}
	return binary.LittleEndian.Uint32(b[:]), nil
}

// memBasicInfo mirrors MEMORY_BASIC_INFORMATION (x64).
type memBasicInfo struct {
	BaseAddress       uintptr
	AllocationBase    uintptr
	AllocationProtect uint32
	_                 uint32
	RegionSize        uintptr
	State             uint32
	Protect           uint32
	Type              uint32
	_                 uint32
}

func (r *reader) query(addr uintptr) (memBasicInfo, bool) {
	var mbi memBasicInfo
	ret, _, _ := procVirtualQueryEx.Call(r.h, addr,
		uintptr(unsafe.Pointer(&mbi)), unsafe.Sizeof(mbi))
	return mbi, ret != 0
}

// ---- PE parsing out of live memory ----------------------------------------------

type section struct {
	name                       string
	vaddr                      uintptr // absolute runtime VA (base + RVA)
	vsize                      uint32
	exec, write, readf         bool
}

type peInfo struct {
	base        uintptr
	sizeOfImage uint32
	sections    []section
}

func parsePE(r *reader, base uintptr) (*peInfo, error) {
	hdr := make([]byte, 0x1000) // DOS + NT + section headers comfortably fit
	if n, err := r.read(base, hdr); err != nil || n < 0x200 {
		return nil, fmt.Errorf("read PE headers @0x%X failed (n=%d): %v", base, n, err)
	}
	if hdr[0] != 'M' || hdr[1] != 'Z' {
		return nil, fmt.Errorf("no MZ at base 0x%X (got %02X %02X)", base, hdr[0], hdr[1])
	}
	eLfanew := binary.LittleEndian.Uint32(hdr[0x3C:])
	if eLfanew+0x108 > uint32(len(hdr)) {
		return nil, fmt.Errorf("e_lfanew 0x%X out of range", eLfanew)
	}
	nt := hdr[eLfanew:]
	if nt[0] != 'P' || nt[1] != 'E' || nt[2] != 0 || nt[3] != 0 {
		return nil, fmt.Errorf("no PE signature at e_lfanew 0x%X", eLfanew)
	}
	// IMAGE_FILE_HEADER follows the 4-byte signature.
	fileHdr := nt[4:]
	numSections := binary.LittleEndian.Uint16(fileHdr[2:])
	sizeOfOptional := binary.LittleEndian.Uint16(fileHdr[16:])
	opt := fileHdr[20:] // IMAGE_OPTIONAL_HEADER64
	if magic := binary.LittleEndian.Uint16(opt[0:]); magic != 0x20B {
		return nil, fmt.Errorf("not a PE32+ image (optional magic 0x%X)", magic)
	}
	sizeOfImage := binary.LittleEndian.Uint32(opt[56:])

	// Section headers start right after the optional header.
	secStart := uint32(eLfanew) + 4 + 20 + uint32(sizeOfOptional)
	pe := &peInfo{base: base, sizeOfImage: sizeOfImage}
	for i := uint32(0); i < uint32(numSections); i++ {
		off := secStart + i*40
		if off+40 > uint32(len(hdr)) {
			break
		}
		s := hdr[off : off+40]
		name := strings.TrimRight(string(s[0:8]), "\x00")
		vsize := binary.LittleEndian.Uint32(s[8:])
		rva := binary.LittleEndian.Uint32(s[12:])
		chars := binary.LittleEndian.Uint32(s[36:])
		pe.sections = append(pe.sections, section{
			name:  name,
			vaddr: base + uintptr(rva),
			vsize: vsize,
			exec:  chars&imageScnMemExecute != 0,
			write: chars&imageScnMemWrite != 0,
			readf: chars&imageScnMemRead != 0,
		})
	}
	return pe, nil
}

// ---- commands --------------------------------------------------------------------

func mustOpen(name string) (*reader, uint32, uintptr, uint32) {
	pid, err := findPID(name)
	if err != nil {
		if n, e2 := strconv.Atoi(name); e2 == nil {
			pid = uint32(n)
		} else {
			fmt.Println("ERROR:", err)
			os.Exit(1)
		}
	}
	h, _, e := procOpenProcess.Call(processVMRead|processQueryLimited, 0, uintptr(pid))
	if h == 0 {
		fmt.Println("ERROR: OpenProcess(VM_READ) failed — run elevated (game is elevated):", e)
		os.Exit(1)
	}
	base, size, err := moduleBaseSize(pid, name)
	if err != nil {
		fmt.Println("ERROR:", err)
		os.Exit(1)
	}
	return &reader{h: h}, pid, base, size
}

func cmdInfo(name string) {
	r, pid, base, size := mustOpen(name)
	defer procCloseHandle.Call(r.h)
	fmt.Printf("PID %d  module %q\n", pid, name)
	fmt.Printf("  module base : 0x%X\n", base)
	fmt.Printf("  module size : 0x%X (%.1f MB)\n", size, float64(size)/(1024*1024))

	pe, err := parsePE(r, base)
	if err != nil {
		fmt.Println("ERROR: PE parse:", err)
		fmt.Println("  (if this fails, RPM at the real base isn't working — the whole route is blocked)")
		os.Exit(1)
	}
	fmt.Printf("  SizeOfImage : 0x%X\n", pe.sizeOfImage)
	fmt.Printf("  sections    : %d\n\n", len(pe.sections))
	fmt.Printf("  %-10s %-18s %-12s %s\n", "NAME", "RUNTIME VA", "VSIZE", "FLAGS")
	var firstExec section
	for _, s := range pe.sections {
		flags := ""
		if s.readf {
			flags += "R"
		}
		if s.write {
			flags += "W"
		}
		if s.exec {
			flags += "X"
		}
		fmt.Printf("  %-10s 0x%-16X 0x%-10X %s\n", s.name, s.vaddr, s.vsize, flags)
		if s.exec && firstExec.vaddr == 0 {
			firstExec = s
		}
	}

	// Prove a real read inside .text: dump the first 16 bytes.
	if firstExec.vaddr != 0 {
		b := make([]byte, 16)
		n, _ := r.read(firstExec.vaddr, b)
		fmt.Printf("\n  sample read of %s @0x%X (%d bytes): % X\n", firstExec.name, firstExec.vaddr, n, b[:n])
		fmt.Println("\nR2.1 OK: external ReadProcessMemory works at the real base and into executable")
		fmt.Println("sections. The scan substrate is ready — next milestone locates GNames/GUObjectArray.")
	}
}

func main() {
	if len(os.Args) == 3 && os.Args[1] == "info" {
		cmdInfo(os.Args[2])
		return
	}
	if len(os.Args) == 3 && os.Args[1] == "names" {
		cmdNames(os.Args[2])
		return
	}
	if len(os.Args) == 3 && os.Args[1] == "objects" {
		cmdObjects(os.Args[2])
		return
	}
	if len(os.Args) == 3 && os.Args[1] == "extract" {
		cmdExtract(os.Args[2])
		return
	}
	if len(os.Args) == 3 && os.Args[1] == "assetmgr" {
		cmdAssetMgr(os.Args[2])
		return
	}
	if len(os.Args) == 4 && os.Args[1] == "strings" {
		cmdStrings(os.Args[2], os.Args[3])
		return
	}
	if len(os.Args) == 4 && os.Args[1] == "xref" {
		cmdXref(os.Args[2], os.Args[3])
		return
	}
	if len(os.Args) == 4 && os.Args[1] == "disasm" {
		cmdDisasm(os.Args[2], os.Args[3])
		return
	}
	if len(os.Args) == 5 && os.Args[1] == "wstrings" {
		cmdWStrings(os.Args[2], os.Args[3], os.Args[4])
		return
	}
	if len(os.Args) == 4 && os.Args[1] == "peek" {
		cmdPeek(os.Args[2], os.Args[3])
		return
	}
	if len(os.Args) == 3 && os.Args[1] == "threads" {
		cmdThreads(os.Args[2])
		return
	}
	if len(os.Args) == 3 && os.Args[1] == "findgametid" {
		cmdFindGameTid(os.Args[2])
		return
	}
	fmt.Println("usage: usmapdump info    <process-name-or-pid>   (R2.1: PE/section recon)")
	fmt.Println("       usmapdump names   <process-name-or-pid>   (R2.2: locate GNames, decode FNames)")
	fmt.Println("       usmapdump objects <process-name-or-pid>   (R2.3: locate GUObjectArray, iterate)")
	fmt.Println("       usmapdump extract <process-name-or-pid>   (R2.4: extract full schema)")
	os.Exit(2)
}

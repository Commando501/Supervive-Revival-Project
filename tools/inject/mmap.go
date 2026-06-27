// mmap.go — manual DLL mapper, Phase 1.
//
// Bypasses Code Integrity Guard (CIG / MicrosoftSignedOnly) by NEVER calling the
// Windows loader. The Windows loader is what enforces signature policy; if we copy
// the DLL bytes into the target and run them ourselves, the policy never gets a vote.
//
// What this does (and only this):
//   1. Read the DLL file from disk locally.
//   2. Parse the PE headers (DOS+NT64+sections+data dirs).
//   3. Stage the image in a LOCAL buffer the size the PE asked for.
//   4. Apply BASE RELOCATIONS to the local copy, choosing a delta from the address
//      we will allocate in the target.
//   5. Resolve the IMPORT TABLE: for each imported module, ensure it's loaded in the
//      target (CreateRemoteThread → LoadLibraryA — legal: imports are MS-signed system
//      DLLs like kernel32, user32, vcruntime, etc.); for each function, compute the
//      target-side address as (target_module_base + (local_proc_addr - local_module_base))
//      and write it into the IAT in our local buffer.
//   6. Allocate PAGE_EXECUTE_READWRITE memory in the target (ACG is OFF — confirmed
//      empirically; this is what gives us "execute" without needing the loader).
//   7. WriteProcessMemory the prepared image + a small x64 bootstrap shellcode.
//   8. CreateRemoteThread on the shellcode, which calls DllMain(imageBase,
//      DLL_PROCESS_ATTACH, 0).
//   9. Verify by reading the first two bytes of the target allocation expecting "MZ"
//      (proof bytes landed) — and by whatever side effect the DLL has (e.g. canary's
//      marker file).
//
// What this does NOT do yet (Phase 2 will add):
//   - TLS callbacks (DLL .tls directory's AddressOfCallBacks).
//   - Exception unwind table registration (RtlAddFunctionTable over .pdata).
//   The canary has none of these so Phase 1 alone is enough to test the mapper.
//
// What this never does:
//   - Anything that would dishonestly identify the module to AV/EDR (no PE header
//     erasure, no PEB linking). The mapped region looks exactly like what it is:
//     a manually-allocated executable region containing our DLL bytes.
//
// Usage:
//   inject mmap <process-name-or-pid> <dll-path>

package main

import (
	"encoding/binary"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"unsafe"
)

// ---------- PE constants & structs ----------

const (
	pageExecReadWrite = 0x40

	imgDosSig  = 0x5A4D     // "MZ"
	imgNtSig   = 0x00004550 // "PE\0\0"
	imgOpt64   = 0x20B      // PE32+ optional header magic
	imgRelHigh = 1
	imgRelLow  = 2
	imgRelHL   = 3 // not used on x64
	imgRelDir64 = 10 // the only x64 reloc type we actually need

	imgDirEntryImport       = 1
	imgDirEntryBaseReloc    = 5
	imgDirEntryTLS          = 9
	imgDirEntryException    = 3
	imgOrdinalFlag64        = uint64(1) << 63
)

type imageDosHeader struct {
	Magic    uint16
	_        [58]byte
	Lfanew   int32
}

type imageFileHeader struct {
	Machine              uint16
	NumberOfSections     uint16
	TimeDateStamp        uint32
	PointerToSymbolTable uint32
	NumberOfSymbols      uint32
	SizeOfOptionalHeader uint16
	Characteristics      uint16
}

type imageDataDirectory struct {
	VirtualAddress uint32
	Size           uint32
}

type imageOptionalHeader64 struct {
	Magic                       uint16
	MajorLinkerVersion          uint8
	MinorLinkerVersion          uint8
	SizeOfCode                  uint32
	SizeOfInitializedData       uint32
	SizeOfUninitializedData     uint32
	AddressOfEntryPoint         uint32
	BaseOfCode                  uint32
	ImageBase                   uint64
	SectionAlignment            uint32
	FileAlignment               uint32
	MajorOperatingSystemVersion uint16
	MinorOperatingSystemVersion uint16
	MajorImageVersion           uint16
	MinorImageVersion           uint16
	MajorSubsystemVersion       uint16
	MinorSubsystemVersion       uint16
	Win32VersionValue           uint32
	SizeOfImage                 uint32
	SizeOfHeaders               uint32
	CheckSum                    uint32
	Subsystem                   uint16
	DllCharacteristics          uint16
	SizeOfStackReserve          uint64
	SizeOfStackCommit           uint64
	SizeOfHeapReserve           uint64
	SizeOfHeapCommit            uint64
	LoaderFlags                 uint32
	NumberOfRvaAndSizes         uint32
	DataDirectory               [16]imageDataDirectory
}

type imageNtHeaders64 struct {
	Signature      uint32
	FileHeader     imageFileHeader
	OptionalHeader imageOptionalHeader64
}

type imageSectionHeader struct {
	Name                 [8]byte
	VirtualSize          uint32
	VirtualAddress       uint32
	SizeOfRawData        uint32
	PointerToRawData     uint32
	PointerToRelocations uint32
	PointerToLinenumbers uint32
	NumberOfRelocations  uint16
	NumberOfLinenumbers  uint16
	Characteristics      uint32
}

type imageBaseRelocation struct {
	VirtualAddress uint32
	SizeOfBlock    uint32
	// followed by SizeOfBlock-8 bytes of uint16 entries
}

type imageImportDescriptor struct {
	OriginalFirstThunk uint32 // RVA → INT (Import Name Table)
	TimeDateStamp      uint32
	ForwarderChain     uint32
	Name               uint32 // RVA → ASCII dll name
	FirstThunk         uint32 // RVA → IAT (overwritten with resolved addrs)
}

// IMAGE_TLS_DIRECTORY64 — the PE TLS data directory's payload.
// What matters for us: AddressOfCallBacks is a VA (absolute, post-relocation) pointing to
// a NULL-terminated array of PIMAGE_TLS_CALLBACK pointers. Each callback has DllMain's
// signature: (PVOID DllHandle, DWORD Reason, PVOID Reserved). MSVC stuffs critical CRT
// init here (atexit registration, EH frame setup); skipping them produces hard-to-debug
// crashes deep in std::__crt_callfn_with_arg.
type imageTlsDirectory64 struct {
	StartAddressOfRawData uint64
	EndAddressOfRawData   uint64
	AddressOfIndex        uint64
	AddressOfCallBacks    uint64 // VA, post-reloc, into the mapped image
	SizeOfZeroFill        uint32
	Characteristics       uint32
}

// ---------- helpers ----------

// readU16 / readU32 / readU64: little-endian reads from a byte slice at offset.
func readU16(b []byte, o int) uint16 { return binary.LittleEndian.Uint16(b[o:]) }
func readU32(b []byte, o int) uint32 { return binary.LittleEndian.Uint32(b[o:]) }
func readU64(b []byte, o int) uint64 { return binary.LittleEndian.Uint64(b[o:]) }
func writeU64(b []byte, o int, v uint64) {
	binary.LittleEndian.PutUint64(b[o:], v)
}

// cstr reads a NUL-terminated ASCII string from a byte slice starting at offset.
func cstr(b []byte, o int) string {
	end := o
	for end < len(b) && b[end] != 0 {
		end++
	}
	return string(b[o:end])
}

// ---------- manual mapper ----------

// manualMap loads dllPath into pid by parsing PE locally, applying relocations,
// resolving imports, copying the prepared image into target RWX memory, and
// invoking DllMain via a small x64 bootstrap shellcode.
func manualMap(pid uint32, dllPath string) error {
	// 1. Read the DLL file off disk.
	raw, err := os.ReadFile(dllPath)
	if err != nil {
		return fmt.Errorf("read dll: %w", err)
	}
	if len(raw) < 64 || readU16(raw, 0) != imgDosSig {
		return fmt.Errorf("not a PE file (no MZ)")
	}
	ntOff := int(int32(readU32(raw, 0x3C)))
	if ntOff <= 0 || ntOff+int(unsafe.Sizeof(imageNtHeaders64{})) > len(raw) {
		return fmt.Errorf("bad e_lfanew (%d)", ntOff)
	}
	if readU32(raw, ntOff) != imgNtSig {
		return fmt.Errorf("not a PE file (no PE\\0\\0)")
	}
	if readU16(raw, ntOff+24) != imgOpt64 {
		return fmt.Errorf("only 64-bit PE32+ supported (this DLL is 32-bit?)")
	}

	// Copy the NT headers into a typed struct for convenience.
	var nt imageNtHeaders64
	if err := binary.Read(newBR(raw[ntOff:]), binary.LittleEndian, &nt); err != nil {
		return fmt.Errorf("parse NT headers: %w", err)
	}
	if nt.FileHeader.Machine != 0x8664 {
		return fmt.Errorf("not x64 (Machine=0x%X)", nt.FileHeader.Machine)
	}
	sectionsOff := ntOff + 4 + int(unsafe.Sizeof(imageFileHeader{})) + int(nt.FileHeader.SizeOfOptionalHeader)
	numSecs := int(nt.FileHeader.NumberOfSections)

	// 2. Stage the image in a local buffer.
	image := make([]byte, nt.OptionalHeader.SizeOfImage)
	// Copy headers (everything before the first section's raw start, but capped at SizeOfHeaders).
	copy(image[:nt.OptionalHeader.SizeOfHeaders], raw[:nt.OptionalHeader.SizeOfHeaders])

	// Copy each section into its VirtualAddress within the local image.
	for i := 0; i < numSecs; i++ {
		var sh imageSectionHeader
		so := sectionsOff + i*int(unsafe.Sizeof(imageSectionHeader{}))
		if err := binary.Read(newBR(raw[so:]), binary.LittleEndian, &sh); err != nil {
			return fmt.Errorf("parse section %d: %w", i, err)
		}
		if sh.SizeOfRawData == 0 {
			continue // .bss-like, already zero in 'image'
		}
		end := int(sh.PointerToRawData) + int(sh.SizeOfRawData)
		if end > len(raw) {
			return fmt.Errorf("section %d raw out of range", i)
		}
		dstEnd := int(sh.VirtualAddress) + int(sh.SizeOfRawData)
		if dstEnd > len(image) {
			return fmt.Errorf("section %d virt out of range", i)
		}
		copy(image[sh.VirtualAddress:dstEnd], raw[sh.PointerToRawData:end])
	}

	// 3. Open the target process. ACG-off + signed-only-off-for-loader (irrelevant here:
	// we don't call the loader) means PAGE_EXECUTE_READWRITE alloc is allowed.
	hProc, _, e := procOpenProcess.Call(processAllAccess, 0, uintptr(pid))
	if hProc == 0 {
		return fmt.Errorf("OpenProcess: %v (run elevated?)", e)
	}
	defer procCloseHandle.Call(hProc)

	// 4. Reserve+commit the image region in target with EXECUTE permissions.
	remoteBase, _, e := procVirtualAllocEx.Call(hProc, 0,
		uintptr(nt.OptionalHeader.SizeOfImage), memCommitReserve, pageExecReadWrite)
	if remoteBase == 0 {
		return fmt.Errorf("VirtualAllocEx(RWX) failed: %v (ACG on?)", e)
	}
	fmt.Printf("  remote image base: 0x%X (size 0x%X)\n",
		remoteBase, nt.OptionalHeader.SizeOfImage)

	// 5. Apply base relocations to the LOCAL image, with delta = (remoteBase - preferredBase).
	delta := uint64(remoteBase) - nt.OptionalHeader.ImageBase
	if delta != 0 {
		relocDir := nt.OptionalHeader.DataDirectory[imgDirEntryBaseReloc]
		if relocDir.Size == 0 {
			// Some DLLs strip relocs; only safe if mapped at preferred base. We're not.
			return fmt.Errorf("delta=0x%X but image has no .reloc directory", delta)
		}
		if err := applyRelocs(image, relocDir.VirtualAddress, relocDir.Size, delta); err != nil {
			return fmt.Errorf("reloc: %w", err)
		}
		fmt.Printf("  relocations applied (delta 0x%X)\n", delta)
	} else {
		fmt.Printf("  no relocations needed (base matched preferred)\n")
	}

	// 6. Resolve imports.
	impDir := nt.OptionalHeader.DataDirectory[imgDirEntryImport]
	if impDir.Size != 0 {
		if err := resolveImports(image, impDir.VirtualAddress, hProc, pid); err != nil {
			return fmt.Errorf("imports: %w", err)
		}
	} else {
		fmt.Printf("  no imports\n")
	}

	// 7. Write the prepared image into the target.
	var written uintptr
	ok, _, e := procWriteProcessMemory.Call(hProc, remoteBase,
		uintptr(unsafe.Pointer(&image[0])), uintptr(len(image)), uintptr(unsafe.Pointer(&written)))
	if ok == 0 || int(written) != len(image) {
		return fmt.Errorf("WriteProcessMemory image: %v (written=%d/%d)", e, written, len(image))
	}

	// 8. Build the x64 bootstrap shellcode. Three pieces to gather first:
	//    (a) DllMain address; (b) exception table info; (c) TLS callback list.
	dllMainAddr := uint64(remoteBase) + uint64(nt.OptionalHeader.AddressOfEntryPoint)
	if nt.OptionalHeader.AddressOfEntryPoint == 0 {
		return fmt.Errorf("DLL has no entry point (no DllMain?)")
	}
	bi := bootstrapInfo{
		imageBase:   uint64(remoteBase),
		dllMainAddr: dllMainAddr,
	}

	// 8a. Exception unwind table. The .pdata data directory points to an array of
	// RUNTIME_FUNCTION (3x DWORD = 12 bytes each). Without registering this via
	// RtlAddFunctionTable, the first thrown C++ exception (and STL throws a LOT)
	// produces a hard process crash because the unwinder can't find our image.
	excDir := nt.OptionalHeader.DataDirectory[imgDirEntryException]
	if excDir.Size > 0 {
		bi.exceptionTable = uint64(remoteBase) + uint64(excDir.VirtualAddress)
		bi.exceptionCount = uint64(excDir.Size / 12)
		fn, err := resolveExternalProc(pid, "ntdll.dll", "RtlAddFunctionTable")
		if err != nil {
			return fmt.Errorf("resolve RtlAddFunctionTable: %w", err)
		}
		bi.rtlAddFnTable = uint64(fn)
		fmt.Printf("  exception table: 0x%X entries at 0x%X (will RtlAddFunctionTable)\n",
			bi.exceptionCount, bi.exceptionTable)
	}

	// 8b. TLS callbacks. After relocs, IMAGE_TLS_DIRECTORY64.AddressOfCallBacks already
	// holds the FINAL target VA (relocations fix it). Read the pointer array from the
	// local image at the equivalent offset. NULL terminates the list.
	tlsDir := nt.OptionalHeader.DataDirectory[imgDirEntryTLS]
	if tlsDir.Size > 0 {
		var td imageTlsDirectory64
		if err := binary.Read(newBR(image[tlsDir.VirtualAddress:]), binary.LittleEndian, &td); err != nil {
			return fmt.Errorf("parse TLS dir: %w", err)
		}
		// td.AddressOfCallBacks is now a target VA. Compute its offset within the image.
		if td.AddressOfCallBacks != 0 {
			cbOff := int(td.AddressOfCallBacks - uint64(remoteBase))
			for i := 0; ; i++ {
				if cbOff+8 > len(image) {
					return fmt.Errorf("TLS callback list past image at #%d", i)
				}
				cb := readU64(image, cbOff)
				if cb == 0 {
					break
				}
				bi.tlsCallbacks = append(bi.tlsCallbacks, cb)
				cbOff += 8
			}
		}
		if len(bi.tlsCallbacks) > 0 {
			imgLo := uint64(remoteBase)
			imgHi := imgLo + uint64(nt.OptionalHeader.SizeOfImage)
			fmt.Printf("  TLS callbacks: %d (will invoke before DllMain)\n", len(bi.tlsCallbacks))
			// Diagnostic: each callback addr should be within [imgLo, imgHi). If it's at
			// the preferred base (e.g. 0x180001xxx) instead, reloc didn't fix the
			// pointer in .CRT$XLB and we'd jump into garbage.
			for i, cb := range bi.tlsCallbacks {
				in := cb >= imgLo && cb < imgHi
				mark := "✓ in-image"
				if !in {
					mark = "✗ OUT OF IMAGE — reloc missed this pointer"
				}
				fmt.Printf("    cb[%d] = 0x%X  %s\n", i, cb, mark)
			}
		}
	}

	shellcode := buildBootstrap(bi)

	// Allocate a separate RWX region for the shellcode; keep it tiny and away from the image.
	shellAddr, _, e := procVirtualAllocEx.Call(hProc, 0,
		uintptr(len(shellcode)), memCommitReserve, pageExecReadWrite)
	if shellAddr == 0 {
		return fmt.Errorf("VirtualAllocEx(shellcode): %v", e)
	}
	ok, _, e = procWriteProcessMemory.Call(hProc, shellAddr,
		uintptr(unsafe.Pointer(&shellcode[0])), uintptr(len(shellcode)), uintptr(unsafe.Pointer(&written)))
	if ok == 0 {
		return fmt.Errorf("WriteProcessMemory shellcode: %v", e)
	}

	// 9. Fire the bootstrap. We don't pass an argument; the shellcode has everything baked in.
	thread, _, e := procCreateRemoteThread.Call(hProc, 0, 0, shellAddr, 0, 0, 0)
	if thread == 0 {
		return fmt.Errorf("CreateRemoteThread(shellcode): %v", e)
	}
	defer procCloseHandle.Call(thread)
	procWaitForSingleObject.Call(thread, infinite)
	var exitCode uint32
	procGetExitCodeThread.Call(thread, uintptr(unsafe.Pointer(&exitCode)))
	fmt.Printf("  DllMain remote-thread exit: 0x%X (DllMain returned BOOL; nonzero = OK)\n", exitCode)

	// 10. Verify bytes landed: read first 2 bytes at remoteBase, expect 'MZ'.
	var verify [2]byte
	var readN uintptr
	procReadProcessMemory.Call(hProc, remoteBase,
		uintptr(unsafe.Pointer(&verify[0])), 2, uintptr(unsafe.Pointer(&readN)))
	if verify[0] != 'M' || verify[1] != 'Z' {
		return fmt.Errorf("verify: image bytes not at remote base (got %v)", verify)
	}
	fmt.Printf("  verify: MZ at 0x%X ✓\n", remoteBase)
	return nil
}

// applyRelocs walks the .reloc directory and applies IMAGE_REL_BASED_DIR64 fixups.
// The directory is a chain of IMAGE_BASE_RELOCATION blocks; each block has a 4-byte
// VirtualAddress + 4-byte SizeOfBlock, followed by (SizeOfBlock-8)/2 uint16 entries
// where the high nibble is the type and the low 12 bits are the offset within the page.
func applyRelocs(image []byte, dirRVA, dirSize uint32, delta uint64) error {
	off := int(dirRVA)
	end := off + int(dirSize)
	for off < end {
		if off+8 > len(image) {
			return fmt.Errorf("reloc block header past image")
		}
		blockRVA := readU32(image, off)
		blockSize := readU32(image, off+4)
		if blockSize < 8 || off+int(blockSize) > len(image) {
			return fmt.Errorf("bad reloc block (size %d)", blockSize)
		}
		entries := (int(blockSize) - 8) / 2
		for i := 0; i < entries; i++ {
			e := readU16(image, off+8+i*2)
			typ := e >> 12
			pageOff := int(e & 0x0FFF)
			switch typ {
			case 0:
				// IMAGE_REL_BASED_ABSOLUTE — used as padding, skip.
			case imgRelDir64:
				where := int(blockRVA) + pageOff
				if where+8 > len(image) {
					return fmt.Errorf("reloc target past image")
				}
				v := readU64(image, where)
				writeU64(image, where, v+delta)
			default:
				return fmt.Errorf("unsupported reloc type %d (only DIR64 expected on x64)", typ)
			}
		}
		off += int(blockSize)
	}
	return nil
}

// resolveImports walks the import descriptor table and writes resolved function
// addresses into each IAT entry in the LOCAL image.
//
// The trick that avoids needing GetProcAddress in the target: a system DLL is mapped
// at the SAME image bytes (same code, same exports, same RVAs) in every process
// during the boot. So if module M is at base bTgt in the target and base bUs in our
// process, then the address of function F in the target is bTgt + (procAddr(F) - bUs).
// This works for kernel32, user32, ntdll, vcruntime, msvcp, etc. — anything signed.
func resolveImports(image []byte, dirRVA uint32, hProc uintptr, pid uint32) error {
	descSize := int(unsafe.Sizeof(imageImportDescriptor{}))
	off := int(dirRVA)
	for {
		if off+descSize > len(image) {
			return fmt.Errorf("import desc past image")
		}
		var d imageImportDescriptor
		if err := binary.Read(newBR(image[off:]), binary.LittleEndian, &d); err != nil {
			return fmt.Errorf("parse import desc: %w", err)
		}
		if d.Name == 0 && d.FirstThunk == 0 {
			return nil // null terminator
		}
		dllName := cstr(image, int(d.Name))

		// Ensure dllName is loaded locally (we need its base + GetProcAddress).
		localMod, _, _ := procGetModuleHandleW.Call(uintptr(unsafe.Pointer(syscall.StringToUTF16Ptr(dllName))))
		if localMod == 0 {
			h, err := syscall.LoadLibrary(dllName)
			if err != nil {
				return fmt.Errorf("LoadLibrary(%s) locally: %w", dllName, err)
			}
			localMod = uintptr(h)
		}

		// Resolve "api set" forwarders (api-ms-win-*) to their real underlying DLL.
		// E.g. LoadLibrary("api-ms-win-crt-heap-l1-1-0.dll") actually returns the
		// handle of ucrtbase.dll. The target's Toolhelp module list enumerates the
		// real name (ucrtbase.dll), not the api-set alias, so we must look up by real
		// name. Harmless for normal DLLs — realName == dllName then.
		realName := resolveRealModuleName(localMod, dllName)
		display := dllName
		if !strings.EqualFold(realName, dllName) {
			display = fmt.Sprintf("%s → %s", dllName, realName)
		}
		fmt.Printf("  import: %s\n", display)

		// Ensure loaded in target by REAL name. moduleLoaded is from main.go.
		if !moduleLoaded(pid, realName) {
			// Use the api-set name (not the real one) for remote LoadLibrary so Windows
			// does the same forwarding inside the target.
			if err := remoteLoadLibrary(hProc, dllName); err != nil {
				return fmt.Errorf("remote LoadLibrary %s: %w", dllName, err)
			}
			if !moduleLoaded(pid, realName) {
				return fmt.Errorf("module %s (real: %s) still not loaded after remote LoadLibrary", dllName, realName)
			}
		}
		targetBase := moduleBase(pid, realName)
		if targetBase == 0 {
			return fmt.Errorf("could not find target base of %s (real: %s)", dllName, realName)
		}

		// Walk the INT (OriginalFirstThunk) for names, write IAT (FirstThunk) with resolved addrs.
		intRVA := d.OriginalFirstThunk
		if intRVA == 0 {
			intRVA = d.FirstThunk // pre-bound import table — same data
		}
		iat := int(d.FirstThunk)
		for i := 0; ; i++ {
			thunkOff := int(intRVA) + i*8
			if thunkOff+8 > len(image) {
				return fmt.Errorf("thunk past image")
			}
			thunk := readU64(image, thunkOff)
			if thunk == 0 {
				break
			}
			var fnAddr uintptr
			if thunk&imgOrdinalFlag64 != 0 {
				ordinal := uintptr(thunk & 0xFFFF)
				fnAddr, _, _ = procGetProcAddress.Call(localMod, ordinal)
			} else {
				// IMAGE_IMPORT_BY_NAME: 2-byte Hint, then ASCII name.
				nameRVA := int(thunk & 0x7FFFFFFF)
				name := cstr(image, nameRVA+2)
				fnAddr, _, _ = procGetProcAddress.Call(localMod,
					uintptr(unsafe.Pointer(syscall.StringBytePtr(name))))
			}
			if fnAddr == 0 {
				return fmt.Errorf("could not resolve import #%d from %s", i, dllName)
			}
			rva := uint64(fnAddr) - uint64(localMod)
			writeU64(image, iat+i*8, uint64(targetBase)+rva)
		}
		off += descSize
	}
}

// remoteLoadLibrary calls LoadLibraryA(dllName) in the target via CreateRemoteThread.
// Used to bring an import dependency into the target if it isn't already loaded.
// LoadLibraryA exists in kernel32 at the same address in every process; OK to use ours.
func remoteLoadLibrary(hProc uintptr, dllName string) error {
	loadLibA, _, _ := procGetProcAddress.Call(
		mustGetModuleHandle("kernel32.dll"),
		uintptr(unsafe.Pointer(syscall.StringBytePtr("LoadLibraryA"))),
	)
	if loadLibA == 0 {
		return fmt.Errorf("could not resolve LoadLibraryA")
	}
	name := append([]byte(dllName), 0)
	remote, _, e := procVirtualAllocEx.Call(hProc, 0, uintptr(len(name)), memCommitReserve, pageReadWrite)
	if remote == 0 {
		return fmt.Errorf("alloc name: %v", e)
	}
	var w uintptr
	procWriteProcessMemory.Call(hProc, remote, uintptr(unsafe.Pointer(&name[0])),
		uintptr(len(name)), uintptr(unsafe.Pointer(&w)))
	th, _, e := procCreateRemoteThread.Call(hProc, 0, 0, loadLibA, remote, 0, 0)
	if th == 0 {
		return fmt.Errorf("CreateRemoteThread(LoadLibraryA): %v", e)
	}
	defer procCloseHandle.Call(th)
	procWaitForSingleObject.Call(th, infinite)
	return nil
}

// resolveRealModuleName takes a local HMODULE and the name we tried to load, and
// returns the BASENAME of the actual file that handle refers to. For api-set DLLs
// (api-ms-win-*) Windows transparently forwards to a real implementing DLL —
// typically ucrtbase.dll for the crt-* set — and our target-side lookup must use
// the forwarded name since that's what Toolhelp enumerates.
func resolveRealModuleName(hModule uintptr, fallback string) string {
	if hModule == 0 {
		return fallback
	}
	var buf [260]uint16
	n, _, _ := procGetModuleFileNameW.Call(hModule, uintptr(unsafe.Pointer(&buf[0])), uintptr(len(buf)))
	if n == 0 {
		return fallback
	}
	return filepath.Base(syscall.UTF16ToString(buf[:n]))
}

func mustGetModuleHandle(name string) uintptr {
	h, _, _ := procGetModuleHandleW.Call(uintptr(unsafe.Pointer(syscall.StringToUTF16Ptr(name))))
	return h
}

// resolveExternalProc returns the address of procName in dllName as it lives IN THE
// TARGET process. The trick (already used for IAT resolution): a system DLL has
// identical bytes at identical RVAs in every process this boot, so
//   target_addr = target_module_base + (local_proc_addr - local_module_base).
// For ntdll/kernel32/user32 etc. this is reliable; for non-system DLLs the bases will
// still match on x64 since ASLR is per-DLL-per-boot, not per-process.
func resolveExternalProc(pid uint32, dllName, procName string) (uintptr, error) {
	localMod, _, _ := procGetModuleHandleW.Call(uintptr(unsafe.Pointer(syscall.StringToUTF16Ptr(dllName))))
	if localMod == 0 {
		h, err := syscall.LoadLibrary(dllName)
		if err != nil {
			return 0, fmt.Errorf("LoadLibrary(%s) locally: %w", dllName, err)
		}
		localMod = uintptr(h)
	}
	localProc, _, _ := procGetProcAddress.Call(localMod,
		uintptr(unsafe.Pointer(syscall.StringBytePtr(procName))))
	if localProc == 0 {
		return 0, fmt.Errorf("%s!%s not found locally", dllName, procName)
	}
	targetBase := moduleBase(pid, dllName)
	if targetBase == 0 {
		return 0, fmt.Errorf("%s not loaded in target", dllName)
	}
	return targetBase + (localProc - localMod), nil
}

// emit3ArgCall appends x64 shellcode that calls `fn(arg1, arg2, arg3)` per the
// Windows x64 ABI (args in rcx, rdx, r8; 32-byte shadow space + 8 align before call).
//
// Bytes (50 total per call):
//   48 B9 <arg1 qword>           mov  rcx, arg1
//   48 BA <arg2 qword>           mov  rdx, arg2
//   49 B8 <arg3 qword>           mov  r8,  arg3
//   48 B8 <fn   qword>           mov  rax, fn
//   48 83 EC 28                  sub  rsp, 0x28
//   FF D0                        call rax
//   48 83 C4 28                  add  rsp, 0x28
//
// Using full 64-bit immediate moves for args (incl. DWORD-typed ones) wastes a few bytes
// vs. a tighter encoding, but trades nothing functionally — high bits of rcx/rdx/r8 are
// ignored by callees that expect DWORD/BOOLEAN parameters.
func emit3ArgCall(buf []byte, arg1, arg2, arg3, fn uint64) []byte {
	buf = append(buf, 0x48, 0xB9); buf = appendU64(buf, arg1)
	buf = append(buf, 0x48, 0xBA); buf = appendU64(buf, arg2)
	buf = append(buf, 0x49, 0xB8); buf = appendU64(buf, arg3)
	buf = append(buf, 0x48, 0xB8); buf = appendU64(buf, fn)
	buf = append(buf, 0x48, 0x83, 0xEC, 0x28)
	buf = append(buf, 0xFF, 0xD0)
	buf = append(buf, 0x48, 0x83, 0xC4, 0x28)
	return buf
}

// bootstrapInfo bundles everything the bootstrap shellcode needs. Zero values for fields
// the DLL doesn't use cause those steps to be skipped (so a no-TLS / no-exception DLL
// like canary.dll gets the same minimal shellcode Phase 1 produced).
type bootstrapInfo struct {
	imageBase       uint64
	dllMainAddr     uint64

	// Exception table registration via RtlAddFunctionTable(table, count, baseAddr).
	exceptionTable  uint64
	exceptionCount  uint64
	rtlAddFnTable   uint64 // target address of ntdll!RtlAddFunctionTable; 0 = skip

	// TLS callbacks to invoke before DllMain. Each gets called like DllMain itself.
	tlsCallbacks    []uint64
}

// buildBootstrap emits the full x64 shellcode that, on a remote thread, will:
//   1. [optional] register the exception unwind table for our mapped image
//   2. [optional] call every TLS callback with (imageBase, DLL_PROCESS_ATTACH, 0)
//   3. call DllMain(imageBase, DLL_PROCESS_ATTACH, 0)
//   4. propagate DllMain's BOOL return as the thread's exit code (mov rcx, rax + ret)
//
// Each callee adheres to Windows x64 ABI; we reset the stack between calls so we never
// drift out of alignment.
func buildBootstrap(bi bootstrapInfo) []byte {
	const dllProcessAttach = 1
	buf := make([]byte, 0, 256)

	// 1. RtlAddFunctionTable(exceptionTable, exceptionCount, imageBase)
	if bi.exceptionCount > 0 && bi.rtlAddFnTable != 0 {
		buf = emit3ArgCall(buf, bi.exceptionTable, bi.exceptionCount, bi.imageBase, bi.rtlAddFnTable)
	}
	// 2. For each TLS callback: cb(imageBase, DLL_PROCESS_ATTACH, 0)
	for _, cb := range bi.tlsCallbacks {
		buf = emit3ArgCall(buf, bi.imageBase, dllProcessAttach, 0, cb)
	}
	// 3. DllMain(imageBase, DLL_PROCESS_ATTACH, 0). rax holds its BOOL return.
	buf = emit3ArgCall(buf, bi.imageBase, dllProcessAttach, 0, bi.dllMainAddr)
	// 4. mov rcx, rax ; ret  → CreateRemoteThread's exit code = DllMain's return
	buf = append(buf, 0x48, 0x89, 0xC1, 0xC3)
	return buf
}

func appendU64(b []byte, v uint64) []byte {
	var tmp [8]byte
	binary.LittleEndian.PutUint64(tmp[:], v)
	return append(b, tmp[:]...)
}

// newBR creates a binary.Read-compatible reader for a byte slice (avoids extra deps).
func newBR(b []byte) *byteReader { return &byteReader{b: b} }

type byteReader struct {
	b []byte
	o int
}

func (r *byteReader) Read(p []byte) (int, error) {
	if r.o >= len(r.b) {
		return 0, fmt.Errorf("EOF")
	}
	n := copy(p, r.b[r.o:])
	r.o += n
	return n, nil
}

// ---------- subcommand dispatch ----------

// mmapMain is called from main.go's CLI dispatcher when args are: mmap <proc> <dll>.
func mmapMain(args []string) {
	if len(args) != 2 {
		fmt.Println("usage: inject mmap <process-name-or-pid> <dll-path>")
		os.Exit(2)
	}
	// Resolve PID (numeric or name).
	var pid uint32
	if n, err := strconv.Atoi(args[0]); err == nil {
		pid = uint32(n)
	} else {
		p, err := findPID(args[0]) // helper from main.go
		if err != nil {
			fmt.Println("ERROR:", err)
			os.Exit(1)
		}
		pid = p
	}
	dllPath, err := filepath.Abs(args[1])
	if err != nil {
		fmt.Println("ERROR: bad path:", err)
		os.Exit(1)
	}
	if _, err := os.Stat(dllPath); err != nil {
		fmt.Println("ERROR: dll not found:", dllPath)
		os.Exit(1)
	}
	fmt.Printf("Manual-mapping %s into PID %d\n", dllPath, pid)
	if err := manualMap(pid, dllPath); err != nil {
		fmt.Println("FAILED:", err)
		os.Exit(1)
	}
	base := filepath.Base(dllPath)
	if strings.EqualFold(base, "canary.dll") {
		fmt.Println("OK: manual-map complete. Check the canary marker file:")
		fmt.Println("    G:\\git\\Supervive Revival Project\\tools\\inject\\canary\\canary_loaded.txt")
	} else {
		fmt.Println("OK: manual-map complete (DllMain returned).")
	}
}

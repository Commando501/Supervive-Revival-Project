// dumpimage.go — secure a static, as-complete-as-possible dump of the live (unpacked)
// game image, for offline whole-program RE in Ghidra/IDA.
//
// WHY THIS EXISTS. Everything else in this tool reads the running process one address
// at a time (peek/disasm/xref). That's fine for spot-checks, but the current frontier
// (server-authoritative round-start / possession logic) wants a COLD image a decompiler
// can chew on: full xref graph, decompiler across everything, stable addresses, offline.
// The on-disk SUPERVIVE-Win64-Shipping.exe is useless for that — it's packed (imports
// only preloader.dll; the real UE engine is unpacked into memory at startup). So we
// snapshot the unpacked image out of live memory instead. Pure ReadProcessMemory: no
// injection, no debugger, no .text write — so CIG, the preloader NtCreateThreadEx hook,
// the VEH anti-debug, and the ~3–5 min integrity check never see us (same read-only
// posture that makes the rest of usmapdump safe).
//
// WHAT WE PRODUCE (in outDir, default "."):
//   <stem>.dump.exe         the main module, dumped from memory with section headers
//                           fixed so file-offset == RVA (the standard "dumped PE" form:
//                           FileAlignment=SectionAlignment, PointerToRawData=VirtualAddress,
//                           ImageBase=live base so applied relocs need no delta). Loads in
//                           Ghidra/IDA; RVAs line up with the base+0x... addresses the
//                           project already uses.
//   <stem>.exec_0xVA_SZ.bin each PRIVATE executable region that lives OUTSIDE the module
//                           image. helpers.go(:37) established that on this packed build
//                           some real code/vtables live in VirtualAlloc'd exec memory, not
//                           the module's own sections — so a "complete" dump must grab
//                           those too. Load raw at 0xVA. (MEM_IMAGE exec regions = other
//                           DLLs; inventoried but not dumped.)
//   <stem>.dump.txt         completeness manifest: per-section read coverage, the data
//                           directory table (Import/IAT — what an IAT-rebuild follow-up
//                           needs), and the full executable-region inventory.
//
// NOT DONE HERE (follow-ups, called out so the dump's limits are explicit): IAT
// reconstruction (the header import dir points at the packer stub, not the resolved
// engine imports — rebuilding it is Scylla's job and error-prone; left for a second
// pass), and de-obfuscation of any heavily-obfuscated functions (a handful won't
// decompile cleanly — the bulk engine .text is plainly resident, which is why disasm
// already works against it).
package main

import (
	"encoding/binary"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

// isExec reports whether a page protection grants execute (and isn't a guard page).
// PAGE_EXECUTE(0x10) has no named const in scan.go — spelled literally, as helpers.go does.
func isExec(protect uint32) bool {
	const anyExec = 0x10 | pageExecuteRead | pageExecuteRW | pageExecuteWC
	return protect&anyExec != 0 && protect&pageGuard == 0
}

func alignUp32(v, a uint32) uint32 {
	if a == 0 {
		return v
	}
	return (v + a - 1) &^ (a - 1)
}

// attemptable reports whether it's worth trying RPM on a committed page. We're broader
// than readable(): execute-only pages (PAGE_EXECUTE 0x10, no read bit) are frequently
// still RPM-readable from kernel-mode, so we try them and let a short read decide. Only
// guard pages and PAGE_NOACCESS are hopeless. This build demand-decrypts pages on access,
// so untouched pages read as 0 no matter what — captured as gaps in the coverage report.
func attemptable(protect uint32) bool {
	const pageNoAccess = 0x01
	return protect&pageGuard == 0 && protect != pageNoAccess
}

// readRange snapshots [addr, addr+len(buf)) into buf, region- and page-aware: committed
// readable pages are RPM'd, everything else is left zero. Returns bytes actually read.
func readRange(r *reader, addr uintptr, buf []byte) int {
	got := 0
	for off := 0; off < len(buf); {
		mbi, ok := r.query(addr + uintptr(off))
		if !ok {
			break
		}
		regionEnd := mbi.BaseAddress + mbi.RegionSize
		if regionEnd <= addr+uintptr(off) { // no forward progress — bail
			break
		}
		// bytes of buf covered by this region
		span := int(regionEnd - (addr + uintptr(off)))
		if span > len(buf)-off {
			span = len(buf) - off
		}
		if mbi.State == memCommit && attemptable(mbi.Protect) {
			for p := 0; p < span; {
				chunk := span - p
				if chunk > 0x1000 {
					chunk = 0x1000
				}
				n, _ := r.read(addr+uintptr(off+p), buf[off+p:off+p+chunk])
				got += n
				p += chunk
			}
		}
		off += span
	}
	return got
}

type secCov struct {
	name     string
	vaddr    uintptr
	vsize    uint32
	readable int
}

func cmdDumpImage(name, outDir string) {
	r, pid, base, size := mustOpen(name)
	defer procCloseHandle.Call(r.h)

	pe, err := parsePE(r, base)
	if err != nil {
		fmt.Println("ERROR: PE parse:", err)
		os.Exit(1)
	}
	sizeOfImage := pe.sizeOfImage
	if sizeOfImage < 0x1000 || sizeOfImage > 0x40000000 { // 0..1GB sanity; fall back to module size
		fmt.Printf("  (SizeOfImage 0x%X looks off; using module size 0x%X)\n", sizeOfImage, size)
		sizeOfImage = size
	}
	end := base + uintptr(sizeOfImage)

	stem := deriveStem(name)
	if outDir == "" {
		outDir = "."
	}
	if err := os.MkdirAll(outDir, 0755); err != nil {
		fmt.Println("ERROR: cannot create outDir:", err)
		os.Exit(1)
	}

	fmt.Printf("PID %d  module %q\n", pid, name)
	fmt.Printf("  base 0x%X  SizeOfImage 0x%X (%.1f MB)  sections %d\n",
		base, sizeOfImage, float64(sizeOfImage)/(1024*1024), len(pe.sections))

	// ---- snapshot the module image, region-aware, tracking per-section coverage ----
	img := make([]byte, sizeOfImage)
	cov := make([]secCov, len(pe.sections))
	for i, s := range pe.sections {
		cov[i] = secCov{name: s.name, vaddr: s.vaddr, vsize: s.vsize}
	}
	regs := r.regions() // one walk, reused for the exec inventory below
	totalRead := 0
	for _, rg := range regs {
		rs, re := rg.base, rg.base+rg.size
		if re <= base || rs >= end || !attemptable(rg.protect) {
			continue
		}
		if rs < base {
			rs = base
		}
		if re > end {
			re = end
		}
		for p := rs; p < re; {
			chunk := re - p
			if chunk > 0x1000 {
				chunk = 0x1000
			}
			off := p - base
			n, _ := r.read(p, img[off:off+uintptr(chunk)])
			if n > 0 {
				totalRead += n
				// attribute to the section containing p (linear scan; few sections)
				for i := range cov {
					if p >= cov[i].vaddr && p < cov[i].vaddr+uintptr(cov[i].vsize) {
						cov[i].readable += n
						break
					}
				}
			}
			p += chunk
		}
	}

	// ---- fix the PE headers so the file loads as a memory image ----
	fixDumpHeaders(img, base)

	dumpPath := filepath.Join(outDir, stem+".dump.exe")
	if err := os.WriteFile(dumpPath, img, 0644); err != nil {
		fmt.Println("ERROR: writing dump:", err)
		os.Exit(1)
	}
	pct := 100.0 * float64(totalRead) / float64(sizeOfImage)
	fmt.Printf("  wrote %s  (%.1f MB, %.2f%% of image readable)\n",
		dumpPath, float64(len(img))/(1024*1024), pct)

	// ---- dump PRIVATE exec regions outside the module; inventory ALL exec regions ----
	const perRegionCap = 128 * 1024 * 1024
	const totalBudget = 512 * 1024 * 1024
	dumpedBytes := 0
	var inv strings.Builder
	fmt.Fprintf(&inv, "%-18s %-12s %-6s %-8s %s\n", "VA", "SIZE", "PROT", "TYPE", "DUMPED")
	nExec, nDumped, nInModule := 0, 0, 0
	for _, rg := range regs {
		if !isExec(rg.protect) {
			continue
		}
		nExec++
		// In-module exec regions are just the page-granular protection fragments of the
		// module's own .text — already captured by the image dump. Count them, don't spam
		// the manifest with thousands of rows; only extern regions carry new information.
		if rg.base >= base && rg.base < end {
			nInModule++
			continue
		}
		regionKind := memTypeName(rg.typ)
		dumped := "-"
		switch {
		case rg.typ != memPrivate:
			dumped = "(skip: " + regionKind + " — other module)" // other DLLs / mapped, not our unpacked code
		case rg.size > perRegionCap:
			dumped = fmt.Sprintf("(skip: %d MB > cap)", rg.size/(1024*1024))
		case dumpedBytes+int(rg.size) > totalBudget:
			dumped = "(skip: budget)"
		default:
			buf := make([]byte, rg.size)
			readRange(r, rg.base, buf)
			fn := fmt.Sprintf("%s.exec_0x%X_%X.bin", stem, rg.base, rg.size)
			if err := os.WriteFile(filepath.Join(outDir, fn), buf, 0644); err != nil {
				dumped = "(write err)"
			} else {
				dumped = fn
				dumpedBytes += int(rg.size)
				nDumped++
			}
		}
		fmt.Fprintf(&inv, "0x%-16X 0x%-10X 0x%-4X %-8s %s\n",
			rg.base, rg.size, rg.protect, regionKind, dumped)
	}
	fmt.Fprintf(&inv, "\n(%d in-module exec sub-regions omitted — captured in the image dump)\n", nInModule)
	fmt.Printf("  exec regions: %d total (%d in-module), %d private-extern dumped (%.1f MB)\n",
		nExec, nInModule, nDumped, float64(dumpedBytes)/(1024*1024))

	// ---- manifest ----
	manPath := filepath.Join(outDir, stem+".dump.txt")
	writeManifest(manPath, name, pid, base, sizeOfImage, img, cov, totalRead, inv.String())
	fmt.Printf("  wrote %s\n", manPath)

	// ---- export map sidecar (addr -> module!export) for offline IAT reconstruction ----
	// Captured NOW, while attached, so `reconstructiat` works later without the game running
	// and without ASLR drift — the addresses here are exactly what the dump's IAT holds.
	resolve := make(map[uintptr]imp, 1<<16)
	for _, m := range modulesOf(pid) {
		r.addExports(m, resolve)
	}
	expPath := filepath.Join(outDir, stem+".exports.txt")
	if err := writeExportMap(expPath, resolve); err != nil {
		fmt.Println("  WARN: exports sidecar write failed:", err)
	} else {
		fmt.Printf("  wrote %s (%d exports)\n", expPath, len(resolve))
	}
	fmt.Println("\nDone. Load the .dump.exe in Ghidra/IDA (ImageBase already set to the live base).")
	fmt.Println("IAT is NOT reconstructed — indirect API calls will show as unresolved thunks;")
	fmt.Println("that's the follow-up. Read <stem>.dump.txt for coverage + the exec-region inventory.")
}

// fixDumpHeaders rewrites the in-buffer PE headers so the memory image is a loadable
// dumped PE: FileAlignment := SectionAlignment, and each section's raw pointer/size are
// set to its RVA/aligned-VirtualSize (file offset == RVA). ImageBase := live base so the
// already-applied relocations need zero delta.
func fixDumpHeaders(img []byte, base uintptr) {
	if len(img) < 0x200 {
		return
	}
	eLfanew := binary.LittleEndian.Uint32(img[0x3C:])
	fileHdr := eLfanew + 4
	optOff := eLfanew + 24 // 4 (PE sig) + 20 (IMAGE_FILE_HEADER)
	if uint32(len(img)) < optOff+0xF0 {
		return
	}
	numSections := binary.LittleEndian.Uint16(img[fileHdr+2:])
	sizeOfOptional := binary.LittleEndian.Uint16(img[fileHdr+16:])
	sectAlign := binary.LittleEndian.Uint32(img[optOff+32:])

	binary.LittleEndian.PutUint64(img[optOff+24:], uint64(base)) // ImageBase
	binary.LittleEndian.PutUint32(img[optOff+36:], sectAlign)    // FileAlignment := SectionAlignment

	secStart := eLfanew + 4 + 20 + uint32(sizeOfOptional)
	for i := uint32(0); i < uint32(numSections); i++ {
		so := secStart + i*40
		if so+40 > uint32(len(img)) {
			break
		}
		vsize := binary.LittleEndian.Uint32(img[so+8:])
		rva := binary.LittleEndian.Uint32(img[so+12:])
		binary.LittleEndian.PutUint32(img[so+16:], alignUp32(vsize, sectAlign)) // SizeOfRawData
		binary.LittleEndian.PutUint32(img[so+20:], rva)                         // PointerToRawData
	}
}

var dirNames = []string{
	"Export", "Import", "Resource", "Exception", "Security", "BaseReloc",
	"Debug", "Architecture", "GlobalPtr", "TLS", "LoadConfig", "BoundImport",
	"IAT", "DelayImport", "CLR", "Reserved",
}

func writeManifest(path, name string, pid uint32, base uintptr, sizeOfImage uint32,
	img []byte, cov []secCov, totalRead int, execInv string) {
	var b strings.Builder
	fmt.Fprintf(&b, "usmapdump dumpimage manifest\n")
	fmt.Fprintf(&b, "generated : %s\n", time.Now().Format("2006-01-02 15:04:05"))
	fmt.Fprintf(&b, "module    : %s (PID %d)\n", name, pid)
	fmt.Fprintf(&b, "base      : 0x%X\n", base)
	fmt.Fprintf(&b, "SizeOfImage: 0x%X (%.1f MB)\n", sizeOfImage, float64(sizeOfImage)/(1024*1024))
	fmt.Fprintf(&b, "coverage  : %d / %d bytes readable (%.2f%%)\n\n",
		totalRead, sizeOfImage, 100.0*float64(totalRead)/float64(sizeOfImage))

	// entry point + data directories (from the buffer's optional header)
	eLfanew := binary.LittleEndian.Uint32(img[0x3C:])
	optOff := eLfanew + 24
	entry := binary.LittleEndian.Uint32(img[optOff+16:])
	fmt.Fprintf(&b, "AddressOfEntryPoint (RVA): 0x%X\n\n", entry)

	fmt.Fprintf(&b, "%-10s %-18s %-12s %s\n", "SECTION", "RUNTIME VA", "VSIZE", "READABLE")
	for _, c := range cov {
		p := 0.0
		if c.vsize > 0 {
			p = 100.0 * float64(c.readable) / float64(c.vsize)
		}
		fmt.Fprintf(&b, "%-10s 0x%-16X 0x%-10X %d (%.1f%%)\n", c.name, c.vaddr, c.vsize, c.readable, p)
	}

	fmt.Fprintf(&b, "\nData directories (RVA/size) — Import & IAT are what an IAT-rebuild needs:\n")
	numDirs := binary.LittleEndian.Uint32(img[optOff+108:])
	ddOff := optOff + 112
	for i := 0; i < 16 && uint32(i) < numDirs; i++ {
		rva := binary.LittleEndian.Uint32(img[ddOff+uint32(i)*8:])
		sz := binary.LittleEndian.Uint32(img[ddOff+uint32(i)*8+4:])
		if rva == 0 && sz == 0 {
			continue
		}
		fmt.Fprintf(&b, "  [%2d] %-13s RVA 0x%-10X size 0x%X\n", i, dirNames[i], rva, sz)
	}

	fmt.Fprintf(&b, "\nExecutable region inventory (private-extern = candidate unpacked code):\n")
	b.WriteString(execInv)

	if err := os.WriteFile(path, []byte(b.String()), 0644); err != nil {
		fmt.Println("WARN: manifest write failed:", err)
	}
}

func memTypeName(t uint32) string {
	switch t {
	case memImage:
		return "Image"
	case memPrivate:
		return "Private"
	case 0x40000: // MEM_MAPPED
		return "Mapped"
	default:
		return fmt.Sprintf("0x%X", t)
	}
}

// deriveStem turns a process arg into a safe output basename ("SUPERVIVE-Win64-Shipping.exe"
// -> "SUPERVIVE-Win64-Shipping"; a bare PID -> "image").
func deriveStem(name string) string {
	s := name
	if i := strings.LastIndexAny(s, `\/`); i >= 0 {
		s = s[i+1:]
	}
	if strings.HasSuffix(strings.ToLower(s), ".exe") {
		s = s[:len(s)-4]
	}
	if s == "" {
		return "image"
	}
	if _, err := strconv.Atoi(s); err == nil {
		return "image"
	}
	return s
}

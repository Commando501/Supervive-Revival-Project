// reconstructiat.go — rebuild a usable import table on a dumpimage snapshot so a
// disassembler resolves API calls to names instead of raw pointers.
//
// THE PROBLEM. A dumped image's IAT holds the RESOLVED absolute addresses the Windows
// loader wrote at runtime (e.g. 0x7FF90E812A70). Ghidra sees `call qword [rip+x]` through
// those slots but the target is outside the file, so every API call shows as an unnamed
// indirect thunk. The packer also destroyed the original import directory (the header's
// Import dir is just the 0x56-byte preloader stub), so there's nothing describing the IAT.
//
// VERIFIED PRECONDITION. This build's IAT (data dir [12], at .rdata start) holds resolved
// system-DLL pointers — NOT packer-redirected stubs — so each slot value equals an export
// address in some loaded module. That makes classic reconstruction possible: for each slot,
// find which module!export the address is, then synthesize an import directory + import
// name table (INT) + name strings describing it.
//
// HOW. Attach to the LIVE process the dump came from (its module bases match the addresses
// baked into the dump's IAT — same boot session), read every module's export table into an
// address→module!name map, classify each IAT slot, group contiguous same-module slots into
// IMAGE_IMPORT_DESCRIPTORs, and write all the new metadata into a fresh section appended to
// the file. FirstThunk points at the EXISTING IAT slots (kept as-is); OriginalFirstThunk
// points at the INT we build. Ghidra then labels each IAT slot module!Name.
//
// SCOPE. Resolves by name, falling back to by-ordinal for name-less exports. Slots whose
// value isn't in any current module are reported unresolved (they'd indicate a stale
// dump/process pair, or the rare redirected import). The original dump file is left intact;
// output is a sibling `*.iat.exe`.
package main

import (
	"encoding/binary"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"unsafe"
)

// --- live module + export enumeration --------------------------------------------

type moduleInfo struct {
	base uintptr
	size uint32
	name string
}

func modulesOf(pid uint32) []moduleInfo {
	snap, _, _ := procCreateToolhelp32Snap.Call(th32csSnapModule|th32csSnapModule32, uintptr(pid))
	if snap == 0 || snap == ^uintptr(0) {
		return nil
	}
	defer procCloseHandle.Call(snap)
	var out []moduleInfo
	var me moduleEntry32
	me.Size = uint32(unsafe.Sizeof(me))
	ret, _, _ := procModule32FirstW.Call(snap, uintptr(unsafe.Pointer(&me)))
	for ret != 0 {
		out = append(out, moduleInfo{
			base: me.ModBaseAddr,
			size: me.ModBaseSize,
			name: syscall.UTF16ToString(me.ModuleName[:]),
		})
		ret, _, _ = procModule32NextW.Call(snap, uintptr(unsafe.Pointer(&me)))
	}
	return out
}

// imp is a resolved import target for one IAT slot value.
type imp struct {
	module  string
	name    string
	ordinal int
	byName  bool
}

func (r *reader) cstr(addr uintptr, max int) string {
	buf := make([]byte, max)
	n, _ := r.read(addr, buf)
	for i := 0; i < n; i++ {
		if buf[i] == 0 {
			return string(buf[:i])
		}
	}
	return string(buf[:n])
}

// addExports parses module m's export directory from live memory and records every
// export address in resolve. Named exports win; name-less ones fall back to ordinal.
// Forwarded exports (RVA inside the export dir) are skipped — the slot's real value lands
// in the forward target module, which is enumerated on its own.
func (r *reader) addExports(m moduleInfo, resolve map[uintptr]imp) {
	hdr := make([]byte, 0x1000)
	if n, _ := r.read(m.base, hdr); n < 0x200 || hdr[0] != 'M' || hdr[1] != 'Z' {
		return
	}
	eLfanew := binary.LittleEndian.Uint32(hdr[0x3C:])
	if eLfanew+0x108 > uint32(len(hdr)) {
		return
	}
	opt := hdr[eLfanew+24:]
	if binary.LittleEndian.Uint16(opt) != 0x20B { // PE32+ only
		return
	}
	expRVA := binary.LittleEndian.Uint32(opt[112:])   // data dir [0] Export RVA
	expSize := binary.LittleEndian.Uint32(opt[116:])  // data dir [0] Export size
	if expRVA == 0 || expSize == 0 {
		return
	}
	ed := make([]byte, 40)
	if n, _ := r.read(m.base+uintptr(expRVA), ed); n < 40 {
		return
	}
	ordinalBase := binary.LittleEndian.Uint32(ed[16:])
	numFuncs := binary.LittleEndian.Uint32(ed[20:])
	numNames := binary.LittleEndian.Uint32(ed[24:])
	funcsRVA := binary.LittleEndian.Uint32(ed[28:])
	namesRVA := binary.LittleEndian.Uint32(ed[32:])
	ordsRVA := binary.LittleEndian.Uint32(ed[36:])
	if numFuncs == 0 || numFuncs > 0x20000 {
		return
	}
	funcs := make([]byte, numFuncs*4)
	if n, _ := r.read(m.base+uintptr(funcsRVA), funcs); n < len(funcs) {
		return
	}
	isForwarder := func(rva uint32) bool { return rva >= expRVA && rva < expRVA+expSize }

	// by-name first
	named := make(map[uint32]bool) // function-index that already has a name
	if numNames > 0 && numNames <= 0x20000 {
		names := make([]byte, numNames*4)
		ords := make([]byte, numNames*2)
		r.read(m.base+uintptr(namesRVA), names)
		r.read(m.base+uintptr(ordsRVA), ords)
		for i := uint32(0); i < numNames; i++ {
			fi := uint32(binary.LittleEndian.Uint16(ords[i*2:]))
			if fi >= numFuncs {
				continue
			}
			fRVA := binary.LittleEndian.Uint32(funcs[fi*4:])
			if fRVA == 0 || isForwarder(fRVA) {
				continue
			}
			nameRVA := binary.LittleEndian.Uint32(names[i*4:])
			nm := r.cstr(m.base+uintptr(nameRVA), 256)
			if nm == "" {
				continue
			}
			addr := m.base + uintptr(fRVA)
			if _, ok := resolve[addr]; !ok {
				resolve[addr] = imp{module: m.name, name: nm, byName: true}
			}
			named[fi] = true
		}
	}
	// name-less exports -> by ordinal
	for fi := uint32(0); fi < numFuncs; fi++ {
		if named[fi] {
			continue
		}
		fRVA := binary.LittleEndian.Uint32(funcs[fi*4:])
		if fRVA == 0 || isForwarder(fRVA) {
			continue
		}
		addr := m.base + uintptr(fRVA)
		if _, ok := resolve[addr]; !ok {
			resolve[addr] = imp{module: m.name, ordinal: int(ordinalBase + fi)}
		}
	}
}

// --- export-map sidecar (dump-time resolution, so reconstruct works offline) ------

// writeExportMap persists addr -> module!name (or module#ordinal), captured live at dump
// time. Sorted by address for stable diffs. Consumed by reconstructiat.
func writeExportMap(path string, resolve map[uintptr]imp) error {
	addrs := make([]uintptr, 0, len(resolve))
	for a := range resolve {
		addrs = append(addrs, a)
	}
	sort.Slice(addrs, func(i, j int) bool { return addrs[i] < addrs[j] })
	var b strings.Builder
	for _, a := range addrs {
		im := resolve[a]
		if im.byName {
			fmt.Fprintf(&b, "%X\t%s!%s\n", a, im.module, im.name)
		} else {
			fmt.Fprintf(&b, "%X\t%s#%d\n", a, im.module, im.ordinal)
		}
	}
	return os.WriteFile(path, []byte(b.String()), 0644)
}

func loadExportMap(path string) (map[uintptr]imp, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	resolve := make(map[uintptr]imp, 1<<16)
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimRight(line, "\r")
		tab := strings.IndexByte(line, '\t')
		if tab < 0 {
			continue
		}
		addr, err := strconv.ParseUint(line[:tab], 16, 64)
		if err != nil {
			continue
		}
		rest := line[tab+1:]
		if bang := strings.IndexByte(rest, '!'); bang >= 0 {
			resolve[uintptr(addr)] = imp{module: rest[:bang], name: rest[bang+1:], byName: true}
		} else if hash := strings.IndexByte(rest, '#'); hash >= 0 {
			ord, _ := strconv.Atoi(rest[hash+1:])
			resolve[uintptr(addr)] = imp{module: rest[:hash], ordinal: ord}
		}
	}
	return resolve, nil
}

// findExportsSidecar locates the export map for a dump: <stem>.exports.txt beside it, else
// the first *.exports.txt anywhere under the dump's directory (all dumps from one boot
// session share the same export addresses, so any of them resolves the others).
func findExportsSidecar(dumpPath string) string {
	stem := strings.TrimSuffix(dumpPath, ".dump.exe")
	if stem == dumpPath {
		stem = strings.TrimSuffix(dumpPath, ".exe")
	}
	if cand := stem + ".exports.txt"; fileExists(cand) {
		return cand
	}
	var found string
	filepath.WalkDir(filepath.Dir(dumpPath), func(p string, d os.DirEntry, err error) error {
		if err == nil && !d.IsDir() && found == "" && strings.HasSuffix(p, ".exports.txt") {
			found = p
		}
		return nil
	})
	return found
}

func fileExists(p string) bool { _, err := os.Stat(p); return err == nil }

// --- reconstruction ---------------------------------------------------------------

type iatDescr struct {
	module        string
	firstThunkRVA uint32
	entries       []imp
}

func cmdReconstructIAT(dumpPath, outPath string) {
	expPath := findExportsSidecar(dumpPath)
	if expPath == "" {
		fmt.Println("ERROR: no *.exports.txt sidecar found beside the dump.")
		fmt.Println("  dumpimage now writes <stem>.exports.txt at dump time — re-dump, then reconstruct.")
		os.Exit(1)
	}
	resolve, err := loadExportMap(expPath)
	if err != nil {
		fmt.Println("ERROR: reading exports sidecar:", err)
		os.Exit(1)
	}
	fmt.Printf("exports: %s (%d entries)\n", filepath.Base(expPath), len(resolve))

	img, err := os.ReadFile(dumpPath)
	if err != nil {
		fmt.Println("ERROR: reading dump:", err)
		os.Exit(1)
	}
	if len(img) < 0x1000 || img[0] != 'M' || img[1] != 'Z' {
		fmt.Println("ERROR: not a dumpimage PE:", dumpPath)
		os.Exit(1)
	}
	eLfanew := binary.LittleEndian.Uint32(img[0x3C:])
	fileHdr := eLfanew + 4
	optOff := eLfanew + 24
	numSec := binary.LittleEndian.Uint16(img[fileHdr+2:])
	sizeOpt := binary.LittleEndian.Uint16(img[fileHdr+16:])
	sectAlign := binary.LittleEndian.Uint32(img[optOff+32:])
	fileAlign := binary.LittleEndian.Uint32(img[optOff+36:])
	sizeOfImage := binary.LittleEndian.Uint32(img[optOff+56:])
	sizeOfHeaders := binary.LittleEndian.Uint32(img[optOff+60:])
	ddOff := optOff + 112
	iatRVA := binary.LittleEndian.Uint32(img[ddOff+12*8:])
	iatSize := binary.LittleEndian.Uint32(img[ddOff+12*8+4:])
	if iatRVA == 0 || iatSize == 0 || int(iatRVA)+int(iatSize) > len(img) {
		fmt.Printf("ERROR: IAT data dir looks invalid (RVA 0x%X size 0x%X)\n", iatRVA, iatSize)
		os.Exit(1)
	}
	secStart := eLfanew + 4 + 20 + uint32(sizeOpt)

	// Walk the IAT, grouping contiguous same-module resolved slots into descriptors.
	var descrs []iatDescr
	curIdx := -1
	resolved, unresolved := 0, 0
	perModule := map[string]int{}
	var unresolvedSample []uintptr
	for off := uint32(0); off+8 <= iatSize; off += 8 {
		slotRVA := iatRVA + off
		val := uintptr(binary.LittleEndian.Uint64(img[slotRVA:]))
		if val == 0 {
			curIdx = -1
			continue
		}
		im, ok := resolve[val]
		if !ok {
			unresolved++
			curIdx = -1
			if len(unresolvedSample) < 12 {
				unresolvedSample = append(unresolvedSample, val)
			}
			continue
		}
		resolved++
		perModule[im.module]++
		if curIdx == -1 || descrs[curIdx].module != im.module {
			descrs = append(descrs, iatDescr{module: im.module, firstThunkRVA: slotRVA})
			curIdx = len(descrs) - 1
		}
		descrs[curIdx].entries = append(descrs[curIdx].entries, im)
	}
	if resolved == 0 {
		fmt.Println("ERROR: resolved 0 IAT slots — the exports sidecar doesn't match this dump")
		fmt.Println("  (a different boot session? use the .exports.txt captured alongside THIS dump).")
		os.Exit(1)
	}

	// Build the new import section: [descriptors + null][INT arrays][hint/name + dll names].
	secRVA := alignUp32(sizeOfImage, sectAlign)
	numDesc := len(descrs)
	dPart := uint32((numDesc + 1) * 20)

	// INT arrays: (len(entries)+1) qwords each.
	intOff := make([]uint32, numDesc)
	off := dPart
	for j := range descrs {
		intOff[j] = off
		off += uint32((len(descrs[j].entries) + 1) * 8)
	}
	namesBase := off

	// Name blob: dedup DLL name strings; append a hint/name entry per by-name import.
	var names []byte
	dllNameOff := map[string]uint32{}
	appendCStr := func(s string) uint32 {
		o := namesBase + uint32(len(names))
		names = append(names, []byte(s)...)
		names = append(names, 0)
		if len(names)%2 == 1 { // keep hint/name entries 2-aligned
			names = append(names, 0)
		}
		return o
	}
	dllRVA := func(mod string) uint32 {
		if o, ok := dllNameOff[mod]; ok {
			return o
		}
		o := appendCStr(mod)
		dllNameOff[mod] = o
		return o
	}
	// hint/name entries, and remember each entry's INT value
	intVals := make([][]uint64, numDesc)
	for j := range descrs {
		vals := make([]uint64, 0, len(descrs[j].entries))
		for _, e := range descrs[j].entries {
			if e.byName {
				o := namesBase + uint32(len(names))
				names = append(names, 0, 0) // hint = 0
				names = append(names, []byte(e.name)...)
				names = append(names, 0)
				if len(names)%2 == 1 {
					names = append(names, 0)
				}
				// INT entry = RVA of the IMAGE_IMPORT_BY_NAME (high bit clear => by name)
				vals = append(vals, uint64(secRVA+o))
			} else {
				vals = append(vals, 0x8000000000000000|uint64(uint16(e.ordinal))) // import by ordinal
			}
		}
		intVals[j] = vals
	}
	// pre-touch dll name strings so their RVAs exist before we write descriptors
	for j := range descrs {
		dllRVA(descrs[j].module)
	}

	secLen := namesBase + uint32(len(names))
	sec := make([]byte, secLen)
	// descriptors
	for j := range descrs {
		d := sec[j*20 : j*20+20]
		binary.LittleEndian.PutUint32(d[0:], secRVA+intOff[j])            // OriginalFirstThunk (INT)
		binary.LittleEndian.PutUint32(d[12:], secRVA+dllNameOff[descrs[j].module]) // Name
		binary.LittleEndian.PutUint32(d[16:], descrs[j].firstThunkRVA)    // FirstThunk (existing IAT)
	}
	// INT arrays
	for j := range descrs {
		base := intOff[j]
		for k, v := range intVals[j] {
			binary.LittleEndian.PutUint64(sec[base+uint32(k*8):], v)
		}
		// terminating null qword already zero
	}
	// names already at namesBase.. within sec? No — names is a separate slice starting at
	// file offset namesBase. Copy it in.
	copy(sec[namesBase:], names)

	// Room for one more section header?
	if secStart+uint32(numSec+1)*40 > sizeOfHeaders || secStart+uint32(numSec+1)*40 > 0x1000 {
		fmt.Println("ERROR: no room in PE header for another section entry")
		os.Exit(1)
	}

	// Write the section header.
	sh := secStart + uint32(numSec)*40
	for i := 0; i < 40; i++ {
		img[sh+uint32(i)] = 0
	}
	copy(img[sh:sh+8], []byte(".idata2"))
	binary.LittleEndian.PutUint32(img[sh+8:], secLen)                       // VirtualSize
	binary.LittleEndian.PutUint32(img[sh+12:], secRVA)                      // VirtualAddress
	binary.LittleEndian.PutUint32(img[sh+16:], alignUp32(secLen, fileAlign)) // SizeOfRawData
	binary.LittleEndian.PutUint32(img[sh+20:], secRVA)                      // PointerToRawData (file==RVA)
	binary.LittleEndian.PutUint32(img[sh+36:], 0x40000040)                  // INITIALIZED_DATA | MEM_READ

	// Patch header counts / dirs.
	binary.LittleEndian.PutUint16(img[fileHdr+2:], numSec+1)
	binary.LittleEndian.PutUint32(img[optOff+56:], secRVA+alignUp32(secLen, sectAlign)) // SizeOfImage
	binary.LittleEndian.PutUint32(img[ddOff+1*8:], secRVA)                              // Import dir RVA
	binary.LittleEndian.PutUint32(img[ddOff+1*8+4:], dPart)                             // Import dir size

	// Assemble the output file: original image, zero-pad to secRVA, then the section.
	out := img
	if uint32(len(out)) < secRVA {
		out = append(out, make([]byte, secRVA-uint32(len(out)))...)
	}
	out = append(out, sec...)
	if pad := alignUp32(secLen, fileAlign) - secLen; pad > 0 {
		out = append(out, make([]byte, pad)...)
	}

	if outPath == "" {
		outPath = strings.TrimSuffix(dumpPath, ".exe") + ".iat.exe"
	}
	if err := os.WriteFile(outPath, out, 0644); err != nil {
		fmt.Println("ERROR: writing output:", err)
		os.Exit(1)
	}

	// Report.
	fmt.Printf("  IAT slots: %d resolved, %d unresolved  ->  %d import descriptors across %d DLLs\n",
		resolved, unresolved, numDesc, len(perModule))
	type mc struct {
		m string
		c int
	}
	var mcs []mc
	for m, c := range perModule {
		mcs = append(mcs, mc{m, c})
	}
	sort.Slice(mcs, func(i, j int) bool { return mcs[i].c > mcs[j].c })
	for i, x := range mcs {
		if i >= 15 {
			fmt.Printf("    … and %d more DLLs\n", len(mcs)-15)
			break
		}
		fmt.Printf("    %-24s %d\n", x.m, x.c)
	}
	if unresolved > 0 {
		fmt.Printf("  unresolved sample: ")
		for _, a := range unresolvedSample {
			fmt.Printf("0x%X ", a)
		}
		fmt.Println("\n    (unresolved = value not in any current module; expected for a stale dump/process pair)")
	}
	fmt.Printf("  wrote %s (+%d bytes import section)\n", outPath, secLen)
	fmt.Println("  Load THIS file in Ghidra/IDA — API calls through the IAT now resolve to module!Name.")
}

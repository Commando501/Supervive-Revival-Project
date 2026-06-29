// vtdump.go — dump a class vtable, slot by slot, identifying real overrides.
//
// Use case: you know a UClass-derived vtable's address (e.g. LokiAssetManager
// vtable at module RVA 0x888CB78). You want to know which methods this class
// OVERRIDES from its base classes, so you can identify the customization
// points to target with a shim.
//
// Output for each slot:
//   - slot index (decimal)
//   - absolute function ptr
//   - module-RVA (if in-module — should always be true for UE class vtables)
//   - first 16 bytes of the function (for prologue identification)
//   - count of OTHER vtable slots also pointing at this same fn within the
//     dumped range (to identify "shared empty stubs" which MSVC ICF-folds
//     across all classes — typically 10+ occurrences for empty virtuals
//     like `virtual void X() {}`)
//
// Slots with count=1 across the dumped range are LIKELY real overrides
// unique to this class (or to a small derived-class group). Slots with
// count>5 are almost certainly shared empty stubs.
//
// Usage:
//   usmapdump vtdump <proc> 0xVTABLE_ADDR [num_slots]   (default 128 slots)

package main

import (
	"encoding/binary"
	"fmt"
)

func cmdVtDump(proc string, vtableAddr uintptr, numSlots int) {
	r, pid, base, size := mustOpen(proc)
	defer procCloseHandle.Call(r.h)
	fmt.Printf("PID %d  %q base=0x%X size=0x%X\n", pid, proc, base, size)
	fmt.Printf("  dumping vtable @ 0x%X, %d slots\n\n", vtableAddr, numSlots)

	// Read all slots in one go.
	bufLen := numSlots * 8
	buf := make([]byte, bufLen)
	got, _ := r.read(vtableAddr, buf)
	if got < 8 {
		fmt.Printf("  ERROR: could not read vtable (got %d bytes)\n", got)
		return
	}
	usable := got / 8
	if usable > numSlots {
		usable = numSlots
	}

	// Collect all fn ptrs.
	type slotInfo struct {
		idx   int
		fnPtr uintptr
		rva   uintptr
		inMod bool
		first []byte // first 16 bytes of fn body
	}
	slots := make([]slotInfo, usable)
	freq := map[uintptr]int{}
	for i := 0; i < usable; i++ {
		fn := uintptr(binary.LittleEndian.Uint64(buf[i*8 : i*8+8]))
		si := slotInfo{idx: i, fnPtr: fn}
		if fn >= base && fn < base+uintptr(size) {
			si.inMod = true
			si.rva = fn - base
		}
		slots[i] = si
		if fn != 0 {
			freq[fn]++
		}
	}

	// For each unique fn, read prologue bytes.
	fnBytes := map[uintptr][]byte{}
	for fn := range freq {
		pb := make([]byte, 16)
		n, _ := r.read(fn, pb)
		if n > 0 {
			fnBytes[fn] = pb[:n]
		}
	}

	// Print each slot with annotations.
	fmt.Printf("  %-5s %-18s %-12s %-7s %-12s %s\n",
		"SLOT", "ABS_ADDR", "MOD_RVA", "DUPS", "TAG", "PROLOGUE (16 bytes)")
	for _, s := range slots {
		if s.fnPtr == 0 {
			fmt.Printf("  %-5d %-18s %-12s %-7d %s\n", s.idx, "(null)", "", 0, "")
			continue
		}
		dupCount := freq[s.fnPtr]
		tag := ""
		if dupCount >= 5 {
			tag = "SHARED-STUB"
		} else if dupCount == 1 {
			tag = "UNIQUE"
		} else {
			tag = fmt.Sprintf("%d-shared", dupCount)
		}
		rva := ""
		if s.inMod {
			rva = fmt.Sprintf("0x%X", s.rva)
		} else {
			rva = "OFF-MODULE"
		}
		prologue := ""
		if pb, ok := fnBytes[s.fnPtr]; ok {
			for _, b := range pb {
				prologue += fmt.Sprintf("%02X ", b)
			}
		}
		fmt.Printf("  %-5d 0x%-16X %-12s %-7d %-12s %s\n",
			s.idx, s.fnPtr, rva, dupCount, tag, prologue)
	}

	// Print a summary of unique fn distributions.
	fmt.Println()
	fmt.Printf("  ── summary ──\n")
	uniqueCount := 0
	for _, c := range freq {
		if c == 1 {
			uniqueCount++
		}
	}
	fmt.Printf("  total slots dumped: %d\n", usable)
	fmt.Printf("  unique fn pointers (likely real overrides): %d\n", uniqueCount)
	fmt.Printf("  distinct fns total: %d\n", len(freq))
}

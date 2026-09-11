// vtslot.go — vtable scanner that finds vtables by SLOT VALUE.
//
// Standard `findptr` finds direct references to a function. But MSVC's
// Identical COMDAT Folding (ICF) can fold identical method implementations
// across multiple classes — each class still has its own vtable in .rdata,
// but the function pointer at the equivalent slot in each vtable points to
// the SAME shared code address. So finding "every class whose vtable
// contains function X at slot N" requires scanning for the SLOT itself,
// not for the function ptr.
//
// Use case: we know `FPakPlatformFile::Initialize` at +0x204AAD0 lives at
// slot 11 of one of the per-pak FPakFile wrapper vtables. The MASTER
// FPakPlatformFile singleton might be a different class whose vtable ALSO
// has +0x204AAD0 at slot 11 (ICF). `findptr +0x204AAD0` only locates the
// known wrapper vtable's slot. This scanner finds OTHER vtables that share
// the slot value.
//
// Usage: usmapdump vtslot <proc> <slot> <hexFnAddr> [maxHits]
//   slot     = vtable slot index (e.g. 11)
//   hexFnAddr = absolute address of the function we expect in that slot
//   maxHits  = optional cap (default 30)
//
// Output: each candidate vtable base + decoded slot 0 (typical dtor) so
//   the operator can sanity-check it looks like a real vtable.
//
// Performance: scans READABLE committed memory at 8-byte stride. Module
// .rdata typically has many vtables; heap also has cached vtables. The
// scanner filters candidates by requiring slot 0 to look like a code
// pointer in the module to reduce false positives.

package main

import (
	"encoding/binary"
	"fmt"
	"strconv"
)

// cmdVtSlot scans committed memory for any 8-byte-aligned address `vt` such
// that the qword at `vt + slot*8` equals `expectedFn`. Candidates are
// validated by checking that slot 0 (the dtor in MSVC layout) looks like
// a code pointer in the module image.
func cmdVtSlot(proc string, slot int, expectedFn uintptr, maxHits int) {
	r, pid, base, size := mustOpen(proc)
	defer procCloseHandle.Call(r.h)
	fmt.Printf("PID %d  %q base=0x%X size=0x%X\n", pid, proc, base, size)
	slotOffset := uintptr(slot) * 8
	fmt.Printf("  scanning for vtables where [base+0x%X] == 0x%X (slot %d)\n",
		slotOffset, expectedFn, slot)

	const stride = 8
	const maxRegion = 1 << 28 // 256 MB cap per region — skip huge heap arenas

	// Code pointer validation range. Any plausible vtable slot pointing at a
	// real method must be in the module's executable range. Module text is
	// roughly base..base+size; tighten to skip PE header.
	codeMin := base + 0x1000
	codeMax := base + uintptr(size)

	hits := 0
	regs := r.regions()
	scanned := 0
	for _, rg := range regs {
		if !readable(rg.protect) {
			continue
		}
		if rg.size > maxRegion {
			continue
		}
		scanned++
		// Read the entire region in one go (it's bounded to 256MB).
		buf := make([]byte, rg.size)
		got, _ := r.read(rg.base, buf)
		if got < int(slotOffset+8) {
			continue
		}
		// Stride 8, check each candidate.
		for off := 0; off+int(slotOffset)+8 <= got; off += stride {
			slotBytes := buf[off+int(slotOffset) : off+int(slotOffset)+8]
			slotVal := uintptr(binary.LittleEndian.Uint64(slotBytes))
			if slotVal != expectedFn {
				continue
			}
			// Slot 0 sanity check: should be a code ptr in module.
			if off+8 > got {
				continue
			}
			slot0 := uintptr(binary.LittleEndian.Uint64(buf[off : off+8]))
			if slot0 < codeMin || slot0 >= codeMax {
				continue
			}
			candVT := rg.base + uintptr(off)
			modInfo := ""
			if candVT >= base && candVT < base+uintptr(size) {
				modInfo = fmt.Sprintf("  mod-RVA 0x%X", candVT-base)
			}
			s0RVA := slot0 - base
			fmt.Printf("  vtable @ 0x%X%s\n", candVT, modInfo)
			fmt.Printf("    slot 0  = 0x%X (mod-RVA 0x%X — typical dtor)\n", slot0, s0RVA)
			fmt.Printf("    slot %d  = 0x%X (target match)\n", slot, slotVal)
			// Print a few neighboring slots for context.
			for ns := 1; ns < 16 && ns != slot; ns++ {
				nOff := off + ns*8
				if nOff+8 > got {
					break
				}
				nv := uintptr(binary.LittleEndian.Uint64(buf[nOff : nOff+8]))
				nRVA := ""
				if nv >= base && nv < base+uintptr(size) {
					nRVA = fmt.Sprintf(" (mod-RVA 0x%X)", nv-base)
				}
				fmt.Printf("    slot %-2d = 0x%X%s\n", ns, nv, nRVA)
			}
			fmt.Println()
			hits++
			if maxHits > 0 && hits >= maxHits {
				goto done
			}
		}
	}
done:
	fmt.Printf("  done: %d hit(s) across %d region(s)\n", hits, scanned)
}

// parseDecimal parses a base-10 int.
func parseDecimal(s string) (int, error) {
	return strconv.Atoi(s)
}

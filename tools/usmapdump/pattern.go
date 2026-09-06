// pattern.go — byte-pattern scanner that finds INLINED FMemory::Malloc call
// sites and reports the rip-relative GLOBAL POINTER each one loads, sorted by
// frequency. The most-common target is GMalloc.
//
// Why: in the SUPERVIVE shipping build FMallocBinned2::Realloc/Free/Malloc are
// devirtualized and inlined into every allocation site. `findptr` and
// `callxref` on the function bodies return ZERO hits — the function bodies
// exist but nothing references them via vtable or direct call. The standard
// "find vtable, locate Malloc slot" approach is unavailable.
//
// The workaround: FMemory::Malloc's source is
//
//   void* FMemory::Malloc(SIZE_T Count, uint32 Alignment) {
//     if (!GMalloc) GCreateMalloc();
//     return GMalloc->Malloc(Count, Alignment);
//   }
//
// MSVC's shipping codegen for the fast path compiles to a fixed prefix:
//
//   48 8B 05 ?? ?? ?? ??   mov  rax, [rip+disp]   ; load GMalloc pointer
//   48 85 C0               test rax, rax
//   74 ??                  jz   <init-path>
//   48 8B 00               mov  rax, [rax]        ; load FMalloc vtable
//   ... arg loads ...
//   FF 60 ??               jmp  [rax+slot]        ; tail-call Malloc
//
// The first 7 bytes carry a rip-relative reference to the GLOBAL holding the
// FMalloc* — GMalloc itself. Since EVERY allocation in UE flows through this
// path and the binary has thousands of allocation sites, GMalloc dominates
// the frequency histogram by orders of magnitude. Other less-common targets
// are unrelated globals that happen to follow the same null-check-and-dispatch
// shape (GLog, GConfig, GEngine, ...).
//
// Usage: usmapdump pattern <proc-name-or-pid> [topN]
//
// Output: top-N targets sorted by hit count. For each: the target address,
// hit count, and the address of one sample call site so you can `disasm`
// around it to read the FF 60 XX (Malloc vtable slot) byte.

package main

import (
	"encoding/binary"
	"fmt"
	"os"
	"sort"
)

// fmemMallocPattern matches the inlined FMemory::Malloc prefix described
// above. 15 bytes of prefix + a window after `mov rax, [rax]` in which we
// require a `FF 60 ??` (jmp [rax+disp8]) for vtable tail-call dispatch.
//
// The first scan v1 with only the 15-byte prefix matched many generic
// "load-global-if-non-null-deref" sites whose dispatch was `call [rip+disp]`
// (function-table style), not `jmp [rax+slot]` (vtable style). The disasm of
// one such hit showed `48 8B 00; 48 85 C0; 74 ??; mov rcx, rdi; call
// [rip+disp]` — entirely the wrong shape. Requiring FF 60 ?? within a short
// window after the second mov filters to vtable dispatch sites; GMalloc's
// path tail-calls through a vtable slot so it survives.
const (
	patSize         = 15
	patRipDispStart = 3
	patRipDispEnd   = 7 // exclusive
	patNextInstrOff = 7 // RIP of mov-rax-[rip+disp] is start+7
	// Window after the second mov in which to look for a vtable tail-call.
	// The compiler inserts a small number of arg-setup instructions
	// (mov rcx, rax; mov rdx, ...; mov r8d, ...) before the jmp; 24 bytes is
	// enough for ~5-6 of those.
	patVTailWindow = 24
)

// matchFMemMalloc returns true if buf[i..] matches the inlined FMemory::Malloc
// pattern: the null-checked load prefix, an optional `mov rcx, rax` to save
// `this` before the vtable load clobbers rax, the `mov rax, [rax]` vtable
// load, and a vtable-dispatch terminator (FF 50/60/90/A0) within
// patVTailWindow bytes. Returns the dispatch slot byte on success.
//
// The original v1 pattern required `48 8B 00` to be at exactly i+12 (right
// after the jz). But MSVC's actual layout for `return GMalloc->Malloc(...)`
// is `jz; mov rcx, rax; mov rax, [rax]; jmp [rax+slot]` — the mov-rcx-rax
// slot saves the FMalloc* before the vtable load clobbers rax. v2 accepts
// 0 or 3 bytes (the mov-rcx-rax sized window) between the jz and the
// vtable-load mov.
func matchFMemMalloc(buf []byte, i int) (slot byte, ok bool) {
	if i+patSize+patVTailWindow+3 > len(buf) {
		return 0, false
	}
	// mov rax, [rip+disp32]
	if buf[i] != 0x48 || buf[i+1] != 0x8B || buf[i+2] != 0x05 {
		return 0, false
	}
	// test rax, rax
	if buf[i+7] != 0x48 || buf[i+8] != 0x85 || buf[i+9] != 0xC0 {
		return 0, false
	}
	// jz short (74 disp8) — disp8 ignored
	if buf[i+10] != 0x74 {
		return 0, false
	}
	// Find mov rax, [rax] (48 8B 00) within the next 8 bytes. Allow an
	// optional `mov rcx, rax` (48 8B C8) or other small reg-reg move in
	// between.
	movRaxOff := -1
	for k := i + 12; k <= i+20; k++ {
		if buf[k] == 0x48 && buf[k+1] == 0x8B && buf[k+2] == 0x00 {
			movRaxOff = k
			break
		}
	}
	if movRaxOff < 0 {
		return 0, false
	}
	// Look for ANY vtable-shaped dispatch (call/jmp through [rax+disp])
	// OR a `call [rip+disp]` (absolute function pointer through table) in
	// the arg-setup window after the vtable-load mov. The devirtualized
	// build in SUPERVIVE may inline FMallocBinned2::Malloc directly so the
	// vtable jmp is gone — but the wider terminator set still catches
	// generic singleton dispatch patterns.
	dispatchStart := movRaxOff + 3
	end := dispatchStart + patVTailWindow
	if end+5 > len(buf) {
		end = len(buf) - 5
	}
	for j := dispatchStart; j < end; j++ {
		if buf[j] != 0xFF {
			continue
		}
		modrm := buf[j+1]
		switch modrm {
		case 0x60, 0x50, 0x20, 0x10: // [rax+disp8] / [rax]
			return buf[j+2], true
		case 0xA0, 0x90: // [rax+disp32]
			return buf[j+2], true
		case 0x15, 0x25: // [rip+disp32] (call/jmp through global fn-ptr)
			return 0xFF, true // sentinel: function-pointer table
		}
	}
	return 0, false
}

// matchVTableTailCall returns true if buf[i..] is `48 8B 00` (mov rax, [rax])
// followed within window bytes by a `FF (60|A0) ??` (jmp [rax+disp]) — the
// unambiguous vtable tail-call shape. Looks BACKWARDS up to lookback bytes
// for the most recent `48 8B 05 ?? ?? ?? ??` (mov rax, [rip+disp]) and
// reports its disp32. Caller uses that as the loaded-global candidate.
func matchVTableTailCall(buf []byte, i int, lookback, window int) (globalDisp int32, slotByte byte, globalOff int, ok bool) {
	if i+3+window+3 > len(buf) {
		return 0, 0, 0, false
	}
	if buf[i] != 0x48 || buf[i+1] != 0x8B || buf[i+2] != 0x00 {
		return 0, 0, 0, false
	}
	// Find vtable JMP within window
	found := false
	for j := i + 3; j+2 < i+3+window && j+5 < len(buf); j++ {
		if buf[j] != 0xFF {
			continue
		}
		modrm := buf[j+1]
		if modrm == 0x60 || modrm == 0xA0 { // jmp [rax+disp8] or [rax+disp32]
			slotByte = buf[j+2]
			found = true
			break
		}
	}
	if !found {
		return 0, 0, 0, false
	}
	// Look back for a `48 8B 05 ?? ?? ?? ??` (mov rax, [rip+disp]) — the
	// most recent such load.
	bk := i - 1
	if bk-lookback < 0 {
		bk = lookback
	}
	for j := i - 7; j >= i-lookback && j >= 0; j-- {
		if buf[j] == 0x48 && buf[j+1] == 0x8B && buf[j+2] == 0x05 {
			disp := int32(binary.LittleEndian.Uint32(buf[j+3 : j+7]))
			return disp, slotByte, j, true
		}
	}
	return 0, 0, 0, false
}

func cmdPattern(proc string, topN int) {
	r, pid, base, size := mustOpen(proc)
	defer procCloseHandle.Call(r.h)
	fmt.Printf("PID %d  %q base=0x%X size=0x%X\n", pid, proc, base, size)
	fmt.Printf("  TWO-PASS scan:\n")
	fmt.Printf("    pass 1: 48 8B 00 ... FF (60|A0) ?? (vtable tail-call)\n")
	fmt.Printf("    pass 2: backward scan for 48 8B 05 ?? ?? ?? ?? (rip-rel global load)\n\n")

	// Per-target stats. firstSite captures the lowest call-site address per
	// target so the operator can `disasm` a deterministic location later.
	// slotCounts tallies which vtable slot (FF 60 XX) each target dispatches
	// through; for the real GMalloc one slot dominates (Malloc).
	counts := make(map[uintptr]int)
	firstSite := make(map[uintptr]uintptr)
	slotCounts := make(map[uintptr]map[byte]int)

	const chunk = 1 << 20
	overlap := patSize - 1
	regionsScanned := 0
	bytesScanned := uintptr(0)

	for _, rg := range r.regions() {
		if rg.protect&pageGuard != 0 {
			continue
		}
		// Only executable regions can hold instructions.
		if rg.protect&(pageExecuteRead|pageExecuteRW|pageExecuteWC) == 0 {
			continue
		}
		regionsScanned++

		// Carve into overlapping chunks so a pattern straddling a chunk
		// boundary is still seen by at least one read.
		for off := uintptr(0); off < rg.size; {
			n := chunk + overlap
			if off+uintptr(n) > rg.size {
				n = int(rg.size - off)
			}
			if n < patSize {
				break
			}
			buf := make([]byte, n)
			got, _ := r.read(rg.base+off, buf)
			if got < patSize {
				break
			}
			bytesScanned += uintptr(got)
			const lookback = 48
			const dispWindow = 32
			for i := lookback; i+3+dispWindow+3 <= got; i++ {
				globalDisp, slot, globalOff, ok := matchVTableTailCall(buf, i, lookback, dispWindow)
				if !ok {
					continue
				}
				// globalOff is the position of `48 8B 05` (the global-load
				// mov). RIP after that instruction = globalOff + 7.
				ripAddr := rg.base + off + uintptr(globalOff) + 7
				tgt := uintptr(int64(ripAddr) + int64(globalDisp))
				site := rg.base + off + uintptr(globalOff)
				counts[tgt]++
				if cur, ok := firstSite[tgt]; !ok || site < cur {
					firstSite[tgt] = site
				}
				if slotCounts[tgt] == nil {
					slotCounts[tgt] = make(map[byte]int)
				}
				slotCounts[tgt][slot]++
			}
			// Advance by chunk (not chunk+overlap) so the next read overlaps
			// the previous one by `overlap` bytes.
			off += chunk
		}
		fmt.Fprintf(os.Stderr, "  scanned %d region(s), %d MB\r",
			regionsScanned, bytesScanned/(1024*1024))
	}
	fmt.Fprintf(os.Stderr, "\n")

	type ent struct {
		target uintptr
		count  int
	}
	ents := make([]ent, 0, len(counts))
	for t, c := range counts {
		ents = append(ents, ent{t, c})
	}
	sort.Slice(ents, func(i, j int) bool {
		if ents[i].count != ents[j].count {
			return ents[i].count > ents[j].count
		}
		return ents[i].target < ents[j].target
	})

	totalHits := 0
	for _, e := range ents {
		totalHits += e.count
	}
	fmt.Printf("  found %d distinct targets across %d hits\n\n", len(ents), totalHits)

	limit := topN
	if limit <= 0 || limit > len(ents) {
		limit = len(ents)
	}

	fmt.Printf("  %-20s %-8s %-8s %-20s %s\n",
		"TARGET (GMalloc?)", "HITS", "SLOT", "SAMPLE SITE", "TARGET MOD-RVA")
	for i := 0; i < limit; i++ {
		e := ents[i]
		tgtRVA := "(outside module)"
		if e.target >= base && e.target < base+uintptr(size) {
			tgtRVA = fmt.Sprintf("0x%X", e.target-base)
		}
		siteRVA := ""
		s := firstSite[e.target]
		if s >= base && s < base+uintptr(size) {
			siteRVA = fmt.Sprintf(" (RVA 0x%X)", s-base)
		}
		// Dominant slot for this target.
		slotStr := ""
		if sm := slotCounts[e.target]; sm != nil {
			var topSlot byte
			var topN int
			for k, v := range sm {
				if v > topN {
					topN = v
					topSlot = k
				}
			}
			slotStr = fmt.Sprintf("0x%02X x%d", topSlot, topN)
		}
		fmt.Printf("  0x%-18X %-8d %-8s 0x%-18X %s%s\n",
			e.target, e.count, slotStr, s, tgtRVA, siteRVA)
	}

	if len(ents) > 0 {
		top := ents[0]
		fmt.Printf("\n  >>> GMalloc candidate: 0x%X  (hits=%d)\n", top.target, top.count)
		// Dominant slot for the top candidate.
		var topSlot byte
		var topN int
		for k, v := range slotCounts[top.target] {
			if v > topN {
				topN = v
				topSlot = k
			}
		}
		fmt.Printf("      Dominant vtable slot dispatched through: 0x%02X (== Malloc slot index %d)\n",
			topSlot, topSlot/8)
		if top.target >= base && top.target < base+uintptr(size) {
			fmt.Printf("      GMalloc mod-RVA: 0x%X\n", top.target-base)
		}
		fmt.Printf("      Next steps:\n")
		fmt.Printf("        usmapdump peek   %s 0x%X 8\n", proc, top.target)
		fmt.Printf("          → reads the FMalloc* pointer stored AT GMalloc\n")
		fmt.Printf("        usmapdump peek   %s 0x<FMalloc_ptr> 8\n", proc)
		fmt.Printf("          → first 8 bytes = vtable pointer\n")
		fmt.Printf("        usmapdump vtdump %s 0x<vtable_ptr> 24\n", proc)
		fmt.Printf("          → dump the FMalloc vtable\n")
		fmt.Printf("        usmapdump disasm %s 0x%X 48\n", proc, firstSite[top.target])
		fmt.Printf("          → see the full inlined site with vtable dispatch\n")
	}
}

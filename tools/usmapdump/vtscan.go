// vtscan.go — frequency-based vtable discovery (R2.3 strategy v3).
//
// Premise: a real shared C++ vtable like UClass's appears as the first qword of every
// instance of that class in the process (thousands of times). Random data, return
// addresses, code immediates do NOT have this property — they're scattered noise.
//
// So instead of searching for a name and hoping the candidates land in real UObjects,
// we histogram every qword-aligned exec-pointer in readable memory. The top entries
// (popularity ≥ 50, "looks like a vtable") are the engine's shared vtables. From any
// such vtable we can:
//   1. find every position in memory whose qword is that vtable → UObject candidates
//   2. read each candidate's NamePrivate at the standard offsets → it decodes to the
//      object's class name (Actor, GameMode, ContentManifest, …)
//   3. find the one named "Class" / "ScriptStruct" / "Enum" → those are the metaclasses
//
// This bypasses FName-search noise entirely.

package main

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"os"
	"sort"
)

type vtRef struct {
	addr  uintptr
	count int
}

// histogramAnyPtrs walks READABLE, NON-EXECUTABLE committed memory (heap-ish) and
// counts how often each 8-byte-aligned userspace pointer appears as a qword — WITHOUT
// requiring the pointer's TARGET to be executable. That's the key fix vs. the previous
// version: vtable pointers themselves live in .rdata (read-only data, NOT exec). We
// were filtering out exactly the values we wanted. The post-filter (looksLikeVtable)
// catches real vtables by reading their contents and checking they're function ptrs.
func histogramAnyPtrs(r *reader) map[uintptr]int {
	counts := make(map[uintptr]int, 1<<18)
	const chunkSz = 32 << 20
	const anyExec = 0x10 | 0x20 | 0x40 | 0x80
	var scannedMB uintptr
	for _, rg := range r.regions() {
		if !readable(rg.protect) {
			continue
		}
		if rg.protect&anyExec != 0 {
			continue // skip code regions
		}
		for chunkBase := rg.base; chunkBase < rg.base+rg.size; chunkBase += chunkSz {
			end := chunkBase + chunkSz
			if end > rg.base+rg.size {
				end = rg.base + rg.size
			}
			buf := make([]byte, end-chunkBase)
			got, _ := r.read(chunkBase, buf)
			if got < 8 {
				continue
			}
			buf = buf[:got]
			for o := 0; o+8 <= len(buf); o += 8 {
				v := u64(buf[o:])
				if v < 0x10000 || v >= 0x7FFFFFFFFFFF || v%8 != 0 {
					continue
				}
				counts[v]++
			}
			scannedMB += uintptr(got) / (1024 * 1024)
			if scannedMB > 0 && scannedMB%512 == 0 {
				fmt.Fprintf(os.Stderr, "  ...histogrammed %d MB data, %d unique ptrs\r",
					scannedMB, len(counts))
			}
		}
	}
	fmt.Fprintln(os.Stderr)
	return counts
}

// histogramSummary prints how many unique pointers fall in each count bucket — gives
// an instant view of whether the heap has shared vtables (long-tail with high-count
// outliers) or is dominated by single-occurrence noise.
func histogramSummary(counts map[uintptr]int) {
	buckets := []struct {
		lo, hi int
		name   string
	}{
		{1, 1, "==1"}, {2, 4, "2-4"}, {5, 19, "5-19"},
		{20, 99, "20-99"}, {100, 999, "100-999"}, {1000, 1 << 30, ">=1000"},
	}
	var counts2 [6]int
	max := 0
	for _, c := range counts {
		if c > max {
			max = c
		}
		for i, b := range buckets {
			if c >= b.lo && c <= b.hi {
				counts2[i]++
				break
			}
		}
	}
	fmt.Printf("  histogram bucket distribution (max count seen=%d):\n", max)
	for i, b := range buckets {
		fmt.Printf("    %-8s %d\n", b.name, counts2[i])
	}
}

// findInstanceAddrs returns every qword-aligned position in readable memory whose
// value equals vt. Slow for one-off calls. Used by the legacy path only — for bulk
// queries (every popular vtable) use collectAllInstancesByVtable below, which is
// O(memory) not O(memory * vtables).
func findInstanceAddrs(r *reader, vt uintptr) []uintptr {
	target := make([]byte, 8)
	binary.LittleEndian.PutUint64(target, uint64(vt))
	var out []uintptr
	const chunkSz = 32 << 20
	for _, rg := range r.regions() {
		if !readable(rg.protect) {
			continue
		}
		for chunkBase := rg.base; chunkBase < rg.base+rg.size; chunkBase += chunkSz {
			end := chunkBase + chunkSz
			if end > rg.base+rg.size {
				end = rg.base + rg.size
			}
			buf := make([]byte, end-chunkBase)
			got, _ := r.read(chunkBase, buf)
			if got < 8 {
				continue
			}
			buf = buf[:got]
			idx := 0
			for {
				rel := bytes.Index(buf[idx:], target)
				if rel < 0 {
					break
				}
				pos := idx + rel
				idx = pos + 8
				if pos%8 == 0 {
					out = append(out, chunkBase+uintptr(pos))
				}
			}
		}
	}
	return out
}

// collectAllInstancesByVtable: ONE memory pass that, for the given set of vtable
// addresses, returns a map of vtable -> all qword-aligned positions in DATA memory
// holding that vtable value. Replaces 940 separate scans with a single scan + N hash
// lookups per qword. O(memory), not O(memory * N).
func collectAllInstancesByVtable(r *reader, vtables map[uintptr]bool) map[uintptr][]uintptr {
	out := make(map[uintptr][]uintptr, len(vtables))
	const chunkSz = 32 << 20
	const anyExec = 0x10 | 0x20 | 0x40 | 0x80
	var scannedMB uintptr
	for _, rg := range r.regions() {
		if !readable(rg.protect) {
			continue
		}
		if rg.protect&anyExec != 0 {
			continue
		}
		for chunkBase := rg.base; chunkBase < rg.base+rg.size; chunkBase += chunkSz {
			end := chunkBase + chunkSz
			if end > rg.base+rg.size {
				end = rg.base + rg.size
			}
			buf := make([]byte, end-chunkBase)
			got, _ := r.read(chunkBase, buf)
			if got < 8 {
				continue
			}
			buf = buf[:got]
			for o := 0; o+8 <= len(buf); o += 8 {
				v := u64(buf[o:])
				if vtables[v] {
					out[v] = append(out[v], chunkBase+uintptr(o))
				}
			}
			scannedMB += uintptr(got) / (1024 * 1024)
			if scannedMB > 0 && scannedMB%512 == 0 {
				fmt.Fprintf(os.Stderr, "  ...collecting instances: %d MB\r", scannedMB)
			}
		}
	}
	fmt.Fprintln(os.Stderr)
	return out
}

// findMetaclassInInstances: given a pre-collected list of instance addresses for
// some vtable, find the instance whose NamePrivate == targetName AND whose
// ClassPrivate points back to itself (the metaclass self-class signature).
// In-memory only — no RPM scans. Returns (addr, nameOff, classOff, ok).
func findMetaclassInInstances(r *reader, p *pool, addrs []uintptr, targetName string) (uintptr, uintptr, uintptr, bool) {
	for _, no := range []uintptr{0x18, 0x1C, 0x20, 0x14, 0x28} {
		for _, addr := range addrs {
			id, _ := r.u32(addr + no)
			if id == 0 {
				continue
			}
			if p.name(r, id) != targetName {
				continue
			}
			for _, co := range []uintptr{0x10, 0x08, 0x18, 0x20} {
				if r.ptr(addr+co) == addr {
					return addr, no, co, true
				}
			}
		}
	}
	return 0, 0, 0, false
}

// topPointersByCount returns the most popular pointers (no shape filter), sorted desc.
func topPointersByCount(counts map[uintptr]int, minCount, topN int) []vtRef {
	var refs []vtRef
	for v, c := range counts {
		if c >= minCount {
			refs = append(refs, vtRef{v, c})
		}
	}
	sort.Slice(refs, func(i, j int) bool { return refs[i].count > refs[j].count })
	if len(refs) > topN {
		refs = refs[:topN]
	}
	return refs
}

// vtablesByFrequency returns top-N exec-pointers that (a) look like real vtables and
// (b) appear ≥ minCount times in memory.
func vtablesByFrequency(r *reader, em *execMap, counts map[uintptr]int, minCount, topN int) []vtRef {
	refs := topPointersByCount(counts, minCount, topN)
	out := refs[:0]
	for _, v := range refs {
		if looksLikeVtable(r, em, v.addr) {
			out = append(out, v)
		}
	}
	return out
}

// dumpTopPointers prints the first 8 qwords each top pointer references plus their
// exec-region membership. Diagnostic — lets us see why looksLikeVtable rejects them.
func dumpTopPointers(r *reader, em *execMap, refs []vtRef, n int) {
	if n > len(refs) {
		n = len(refs)
	}
	fmt.Println("  top pointers (unfiltered) — first 8 qwords each:")
	for i := 0; i < n; i++ {
		v := refs[i]
		var buf [64]byte
		got, _ := r.read(v.addr, buf[:])
		fmt.Printf("    [%d] vt=0x%-14X count=%d aligned=%v read=%d\n",
			i, v.addr, v.count, v.addr%8 == 0, got)
		if got < 64 {
			continue
		}
		execHits := 0
		for k := 0; k < 8; k++ {
			q := u64(buf[k*8:])
			ex := em.contains(q)
			if ex {
				execHits++
			}
			fmt.Printf("        q[%d] = 0x%-16X  exec?=%v\n", k, q, ex)
		}
		fmt.Printf("        => exec-hit count = %d/8\n", execHits)
	}
}

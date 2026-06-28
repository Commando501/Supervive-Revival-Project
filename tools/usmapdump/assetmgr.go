// assetmgr.go — locate the live ULokiAssetManager singleton and inspect its state.
//
// Purpose (Milestone: native missions/content unlock): the custom LokiAssetManager
// registers primary assets ONLY from the content-service manifest's named maps and never
// runs UE's config-driven directory scan, so baked primary assets (missions, mission
// pools, and the hunter roster) never register — confirmed via the backend probes. The
// fix is to trigger the scan natively. This command does the read-only RE foundation:
//   1. find the FName id for "LokiAssetManager" (full-pool walk; it's not a block-0 name)
//   2. find the UObject(s) whose NamePrivate == that id, classify the UClass among them
//      (its ClassPrivate->NamePrivate == "Class")
//   3. scan for instances whose ClassPrivate == that UClass (the CDO + the live singleton)
//   4. dump the singleton's vtable + header so we can (next) disassemble its
//      StartInitialLoading override and locate ScanPrimaryAssetTypesFromConfig.
//
// Read-only: same VM_READ-only handle as the rest of usmapdump. Nothing is written or
// executed in the target.
package main

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"os"
)

// findNameIDFull walks EVERY pool block (not just block 0) for an exact ANSI match.
// Returns the composed FName id (block<<16 | offsetIndex) and whether found.
func findNameIDFull(r *reader, p *pool, target string) (uint32, bool) {
	for bi, blk := range p.blocks {
		if blk == 0 {
			continue
		}
		off := 0
		const maxOff = 0x10000 * fnameStride
		for off < maxOff {
			s, sz, ok := r.decodeEntryAnsi(blk+uintptr(off), p.layout)
			if sz == 0 {
				break
			}
			if ok && s == target {
				return uint32(bi)<<16 | uint32(off/fnameStride), true
			}
			off += align2(sz)
		}
	}
	return 0, false
}

// objsByNameID scans readable memory for UObjects whose NamePrivate (4-byte
// ComparisonIndex at one of the plausible name offsets) == nameID and whose first qword
// is a vtable in executable memory. Returns (addr, nameOff) pairs.
func objsByNameID(r *reader, em *execMap, nameID uint32) []struct {
	addr    uintptr
	nameOff uintptr
} {
	target := make([]byte, 4)
	binary.LittleEndian.PutUint32(target, nameID)
	tryNameOffsets := []uintptr{0x18, 0x1C, 0x20, 0x24, 0x28, 0x14}
	var out []struct {
		addr    uintptr
		nameOff uintptr
	}
	var rawHits, alignedHits, vtFail int
	seen := map[uintptr]bool{}
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
			readLen := end - chunkBase + 4
			if chunkBase+readLen > rg.base+rg.size {
				readLen = rg.base + rg.size - chunkBase
			}
			buf := make([]byte, readLen)
			got, _ := r.read(chunkBase, buf)
			if got < 4 {
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
				idx = pos + 4
				rawHits++
				if pos%4 != 0 {
					continue
				}
				alignedHits++
				// This build is case-preserving (12-byte FName: ComparisonIndex,
				// DisplayIndex, Number). findNameIDFull matched by decoded STRING, which
				// yields the DISPLAY id. So the id can sit at the NamePrivate start
				// (ComparisonIndex == DisplayIndex for canonical names) OR 4 bytes in (the
				// DisplayIndex slot, when comparison != display for mixed case). Try both:
				// preDeltas[0]=0 => pos is ComparisonIndex; =4 => pos is DisplayIndex.
				for _, pre := range []uintptr{0, 4} {
					if uintptr(pos) < pre {
						continue
					}
					npStart := chunkBase + uintptr(pos) - pre // NamePrivate (ComparisonIndex) start
					for _, nameOff := range tryNameOffsets {
						if npStart < nameOff {
							continue
						}
						objAddr := npStart - nameOff
						if seen[objAddr] {
							continue
						}
						vt := r.ptr(objAddr)
						if !em.contains(vt) || !looksLikeVtable(r, em, vt) {
							vtFail++
							continue
						}
						seen[objAddr] = true
						out = append(out, struct {
							addr    uintptr
							nameOff uintptr
						}{objAddr, nameOff})
					}
				}
			}
		}
	}
	fmt.Fprintf(os.Stderr, "  [objsByNameID diag] id=0x%X rawHits=%d alignedHits=%d vtFail=%d found=%d\n",
		nameID, rawHits, alignedHits, vtFail, len(out))
	return out
}

func cmdAssetMgr(name string) {
	r, pid, base, size := mustOpen(name)
	defer procCloseHandle.Call(r.h)
	fmt.Printf("PID %d  %q base=0x%X size=0x%X\n", pid, name, base, size)

	p, err := findNamePool(r)
	if err != nil {
		fmt.Println("ERROR (name pool):", err)
		os.Exit(1)
	}
	fmt.Printf("  GNames blocks=%d layout=%s\n", len(p.blocks), p.layout)
	gpool = p
	em := r.execMap()

	// Reuse the PROVEN reflection-discovery path (same as cmdObjects): histogram all
	// data-region pointers, keep the popular vtable-shaped ones, collect every instance
	// of each in one pass, then identify the UClass metaclass by self-class signature.
	// This reads mixed-case names correctly (AIController, LokiAssetManager, ...).
	fmt.Println("  histogramming data-region pointers...")
	counts := histogramAnyPtrs(r)
	popular := vtablesByFrequency(r, em, counts, 20, 20000)
	fmt.Printf("  %d popular vtables\n", len(popular))
	vtset := make(map[uintptr]bool, len(popular))
	for _, v := range popular {
		vtset[v.addr] = true
	}
	instMap := collectAllInstancesByVtable(r, vtset)

	var classVtable, nameOff, classOff uintptr
	for _, v := range popular {
		if _, no, co, ok := findMetaclassInInstances(r, p, instMap[v.addr], "Class"); ok {
			classVtable, nameOff, classOff = v.addr, no, co
			break
		}
	}
	if classVtable == 0 {
		fmt.Println("ERROR: UClass metaclass not found")
		os.Exit(1)
	}
	fmt.Printf("  UClass vtable=0x%X nameOff=0x%X classOff=0x%X\n", classVtable, nameOff, classOff)

	// Find ALL UClass instances named "LokiAssetManager" (there may be SKEL/REINST/dup
	// variants; the live manager points at one specific object).
	var amClasses []uintptr
	for _, addr := range instMap[classVtable] {
		id, _ := r.u32(addr + nameOff)
		if p.name(r, id) == "LokiAssetManager" {
			amClasses = append(amClasses, addr)
		}
	}
	if len(amClasses) == 0 {
		fmt.Println("ERROR: LokiAssetManager UClass not found among UClass instances")
		os.Exit(1)
	}
	fmt.Printf("\n  %d UClass instance(s) named LokiAssetManager:\n", len(amClasses))
	for _, c := range amClasses {
		fmt.Printf("    @0x%X\n", c)
	}
	amClass := amClasses[0]

	// Scan for INSTANCES: UObjects whose ClassPrivate == amClass (CDO + live singleton).
	insts := objsByClassPtr(r, em, amClass, classOff, nameOff)
	fmt.Printf("\n  %d instance(s) of LokiAssetManager (ClassPrivate==0x%X):\n", len(insts), amClass)
	for _, ia := range insts {
		nid, _ := r.u32(ia + nameOff)
		fmt.Printf("    instance @0x%X name=%q\n", ia, p.name(r, nid))
	}

	// Dump the live singleton (prefer the non-CDO instance) header + vtable.
	var singleton uintptr
	for _, ia := range insts {
		nid, _ := r.u32(ia + nameOff)
		nm := p.name(r, nid)
		if len(nm) < 9 || nm[:9] != "Default__" {
			singleton = ia
			break
		}
	}
	if singleton == 0 && len(insts) > 0 {
		singleton = insts[0]
	}
	if singleton != 0 {
		fmt.Printf("\n  === live singleton @0x%X ===\n", singleton)
		dumpObjHeader(r, p, singleton, nameOff)
		vt := r.ptr(singleton)
		modLo, modHi := base, base+uintptr(size)
		vtRVA := ""
		if vt >= modLo && vt < modHi {
			vtRVA = fmt.Sprintf(" (module RVA 0x%X)", vt-base)
		}
		fmt.Printf("\n  vtable @0x%X%s — first 48 virtual slots (loc: MOD=module image RVA, PRIV=unpacked heap):\n", vt, vtRVA)
		for i := 0; i < 48; i++ {
			fn := r.ptr(vt + uintptr(i*8))
			loc := "?"
			if fn >= modLo && fn < modHi {
				loc = fmt.Sprintf("MOD  rva=0x%X", fn-base)
			} else if em.contains(fn) {
				loc = "PRIV(exec)"
			} else if fn == 0 {
				loc = "null"
			}
			fmt.Printf("    vt[%2d] = 0x%-14X  %s\n", i, fn, loc)
		}
	}
}

// objsByClassPtr finds 8-aligned positions holding classAddr (a ClassPrivate field). For
// each raw hit it reports, treating the hit as the ClassPrivate at classOff, whether the
// would-be object has a valid vtable. Diagnostic-rich: prints raw hit count + a sample.
func objsByClassPtr(r *reader, em *execMap, classAddr, classOff, nameOff uintptr) []uintptr {
	target := make([]byte, 8)
	binary.LittleEndian.PutUint64(target, uint64(classAddr))
	seen := map[uintptr]bool{}
	var out []uintptr
	var rawHits, sample int
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
			readLen := end - chunkBase + 8
			if chunkBase+readLen > rg.base+rg.size {
				readLen = rg.base + rg.size - chunkBase
			}
			buf := make([]byte, readLen)
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
				if pos%8 != 0 {
					continue
				}
				rawHits++
				hitAddr := chunkBase + uintptr(pos)
				// Print EVERY hit fully classified: treat hit as ClassPrivate@+0x18, dump the
				// object's candidate vtable + name, so we can see exactly which hit (if any)
				// is the live singleton / CDO.
				if sample < 40 {
					sample++
					obj := hitAddr - 0x18 // ClassPrivate at +0x18 (this build's UObject layout)
					vt := r.ptr(obj)
					nid, _ := r.u32(obj + 0x20) // NamePrivate at +0x20
					fmt.Fprintf(os.Stderr, "    [hit %2d] field@0x%X obj@0x%X vt=0x%X vtExec=%v looksVT=%v name=%q\n",
						sample, hitAddr, obj, vt, em.contains(vt), looksLikeVtable(r, em, vt), p0name(r, nid))
				}
				// Accept a hit as a real instance if obj=hit-0x18 has a real vtable. The
				// vtable POINTER lives in .rdata (NOT exec), so validate via looksLikeVtable
				// (which checks the vtable's ENTRIES are exec), not em.contains(vt).
				obj := hitAddr - 0x18
				if seen[obj] {
					continue
				}
				if looksLikeVtable(r, em, r.ptr(obj)) {
					seen[obj] = true
					out = append(out, obj)
				}
			}
		}
	}
	fmt.Fprintf(os.Stderr, "  [objsByClassPtr diag] classAddr=0x%X rawHits=%d found=%d\n", classAddr, rawHits, len(out))
	return out
}

// p0name is set to the active pool's name() at the start of cmdAssetMgr so deep helpers
// can decode FNames for diagnostics without threading the pool through every call.
var gpool *pool

func p0name(r *reader, id uint32) string {
	if gpool == nil {
		return ""
	}
	return gpool.name(r, id)
}

func dumpObjHeader(r *reader, p *pool, addr, nameOff uintptr) {
	buf := make([]byte, 0x40)
	r.read(addr, buf)
	for off := 0; off+8 <= 0x40; off += 8 {
		v := u64(buf[off:])
		fmt.Printf("    +0x%02X = 0x%-16X\n", off, v)
	}
	nid, _ := r.u32(addr + nameOff)
	fmt.Printf("    name(@+0x%X) = %q\n", nameOff, p.name(r, nid))
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

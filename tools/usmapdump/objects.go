// objects.go — MILESTONE R2.3 (vtable strategy):
//
// Find UClass / UScriptStruct / UEnum instances *directly* by vtable scanning, no
// GUObjectArray required. This sidesteps the packed-binary problem that broke array
// pattern-matching (false positives whose int fields look like array headers).
//
// The trick:
//   1. Look up the FName id for "Class" by walking the name pool block 0.
//   2. Scan memory for the 8 bytes [classID, 0] (FName: id=classID, Number=0). The
//      ONE UObject in the process whose NamePrivate decodes to "Class" is the UClass
//      metaclass. Auto-tune NamePrivate offset by which makes a valid UObject:
//      first qword is a pointer in an executable region, +0x10 (ClassPrivate) is a
//      pointer to another UObject whose first qword is also executable.
//   3. The metaclass's first qword IS the UClass vtable. Scan all qword-aligned
//      readable memory for that exact value — every match is a UClass instance.
//   4. Same trick for "ScriptStruct" and "Enum".

package main

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"os"
	"sort"
)

// findNameID walks block 0 of the pool looking for an exact ANSI name match.
// Returns its FName id and whether found. Sequential walk because block 0 packs
// the engine's most-common names — all the metaclass names we need ("Class",
// "ScriptStruct", "Enum") live there.
func findNameID(r *reader, p *pool, target string) (uint32, bool) {
	if len(p.blocks) == 0 {
		return 0, false
	}
	off := 0
	const maxOff = 0x10000 * fnameStride
	for off < maxOff {
		s, sz, ok := r.decodeEntryAnsi(p.blocks[0]+uintptr(off), p.layout)
		if sz == 0 {
			break
		}
		if ok && s == target {
			return uint32(off / fnameStride), true
		}
		off += align2(sz)
	}
	return 0, false
}

// findMetaclass locates the single UObject whose NamePrivate matches the given FName id.
// We search for just the 4-byte ComparisonIndex (not the whole FName) because this build
// is CASE-PRESERVING (Len10+probehash layout), so FName is 12 bytes (ComparisonIndex,
// DisplayIndex, Number), not 8 — searching for the 8-byte [id, 0] would miss everything.
// Each 4-byte hit is validated by trying all plausible UObject layouts.
//
// On the FIRST call we report how many ComparisonIndex hits we got and how many had a
// valid vtable, so a failed search prints something actionable.
func findMetaclass(r *reader, p *pool, em *execMap, nameID uint32, verbose bool) (uintptr, uintptr, uintptr, bool) {
	target := make([]byte, 4)
	binary.LittleEndian.PutUint32(target, nameID)

	tryNameOffsets := []uintptr{0x18, 0x1C, 0x20, 0x24, 0x28, 0x14}
	tryClassOffsets := []uintptr{0x10, 0x08, 0x18, 0x20, 0x28}

	type cand struct {
		addr            uintptr
		nameOff, clsOff uintptr
		clsAddr         uintptr
		vt              uintptr
		internalIdx     uint32
	}
	var hits, vtok, vtshape, idxok int
	var candWithExec []cand

	regs := r.regions()
	// CRITICAL: do NOT skip huge regions — UE's UObject heap arena can be multi-GB.
	// Chunk-iterate so we don't allocate a 4GB buffer.
	const chunkSz = 32 << 20 // 32 MB per pass
	scannedMB := uintptr(0)
	for _, rg := range regs {
		if !readable(rg.protect) {
			continue
		}
		for chunkBase := rg.base; chunkBase < rg.base+rg.size; chunkBase += chunkSz {
			end := chunkBase + chunkSz
			if end > rg.base+rg.size {
				end = rg.base + rg.size
			}
			// Read one extra byte past chunk so 0x217 straddling boundary isn't lost.
			readLen := end - chunkBase + 7
			if chunkBase+readLen > rg.base+rg.size {
				readLen = rg.base + rg.size - chunkBase
			}
			buf := make([]byte, readLen)
			got, _ := r.read(chunkBase, buf)
			if got < 4 {
				continue
			}
			buf = buf[:got]
			scannedMB += uintptr(got) / (1024 * 1024)
			if verbose && scannedMB > 0 && scannedMB%512 == 0 {
				fmt.Fprintf(os.Stderr, "  ...scanned %d MB for metaclass\r", scannedMB)
			}
			idx := 0
			for {
				rel := bytes.Index(buf[idx:], target)
				if rel < 0 {
					break
				}
				pos := idx + rel
				idx = pos + 4
				if pos%4 != 0 {
					continue
				}
				hits++
			// Best heuristic for the case-preserving FName: the very NEXT 4 bytes (the
			// DisplayIndex slot) is either == ComparisonIndex (canonical case, the common
			// case for engine names like "Class") or zero.
			if pos+8 <= len(buf) {
				next4 := u32le(buf[pos+4:])
				if next4 != 0 && next4 != nameID {
					continue
				}
			}
			for _, nameOff := range tryNameOffsets {
				if uintptr(pos) < nameOff {
					continue
				}
				objAddr := chunkBase + uintptr(pos) - nameOff
				vt := r.ptr(objAddr)
				if !em.contains(vt) {
					continue
				}
				vtok++
				// Diagnostic: for the very first vt-in-exec hit per call, dump the
				// vtable raw so we can see why it's failing shape (or confirm it's
				// passing). Cheap; once.
				if verbose && vtok <= 3 {
					var buf [64]byte
					r.read(vt, buf[:])
					fmt.Printf("    [vt diag] candidate addr=0x%X nameOff=0x%X vt=0x%X aligned=%v\n",
						objAddr, nameOff, vt, vt%8 == 0)
					for k := 0; k < 8; k++ {
						q := uintptr(0)
						for b := 0; b < 8; b++ {
							q |= uintptr(buf[k*8+b]) << (8 * b)
						}
						fmt.Printf("      vt[%d] = 0x%-16X  exec?=%v\n", k, q, em.contains(q))
					}
				}
				if !looksLikeVtable(r, em, vt) {
					continue
				}
				vtshape++
				ii, _ := r.u32(objAddr + 0x0C)
				if ii > 10_000_000 {
					continue
				}
				idxok++
				for _, classOff := range tryClassOffsets {
					classPtr := r.ptr(objAddr + classOff)
					if !userspacePtr(classPtr) {
						continue
					}
					if len(candWithExec) < 50 {
						candWithExec = append(candWithExec, cand{objAddr, nameOff, classOff, classPtr, vt, ii})
					}
				}
			}
		}
		}
	}
	if verbose {
		fmt.Fprintf(os.Stderr, "\n")
	}

	if verbose {
		fmt.Printf("  search id=0x%X: 4B hits=%d  vt-in-exec=%d  vt-shape-ok=%d  idx-ok=%d  classPtr-ok=%d\n",
			nameID, hits, vtok, vtshape, idxok, len(candWithExec))
		for i, c := range candWithExec {
			if i >= 8 {
				break
			}
			fmt.Printf("    cand[%d] addr=0x%X vt=0x%X nameOff=0x%X classOff=0x%X idx=%d clsAddr=0x%X\n",
				i, c.addr, c.vt, c.nameOff, c.clsOff, c.internalIdx, c.clsAddr)
		}
	}

	if len(candWithExec) == 0 {
		return 0, 0, 0, false
	}
	// Self-class signal: the UClass metaclass is the unique UObject whose ClassPrivate
	// points to itself (its own type IS UClass). Pick that one if present.
	for _, c := range candWithExec {
		if c.clsAddr == c.addr {
			return c.addr, c.nameOff, c.clsOff, true
		}
	}
	// Otherwise prefer the candidate whose class's NamePrivate also reads "Class".
	for _, c := range candWithExec {
		id, _ := r.u32(c.clsAddr + c.nameOff)
		if id == nameID {
			return c.addr, c.nameOff, c.clsOff, true
		}
	}
	// Fallback: take the first; later decoding will reveal if it's wrong.
	c := candWithExec[0]
	return c.addr, c.nameOff, c.clsOff, true
}

// scanByVtable finds every qword-aligned occurrence of vtable in readable memory.
// Each hit is a candidate UObject; we validate by decoding its NamePrivate.
func scanByVtable(r *reader, p *pool, vtable uintptr, nameOff uintptr) []objref {
	target := make([]byte, 8)
	binary.LittleEndian.PutUint64(target, uint64(vtable))

	seen := make(map[uintptr]bool)
	var out []objref
	regs := r.regions()
	const chunkSz = 32 << 20
	for _, rg := range regs {
		if !readable(rg.protect) {
			continue
		}
		for chunkBase := rg.base; chunkBase < rg.base+rg.size; chunkBase += chunkSz {
			end := chunkBase + chunkSz
			if end > rg.base+rg.size {
				end = rg.base + rg.size
			}
			readLen := end - chunkBase + 7
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
				objAddr := chunkBase + uintptr(pos)
				if seen[objAddr] {
					continue
				}
				seen[objAddr] = true
				id, _ := r.u32(objAddr + nameOff)
				if id == 0 || id >= uint32(len(p.blocks))*0x10000 {
					continue
				}
				nm := p.name(r, id)
				if len(nm) == 0 || nm[0] == '<' {
					continue
				}
				out = append(out, objref{addr: objAddr, name: nm})
			}
		}
	}
	return out
}

type objref struct {
	addr uintptr
	name string
}

func cmdObjects(name string) {
	r, pid, base, size := mustOpen(name)
	defer procCloseHandle.Call(r.h)
	fmt.Printf("PID %d  %q base=0x%X size=0x%X\n", pid, name, base, size)

	p, err := findNamePool(r)
	if err != nil {
		fmt.Println("ERROR (name pool):", err)
		os.Exit(1)
	}
	fmt.Printf("  GNames blocks=%d layout=%s\n", len(p.blocks), p.layout)

	em := r.execMap()
	fmt.Printf("  exec regions: %d\n", len(em.regs))

	classID, ok := findNameID(r, p, "Class")
	if !ok {
		fmt.Println("ERROR: FName \"Class\" not found in name pool block 0")
		os.Exit(1)
	}
	structID, _ := findNameID(r, p, "ScriptStruct")
	enumID, _ := findNameID(r, p, "Enum")
	fmt.Printf("  FName ids: Class=0x%X ScriptStruct=0x%X Enum=0x%X\n", classID, structID, enumID)

	// PRIMARY STRATEGY (R2.3 v3): frequency-based vtable discovery.
	// Real shared vtables (UClass / UScriptStruct / UEnum) appear hundreds-to-thousands
	// of times in memory — once per instance. Histogram every qword-aligned exec ptr,
	// then for each popular vtable look for its instance named "Class" / "ScriptStruct"
	// / "Enum". Robust because we never search for FName bytes (which mostly hit noise).
	fmt.Println("\n  histogramming ALL 8-aligned ptrs in DATA regions (vtable ptrs live in .rdata, not exec)...")
	counts := histogramAnyPtrs(r)
	fmt.Printf("  %d unique 8-aligned ptrs in data\n", len(counts))
	histogramSummary(counts)

	// Diagnostic: top 5 unfiltered, so we see what dominates the histogram now.
	topUnfiltered := topPointersByCount(counts, 100, 5)
	dumpTopPointers(r, em, topUnfiltered, 5)

	popular := vtablesByFrequency(r, em, counts, 20, 20000)
	fmt.Printf("  %d real-looking vtables (count >= 20, shape-ok)\n", len(popular))
	if len(popular) > 0 {
		fmt.Println("  top 10 by frequency:")
		for i, v := range popular {
			if i >= 10 {
				break
			}
			fmt.Printf("    vt=0x%X  instances=%d\n", v.addr, v.count)
		}
	}

	// CRITICAL: collect every instance of every popular vtable in ONE memory pass.
	// Doing per-vtable scans would be 940 * 5 GB = literally hours. Single pass
	// with a hash-set lookup per qword runs in one scan's time (~1-2 min).
	vtableSet := make(map[uintptr]bool, len(popular))
	for _, v := range popular {
		vtableSet[v.addr] = true
	}
	fmt.Printf("\n  collecting instances for %d popular vtables in ONE pass...\n", len(popular))
	instMap := collectAllInstancesByVtable(r, vtableSet)
	totalInst := 0
	for _, list := range instMap {
		totalInst += len(list)
	}
	fmt.Printf("  collected %d total instances across %d vtables\n", totalInst, len(instMap))

	// STEP 1: find UClass via self-class signature (UClass.class IS UClass — the only
	// metaclass with ClassPrivate pointing to itself).
	var classMeta, classVtable, nameOff, classOff uintptr
	for _, v := range popular {
		addrs := instMap[v.addr]
		obj, no, co, ok := findMetaclassInInstances(r, p, addrs, "Class")
		if ok {
			classMeta, classVtable, nameOff, classOff = obj, v.addr, no, co
			fmt.Printf("  UClass metaclass @0x%X  vtable=0x%X (count=%d)  nameOff=0x%X classOff=0x%X (self-class verified)\n",
				obj, v.addr, v.count, no, co)
			break
		}
	}
	if classVtable == 0 {
		fmt.Println("\nERROR: UClass metaclass not found — frequency strategy yielded no self-class match.")
		os.Exit(1)
	}

	// STEP 2: UScriptStruct / UEnum themselves are UClass INSTANCES (their C++ type IS
	// UClass), so they live in the SAME UClass vtable instance list. No self-class —
	// just name match. Their ClassPrivate points to the UClass metaclass.
	findUClassInstanceByName := func(target string) uintptr {
		for _, addr := range instMap[classVtable] {
			id, _ := r.u32(addr + nameOff)
			if p.name(r, id) == target {
				return addr
			}
		}
		return 0
	}
	structMeta := findUClassInstanceByName("ScriptStruct")
	enumMeta := findUClassInstanceByName("Enum")
	fmt.Printf("  UScriptStruct meta-UClass @0x%X  (its ClassPrivate->UClass meta)\n", structMeta)
	fmt.Printf("  UEnum         meta-UClass @0x%X\n", enumMeta)

	// STEP 3: find the VTABLES used by ACTUAL UScriptStruct / UEnum instances (e.g.
	// FVector, EObjectFlags). Iterate popular vtables; the one whose instances have
	// ClassPrivate == structMeta is the UScriptStruct vtable. Same for enum.
	findVtableWhoseInstancesPointTo := func(meta uintptr) uintptr {
		for _, v := range popular {
			if v.addr == classVtable {
				continue
			}
			addrs := instMap[v.addr]
			// Check first few instances — if ANY has ClassPrivate == meta, this vtable's
			// instances are of that metaclass.
			hits := 0
			for i, addr := range addrs {
				if i >= 16 {
					break
				}
				if r.ptr(addr+classOff) == meta {
					hits++
				}
			}
			if hits >= 4 {
				return v.addr
			}
		}
		return 0
	}
	structVtable := findVtableWhoseInstancesPointTo(structMeta)
	enumVtable := findVtableWhoseInstancesPointTo(enumMeta)
	fmt.Printf("  UScriptStruct instance vtable=0x%X\n", structVtable)
	fmt.Printf("  UEnum         instance vtable=0x%X\n", enumVtable)
	_ = classMeta

	// Use the pre-collected instMap — no additional scans needed.
	resolveInstances := func(vt uintptr) []objref {
		if vt == 0 {
			return nil
		}
		raw := instMap[vt]
		out := make([]objref, 0, len(raw))
		for _, addr := range raw {
			id, _ := r.u32(addr + nameOff)
			if id == 0 || id >= uint32(len(p.blocks))*0x10000 {
				continue
			}
			nm := p.name(r, id)
			if len(nm) == 0 || nm[0] == '<' {
				continue
			}
			out = append(out, objref{addr: addr, name: nm})
		}
		return out
	}
	classes := resolveInstances(classVtable)
	structs := resolveInstances(structVtable)
	enums := resolveInstances(enumVtable)
	fmt.Printf("\n  UClass: %d   UScriptStruct: %d   UEnum: %d (from pre-collected instances)\n",
		len(classes), len(structs), len(enums))

	// Print samples — first 20 of each, sorted by name for readability.
	printSample := func(label string, list []objref) {
		if len(list) == 0 {
			return
		}
		cp := make([]objref, len(list))
		copy(cp, list)
		sort.Slice(cp, func(i, j int) bool { return cp[i].name < cp[j].name })
		fmt.Printf("\n  first %s names (sorted):\n", label)
		for i := 0; i < len(cp) && i < 20; i++ {
			fmt.Printf("    %-32s @0x%X\n", cp[i].name, cp[i].addr)
		}
	}
	printSample("UClass", classes)
	printSample("UScriptStruct", structs)
	printSample("UEnum", enums)

	if len(classes) > 100 && len(structs) > 50 {
		fmt.Println("\nR2.3 OK: reflection objects enumerated via vtable scan.")
	} else {
		fmt.Println("\nR2.3 PARTIAL: counts low — paste output; metaclass detection may need a tweak.")
		return
	}

	// R2.4 layout discovery: dump a few well-known UStructs and annotate pointers
	// that hit other UStructs we've enumerated. Reveals SuperStruct/Children/
	// ChildProperties offsets without guessing from stock UE5 docs.
	fmt.Println("\n=== R2.4 layout discovery ===")
	x := buildAddrIndex(classes, structs, enums)

	// Pick stable targets. Actor is the canonical UClass everyone inherits from;
	// AIController extends Controller. Vector2D is a tiny known UScriptStruct.
	pickTargets := []struct {
		label string
		list  []objref
		name  string
	}{
		{"UClass AIController", classes, "AIController"},
		{"UClass Actor", classes, "Actor"},
		{"UScriptStruct Vector", structs, "Vector"},
		{"UScriptStruct Transform", structs, "Transform"},
		{"UEnum AnimationKeyFormat", enums, "AnimationKeyFormat"},
	}
	for _, t := range pickTargets {
		if o, ok := pickByName(t.list, t.name); ok {
			inspectStruct(r, p, x, t.label, o.addr, 0xB0)
		} else {
			fmt.Printf("\n  (skipping %s — not found by exact name)\n", t.label)
		}
	}

	// Drill into actual FProperty / FField memory now that we know
	// ChildProperties lives at +0x58. Vector.X is the cleanest test: a single double
	// field with no parent. Read +0x58 of Vector, then dump 0x80 bytes there.
	fmt.Println("\n  === FField/FProperty layout discovery ===")
	dumpAtSuffix := func(label string, structAddr, fieldOff uintptr, n int) {
		fldPtr := r.ptr(structAddr + fieldOff)
		if fldPtr == 0 {
			fmt.Printf("\n  (%s @0x%X +0x%X is null, skip)\n", label, structAddr, fieldOff)
			return
		}
		inspectStruct(r, p, x, label+" FField @"+fmt.Sprintf("0x%X", fldPtr), fldPtr, n)
	}
	if vec, ok := pickByName(structs, "Vector"); ok {
		dumpAtSuffix("Vector.ChildProperties[0]", vec.addr, 0x58, 0x80)
	}
	if act, ok := pickByName(classes, "Actor"); ok {
		dumpAtSuffix("Actor.ChildProperties[0]", act.addr, 0x58, 0x80)
	}
	if t, ok := pickByName(structs, "Transform"); ok {
		dumpAtSuffix("Transform.ChildProperties[0]", t.addr, 0x58, 0x80)
	}

	// Walk Vector's full property chain — should print X, Y, Z each labeled with its
	// FFieldClass name ("DoubleProperty"). Discovery: read FFieldClass at FField+0x00,
	// then FName at FFieldClass+0x00 (assume same layout as elsewhere).
	fmt.Println("\n  === Vector property chain walk ===")
	if vec, ok := pickByName(structs, "Vector"); ok {
		propType := func(fld uintptr) string {
			fc := r.ptr(fld)
			if fc == 0 {
				return "<no class>"
			}
			// Try ComparisonIndex at +0x00 of FFieldClass first.
			id, _ := r.u32(fc)
			if nm := p.name(r, id); len(nm) > 0 && nm[0] != '<' {
				return nm
			}
			return fmt.Sprintf("<class@0x%X>", fc)
		}
		propName := func(fld uintptr) string {
			id, _ := r.u32(fld + 0x20)
			return p.name(r, id)
		}
		f := r.ptr(vec.addr + 0x58)
		for i := 0; i < 20 && f != 0; i++ {
			ext := r.ptr(f + 0x70)
			extTag := ""
			if ext != 0 {
				if tag := x.labelPtr(ext); tag != "" {
					extTag = " (Inner=" + tag + ")"
				}
			}
			fmt.Printf("    [%d] %-16s : %-24s @0x%X%s\n",
				i, propName(f), propType(f), f, extTag)
			f = r.ptr(f + 0x18) // Next
		}
	}

	// Dump FFieldClass for DoubleProperty and StructProperty so we can find FName offset.
	fmt.Println("\n  === FFieldClass layout (DoubleProperty & StructProperty) ===")
	dumpFC := func(label string, addr uintptr) {
		fmt.Printf("  %s FFieldClass @0x%X\n", label, addr)
		buf := make([]byte, 0x40)
		r.read(addr, buf)
		for off := 0; off+8 <= 0x40; off += 8 {
			v := u64(buf[off:])
			i32a := u32le(buf[off:])
			i32b := u32le(buf[off+4:])
			// Try as FName id at this offset
			extra := ""
			if i32a > 0 && i32a < uint32(len(p.blocks))*0x10000 {
				if nm := p.name(r, i32a); len(nm) > 0 && nm[0] != '<' {
					extra = fmt.Sprintf("  // i32a as FName: %q", nm)
				}
			}
			if i32b > 0 && i32b < uint32(len(p.blocks))*0x10000 {
				if nm := p.name(r, i32b); len(nm) > 0 && nm[0] != '<' {
					extra += fmt.Sprintf("  // i32b as FName: %q", nm)
				}
			}
			fmt.Printf("    +0x%02X = 0x%-16X  (i32 %d, %d)%s\n", off, v, int32(i32a), int32(i32b), extra)
		}
	}
	if vec, ok := pickByName(structs, "Vector"); ok {
		f := r.ptr(vec.addr + 0x58)
		if f != 0 {
			dumpFC("DoubleProperty (via FField+0x08)", r.ptr(f+0x08))
		}
	}
	if t, ok := pickByName(structs, "Transform"); ok {
		f := r.ptr(t.addr + 0x58)
		if f != 0 {
			dumpFC("StructProperty (via FField+0x08)", r.ptr(f+0x08))
		}
	}

	// Find an ArrayProperty in the wild — Actor has dozens. Dump one to discover
	// where FArrayProperty stores its Inner FProperty pointer.
	fmt.Println("\n  === ArrayProperty Inner offset discovery ===")
	if actor, ok := pickByName(classes, "Actor"); ok {
		f := r.ptr(actor.addr + 0x58)
		for i := 0; i < 200 && f != 0; i++ {
			fc := r.ptr(f + 0x08)
			tnID, _ := r.u32(fc)
			tn := p.name(r, tnID)
			nm := decodeName(r, p, f+0x20)
			if tn == "ArrayProperty" {
				fmt.Printf("  found ArrayProperty %q at FField 0x%X\n", nm, f)
				buf := make([]byte, 0xB0)
				r.read(f, buf)
				for off := 0; off+8 <= 0xB0; off += 8 {
					v := u64(buf[off:])
					annot := ""
					if v >= 0x10000 && v < 0x7FFFFFFFFFFF && v%8 == 0 {
						// If v is itself an FField, +0x08 should be an FFieldClass with a
						// recognizable property-type name at +0.
						maybeFC := r.ptr(v + 0x08)
						if maybeFC != 0 {
							if tid, _ := r.u32(maybeFC); tid > 0 {
								tnm := p.name(r, tid)
								if len(tnm) > 0 && tnm[0] != '<' {
									innerName := decodeName(r, p, v+0x20)
									annot = fmt.Sprintf(" -> looks like FField {%s %q}", tnm, innerName)
								}
							}
						}
					}
					fmt.Printf("    +0x%02X = 0x%-14X%s\n", off, v, annot)
				}
				break
			}
			f = r.ptr(f + 0x18)
		}
	}

	// Same for Transform — has Rotation (Struct→Quat), Translation, Scale3D.
	fmt.Println("\n  === Transform property chain walk ===")
	if t, ok := pickByName(structs, "Transform"); ok {
		propType := func(fld uintptr) string {
			fc := r.ptr(fld)
			id, _ := r.u32(fc)
			return p.name(r, id)
		}
		propName := func(fld uintptr) string {
			id, _ := r.u32(fld + 0x20)
			return p.name(r, id)
		}
		f := r.ptr(t.addr + 0x58)
		for i := 0; i < 20 && f != 0; i++ {
			ext := r.ptr(f + 0x70)
			extTag := ""
			if ext != 0 {
				if tag := x.labelPtr(ext); tag != "" {
					extTag = " (Inner=" + tag + ")"
				}
			}
			fmt.Printf("    [%d] %-16s : %-24s @0x%X%s\n",
				i, propName(f), propType(f), f, extTag)
			f = r.ptr(f + 0x18)
		}
	}
}

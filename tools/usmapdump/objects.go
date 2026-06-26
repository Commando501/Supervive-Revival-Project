// objects.go — MILESTONE R2.3: locate GUObjectArray, iterate UObjects, categorize.
//
// We try BOTH global object-array layouts and auto-tune UObject offsets:
//   chunked (FChunkedFixedUObjectArray, 32B):
//     +0x00 FUObjectItem** Objects   +0x08 PreAlloc   +0x10 Max  +0x14 Num  +0x18 MaxChunks  +0x1C NumChunks
//   fixed  (FFixedUObjectArray, 16B):
//     +0x00 FUObjectItem*  Objects   +0x08 Max  +0x0C Num
// A candidate is confirmed by resolving real reflection class names through the pool;
// itemSize / nameOff / classOff are auto-tuned. If nothing confirms, we dump diagnostics.

package main

import (
	"fmt"
	"os"
)

const perChunk = 64 * 1024 // FUObjectArray NumElementsPerChunk

var (
	tryNameOffs  = []uintptr{0x18, 0x1C, 0x14, 0x10, 0x20, 0x28, 0x0C}
	tryClassOffs = []uintptr{0x10, 0x08, 0x18, 0x20}
	tryItemSizes = []uintptr{24, 16, 32}
)

var knownReflClass = map[string]bool{
	"Class": true, "ScriptStruct": true, "Function": true, "Package": true,
	"Enum": true, "Field": true, "ArrayProperty": true, "ObjectProperty": true,
	"StructProperty": true, "BoolProperty": true, "IntProperty": true,
	"FloatProperty": true, "ByteProperty": true, "NameProperty": true,
	"StrProperty": true, "DelegateProperty": true,
}

func (r *reader) ptr(addr uintptr) uintptr {
	var b [8]byte
	if n, _ := r.read(addr, b[:]); n < 8 {
		return 0
	}
	v := uintptr(0)
	for i := 0; i < 8; i++ {
		v |= uintptr(b[i]) << (8 * i)
	}
	return v
}

func userspacePtr(p uintptr) bool { return p >= 0x10000 && p < 0x7FFFFFFFFFFF && p%4 == 0 }
func ceilDiv(a, b int) int        { return (a + b - 1) / b }
func abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}
func u64(b []byte) uintptr {
	v := uintptr(0)
	for i := 0; i < 8; i++ {
		v |= uintptr(b[i]) << (8 * i)
	}
	return v
}
func u32le(b []byte) uint32 {
	return uint32(b[0]) | uint32(b[1])<<8 | uint32(b[2])<<16 | uint32(b[3])<<24
}

type gobjects struct {
	objectsPtr  uintptr
	numElements int
	chunked     bool
	itemSize    uintptr
	nameOff     uintptr
	classOff    uintptr
}

func (g *gobjects) objAddr(r *reader, i int) uintptr {
	if i < 0 || i >= g.numElements {
		return 0
	}
	var item uintptr
	if g.chunked {
		chunkPtr := r.ptr(g.objectsPtr + uintptr(i/perChunk)*8)
		if chunkPtr == 0 {
			return 0
		}
		item = chunkPtr + uintptr(i%perChunk)*g.itemSize
	} else {
		item = g.objectsPtr + uintptr(i)*g.itemSize
	}
	return r.ptr(item)
}

func (g *gobjects) nameOf(r *reader, p *pool, obj uintptr) string {
	if obj == 0 {
		return ""
	}
	id, _ := r.u32(obj + g.nameOff)
	return p.name(r, id)
}
func (g *gobjects) classNameOf(r *reader, p *pool, obj uintptr) string {
	if obj == 0 {
		return ""
	}
	cls := r.ptr(obj + g.classOff)
	if cls == 0 {
		return ""
	}
	id, _ := r.u32(cls + g.nameOff)
	return p.name(r, id)
}

// score: how many of the first N objects resolve to a known reflection class name.
func (g *gobjects) score(r *reader, p *pool, n int) int {
	if n > g.numElements {
		n = g.numElements
	}
	s := 0
	for i := 0; i < n; i++ {
		if knownReflClass[g.classNameOf(r, p, g.objAddr(r, i))] {
			s++
		}
	}
	return s
}

type candidate struct {
	at          uintptr
	objectsPtr  uintptr
	numElements int
	chunked     bool
}

func findGObjects(r *reader, p *pool) (*gobjects, error) {
	regs := r.regions()
	order := func(want uint32) []region {
		var out []region
		for _, rg := range regs {
			if rg.typ == want && writable(rg.protect) && rg.size <= (1<<28) {
				out = append(out, rg)
			}
		}
		return out
	}
	scanList := append(order(memImage), order(memPrivate)...)

	var cands []candidate
	for _, rg := range scanList {
		buf := make([]byte, rg.size)
		got, _ := r.read(rg.base, buf)
		if got < 0x20 {
			continue
		}
		buf = buf[:got]
		for o := 0; o+0x20 <= len(buf); o += 8 {
			objectsPtr := u64(buf[o:])
			if !userspacePtr(objectsPtr) {
				continue
			}
			// chunked?
			preAlloc := u64(buf[o+8:])
			maxE := int(int32(u32le(buf[o+0x10:])))
			numE := int(int32(u32le(buf[o+0x14:])))
			maxC := int(int32(u32le(buf[o+0x18:])))
			numC := int(int32(u32le(buf[o+0x1C:])))
			if (preAlloc == 0 || userspacePtr(preAlloc)) &&
				maxE >= perChunk && maxE <= 100_000_000 && numE >= 1000 && numE <= maxE &&
				maxC >= 1 && maxC <= 4000 && numC >= 1 && numC <= maxC &&
				abs(maxC-ceilDiv(maxE, perChunk)) <= 1 && abs(numC-ceilDiv(numE, perChunk)) <= 1 {
				cands = append(cands, candidate{rg.base + uintptr(o), objectsPtr, numE, true})
			}
			// fixed?
			fmaxE := int(int32(u32le(buf[o+0x08:])))
			fnumE := int(int32(u32le(buf[o+0x0C:])))
			if fmaxE >= 10000 && fmaxE <= 100_000_000 && fnumE >= 1000 && fnumE <= fmaxE &&
				fmaxE-fnumE >= 0 && fmaxE-fnumE < fmaxE {
				cands = append(cands, candidate{rg.base + uintptr(o), objectsPtr, fnumE, false})
			}
		}
	}
	fmt.Printf("  structural candidates: %d\n", len(cands))

	var best *gobjects
	bestScore := 0
	for _, c := range cands {
		for _, is := range tryItemSizes {
			for _, no := range tryNameOffs {
				for _, co := range tryClassOffs {
					g := &gobjects{c.objectsPtr, c.numElements, c.chunked, is, no, co}
					// cheap pre-filter: obj0 must be a userspace ptr
					if !userspacePtr(g.objAddr(r, 1)) {
						continue
					}
					if s := g.score(r, p, 200); s > bestScore {
						bestScore, best = s, g
					}
				}
			}
		}
	}

	if best != nil && bestScore >= 15 {
		kind := "fixed"
		if best.chunked {
			kind = "chunked"
		}
		fmt.Printf("  CONFIRMED %s array  Objects=0x%X  Num=%d  itemSize=%d nameOff=0x%X classOff=0x%X (score %d/200)\n",
			kind, best.objectsPtr, best.numElements, best.itemSize, best.nameOff, best.classOff, bestScore)
		return best, nil
	}

	// --- diagnostics: dump the most promising candidate's first object raw ---
	fmt.Println("  NOT CONFIRMED. Diagnostics for first structural candidate:")
	if len(cands) == 0 {
		fmt.Println("  (no structural candidates at all — array layout differs; need a wider scan)")
		return nil, fmt.Errorf("no candidates")
	}
	c := cands[0]
	if best != nil {
		fmt.Printf("  best partial score=%d (itemSize=%d nameOff=0x%X classOff=0x%X chunked=%v)\n",
			bestScore, best.itemSize, best.nameOff, best.classOff, best.chunked)
	}
	g := &gobjects{c.objectsPtr, c.numElements, c.chunked, 24, 0x18, 0x10}
	fmt.Printf("  candidate@0x%X chunked=%v Objects=0x%X Num=%d\n", c.at, c.chunked, c.objectsPtr, c.numElements)
	for _, idx := range []int{0, 1, 2, 3} {
		obj := g.objAddr(r, idx)
		fmt.Printf("  obj[%d] = 0x%X\n", idx, obj)
		if obj == 0 {
			continue
		}
		raw := make([]byte, 0x40)
		r.read(obj, raw)
		fmt.Printf("    raw: % X\n", raw)
		// interpret each 4-byte slot as a possible FName id; each 8-byte slot as a class ptr
		for off := uintptr(0x08); off <= 0x30; off += 4 {
			id := u32le(raw[off:])
			nm := p.name(r, id)
			if len(nm) > 0 && nm[0] != '<' {
				fmt.Printf("      +0x%02X u32=0x%-6X -> FName %q\n", off, id, nm)
			}
		}
		for off := uintptr(0x08); off <= 0x28; off += 8 {
			cp := u64(raw[off:])
			if userspacePtr(cp) {
				cid, _ := r.u32(cp + 0x18)
				cn := p.name(r, cid)
				if len(cn) > 0 && cn[0] != '<' {
					fmt.Printf("      +0x%02X ptr=0x%-12X -> *(+0x18) FName %q  (class candidate)\n", off, cp, cn)
				}
			}
		}
	}
	return nil, fmt.Errorf("GUObjectArray not confirmed (see diagnostics above)")
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
	fmt.Printf("  GNames: &Blocks[0]@0x%X blocks=%d layout=%s\n", p.blocksAddr, len(p.blocks), p.layout)

	g, err := findGObjects(r, p)
	if err != nil {
		fmt.Println("ERROR (gobjects):", err)
		os.Exit(1)
	}

	fmt.Println("\n  first objects (index: Class  Name):")
	for i := 0; i < 25; i++ {
		obj := g.objAddr(r, i)
		if obj == 0 {
			continue
		}
		fmt.Printf("    %5d: %-16s %s\n", i, g.classNameOf(r, p, obj), g.nameOf(r, p, obj))
	}

	var classes, structs, enums, funcs, total int
	for i := 0; i < g.numElements; i++ {
		obj := g.objAddr(r, i)
		if obj == 0 {
			continue
		}
		total++
		switch g.classNameOf(r, p, obj) {
		case "Class":
			classes++
		case "ScriptStruct":
			structs++
		case "Enum", "UserDefinedEnum":
			enums++
		case "Function":
			funcs++
		}
	}
	fmt.Printf("\n  live objects: %d   UClass=%d  UScriptStruct=%d  UEnum=%d  UFunction=%d\n",
		total, classes, structs, enums, funcs)
	if classes > 100 && structs > 100 {
		fmt.Println("\nR2.3 OK: object iteration + categorization works. Next: UStruct property walk (R2.4).")
	} else {
		fmt.Println("\nR2.3 PARTIAL: counts look low — paste output; UObject offsets may need a tweak.")
	}
}

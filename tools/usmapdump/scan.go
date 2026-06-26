// scan.go — MILESTONE R2.2: locate FNamePool (GNames) externally and decode FName ids.
//
// Strategy (no fragile fixed offsets — update-proof):
//   1. Block 0 of the pool begins with the entry for "None" (FName id 0), immediately
//      followed by the core engine names UE registers first (ByteProperty, ObjectProperty,
//      Class, Package, ...). We scan private read/write regions for an FNameEntry that
//      decodes to "None" AND is followed by a chain of recognizable core names. That
//      simultaneously finds block 0 and tells us which FNameEntryHeader layout this build
//      uses (10-bit-Len+probehash vs 15-bit-Len).
//   2. Blocks[0] in the global FNamePool points exactly at that block-0 address. We scan
//      writable memory for a pointer holding that value => that location is &Blocks[0].
//   3. With Blocks[] in hand, any FName id resolves: addr = Blocks[id>>16] + (id&0xFFFF)*2.

package main

import (
	"bytes"
	"fmt"
	"os"
)

const (
	memCommit  = 0x1000
	memPrivate = 0x20000
	memImage   = 0x1000000

	pageReadOnly       = 0x02
	pageReadWrite      = 0x04
	pageWriteCopy      = 0x08
	pageExecuteRead    = 0x20
	pageExecuteRW      = 0x40
	pageExecuteWC      = 0x80
	pageGuard          = 0x100

	fnameBlockOffsetBits = 16
	fnameStride          = 2 // = alignof(FNameEntry); byte offset = Offset * Stride
)

// header layouts we try (bIsWide is always bit 0):
//
//	layoutLen10: bIsWide:1, LowercaseProbeHash:5, Len:10   => len = hdr>>6
//	layoutLen15: bIsWide:1, Len:15                          => len = hdr>>1
type hdrLayout int

const (
	layoutLen10 hdrLayout = iota
	layoutLen15
)

func (l hdrLayout) String() string {
	if l == layoutLen10 {
		return "Len10(+probehash)"
	}
	return "Len15"
}

func (l hdrLayout) decode(hdr uint16) (length int, wide bool) {
	wide = hdr&1 != 0
	if l == layoutLen10 {
		return int(hdr >> 6), wide
	}
	return int(hdr >> 1), wide
}

// coreNames: a handful of names UE registers very early, used to validate a candidate
// block-0 chain (distinguishes the real pool from stray "None" strings elsewhere).
var coreNames = map[string]bool{
	"None": true, "ByteProperty": true, "IntProperty": true, "BoolProperty": true,
	"FloatProperty": true, "ObjectProperty": true, "NameProperty": true,
	"DelegateProperty": true, "DoubleProperty": true, "ArrayProperty": true,
	"StructProperty": true, "StrProperty": true, "TextProperty": true,
	"Class": true, "Package": true, "Function": true, "Object": true, "Field": true,
	"Enum": true, "ScriptStruct": true, "Interface": true, "UInt32Property": true,
	"UInt64Property": true, "Int8Property": true, "MapProperty": true, "SetProperty": true,
	"EnumProperty": true, "Default": true, "Core": true, "CoreUObject": true,
}

func align2(n int) int { return (n + 1) &^ 1 }

func readable(protect uint32) bool {
	if protect&pageGuard != 0 {
		return false
	}
	return protect&(pageReadOnly|pageReadWrite|pageWriteCopy|pageExecuteRead|pageExecuteRW|pageExecuteWC) != 0
}
func writable(protect uint32) bool {
	if protect&pageGuard != 0 {
		return false
	}
	return protect&(pageReadWrite|pageWriteCopy|pageExecuteRW|pageExecuteWC) != 0
}

// region is a committed memory range.
type region struct {
	base   uintptr
	size   uintptr
	protect uint32
	typ    uint32
}

func (r *reader) regions() []region {
	var out []region
	addr := uintptr(0)
	for {
		mbi, ok := r.query(addr)
		if !ok {
			break
		}
		next := mbi.BaseAddress + mbi.RegionSize
		if mbi.State == memCommit && mbi.RegionSize > 0 {
			out = append(out, region{mbi.BaseAddress, mbi.RegionSize, mbi.Protect, mbi.Type})
		}
		if next <= addr {
			break
		}
		addr = next
	}
	return out
}

// decodeEntryAnsi reads an FNameEntry at addr under layout; returns the ansi string,
// total entry byte length (header+name, unaligned), and ok.
func (r *reader) decodeEntryAnsi(addr uintptr, l hdrLayout) (string, int, bool) {
	var hb [2]byte
	if n, _ := r.read(addr, hb[:]); n < 2 {
		return "", 0, false
	}
	hdr := uint16(hb[0]) | uint16(hb[1])<<8
	length, wide := l.decode(hdr)
	if length <= 0 || length > 1024 {
		return "", 0, false
	}
	if wide {
		// We only need ansi core/type names; signal "valid but wide" by returning ok=false
		// with a nonzero size so the chain walker can still advance.
		return "", 2 + length*2, false
	}
	buf := make([]byte, length)
	if n, _ := r.read(addr+2, buf); n < length {
		return "", 0, false
	}
	for _, c := range buf {
		if c < 0x20 || c > 0x7e {
			return "", 0, false
		}
	}
	return string(buf), 2 + length, true
}

// validateChain walks up to maxEntries from a candidate block start, counting how many
// decode to known core names. Returns matches and whether the first entry is "None".
func (r *reader) validateChain(blockStart uintptr, l hdrLayout, maxEntries int) (matches int, firstIsNone bool) {
	off := 0
	for i := 0; i < maxEntries; i++ {
		s, sz, ok := r.decodeEntryAnsi(blockStart+uintptr(off), l)
		if sz == 0 {
			break
		}
		if ok {
			if i == 0 && s == "None" {
				firstIsNone = true
			}
			if coreNames[s] {
				matches++
			}
		}
		off += align2(sz)
	}
	return
}

// pool holds the discovered FNamePool location.
type pool struct {
	blocksAddr uintptr   // address of &Blocks[0]
	blocks     []uintptr // resolved block base pointers
	layout     hdrLayout
}

func (p *pool) name(r *reader, id uint32) string {
	block := int(id >> fnameBlockOffsetBits)
	off := int(id&0xFFFF) * fnameStride
	if block < 0 || block >= len(p.blocks) || p.blocks[block] == 0 {
		return fmt.Sprintf("<bad id 0x%X>", id)
	}
	s, _, ok := r.decodeEntryAnsi(p.blocks[block]+uintptr(off), p.layout)
	if !ok {
		return fmt.Sprintf("<undecodable 0x%X>", id)
	}
	return s
}

// findNamePool scans for block 0 + layout, then for &Blocks[0].
func findNamePool(r *reader) (*pool, error) {
	regs := r.regions()

	// --- Phase 1: find block 0 (the "None"-led core-name chain) in private RW memory ---
	const chunk = 1 << 20
	var block0 uintptr
	var layout hdrLayout
	found := false
	scanned := 0
	for _, rg := range regs {
		if found {
			break
		}
		if rg.typ != memPrivate || !writable(rg.protect) {
			continue
		}
		for base := rg.base; base < rg.base+rg.size && !found; base += chunk {
			n := chunk + 8
			if uintptr(n) > rg.base+rg.size-base {
				n = int(rg.base + rg.size - base)
			}
			buf := make([]byte, n)
			got, _ := r.read(base, buf)
			if got < 6 {
				continue
			}
			buf = buf[:got]
			scanned++
			if scanned%256 == 0 {
				fmt.Fprintf(os.Stderr, "  ...scanned %d MB for name pool\r", scanned)
			}
			idx := 0
			for {
				rel := bytes.Index(buf[idx:], []byte("None"))
				if rel < 0 {
					break
				}
				pos := idx + rel
				idx = pos + 1
				if pos < 2 {
					continue
				}
				entryAddr := base + uintptr(pos) - 2
				for _, l := range []hdrLayout{layoutLen10, layoutLen15} {
					s, _, ok := r.decodeEntryAnsi(entryAddr, l)
					if !ok || s != "None" {
						continue
					}
					m, isNone := r.validateChain(entryAddr, l, 40)
					if isNone && m >= 5 {
						block0 = entryAddr
						layout = l
						found = true
						break
					}
				}
				if found {
					break
				}
			}
		}
	}
	fmt.Fprintf(os.Stderr, "\n")
	if !found {
		return nil, fmt.Errorf("could not locate FNamePool block 0 (no 'None'-led core-name chain in private RW memory)")
	}
	fmt.Printf("  block0 @0x%X  layout=%s\n", block0, layout)

	// --- Phase 2: find &Blocks[0] = a pointer in writable memory equal to block0 ---
	target := make([]byte, 8)
	for i := 0; i < 8; i++ {
		target[i] = byte(block0 >> (8 * i))
	}
	var blocksAddr uintptr
	for _, rg := range regs {
		if !writable(rg.protect) || rg.size > (1<<30) {
			continue
		}
		buf := make([]byte, rg.size)
		got, _ := r.read(rg.base, buf)
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
			cand := rg.base + uintptr(idx+rel)
			// Validate: this looks like Blocks[] if Blocks[0]==block0 and Blocks[1] is
			// either 0 or a readable pointer.
			if cand%8 == 0 {
				var nxt [8]byte
				r.read(cand+8, nxt[:])
				p1 := uintptr(0)
				for i := 0; i < 8; i++ {
					p1 |= uintptr(nxt[i]) << (8 * i)
				}
				if p1 == 0 || func() bool { var t [2]byte; n, _ := r.read(p1, t[:]); return n == 2 }() {
					blocksAddr = cand
					break
				}
			}
			idx = idx + rel + 1
		}
		if blocksAddr != 0 {
			break
		}
	}
	if blocksAddr == 0 {
		return nil, fmt.Errorf("found block0 @0x%X but no &Blocks[0] pointer to it", block0)
	}

	// --- Phase 3: read Blocks[] until a null/invalid pointer ---
	p := &pool{blocksAddr: blocksAddr, layout: layout}
	for i := 0; i < 8192; i++ {
		var pb [8]byte
		if n, _ := r.read(blocksAddr+uintptr(i*8), pb[:]); n < 8 {
			break
		}
		ptr := uintptr(0)
		for k := 0; k < 8; k++ {
			ptr |= uintptr(pb[k]) << (8 * k)
		}
		if ptr == 0 {
			break
		}
		// sanity: block must be readable
		var t [2]byte
		if n, _ := r.read(ptr, t[:]); n < 2 {
			break
		}
		p.blocks = append(p.blocks, ptr)
	}
	return p, nil
}

func cmdNames(name string) {
	r, pid, base, size := mustOpen(name)
	defer procCloseHandle.Call(r.h)
	fmt.Printf("PID %d  %q base=0x%X size=0x%X\n", pid, name, base, size)

	p, err := findNamePool(r)
	if err != nil {
		fmt.Println("ERROR:", err)
		os.Exit(1)
	}
	fmt.Printf("  &Blocks[0] @0x%X   blocks=%d   layout=%s\n\n", p.blocksAddr, len(p.blocks), p.layout)

	// Validation: id 0 must be "None"; print the first 40 names by sequential id.
	fmt.Println("  first names by id (id 0 must be \"None\"):")
	id := uint32(0)
	printed := 0
	off := 0
	for printed < 40 && off < 0x4000 {
		s, sz, ok := r.decodeEntryAnsi(p.blocks[0]+uintptr(off), p.layout)
		if sz == 0 {
			break
		}
		realID := uint32(off / fnameStride) // block 0
		if ok {
			fmt.Printf("    id=0x%-6X %q\n", realID, s)
			printed++
		}
		off += align2(sz)
		_ = id
	}
	fmt.Printf("\n  spot-check name(0x0)=%q  (want \"None\")\n", p.name(r, 0))
	if p.name(r, 0) == "None" {
		fmt.Println("\nR2.2 OK: FNamePool located and FName decoding verified. Next: GUObjectArray.")
	} else {
		fmt.Println("\nR2.2 PARTIAL: pool found but id 0 != None — paste output, layout/stride needs a tweak.")
	}
}

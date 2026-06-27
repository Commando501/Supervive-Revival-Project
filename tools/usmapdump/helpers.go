// helpers.go — small shared helpers used by both the name-pool scan (scan.go) and
// the reflection-object scan (objects.go). Kept in their own file so a rewrite of
// either consumer doesn't lose them.

package main

// ptr reads a qword pointer from the target. 0 on failure (short read).
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

// userspacePtr is a cheap sanity check: in-range x64 userspace, qword-aligned-ish.
func userspacePtr(p uintptr) bool { return p >= 0x10000 && p < 0x7FFFFFFFFFFF && p%4 == 0 }

// u32le decodes a little-endian uint32 from a byte slice (in-buffer reads).
func u32le(b []byte) uint32 {
	return uint32(b[0]) | uint32(b[1])<<8 | uint32(b[2])<<16 | uint32(b[3])<<24
}

// u64 decodes a little-endian uint64 (8 bytes) from a byte slice as a uintptr.
func u64(b []byte) uintptr {
	v := uintptr(0)
	for i := 0; i < 8; i++ {
		v |= uintptr(b[i]) << (8 * i)
	}
	return v
}

// execMap caches executable committed regions for fast vtable validation.
// For a packed binary the engine code lives in PRIVATE executable memory (unpacked
// at startup), NOT in the on-disk module image — so a real UObject vtable can point
// EITHER into the module OR into the private exec heap. "vtable in module" is wrong.
type execMap struct{ regs []region }

func (e *execMap) contains(p uintptr) bool {
	for _, rg := range e.regs {
		if p >= rg.base && p < rg.base+rg.size {
			return true
		}
	}
	return false
}
func (r *reader) execMap() *execMap {
	var em execMap
	// Any of PAGE_EXECUTE (0x10) / EXECUTE_READ (0x20) / EXECUTE_READWRITE (0x40) /
	// EXECUTE_WRITECOPY (0x80). Bit 0x10 is what we were missing before.
	const anyExec = 0x10 | 0x20 | 0x40 | 0x80
	for _, rg := range r.regions() {
		if rg.protect&anyExec != 0 && rg.protect&pageGuard == 0 {
			em.regs = append(em.regs, rg)
		}
	}
	return &em
}

// looksLikeVtable validates that vt POINTS TO a real vtable: 8-byte aligned, and its
// first 8 entries are themselves pointers into executable memory. Random heap qwords
// that happen to land in exec memory don't have a contiguous run of function pointers
// after them — only real vtables do.
func looksLikeVtable(r *reader, em *execMap, vt uintptr) bool {
	if vt == 0 || vt%8 != 0 {
		return false
	}
	var buf [64]byte
	if n, _ := r.read(vt, buf[:]); n < 64 {
		return false
	}
	hits := 0
	for i := 0; i < 8; i++ {
		v := uintptr(0)
		for k := 0; k < 8; k++ {
			v |= uintptr(buf[i*8+k]) << (8 * k)
		}
		if em.contains(v) {
			hits++
		}
	}
	return hits >= 6 // tolerate the rare pure-virtual / null slot
}

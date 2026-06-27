// inspect.go — R2.4 layout discovery: given a known UStruct, dump its first 0x100
// bytes with per-qword annotations marking pointers that look like:
//   - a pointer to another UStruct we've enumerated (SuperStruct candidate)
//   - a pointer to a UStruct INTERNAL field (Children/ChildProperties candidate)
// This lets us read off SuperStruct / Children / ChildProperties offsets directly
// instead of guessing from stock UE5 docs (this build's layout is non-standard).

package main

import (
	"fmt"
	"sort"
)

// addrIndex builds two maps: knownAddrs[a]=name for every UStruct we found, and
// the same indexed by class kind. Used by inspect to label pointers cheaply.
type addrIndex struct {
	classByAddr  map[uintptr]string
	structByAddr map[uintptr]string
	enumByAddr   map[uintptr]string
}

func buildAddrIndex(classes, structs, enums []objref) *addrIndex {
	x := &addrIndex{
		classByAddr:  make(map[uintptr]string, len(classes)),
		structByAddr: make(map[uintptr]string, len(structs)),
		enumByAddr:   make(map[uintptr]string, len(enums)),
	}
	for _, o := range classes {
		x.classByAddr[o.addr] = o.name
	}
	for _, o := range structs {
		x.structByAddr[o.addr] = o.name
	}
	for _, o := range enums {
		x.enumByAddr[o.addr] = o.name
	}
	return x
}

// labelPtr returns a short tag if v is the address of a known UStruct, else "".
func (x *addrIndex) labelPtr(v uintptr) string {
	if n, ok := x.classByAddr[v]; ok {
		return "UClass:" + n
	}
	if n, ok := x.structByAddr[v]; ok {
		return "UStruct:" + n
	}
	if n, ok := x.enumByAddr[v]; ok {
		return "UEnum:" + n
	}
	return ""
}

// inspectStruct dumps the first dumpLen bytes of obj, qword-by-qword. For each
// qword we print the value, any matching known-struct label, and (if the value is
// a userspace pointer) what the first 4 bytes at that target decode as via FName.
// The latter helps spot FField chain heads where the first field is an FFieldClass*
// followed by an Owner ptr followed by Next ptr followed by FName NamePrivate.
func inspectStruct(r *reader, p *pool, x *addrIndex, label string, obj uintptr, dumpLen int) {
	fmt.Printf("\n  === inspect %s @0x%X (first 0x%X bytes) ===\n", label, obj, dumpLen)
	buf := make([]byte, dumpLen)
	got, _ := r.read(obj, buf)
	if got < dumpLen {
		fmt.Printf("    short read: %d bytes\n", got)
		dumpLen = got
	}
	for off := 0; off+8 <= dumpLen; off += 8 {
		v := u64(buf[off:])
		annot := ""
		if v >= 0x10000 && v < 0x7FFFFFFFFFFF && v%8 == 0 {
			if tag := x.labelPtr(v); tag != "" {
				annot = " -> " + tag
			} else {
				// Try interpreting *(v + 0x20) as an FName id (UObject NamePrivate offset)
				if id, _ := r.u32(v + 0x20); id > 0 && id < uint32(len(p.blocks))*0x10000 {
					nm := p.name(r, id)
					if len(nm) > 0 && nm[0] != '<' {
						annot = fmt.Sprintf(" -> ptr; *(+0x20)=FName %q", nm)
					}
				}
			}
		}
		// Also peek at 2x int32 interpretation for offsets/sizes.
		i32a := u32le(buf[off:])
		i32b := u32le(buf[off+4:])
		fmt.Printf("    +0x%02X = 0x%-16X  (i32 %d, %d)%s\n", off, v, int32(i32a), int32(i32b), annot)
	}
}

// pickByName finds the objref with exact name match (case-sensitive), or returns
// an empty objref if not found.
func pickByName(list []objref, name string) (objref, bool) {
	for _, o := range list {
		if o.name == name {
			return o, true
		}
	}
	return objref{}, false
}

// pickFirstByPrefix returns the first objref whose name starts with the prefix.
// Iterates in sorted order so picks are stable across runs.
func pickFirstByPrefix(list []objref, prefix string) (objref, bool) {
	sorted := make([]objref, len(list))
	copy(sorted, list)
	sort.Slice(sorted, func(i, j int) bool { return sorted[i].name < sorted[j].name })
	for _, o := range sorted {
		if len(o.name) >= len(prefix) && o.name[:len(prefix)] == prefix {
			return o, true
		}
	}
	return objref{}, false
}

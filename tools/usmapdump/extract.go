// extract.go — R2.4: walk every UStruct's property chain and every UEnum's value
// table, producing the complete schema we'll serialize into a .usmap (R2.5).
//
// Layout (this build — non-standard +8B pad in UObjectBase):
//   UObject base: 0x30 bytes
//   UField::Next         : +0x38
//   UStruct::SuperStruct : +0x48
//   UStruct::Children    : +0x50 (UField* chain — incl. UFunctions; we skip)
//   UStruct::ChildProps  : +0x58 (FField* chain — what we want)
//   UEnum::Names         : +0x40 (TArray<TPair<FName,int64>>: Num i32 @+0x40, Max @+0x44, Data @+0x48)
//   FField::vtable       : +0x00 (property-type-specific C++ vtable)
//   FField::ClassPrivate : +0x08 (FFieldClass*)
//   FField::Owner        : +0x10 (UStruct* with low bit set if UObject-owned)
//   FField::Next         : +0x18
//   FField::NamePrivate  : +0x20 (FName: ComparisonIndex/DisplayIndex/Number)
//   FField::PropertyFlags: +0x38 (uint64)
//   FField::Inner        : +0x70 (Struct ptr for StructProperty, etc.)
//   FFieldClass::Name    : +0x00 (FName — ComparisonIndex decodes to "DoubleProperty" etc.)

package main

import (
	"fmt"
	"os"
	"sort"
)

const (
	offUStructSuperStruct = 0x48
	offUStructChildProps  = 0x58
	offUEnumNamesArrayPtr = 0x48 // pointer to TPair<FName,int64>[] (standard TArray data first)
	offUEnumNamesArrayNum = 0x50 // ArrayNum i32, then ArrayMax i32 at +0x54
	offFFieldClass        = 0x08
	offFFieldNext         = 0x18
	offFFieldName         = 0x20 // FName ComparisonIndex first (we lookup DisplayIndex too)
	offFFieldInner        = 0x70
	offFFieldClassName    = 0x00 // FName at FFieldClass+0 (ComparisonIndex)
)

// propInfo is what we'll emit per FProperty.
//
// `inner`/`innerName` are populated for StructProperty (the struct type),
// ObjectProperty/ClassProperty (the class), EnumProperty (the enum).
//
// `innerProp` is populated for "container" properties that wrap another FProperty:
//   ArrayProperty.Inner   → element FProperty
//   SetProperty.ElementProp → element FProperty
//   OptionalProperty.Inner  → wrapped FProperty
//   EnumProperty.UnderlyingProp → underlying integer FProperty (Byte/Int/etc.)
// MapProperty has both Key and Value inner FProperties: stored as innerProp + valueProp.
type propInfo struct {
	name      string
	typeName  string
	inner     uintptr
	innerName string
	innerProp *propInfo // for Array/Set/Optional/Enum (single inner)
	valueProp *propInfo // for Map (the value FProperty; innerProp is the key)
}

// structInfo is what we'll emit per UClass / UScriptStruct.
type structInfo struct {
	name        string
	addr        uintptr
	superName   string
	properties  []propInfo
}

// enumInfo is what we'll emit per UEnum.
type enumInfo struct {
	name   string
	addr   uintptr
	values []enumValue
}

type enumValue struct {
	name  string
	value int64
}

// decodeName returns the best-effort string for an FName stored as a pair of
// (ComparisonIndex, DisplayIndex) at addr. This build is not truly case-preserving
// despite the pool's Len10 layout: ComparisonIndex points to the canonical-case
// entry directly, and DisplayIndex is usually 0 (decoding to literal "None" — the
// "trap" my earlier code fell into). So: prefer ComparisonIndex, only use
// DisplayIndex if it's non-zero AND resolves to a non-None real name.
func decodeName(r *reader, p *pool, addr uintptr) string {
	id, _ := r.u32(addr)
	if id == 0 {
		// Try DisplayIndex as a last resort if ComparisonIndex is zero.
		if d, _ := r.u32(addr + 4); d != 0 {
			n := p.name(r, d)
			if len(n) > 0 && n[0] != '<' && n != "None" {
				return n
			}
		}
		return "None"
	}
	return p.name(r, id)
}

// Container FProperties embed their inner FProperty INLINE at FField+0x80:
//   FArrayProperty.Inner, FSetProperty.ElementProp, FOptionalProperty.ValueProperty,
//   FEnumProperty.UnderlyingProp. (StructProperty/ObjectProperty use FField+0x70 to
//   point at a UStruct/UClass — different shape.) FMapProperty has Key inline at +0x80
//   then Value inline starting where Key ends.
const offFFieldEmbeddedInner = 0x80

// recognized property types — used to filter out junk inner reads where the
// "FFieldClass" pointer happens to land somewhere unrelated.
var knownPropTypes = map[string]bool{
	"ByteProperty": true, "BoolProperty": true, "IntProperty": true, "FloatProperty": true,
	"DoubleProperty": true, "ObjectProperty": true, "ClassProperty": true, "NameProperty": true,
	"StrProperty": true, "TextProperty": true, "InterfaceProperty": true, "StructProperty": true,
	"ArrayProperty": true, "SetProperty": true, "MapProperty": true, "EnumProperty": true,
	"OptionalProperty": true, "DelegateProperty": true,
	"MulticastDelegateProperty":       true,
	"MulticastInlineDelegateProperty": true, "MulticastSparseDelegateProperty": true,
	"WeakObjectProperty": true, "LazyObjectProperty": true, "SoftObjectProperty": true,
	"SoftClassProperty": true, "AssetObjectProperty": true, "FieldPathProperty": true,
	"Int8Property": true, "Int16Property": true, "Int64Property": true,
	"UInt16Property": true, "UInt32Property": true, "UInt64Property": true,
}

// extractFField reads ONE FField at the given address into a propInfo, recursing
// into embedded inner FProperties for container types. `ownerHint` is the outer
// FField's Owner — a sanity check that the inner is part of the same allocation
// and not random memory past the FProperty.
func extractFField(r *reader, p *pool, x *addrIndex, f uintptr, depth int, ownerHint uintptr) propInfo {
	pi := propInfo{
		name: decodeName(r, p, f+offFFieldName),
	}
	if fc := r.ptr(f + offFFieldClass); fc != 0 {
		pi.typeName = decodeName(r, p, fc+offFFieldClassName)
	}
	pi.inner = r.ptr(f + offFFieldInner)
	if pi.inner != 0 {
		pi.innerName = x.labelPtr(pi.inner)
	}
	if depth >= 3 {
		return pi
	}

	myOwner := r.ptr(f + 0x10)

	// Validate an embedded inner read: the inner must (a) have a recognized property
	// type and (b) share the SAME Owner as the outer (proves we're reading the actual
	// embedded inner FProperty, not garbage past the outer's allocation).
	tryEmbedded := func(off uintptr) (propInfo, bool) {
		inner := extractFField(r, p, x, f+off, depth+1, myOwner)
		if !knownPropTypes[inner.typeName] {
			return propInfo{}, false
		}
		innerOwner := r.ptr(f + off + 0x10)
		if ownerHint != 0 && innerOwner != ownerHint && innerOwner != myOwner {
			return propInfo{}, false
		}
		return inner, true
	}

	switch pi.typeName {
	case "ArrayProperty", "SetProperty", "OptionalProperty":
		if inner, ok := tryEmbedded(offFFieldEmbeddedInner); ok {
			pi.innerProp = &inner
		}
	case "EnumProperty":
		if inner, ok := tryEmbedded(offFFieldEmbeddedInner); ok {
			pi.innerProp = &inner
		}
	case "MapProperty":
		key, kok := tryEmbedded(offFFieldEmbeddedInner)
		val, vok := tryEmbedded(offFFieldEmbeddedInner + 0x80)
		if kok && vok {
			pi.innerProp = &key
			pi.valueProp = &val
		}
	}
	return pi
}

// walkProperties walks a UStruct's ChildProperties chain. Bounded to 4096.
func walkProperties(r *reader, p *pool, x *addrIndex, sAddr uintptr) []propInfo {
	var out []propInfo
	f := r.ptr(sAddr + offUStructChildProps)
	for i := 0; i < 4096 && f != 0; i++ {
		out = append(out, extractFField(r, p, x, f, 0, 0))
		f = r.ptr(f + offFFieldNext)
	}
	return out
}

// walkStruct collects super-struct name + property list for a UStruct.
func walkStruct(r *reader, p *pool, x *addrIndex, name string, addr uintptr) structInfo {
	si := structInfo{name: name, addr: addr}
	sup := r.ptr(addr + offUStructSuperStruct)
	if sup != 0 {
		si.superName = x.labelPtr(sup)
		if si.superName == "" {
			si.superName = fmt.Sprintf("@0x%X", sup)
		}
	}
	si.properties = walkProperties(r, p, x, addr)
	return si
}

// walkEnum reads UEnum::Names as a TArray<TPair<FName, int64>>.
// In UE5 the entry size is 16 bytes (FName=8B + int64=8B, but FName takes 4+4+4=12,
// then 4 pad, then int64 = 24B? Or is FName only 8B in non-case-preserving mode?).
// Empirically: we'll try a few entry sizes and pick the one that decodes consistently.
func walkEnum(r *reader, p *pool, name string, addr uintptr) enumInfo {
	ei := enumInfo{name: name, addr: addr}
	num, _ := r.u32(addr + offUEnumNamesArrayNum)
	dataPtr := r.ptr(addr + offUEnumNamesArrayPtr)
	if num == 0 || num > 4096 || dataPtr == 0 {
		return ei
	}
	// Try entry size 16 (FName 8B + int64 8B, no DisplayIndex) and 24 (case-pres + pad).
	// Entry size is 16 in this build (TPair<FName(8B), int64(8B)>): empirically
	// confirmed by the AnimationKeyFormat diag — sequential FName ids with sequential
	// int64 values at byte offsets 0/4/8 within 16B entries.
	const sz = 16
	buf := make([]byte, uintptr(num)*sz)
	got, _ := r.read(dataPtr, buf)
	if got < int(uintptr(num)*sz) {
		return ei
	}
	for i := uintptr(0); i < uintptr(num); i++ {
		ent := buf[i*sz:]
		id := u32le(ent[0:])
		number := u32le(ent[4:])
		n := p.name(r, id)
		if number > 0 && n != "None" {
			n = fmt.Sprintf("%s_%d", n, number-1)
		}
		var v int64
		for k := 0; k < 8; k++ {
			v |= int64(ent[8+k]) << (8 * k)
		}
		ei.values = append(ei.values, enumValue{name: n, value: v})
	}
	return ei
}

// emitSchema prints a human-readable view of everything we extracted.
// (R2.5 will reuse the same in-memory structs to write the .usmap binary.)
func emitSchema(structs []structInfo, enums []enumInfo, w *os.File, sample int) {
	sort.Slice(structs, func(i, j int) bool { return structs[i].name < structs[j].name })
	sort.Slice(enums, func(i, j int) bool { return enums[i].name < enums[j].name })
	renderTail := func(pr propInfo) string {
		ext := ""
		if pr.innerName != "" {
			ext = " (" + pr.innerName + ")"
		}
		if pr.innerProp != nil {
			ext += "<" + pr.innerProp.typeName
			if pr.innerProp.innerName != "" {
				ext += " " + pr.innerProp.innerName
			}
			if pr.valueProp != nil {
				ext += ", " + pr.valueProp.typeName
				if pr.valueProp.innerName != "" {
					ext += " " + pr.valueProp.innerName
				}
			}
			ext += ">"
		}
		return ext
	}
	fmt.Fprintf(w, "=== %d UStructs ===\n", len(structs))
	for i, s := range structs {
		if sample > 0 && i >= sample {
			fmt.Fprintf(w, "  ... (%d more)\n", len(structs)-sample)
			break
		}
		fmt.Fprintf(w, "  %s : %s  (%d props)\n", s.name, s.superName, len(s.properties))
		for _, pr := range s.properties {
			fmt.Fprintf(w, "      %-32s %s%s\n", pr.name, pr.typeName, renderTail(pr))
		}
	}
	fmt.Fprintf(w, "\n=== %d UEnums ===\n", len(enums))
	for i, e := range enums {
		if sample > 0 && i >= sample {
			fmt.Fprintf(w, "  ... (%d more)\n", len(enums)-sample)
			break
		}
		fmt.Fprintf(w, "  %s  (%d values)\n", e.name, len(e.values))
		for _, v := range e.values {
			fmt.Fprintf(w, "      %-32s = %d\n", v.name, v.value)
		}
	}
}

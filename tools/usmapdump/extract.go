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
//   FFieldClass::Name    : +0x00 (FName — ComparisonIndex decodes to "DoubleProperty" etc.)
//
// ★ FK-14 (S116): every FProperty SUB-OBJECT offset below is now resolved at run time by
//   calibrate.go against the process being dumped, not hardcoded here. The old
//   `offFFieldEmbeddedInner = 0x80` inline read was one byte past the end of an
//   FArrayProperty and captured the next FField in the heap, which is why ~70 % of
//   container inner types were wrong in every usmap this project ever produced.
//   Read docs/fk14-usmap-settled.md before changing anything in this file.

package main

import (
	"fmt"
	"os"
	"sort"
	"strings"
)

const (
	offUStructSuperStruct = 0x48
	offUStructChildProps  = 0x58
	offUEnumNamesArrayPtr = 0x48 // pointer to TPair<FName,int64>[] (standard TArray data first)
	offUEnumNamesArrayNum = 0x50 // ArrayNum i32, then ArrayMax i32 at +0x54
	offFFieldClass        = 0x08
	offFFieldNext         = 0x18
	offFFieldName         = 0x20 // FName ComparisonIndex first (we lookup DisplayIndex too)
	offFFieldPropFlags    = 0x38 // FField::PropertyFlags (uint64, CPF_* bitfield)
	offFFieldClassName    = 0x00 // FName at FFieldClass+0 (ComparisonIndex)
)

// CPF_* flags we care about for replication schema RE (UE 5.4 ObjectMacros.h).
const (
	cpfNet        = 0x0000000000000020 // CPF_Net — property is replicated (in ClassReps)
	cpfRepNotify  = 0x0000000100000000 // CPF_RepNotify — has an OnRep_ handler
	cpfRepSkip    = 0x0000000000200000 // CPF_RepSkip — conditionally skipped by DOREPLIFETIME_CONDITION
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
	propFlags uint64    // FField::PropertyFlags @+0x38 (CPF_* bitfield)
	arrayDim  int       // FProperty::ArrayDim — >1 for a C-style static array member.
	// ArrayDim was hardcoded to 1 by the writer (usmap.go:262 pre-FK-14). 66 of 75,907
	// UHT records (0.087 %) have ArrayDim != 1 (StyleColors[61], BoneIndices[12],
	// Translation[3]) and each one shifts every schema index after it in its struct.
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

// ⚠ RETRACTED (FK-14, S116). The comment that stood here said:
//
//	"Container FProperties embed their inner FProperty INLINE at FField+0x80"
//
// That is FALSE. sizeof(FArrayProperty) is 0x80 in this build, so +0x80 is one byte PAST
// the object and the read captured whichever FField the allocator placed next — a
// same-Owner neighbour, which is why the owner guard could not catch it and why the
// output looked plausible. MEASURED (docs/fk14-usmap-settled.md §3.2, 4,247 live
// containers, three simultaneous discriminators):
//
//	*(outer+0x78) as a POINTER : 4,103 = 96.6 %
//	*(outer+0x70)              :   144 =  3.4 %
//	inline at outer+0x80       :     5 =  0.1 %   <- what this tool used to do
//
// Containers now DEREFERENCE a pointer, and the offset is decided per family at run time
// by calibrate.go. No offset for a sub-object is hardcoded in this file any more.

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

// extractFField reads ONE FField at the given address into a propInfo, DEREFERENCING the
// pointers to its inner FProperties for container / enum types. All offsets come from
// gOff, which calibrate.go resolved by measurement against this process.
//
// The old `ownerHint` parameter is gone. It was inert: walkProperties always passed 0, so
// `ownerHint != 0` was never true for any top-level property — and it was self-confirming
// anyway, because the neighbouring FField the bug actually read has the SAME Owner. The
// owner check that survives here compares the target's Owner against the OUTER FIELD
// ITSELF (f), which a neighbour cannot pass.
func extractFField(r *reader, p *pool, x *addrIndex, f uintptr, depth int) propInfo {
	pi := propInfo{
		name:      decodeName(r, p, f+offFFieldName),
		propFlags: uint64(r.ptr(f + offFFieldPropFlags)),
		arrayDim:  1,
	}
	if fc := r.ptr(f + offFFieldClass); fc != 0 {
		pi.typeName = decodeName(r, p, fc+offFFieldClassName)
	}
	if depth == 0 {
		gStats.propsWalked++
		if ad, err := r.u32(f + gOff.arrayDim); err == nil {
			switch {
			case ad == 1:
			case ad >= 2 && ad <= 0x10000:
				pi.arrayDim = int(ad)
				gStats.arrayDimNot1++
			default:
				gStats.arrayDimBad++
			}
		}
		if gOff.forceArrayDim1 {
			pi.arrayDim = 1
		}
	}

	// The type-object slot. It is meaningful ONLY for the type-carrying families; for
	// containers it holds something else entirely and labelPtr's occasional hit on it is
	// pure noise (3.4 % — measured). That noise is what produced schema.txt's cosmetic
	// "(UEnum:ELokiGameFeatureToggle)" column on ScreenEffectCollections, which three
	// sessions of S88 work were then built on. Do not reinstate it for containers.
	switch pi.typeName {
	case "ArrayProperty", "SetProperty", "MapProperty", "OptionalProperty":
		// no type object of its own — its type lives in the inner FProperty
	case "EnumProperty":
		pi.inner = r.ptr(f + gOff.enumEnum)
		if pi.inner != 0 {
			pi.innerName = x.labelPtr(pi.inner)
		}
		if depth == 0 {
			if strings.HasPrefix(pi.innerName, "UEnum:") {
				gStats.enumObjResolved++
			} else {
				gStats.enumObjUnlabeled++
			}
		}
	default:
		pi.inner = r.ptr(f + gOff.typeSlot)
		if pi.inner != 0 {
			pi.innerName = x.labelPtr(pi.inner)
		}
	}
	if depth >= 3 {
		return pi
	}

	// deref reads *(f+off) as a POINTER to an inner FProperty and validates it:
	//   (a) the target's ClassPrivate names a known property type;
	//   (b) the target's Owner is f itself (low bit is the UObject-owned tag).
	// (b) is the discriminator the old code could not express, and it is what makes a
	// neighbouring FField impossible to accept. Every rejection is COUNTED.
	deref := func(off uintptr, numericOnly bool) (propInfo, bool) {
		ip := r.ptr(f + off)
		if ip == 0 || !userspacePtr(ip) {
			gStats.innerNilPtr++
			return propInfo{}, false
		}
		inner := extractFField(r, p, x, ip, depth+1)
		if !knownPropTypes[inner.typeName] || (numericOnly && !numericPropTypes[inner.typeName]) {
			gStats.innerBadType++
			return propInfo{}, false
		}
		if r.ptr(ip+offFFieldOwner)&^1 != f {
			gStats.innerBadOwner++
			return propInfo{}, false
		}
		gStats.innerOK++
		return inner, true
	}

	// ⚠ Each container family gets its OWN calibrated offset. Pooling them is what the
	// settlement's headline "containers -> *(+0x78)" did, and the calibrator showed that
	// number is a mixture: Array and Map really are at +0x78, but Set and Optional are at
	// +0x70 — they ARE the settlement's unexplained 3.4 % residual (142 + 2 = 144).
	switch pi.typeName {
	case "ArrayProperty":
		if inner, ok := deref(gOff.arrayInner, false); ok {
			pi.innerProp = &inner
		}
	case "SetProperty":
		if inner, ok := deref(gOff.setInner, false); ok {
			pi.innerProp = &inner
		}
	case "OptionalProperty":
		if inner, ok := deref(gOff.optionalInner, false); ok {
			pi.innerProp = &inner
		}
	case "EnumProperty":
		if inner, ok := deref(gOff.enumUnderlying, true); ok {
			pi.innerProp = &inner
		}
	case "MapProperty":
		if key, ok := deref(gOff.mapKey, false); ok {
			pi.innerProp = &key
		}
		if val, ok := deref(gOff.mapValue, false); ok {
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
		out = append(out, extractFField(r, p, x, f, 0))
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
// ⚠ FK-14 defect #5: this used to sort `structs` and `enums` IN PLACE — and they are the
// same backing arrays emitUsmapBeside serialises afterwards (pipeline.go runs emitSchema
// first). So printing the schema silently decided the usmap's section order. It now sorts
// COPIES: emitSchema is a pure reader of its arguments.
func emitSchema(structsIn []structInfo, enumsIn []enumInfo, w *os.File, sample int) {
	structs := append([]structInfo(nil), structsIn...)
	enums := append([]enumInfo(nil), enumsIn...)
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
		// Count replicated props so a class's ClassReps size is visible at a glance.
		nNet := 0
		for _, pr := range s.properties {
			if pr.propFlags&cpfNet != 0 {
				nNet++
			}
		}
		fmt.Fprintf(w, "  %s : %s  (%d props, %d replicated)\n", s.name, s.superName, len(s.properties), nNet)
		for _, pr := range s.properties {
			netTag := ""
			if pr.propFlags&cpfNet != 0 {
				netTag = "  <<NET"
				if pr.propFlags&cpfRepNotify != 0 {
					netTag += ",RepNotify"
				}
				if pr.propFlags&cpfRepSkip != 0 {
					netTag += ",RepSkip"
				}
				netTag += fmt.Sprintf(" flags=0x%X>>", pr.propFlags)
			}
			dimTag := ""
			if pr.arrayDim > 1 {
				dimTag = fmt.Sprintf("[%d]", pr.arrayDim)
			}
			fmt.Fprintf(w, "      %-32s %s%s%s%s\n", pr.name, pr.typeName, dimTag, renderTail(pr), netTag)
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

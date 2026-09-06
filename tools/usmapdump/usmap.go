// usmap.go — R2.5: serialize the extracted schema into the .usmap binary format
// that CUE4Parse / FModel consume.
//
// Format (v0 unversioned, no compression — matches OutTheShade's UnrealMappingsDumper
// minimum-viable output that CUE4Parse loads):
//
//   u16 Magic = 0x30C4
//   u8  Version = 0
//   u8  CompressionMethod = 0 (none)
//   u32 CompressedSize
//   u32 DecompressedSize
//   then DecompressedSize bytes of body:
//     u32 NameCount; NameCount × (u8 Len; Len × byte) // ANSI strings, no null
//     u32 EnumCount; EnumCount × (u32 EnumNameIdx; u8 ValueCount; ValueCount × u32 ValueNameIdx)
//     u32 StructCount; StructCount × (
//         u32 StructNameIdx
//         u32 SuperStructNameIdx  (0xFFFFFFFF if none)
//         u16 PropertyCount
//         u16 SerializablePropertyCount
//         SerializablePropertyCount × FProperty
//     )
//
// FProperty:
//   u16 SchemaIdx — the ABSOLUTE schema slot of this property in its struct
//   u8  ArrayDim  — number of schema slots this property occupies
//   u32 NameIdx
//   u8  PropertyType (EPropertyType byte)
//   [type-specific tail]
//
// ★ FK-14 (S116) fixed five writer defects here. Read docs/fk14-usmap-settled.md §4 first.
//   #2 properties whose inner NAME didn't resolve were DROPPED — 1,840 EnumProperty
//      records, 100 % of them, in every base usmap this project produced. No longer.
//   #3 SchemaIdx was `i` over the FILTERED list, so 7,713 properties across 1,222 structs
//      carried a wrong index (max shift 10). It is now the absolute slot, advancing by
//      ArrayDim over the UNFILTERED list; an un-emittable property leaves a HOLE, which
//      CUE4Parse fails loudly on, instead of silently re-labelling every later property.
//   #4 ArrayDim was hardcoded 1.
//   #6 the format is name-keyed, so duplicate struct records collapse to the LAST written
//      — and the canonical file's 84 AnimBlueprintGenerated*Data records collapsed to one
//      with 0 properties while siblings carried up to 259. Now de-duplicated to the
//      RICHEST record, deliberately.
//   #7 `nt.idx[...]` map misses silently aliased to name index 0, i.e. to a real,
//      arbitrary name. All lookups now go through nameTable.get, which counts misses and
//      returns the reserved "__UsmapUnresolved" placeholder.

package main

import (
	"encoding/binary"
	"fmt"
	"os"
)

// EPropertyType — CUE4Parse byte tags.
const (
	pByteProperty              = 0
	pBoolProperty              = 1
	pIntProperty               = 2
	pFloatProperty             = 3
	pObjectProperty            = 4
	pNameProperty              = 5
	pDelegateProperty          = 6
	pDoubleProperty            = 7
	pArrayProperty             = 8
	pStructProperty            = 9
	pStrProperty               = 10
	pTextProperty              = 11
	pInterfaceProperty         = 12
	pMulticastDelegateProperty = 13
	pWeakObjectProperty        = 14
	pLazyObjectProperty        = 15
	pAssetObjectProperty       = 16
	pSoftObjectProperty        = 17
	pUInt64Property            = 18
	pUInt32Property            = 19
	pUInt16Property            = 20
	pInt64Property             = 21
	pInt16Property             = 22
	pInt8Property              = 23
	pMapProperty               = 24
	pSetProperty               = 25
	pEnumProperty              = 26
	pFieldPathProperty         = 27
	pOptionalProperty          = 28
	pUnknown                   = 0xFF
)

func propTypeByte(name string) byte {
	switch name {
	case "ByteProperty":
		return pByteProperty
	case "BoolProperty":
		return pBoolProperty
	case "IntProperty":
		return pIntProperty
	case "FloatProperty":
		return pFloatProperty
	case "ObjectProperty":
		return pObjectProperty
	case "ClassProperty": // class property is a subtype of ObjectProperty
		return pObjectProperty
	case "NameProperty":
		return pNameProperty
	case "DelegateProperty":
		return pDelegateProperty
	case "DoubleProperty":
		return pDoubleProperty
	case "ArrayProperty":
		return pArrayProperty
	case "StructProperty":
		return pStructProperty
	case "StrProperty":
		return pStrProperty
	case "TextProperty":
		return pTextProperty
	case "InterfaceProperty":
		return pInterfaceProperty
	case "MulticastDelegateProperty",
		"MulticastInlineDelegateProperty",
		"MulticastSparseDelegateProperty":
		return pMulticastDelegateProperty
	case "WeakObjectProperty":
		return pWeakObjectProperty
	case "LazyObjectProperty":
		return pLazyObjectProperty
	case "AssetObjectProperty":
		return pAssetObjectProperty
	case "SoftObjectProperty", "SoftClassProperty":
		return pSoftObjectProperty
	case "UInt64Property":
		return pUInt64Property
	case "UInt32Property":
		return pUInt32Property
	case "UInt16Property":
		return pUInt16Property
	case "Int64Property":
		return pInt64Property
	case "Int16Property":
		return pInt16Property
	case "Int8Property":
		return pInt8Property
	case "MapProperty":
		return pMapProperty
	case "SetProperty":
		return pSetProperty
	case "EnumProperty":
		return pEnumProperty
	case "FieldPathProperty":
		return pFieldPathProperty
	case "OptionalProperty":
		return pOptionalProperty
	}
	return pUnknown
}

// nameTable builds the global name index used throughout the file. UE5 .usmap stores
// every unique name once and references it by u32 index everywhere.
type nameTable struct {
	idx      map[string]uint32
	arr      []string
	frozen   bool // set once the names section has been written
	misses   int  // get() calls that found nothing — MUST be reported
	lateAdds int  // add() after freeze — would emit an out-of-range index
}

// unresolvedName occupies index 0 so that any lookup miss lands on a name that is
// obviously wrong in the output rather than silently aliasing to whatever real name
// happened to be registered first.
const unresolvedName = "__UsmapUnresolved"

func newNameTable() *nameTable {
	n := &nameTable{idx: map[string]uint32{}}
	n.add(unresolvedName)
	return n
}

func (n *nameTable) add(s string) uint32 {
	if s == "" {
		return 0xFFFFFFFF
	}
	if i, ok := n.idx[s]; ok {
		return i
	}
	if n.frozen {
		// The names section is already on the wire; a new index would point past the end
		// of the table and CUE4Parse would read out of range.
		n.lateAdds++
		return 0
	}
	i := uint32(len(n.arr))
	n.idx[s] = i
	n.arr = append(n.arr, s)
	return i
}

// get is the ONLY way to turn a name into an index at write time. A Go map miss on
// `nt.idx[...]` yields the zero value, which is a perfectly valid name index — that is
// defect #7, and it is invisible. This is not.
func (n *nameTable) get(s string) uint32 {
	if s == "" {
		n.misses++
		return 0
	}
	if i, ok := n.idx[s]; ok {
		return i
	}
	n.misses++
	return 0
}

// writeUsmap serializes the schema to dst. structs is the combined UClass + UScriptStruct
// list; enums is UEnum list; addrName maps any uintptr to a string (used to resolve
// inner-property struct/class names that were captured by address).
// writeStats counts everything the writer would otherwise swallow. Printed after every
// run: a run with a silent zero everywhere is the no-op tell.
type writeStats struct {
	dupStructRecords int // duplicate RECORDS discarded (records minus distinct names)
	collapsedNames   int // distinct NAMES that carried more than one record
	lossyCollapses   int // names where KEEP-LAST would have kept a poorer record
	propsSavedVsLast int // properties KEEP-RICHEST retains that KEEP-LAST would drop
	enumSavedVsLast  int // …of which are EnumProperty records
	richestImproved  int // loop statistic: times the running maximum was replaced
	unknownType      int // propTypeByte == pUnknown (expected: 0)
	holes            int // schema slots left empty because a property was un-emittable
	arrayDimEmitted  int // records emitted with ArrayDim != 1
	arrayDimClamped  int // ArrayDim > 255 (format limit)
	innerFallback    int // writeInnerType could not type an inner and fell back to Byte
	innerNil         int // …of which the inner was nil (extraction never captured it)
	structPropInner  int // nested StructProperty inners emitted (was impossible pre-fix)
	nestedContainer  int // nested container inners emitted (was impossible pre-fix)
	enumRecords      int // EnumProperty records emitted (was 0 pre-fix)
	propsEmitted     int // total FProperty records written
	slotsTotal       int // total schema slots (sum of ArrayDim)
	schemaIdxClamped int
	propCountClamped int
}

// dedupRule names the collapse rule in the output. It is not cosmetic: the format is
// name-keyed, so CUE4Parse keeps ONE record per name, and the pre-fix tool's incidental
// rule was KEEP-LAST.
//
// ⚠ Settlement §2 describes the kept ConstantData record as having "0 properties" while
// siblings carry "up to 259". Neither number reproduces on this build: measured live, the
// LAST-written record holds 49 and the RICHEST holds 263. Both figures are anim-BP
// RESIDENCY-dependent and will keep moving. The durable invariant is `kept < richest`, and
// the cost of keep-last is MEASURED per run below rather than quoted from any document.
const dedupRule = "KEEP-RICHEST"

var gWrite writeStats

func countEnumProps(s structInfo) int {
	n := 0
	for _, pr := range s.properties {
		if pr.typeName == "EnumProperty" {
			n++
		}
	}
	return n
}

// dedupStructs collapses records that share a name, keeping the RICHEST rather than the
// last. It also measures what that choice is worth, by comparing the record it keeps
// against the one keep-last would have kept — so the tool states its own advantage from
// this run's data instead of repeating a number from a write-up.
//
// ⚠ Three different counts live here and are easy to swap (§2's "84" already was):
//   - collapsedNames    — distinct NAMES that had more than one record
//   - dupStructRecords  — duplicate RECORDS discarded (records - names)
//   - lossyCollapses    — names where keep-last would have kept a POORER record
//
// A fourth, richestImproved, counts how many times the running maximum was replaced while
// scanning. It is a loop statistic, NOT a count of anything about the output, and it must
// never be reported as one.
func dedupStructs(in []structInfo) []structInfo {
	type agg struct {
		outIdx               int
		recs                 int
		lastProps, lastEnums int // the record KEEP-LAST would have kept
	}
	info := make(map[string]*agg, len(in))
	out := make([]structInfo, 0, len(in))
	for _, s := range in {
		if a, ok := info[s.name]; ok {
			a.recs++
			a.lastProps, a.lastEnums = len(s.properties), countEnumProps(s)
			gWrite.dupStructRecords++
			if len(s.properties) > len(out[a.outIdx].properties) {
				gWrite.richestImproved++
				out[a.outIdx] = s
			}
			continue
		}
		info[s.name] = &agg{outIdx: len(out), recs: 1, lastProps: len(s.properties), lastEnums: countEnumProps(s)}
		out = append(out, s)
	}
	// Map iteration order is randomised in Go, but every use below is an order-independent
	// sum or count, so nothing here can reach the output. (vtscan.go:221 is the one place
	// in this tool where map order feeds a sort — see the settlement's §1 source audit.)
	for _, a := range info {
		if a.recs < 2 {
			continue
		}
		gWrite.collapsedNames++
		keptProps := len(out[a.outIdx].properties)
		keptEnums := countEnumProps(out[a.outIdx])
		if keptProps != a.lastProps || keptEnums != a.lastEnums {
			gWrite.lossyCollapses++
		}
		gWrite.propsSavedVsLast += keptProps - a.lastProps
		gWrite.enumSavedVsLast += keptEnums - a.lastEnums
	}
	return out
}

func writeUsmap(dst string, structsIn []structInfo, enums []enumInfo) error {
	gWrite = writeStats{}
	nt := newNameTable()
	structs := dedupStructs(structsIn)

	// Recursively register names referenced by a propInfo and any embedded inner ones.
	var addProp func(pr *propInfo)
	addProp = func(pr *propInfo) {
		if pr == nil {
			return
		}
		nt.add(pr.name)
		if s := stripKind(pr.innerName); s != "" {
			nt.add(s)
		}
		addProp(pr.innerProp)
		addProp(pr.valueProp)
	}

	for _, s := range structs {
		nt.add(s.name)
		nt.add(stripKind(s.superName))
		for i := range s.properties {
			addProp(&s.properties[i])
		}
	}
	for _, e := range enums {
		nt.add(e.name)
		for _, v := range e.values {
			nt.add(v.name)
		}
	}

	// Build the body in memory first (we need DecompressedSize for the header).
	body := newBuf()

	// Names section.
	body.u32(uint32(len(nt.arr)))
	for _, s := range nt.arr {
		if len(s) > 255 {
			s = s[:255]
		}
		body.u8(byte(len(s)))
		body.bytes([]byte(s))
	}

	// Everything referenced from here on must already be in the table.
	nt.frozen = true

	// Enums section.
	body.u32(uint32(len(enums)))
	for _, e := range enums {
		body.u32(nt.get(e.name))
		n := len(e.values)
		if n > 255 {
			n = 255
		}
		body.u8(byte(n))
		for i := 0; i < n; i++ {
			body.u32(nt.get(e.values[i].name))
		}
	}

	// Structs section.
	body.u32(uint32(len(structs)))
	for _, s := range structs {
		body.u32(nt.get(s.name))
		if sup := stripKind(s.superName); sup == "" {
			body.u32(0xFFFFFFFF)
		} else if i, ok := nt.idx[sup]; ok {
			body.u32(i)
		} else {
			body.u32(0xFFFFFFFF)
		}

		// Walk the UNFILTERED property list, tracking the absolute schema slot. A
		// property we cannot emit still consumes its slots — it leaves a HOLE. CUE4Parse
		// fails loudly on the one missing index, which is strictly better than silently
		// re-labelling every property after it (defect #3: 7,713 properties, max shift 10).
		type rec struct {
			pr  propInfo
			idx int
			dim int
		}
		var recs []rec
		slots := 0
		for _, pr := range s.properties {
			dim := pr.arrayDim
			if dim < 1 {
				dim = 1
			}
			if dim > 255 {
				dim = 255
				gWrite.arrayDimClamped++
			}
			if propTypeByte(pr.typeName) == pUnknown {
				gWrite.unknownType++
				gWrite.holes++
			} else {
				recs = append(recs, rec{pr: pr, idx: slots, dim: dim})
			}
			slots += dim
		}
		if slots > 0xFFFF {
			slots = 0xFFFF
			gWrite.propCountClamped++
		}
		body.u16(uint16(slots))     // PropertyCount = total schema slots
		body.u16(uint16(len(recs))) // SerializablePropertyCount = records that follow
		gWrite.propsEmitted += len(recs)
		gWrite.slotsTotal += slots
		for _, rc := range recs {
			idx := rc.idx
			if idx > 0xFFFF {
				idx = 0xFFFF
				gWrite.schemaIdxClamped++
			}
			body.u16(uint16(idx))
			body.u8(byte(rc.dim))
			if rc.dim != 1 {
				gWrite.arrayDimEmitted++
			}
			body.u32(nt.get(rc.pr.name))
			writeInnerType(body, nt, &rc.pr, 0)
		}
	}

	bodyBytes := body.bytes_()

	fmt.Println("\n=== FK-14 writer counters (all printed; a silent zero everywhere is the no-op tell) ===")
	fmt.Printf("  struct records in                : %d   emitted after de-dup: %d\n", len(structsIn), len(structs))
	fmt.Printf("      duplicate RECORDS discarded  : %d   across %d distinct NAMES  (three different\n",
		gWrite.dupStructRecords, gWrite.collapsedNames)
	fmt.Printf("      counts, easy to swap: records / names / lossy collapses = %d / %d / %d)\n",
		gWrite.dupStructRecords, gWrite.collapsedNames, gWrite.lossyCollapses)
	fmt.Printf("  de-dup rule                      : %s\n", dedupRule)
	// ★ The tool measures the rule's worth from THIS run rather than quoting a figure: for
	// each collapsed name it compares the record it kept against the one KEEP-LAST would
	// have kept. Both are residency-dependent, so a fixed number would rot.
	fmt.Printf("      recovered vs KEEP-LAST       : +%d properties, +%d EnumProperty records\n",
		gWrite.propsSavedVsLast, gWrite.enumSavedVsLast)
	fmt.Printf("  property records emitted         : %d   in %d schema slots\n", gWrite.propsEmitted, gWrite.slotsTotal)
	fmt.Printf("  EnumProperty records emitted     : %d   (pre-fix: 0 — 100 %% were dropped)\n", gWrite.enumRecords)
	// ★ Permanent regression canary: the de-dup rules are DISCRIMINABLE from the output
	// alone. The margin is exactly the "recovered vs KEEP-LAST" pair printed above, so the
	// canary is self-computing and cannot go stale as anim-BP residency drifts.
	fmt.Printf("      canary: reverting to KEEP-LAST would print %d records / %d enum here\n",
		gWrite.propsEmitted-gWrite.propsSavedVsLast, gWrite.enumRecords-gWrite.enumSavedVsLast)
	fmt.Printf("  nested StructProperty inners     : %d   (pre-fix: impossible, flattened to Byte)\n", gWrite.structPropInner)
	fmt.Printf("  nested container inners          : %d   (pre-fix: impossible, flattened to Byte)\n", gWrite.nestedContainer)
	fmt.Printf("  ArrayDim != 1 records emitted    : %d   (pre-fix: 0 — hardcoded 1)\n", gWrite.arrayDimEmitted)
	fmt.Printf("  inner fell back to Byte          : %d   (of which inner was nil: %d)\n", gWrite.innerFallback, gWrite.innerNil)
	fmt.Printf("  unknown property type            : %d   (settlement: this filter has never fired)\n", gWrite.unknownType)
	fmt.Printf("  schema holes left                : %d\n", gWrite.holes)
	fmt.Printf("  name lookup misses               : %d   (-> %q, index 0)\n", nt.misses, unresolvedName)
	fmt.Printf("  late name adds (would corrupt)   : %d\n", nt.lateAdds)
	fmt.Printf("  clamped: ArrayDim %d  SchemaIdx %d  PropertyCount %d\n",
		gWrite.arrayDimClamped, gWrite.schemaIdxClamped, gWrite.propCountClamped)

	// Header + body to file.
	f, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer f.Close()
	var hdr [12]byte
	binary.LittleEndian.PutUint16(hdr[0:], 0x30C4)
	hdr[2] = 0
	hdr[3] = 0
	binary.LittleEndian.PutUint32(hdr[4:], uint32(len(bodyBytes)))
	binary.LittleEndian.PutUint32(hdr[8:], uint32(len(bodyBytes)))
	if _, err := f.Write(hdr[:]); err != nil {
		return err
	}
	if _, err := f.Write(bodyBytes); err != nil {
		return err
	}
	return nil
}

// writeInnerType emits an FProperty type byte plus its type-specific tail, RECURSIVELY.
//
// It replaces writeInnerOrByte, which had no StructProperty branch and flattened every
// Struct / Enum / Array / Map inner to a bare ByteProperty. That was deliberate — its own
// comment said a Byte inner "is safer than crashing on a wrong inner-name lookup" — and it
// was a defensive workaround for the +0x80 read: with a garbage inner, emitting its real
// type would have been actively harmful. With the inner read correctly there is nothing to
// defend against, and the flattening was doing real damage: 41.0 % of container inners in
// the canonical file are ByteProperty against 4.8 % genuinely byte, and every MapProperty
// (555) and SetProperty (142) ever produced was Map<Byte,Byte> / Set<Byte>.
//
// Every remaining fallback is COUNTED. A run reporting zero fallbacks everywhere is the
// tell that the writer did nothing at all.
func writeInnerType(b *buf, nt *nameTable, pr *propInfo, depth int) {
	if pr == nil {
		gWrite.innerFallback++
		gWrite.innerNil++
		b.u8(pByteProperty)
		return
	}
	t := propTypeByte(pr.typeName)
	if t == pUnknown || depth > 4 {
		gWrite.innerFallback++
		b.u8(pByteProperty)
		return
	}
	b.u8(t)
	if depth > 0 {
		switch t {
		case pStructProperty:
			gWrite.structPropInner++
		case pArrayProperty, pSetProperty, pMapProperty, pOptionalProperty:
			gWrite.nestedContainer++
		}
	} else if t == pEnumProperty {
		gWrite.enumRecords++
	}
	switch t {
	case pStructProperty:
		b.u32(nt.get(stripKind(pr.innerName)))
	case pEnumProperty:
		// UnderlyingProp (a numeric FProperty), then the UEnum's name index.
		writeInnerType(b, nt, pr.innerProp, depth+1)
		b.u32(nt.get(stripKind(pr.innerName)))
	case pArrayProperty, pSetProperty, pOptionalProperty:
		writeInnerType(b, nt, pr.innerProp, depth+1)
	case pMapProperty:
		writeInnerType(b, nt, pr.innerProp, depth+1)
		writeInnerType(b, nt, pr.valueProp, depth+1)
	}
}

// stripKind drops "UClass:" / "UStruct:" / "UEnum:" prefix from addrIndex labels.
func stripKind(s string) string {
	for _, pref := range []string{"UClass:", "UStruct:", "UEnum:"} {
		if len(s) > len(pref) && s[:len(pref)] == pref {
			return s[len(pref):]
		}
	}
	return s
}

// ===== little byte-writer =====

type buf struct{ b []byte }

func newBuf() *buf      { return &buf{} }
func (b *buf) bytes_() []byte { return b.b }
func (b *buf) u8(v byte) { b.b = append(b.b, v) }
func (b *buf) u16(v uint16) {
	b.b = append(b.b, byte(v), byte(v>>8))
}
func (b *buf) u32(v uint32) {
	b.b = append(b.b, byte(v), byte(v>>8), byte(v>>16), byte(v>>24))
}
func (b *buf) bytes(p []byte) { b.b = append(b.b, p...) }

// emitUsmapBeside writes the .usmap next to the extractor binary, copying through
// tools/extractor so the existing search-path logic picks it up.
func emitUsmapBeside(path string, classes, structs []structInfo, enums []enumInfo) {
	all := append([]structInfo{}, classes...)
	all = append(all, structs...)
	if err := writeUsmap(path, all, enums); err != nil {
		fmt.Println("ERROR writing usmap:", err)
		return
	}
	info, _ := os.Stat(path)
	fmt.Printf("Wrote .usmap: %s (%d bytes)\n", path, info.Size())
}

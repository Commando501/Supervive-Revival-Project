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
//   u16 SchemaIdx (we emit sequential)
//   u8  ArrayDim = 1
//   u32 NameIdx
//   u8  PropertyType (EPropertyType byte)
//   [type-specific tail]

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
	idx map[string]uint32
	arr []string
}

func newNameTable() *nameTable { return &nameTable{idx: map[string]uint32{}} }

func (n *nameTable) add(s string) uint32 {
	if s == "" {
		return 0xFFFFFFFF
	}
	if i, ok := n.idx[s]; ok {
		return i
	}
	i := uint32(len(n.arr))
	n.idx[s] = i
	n.arr = append(n.arr, s)
	return i
}

// writeUsmap serializes the schema to dst. structs is the combined UClass + UScriptStruct
// list; enums is UEnum list; addrName maps any uintptr to a string (used to resolve
// inner-property struct/class names that were captured by address).
func writeUsmap(dst string, structs []structInfo, enums []enumInfo) error {
	nt := newNameTable()

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

	// Enums section.
	body.u32(uint32(len(enums)))
	for _, e := range enums {
		body.u32(nt.idx[e.name])
		n := len(e.values)
		if n > 255 {
			n = 255
		}
		body.u8(byte(n))
		for i := 0; i < n; i++ {
			body.u32(nt.add(e.values[i].name))
		}
	}

	// Structs section.
	body.u32(uint32(len(structs)))
	for _, s := range structs {
		body.u32(nt.idx[s.name])
		sup := stripKind(s.superName)
		if sup == "" {
			body.u32(0xFFFFFFFF)
		} else {
			if i, ok := nt.idx[sup]; ok {
				body.u32(i)
			} else {
				body.u32(0xFFFFFFFF)
			}
		}
		// Filter to serializable (non-zero type) properties.
		var props []propInfo
		for _, pr := range s.properties {
			if propTypeByte(pr.typeName) != pUnknown {
				props = append(props, pr)
			}
		}
		// Drop props whose tail needs an inner name we couldn't resolve — CUE4Parse
		// crashes on an out-of-range nameLut index. Better to omit than corrupt.
		var emit []propInfo
		for _, pr := range props {
			t := propTypeByte(pr.typeName)
			needsName := t == pStructProperty || t == pEnumProperty
			if needsName {
				s := stripKind(pr.innerName)
				if _, ok := nt.idx[s]; !ok || s == "" {
					continue
				}
			}
			emit = append(emit, pr)
		}
		body.u16(uint16(len(emit)))
		body.u16(uint16(len(emit)))
		for i, pr := range emit {
			body.u16(uint16(i))                // SchemaIdx
			body.u8(1)                         // ArrayDim
			body.u32(nt.idx[pr.name])          // NameIdx
			writePropertyType(body, nt, pr)
		}
	}

	bodyBytes := body.bytes_()

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

// writePropertyType emits the type byte plus type-specific tail (CUE4Parse format).
func writePropertyType(b *buf, nt *nameTable, pr propInfo) {
	t := propTypeByte(pr.typeName)
	b.u8(t)
	switch t {
	case pStructProperty:
		s := stripKind(pr.innerName)
		i, ok := nt.idx[s]
		if !ok {
			i = 0
		}
		b.u32(i)
	case pEnumProperty:
		// Recursive UnderlyingProp (typed inner), then u32 enumNameIdx.
		writeInnerOrByte(b, nt, pr.innerProp)
		s := stripKind(pr.innerName)
		i, ok := nt.idx[s]
		if !ok {
			i = 0
		}
		b.u32(i)
	case pArrayProperty, pSetProperty, pOptionalProperty:
		writeInnerOrByte(b, nt, pr.innerProp)
	case pMapProperty:
		writeInnerOrByte(b, nt, pr.innerProp)
		writeInnerOrByte(b, nt, pr.valueProp)
	}
}

// writeInnerOrByte emits a nested FProperty type tree. We only emit inner types we're
// HIGHLY confident about — simple no-tail types like Int/Float/Bool/Str/Name/Object.
// For Struct/Enum/Array/Map (which have tails or need their own inner walk) we fall
// back to a bare Byte; CUE4Parse then sees ArrayProperty<Byte> and parses element-wise,
// which is safer than crashing on a wrong inner-name lookup.
func writeInnerOrByte(b *buf, nt *nameTable, inner *propInfo) {
	if inner == nil {
		b.u8(pByteProperty)
		return
	}
	switch propTypeByte(inner.typeName) {
	case pByteProperty, pBoolProperty, pIntProperty, pFloatProperty, pDoubleProperty,
		pStrProperty, pNameProperty, pTextProperty,
		pInt8Property, pInt16Property, pInt64Property,
		pUInt16Property, pUInt32Property, pUInt64Property,
		pObjectProperty, pSoftObjectProperty, pWeakObjectProperty, pLazyObjectProperty,
		pInterfaceProperty, pDelegateProperty, pMulticastDelegateProperty,
		pFieldPathProperty:
		// These all have no required tail in CUE4Parse's parser.
		b.u8(propTypeByte(inner.typeName))
	default:
		b.u8(pByteProperty)
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

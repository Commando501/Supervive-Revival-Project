// pipeline.go — the slow shared phases (name pool scan, exec-ptr histogram,
// instance collection, metaclass identification) factored out so multiple commands
// can reuse them without re-running the multi-minute scans.

package main

import (
	"fmt"
	"os"
)

// classified holds the three reflection categories plus the resolved layout offsets.
type classified struct {
	r            *reader
	p            *pool
	em           *execMap
	instMap      map[uintptr][]uintptr
	classes      []objref
	structs      []objref
	enums        []objref
	classVtable  uintptr
	structVtable uintptr
	enumVtable   uintptr
	nameOff      uintptr // FName offset within UObject
	classOff     uintptr // ClassPrivate offset within UObject
}

// runPipeline does the full R2.1 → R2.3 sequence and returns everything needed for
// downstream commands. Verbose=false suppresses the diagnostic prints.
func runPipeline(name string, verbose bool) *classified {
	r, pid, base, size := mustOpen(name)
	if verbose {
		fmt.Printf("PID %d  %q base=0x%X size=0x%X\n", pid, name, base, size)
	}

	p, err := findNamePool(r)
	if err != nil {
		fmt.Println("ERROR (name pool):", err)
		os.Exit(1)
	}
	if verbose {
		fmt.Printf("  GNames blocks=%d layout=%s\n", len(p.blocks), p.layout)
	}
	em := r.execMap()
	if verbose {
		fmt.Printf("  exec regions: %d\n", len(em.regs))
	}

	classID, ok := findNameID(r, p, "Class")
	if !ok {
		fmt.Println("ERROR: FName \"Class\" not found")
		os.Exit(1)
	}
	_ = classID

	if verbose {
		fmt.Println("\n  histogramming all 8-aligned ptrs in DATA regions...")
	}
	counts := histogramAnyPtrs(r)
	popular := vtablesByFrequency(r, em, counts, 20, 20000)
	if verbose {
		fmt.Printf("  %d real-looking vtables (count >= 20, shape-ok)\n", len(popular))
	}

	vtableSet := make(map[uintptr]bool, len(popular))
	for _, v := range popular {
		vtableSet[v.addr] = true
	}
	if verbose {
		fmt.Printf("  collecting instances for %d popular vtables...\n", len(popular))
	}
	instMap := collectAllInstancesByVtable(r, vtableSet)

	// UClass metaclass via self-class signature.
	var classMeta, classVtable, nameOff, classOff uintptr
	for _, v := range popular {
		addrs := instMap[v.addr]
		obj, no, co, ok := findMetaclassInInstances(r, p, addrs, "Class")
		if ok {
			classMeta, classVtable, nameOff, classOff = obj, v.addr, no, co
			break
		}
	}
	if classVtable == 0 {
		fmt.Println("ERROR: UClass metaclass not found.")
		os.Exit(1)
	}

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

	findVtableForInstancesOf := func(meta uintptr) uintptr {
		for _, v := range popular {
			if v.addr == classVtable {
				continue
			}
			addrs := instMap[v.addr]
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
	structVtable := findVtableForInstancesOf(structMeta)
	enumVtable := findVtableForInstancesOf(enumMeta)

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
	c := &classified{
		r: r, p: p, em: em, instMap: instMap,
		classes:      resolveInstances(classVtable),
		structs:      resolveInstances(structVtable),
		enums:        resolveInstances(enumVtable),
		classVtable:  classVtable, structVtable: structVtable, enumVtable: enumVtable,
		nameOff: nameOff, classOff: classOff,
	}
	if verbose {
		fmt.Printf("  UClass=%d  UScriptStruct=%d  UEnum=%d  nameOff=0x%X classOff=0x%X\n",
			len(c.classes), len(c.structs), len(c.enums), c.nameOff, c.classOff)
		_ = classMeta
	}
	return c
}

func cmdExtract(name string) {
	c := runPipeline(name, true)
	defer procCloseHandle.Call(c.r.h)

	x := buildAddrIndex(c.classes, c.structs, c.enums)

	fmt.Println("\n  walking UClass properties...")
	classInfos := make([]structInfo, 0, len(c.classes))
	for _, o := range c.classes {
		classInfos = append(classInfos, walkStruct(c.r, c.p, x, o.name, o.addr))
	}
	fmt.Println("  walking UScriptStruct properties...")
	structInfos := make([]structInfo, 0, len(c.structs))
	for _, o := range c.structs {
		structInfos = append(structInfos, walkStruct(c.r, c.p, x, o.name, o.addr))
	}
	fmt.Println("  walking UEnum values...")
	enumInfos := make([]enumInfo, 0, len(c.enums))
	for _, o := range c.enums {
		enumInfos = append(enumInfos, walkEnum(c.r, c.p, o.name, o.addr))
	}

	totalProps := 0
	for _, s := range classInfos {
		totalProps += len(s.properties)
	}
	for _, s := range structInfos {
		totalProps += len(s.properties)
	}
	totalEnumValues := 0
	for _, e := range enumInfos {
		totalEnumValues += len(e.values)
	}
	fmt.Printf("\nR2.4 result: %d UClass + %d UScriptStruct = %d total props; %d UEnum values\n",
		len(classInfos), len(structInfos), totalProps, totalEnumValues)

	// Print first 10 of each kind to stdout for eyeball verification.
	allStructs := append([]structInfo{}, classInfos...)
	allStructs = append(allStructs, structInfos...)
	fmt.Println("\n=== sample schema (first 10 UStructs + 10 UEnums) ===")
	emitSchema(allStructs, enumInfos, os.Stdout, 10)

	// Write the FULL schema to disk for inspection.
	out, err := os.Create("schema.txt")
	if err == nil {
		emitSchema(allStructs, enumInfos, out, 0)
		out.Close()
		fmt.Println("\nFull schema written to: schema.txt")
	}

	// R2.5: serialize to .usmap. Drop into the extractor's search dir (Program.cs picks
	// up the first *.usmap in tools/extractor/).
	fmt.Println("\n=== R2.5 serialize .usmap ===")
	emitUsmapBeside("mappings.usmap", classInfos, structInfos, enumInfos)
	emitUsmapBeside(`G:\git\Supervive Revival Project\tools\extractor\mappings.usmap`, classInfos, structInfos, enumInfos)
}

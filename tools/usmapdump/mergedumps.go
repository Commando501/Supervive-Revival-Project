// mergedumps.go — union several dumpimage snapshots into one maximally-covered image.
//
// WHY. A single dumpimage run only captures the .text pages the game had EXECUTED by that
// moment (this build demand-decrypts code pages on access — see dumpimage.go). Different
// game states run different code, so a menu dump and an in-game dump have DIFFERENT
// readable pages. Merging takes, for every byte, the readable version from whichever dump
// has it — pushing .text coverage toward 100% as you feed in dumps from more states.
//
// THE UNION IS "primary's non-zero bytes win; its zero (unread) bytes get filled from the
// next dump that has them non-zero." That is exactly correct for .text: a demand-decrypt
// gap reads as a zero page, real code is never a zero page, and — critically — a given RVA
// in a statically-loaded image has ONE true value across all dumps (readable => identical
// bytes, unread => zero). So "any non-zero wins" reconstructs the true image.
//
// HARD CONSTRAINT: every input must share the same module base (same ImageBase). A
// different base means ASLR relocated the image, so every relocated pointer baked into
// .text differs by the delta — byte-merging two different bases would splice incompatible
// code. Mismatched-base inputs are rejected, not merged.
//
// CAVEAT (reported, not fatal): .data is writable, so unioning snapshots taken at different
// times can mix runtime global state. It doesn't matter in practice here — .data comes out
// 100% covered in every single dump, so the union barely touches it — but .text (read-only)
// is the exact, authoritative part of a merged image.
package main

import (
	"encoding/binary"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type mergeSec struct {
	name  string
	rva   uint32
	vsize uint32
}

// parseImageBuf reads base/SizeOfImage/sections straight from an on-disk dumpimage file
// (headers are the fixed ones dumpimage wrote: file-offset==RVA, ImageBase=live base).
func parseImageBuf(img []byte) (base uintptr, sizeOfImage uint32, secs []mergeSec, ok bool) {
	if len(img) < 0x200 || img[0] != 'M' || img[1] != 'Z' {
		return
	}
	eLfanew := binary.LittleEndian.Uint32(img[0x3C:])
	if int(eLfanew)+0x108 > len(img) {
		return
	}
	if img[eLfanew] != 'P' || img[eLfanew+1] != 'E' {
		return
	}
	fileHdr := eLfanew + 4
	optOff := eLfanew + 24 // 4 (PE sig) + 20 (IMAGE_FILE_HEADER)
	numSections := binary.LittleEndian.Uint16(img[fileHdr+2:])
	sizeOfOptional := binary.LittleEndian.Uint16(img[fileHdr+16:])
	if binary.LittleEndian.Uint16(img[optOff:]) != 0x20B { // PE32+ magic
		return
	}
	base = uintptr(binary.LittleEndian.Uint64(img[optOff+24:])) // ImageBase
	sizeOfImage = binary.LittleEndian.Uint32(img[optOff+56:])
	secStart := eLfanew + 4 + 20 + uint32(sizeOfOptional)
	for i := uint32(0); i < uint32(numSections); i++ {
		so := secStart + i*40
		if int(so)+40 > len(img) {
			break
		}
		name := strings.TrimRight(string(img[so:so+8]), "\x00")
		secs = append(secs, mergeSec{
			name:  name,
			vsize: binary.LittleEndian.Uint32(img[so+8:]),
			rva:   binary.LittleEndian.Uint32(img[so+12:]),
		})
	}
	ok = true
	return
}

func countNonZero(b []byte, start, n int) int {
	end := start + n
	if end > len(b) {
		end = len(b)
	}
	c := 0
	for i := start; i < end; i++ {
		if b[i] != 0 {
			c++
		}
	}
	return c
}

type mergeContrib struct {
	path   string
	filled int // bytes this input newly filled (primary: its total non-zero = seed)
	primary bool
}

func cmdMergeDumps(outFile string, inputs []string) {
	// A single directory arg expands (recursively) to every *.dump.exe under it, so
	// per-state dumps in subfolders (dumps/menu/, dumps/match/, …) are all found. The
	// output file is excluded so a re-merge into the same tree doesn't fold itself in.
	if len(inputs) == 1 {
		if fi, err := os.Stat(inputs[0]); err == nil && fi.IsDir() {
			oabs, _ := filepath.Abs(outFile)
			var found []string
			filepath.WalkDir(inputs[0], func(p string, d os.DirEntry, err error) error {
				if err != nil || d.IsDir() || !strings.HasSuffix(p, ".dump.exe") {
					return nil
				}
				if abs, _ := filepath.Abs(p); abs != oabs {
					found = append(found, p)
				}
				return nil
			})
			inputs = found
		}
	}
	if len(inputs) == 0 {
		fmt.Println("ERROR: no input dumps (give files, or a directory containing *.dump.exe)")
		os.Exit(1)
	}

	var acc []byte
	var accBase uintptr
	var accSize uint32
	var accSecs []mergeSec
	var contribs []mergeContrib

	for _, in := range inputs {
		data, err := os.ReadFile(in)
		if err != nil {
			fmt.Printf("  skip %s: %v\n", in, err)
			continue
		}
		base, soi, secs, ok := parseImageBuf(data)
		if !ok {
			fmt.Printf("  skip %s: not a valid dumpimage PE\n", in)
			continue
		}
		if acc == nil {
			acc, accBase, accSize, accSecs = data, base, soi, secs
			seed := countNonZero(acc, 0, len(acc))
			contribs = append(contribs, mergeContrib{path: in, filled: seed, primary: true})
			fmt.Printf("  primary %s  base 0x%X  %.2f%% non-zero\n",
				filepath.Base(in), base, 100*float64(seed)/float64(len(acc)))
			continue
		}
		if len(data) != len(acc) {
			fmt.Printf("  skip %s: size 0x%X != primary 0x%X\n", in, len(data), len(acc))
			continue
		}
		if base != accBase {
			fmt.Printf("  skip %s: ImageBase 0x%X != primary 0x%X (different ASLR base — not mergeable)\n",
				in, base, accBase)
			continue
		}
		filled := 0
		for i := 0; i < len(acc); i++ {
			if acc[i] == 0 && data[i] != 0 {
				acc[i] = data[i]
				filled++
			}
		}
		contribs = append(contribs, mergeContrib{path: in, filled: filled})
		fmt.Printf("  merged %s  +%d bytes (%.2f MB)\n",
			filepath.Base(in), filled, float64(filled)/(1024*1024))
	}
	if acc == nil {
		fmt.Println("ERROR: no valid input dumps could be read")
		os.Exit(1)
	}

	if err := os.WriteFile(outFile, acc, 0644); err != nil {
		fmt.Println("ERROR: writing merged image:", err)
		os.Exit(1)
	}
	total := countNonZero(acc, 0, len(acc))
	fmt.Printf("  wrote %s  (%.1f MB, %.2f%% non-zero merged)\n",
		outFile, float64(len(acc))/(1024*1024), 100*float64(total)/float64(len(acc)))

	writeMergeManifest(outFile+".txt", outFile, accBase, accSize, acc, accSecs, contribs)
	fmt.Printf("  wrote %s\n", outFile+".txt")
}

func writeMergeManifest(path, outFile string, base uintptr, sizeOfImage uint32,
	acc []byte, secs []mergeSec, contribs []mergeContrib) {
	var b strings.Builder
	fmt.Fprintf(&b, "usmapdump mergedumps manifest\n")
	fmt.Fprintf(&b, "generated : %s\n", time.Now().Format("2006-01-02 15:04:05"))
	fmt.Fprintf(&b, "output    : %s (%.1f MB)\n", filepath.Base(outFile), float64(len(acc))/(1024*1024))
	fmt.Fprintf(&b, "base      : 0x%X   SizeOfImage 0x%X\n\n", base, sizeOfImage)

	fmt.Fprintf(&b, "%-44s %s\n", "INPUT", "BYTES CONTRIBUTED")
	for _, c := range contribs {
		tag := ""
		if c.primary {
			tag = " (primary/seed)"
		}
		fmt.Fprintf(&b, "%-44s %d (%.2f MB)%s\n",
			filepath.Base(c.path), c.filled, float64(c.filled)/(1024*1024), tag)
	}

	fmt.Fprintf(&b, "\nMerged coverage (non-zero bytes per section):\n")
	fmt.Fprintf(&b, "%-10s %-12s %-12s %s\n", "SECTION", "RVA", "VSIZE", "COVERED")
	for _, s := range secs {
		cov := countNonZero(acc, int(s.rva), int(s.vsize))
		pct := 0.0
		if s.vsize > 0 {
			pct = 100 * float64(cov) / float64(s.vsize)
		}
		fmt.Fprintf(&b, "%-10s 0x%-10X 0x%-10X %d (%.1f%%)\n", s.name, s.rva, s.vsize, cov, pct)
	}
	total := countNonZero(acc, 0, len(acc))
	fmt.Fprintf(&b, "overall   : %d / %d (%.2f%%)\n", total, len(acc), 100*float64(total)/float64(len(acc)))

	fmt.Fprintf(&b, "\nNOTE: coverage counts NON-ZERO bytes, so a genuinely-zero readable byte reads\n")
	fmt.Fprintf(&b, "as a gap here (slight undercount). .text (read-only) is exact; .data union across\n")
	fmt.Fprintf(&b, "differently-timed dumps may mix runtime state. All inputs shared module base 0x%X;\n", base)
	fmt.Fprintf(&b, "any dump with a different ImageBase was rejected (not byte-mergeable).\n")

	if err := os.WriteFile(path, []byte(b.String()), 0644); err != nil {
		fmt.Println("WARN: merge manifest write failed:", err)
	}
}

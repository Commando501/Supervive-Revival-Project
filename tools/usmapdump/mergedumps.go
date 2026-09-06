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
// ── 2026-08-14 (S121, FK-18/FK-19): .text-ONLY, PAGE-GRANULAR, BASE-AGNOSTIC BY DEFAULT ──
//
// The old rule was: "every input must share the same ImageBase; a different base means every
// relocated pointer baked into .text differs by the delta, so byte-merging would splice
// incompatible code" — and mismatched inputs were dropped whole. That rule is RIGHT for
// .rdata/.data and WRONG for .text, which is what FK-3 §8.0 measured and prescribed a fix for
// (docs/fk3-fk4-settled.md:604-620) — a fix nobody had implemented until now. ASLR hands out a
// new base most launches, so the old behaviour silently discarded every cross-session capture:
// rcb, tutorial-hero and lobby-dispatch-decrypted were all on disk and all thrown away.
//
// MEASURED (S121, two independent passes):
//   * The base-relocation directory holds 1,403,750 DIR64 fixups + 3,048 ABSOLUTE padding.
//     1,257,732 land in .rdata, 146,018 in .data, and **0 in .text**. A .text rebase is not
//     invasive, it is EMPTY.
//   * Across all 10 pairwise comparisons against `menu` (7 same-base, 3 cross-base), .text has
//     **0 differing bytes** on every page decrypted in both — 15,199-15,739 shared pages a pair.
//   * A decrypted page is never partially populated (min 963 non-zero bytes/page, 0 pages under
//     256), so "page is all zero" == "never executed" and the union is page-clean.
//   * .rdata, .data and .pdata gain **+0 non-zero pages** from every one of the 10 donors.
//     There is nothing outside .text to merge.
//
// So the default is now: merge **.text only**, **page-granular**, ignoring ImageBase entirely.
// That is strictly better in three ways:
//   1. it recovers every cross-session capture (the whole point of merging);
//   2. copying whole 4 KiB pages means bytes from two donors can never interleave inside one
//      page — safe by construction, not merely safe by measurement, so it survives a patch;
//   3. it makes the output's .rdata/.data EXACTLY THE SEED'S. The old whole-image fill spliced
//      writable globals from every input, so a global read out of a merged image could be a
//      value that never simultaneously existed — and, worse, which value you got depended on
//      the seed, i.e. on directory-walk order. MEASURED: 4,678 .data bytes change identity
//      purely from choosing a different seed, and two same-base dumps from different sessions
//      disagree on ~485 KB of .data. Merging .text only retires that caveat instead of
//      documenting it.
//
// Every donor is still checked against the accumulator on the pages both hold (the "conflict"
// count). For .text that must be 0; a non-zero count means base-independence has stopped
// holding for this build and the donor is REJECTED rather than spliced (override with -force).
//
// `-wholeimage` restores the pre-S121 semantics (whole-image byte fill; cross-base donors
// restricted to sections their own reloc table proves base-independent). It is the rollback
// path and it is what reproduces the historical dumps/merged.dump.exe.
//
// METRIC WARNING, load-bearing: the coverage table below counts NON-ZERO BYTES. That metric is
// sound for .text (demand-decrypt zeroes whole 4 KiB pages, so non-zero-byte % and readable %
// agree) and MEANINGLESS for .rdata/.data, where legally-zero bytes (vtable null slots, string
// padding, zeroed globals) read as gaps. Quoting the .rdata figure as a readability number is
// exactly what produced false-known FK-3 ("`.rdata` is capped at 63.12% and that is
// STRUCTURAL" — it is 99.6% readable). The manifest therefore prints BOTH metrics side by side
// and labels them, so the two can never again be compared as if commensurable.
package main

import (
	"encoding/binary"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

const mergePageSize = 0x1000

type mergeSec struct {
	name  string
	rva   uint32
	vsize uint32
}

// parseImageBuf reads base/SizeOfImage/sections straight from an on-disk dumpimage file
// (headers are the fixed ones dumpimage wrote: file-offset==RVA, ImageBase=live base).
func parseImageBuf(img []byte) (base uintptr, sizeOfImage uint32, secs []mergeSec, ok bool) {
	base, sizeOfImage, secs, _, _, ok = parseImageBufFull(img)
	return
}

// parseImageBufFull additionally returns the base-relocation directory (RVA, size), which is
// what lets a cross-base input be merged section-selectively instead of dropped whole.
func parseImageBufFull(img []byte) (base uintptr, sizeOfImage uint32, secs []mergeSec,
	relocRVA, relocSize uint32, ok bool) {
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
	// PE32+ optional header: NumberOfRvaAndSizes @108, DataDirectory @112, entry 5 = BaseReloc.
	if numDirs := binary.LittleEndian.Uint32(img[optOff+108:]); numDirs > 5 {
		relocRVA = binary.LittleEndian.Uint32(img[optOff+112+5*8:])
		relocSize = binary.LittleEndian.Uint32(img[optOff+112+5*8+4:])
	}
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

// relocTargetsPerSection walks IMAGE_BASE_RELOCATION blocks and returns, per section name, the
// number of non-ABSOLUTE relocation entries landing inside it, plus a type histogram and the
// count of entries that fall outside every section. In a dumpimage snapshot file-offset==RVA,
// so the directory can be read at its RVA directly. .reloc is 100% readable in every dump we
// hold, so this never has to guess.
func relocTargetsPerSection(img []byte, relocRVA, relocSize uint32, secs []mergeSec) (
	perSec map[string]int, byType map[uint16]int, outside int, entries int, ok bool) {
	perSec = map[string]int{}
	byType = map[uint16]int{}
	if relocRVA == 0 || relocSize == 0 || int(relocRVA)+int(relocSize) > len(img) {
		return perSec, byType, 0, 0, false
	}
	off := int(relocRVA)
	end := off + int(relocSize)
	for off+8 <= end {
		blockRVA := binary.LittleEndian.Uint32(img[off:])
		blockSize := binary.LittleEndian.Uint32(img[off+4:])
		if blockSize < 8 || off+int(blockSize) > end {
			break
		}
		n := (int(blockSize) - 8) / 2
		for i := 0; i < n; i++ {
			w := binary.LittleEndian.Uint16(img[off+8+i*2:])
			typ := w >> 12
			byType[typ]++
			if typ == 0 { // IMAGE_REL_BASED_ABSOLUTE — padding, relocates nothing
				continue
			}
			entries++
			rva := blockRVA + uint32(w&0xFFF)
			hit := false
			for _, s := range secs {
				if rva >= s.rva && rva < s.rva+s.vsize {
					perSec[s.name]++
					hit = true
					break
				}
			}
			if !hit {
				outside++
			}
		}
		off += int(blockSize)
	}
	return perSec, byType, outside, entries, true
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

// countZeroPages reports how many whole 4 KiB pages in [start,start+n) are entirely zero, and
// how many pages the range spans. For .text an all-zero page == a page the process never
// executed (demand-decrypt), which is the only honest readability proxy an offline file has.
func countZeroPages(b []byte, start, n int) (zero, total int) {
	end := start + n
	if end > len(b) {
		end = len(b)
	}
	for p := start; p < end; p += mergePageSize {
		q := p + mergePageSize
		if q > end {
			q = end
		}
		total++
		allZero := true
		for i := p; i < q; i++ {
			if b[i] != 0 {
				allZero = false
				break
			}
		}
		if allZero {
			zero++
		}
	}
	return
}

// conflicts counts positions in [start,start+n) where BOTH images are non-zero and DISAGREE.
// On a section that is genuinely base-independent and read-only this must be 0 — it is the
// per-merge positive control that keeps cross-base merging honest.
func conflicts(a, b []byte, start, n int) int {
	end := start + n
	if end > len(a) {
		end = len(a)
	}
	if end > len(b) {
		end = len(b)
	}
	c := 0
	for i := start; i < end; i++ {
		if a[i] != 0 && b[i] != 0 && a[i] != b[i] {
			c++
		}
	}
	return c
}

// pickSeed returns the index of the best seed: the input holding the most non-zero .text among
// those sharing the corpus's most common ImageBase. It reads only each candidate's .text range,
// so it costs one streamed pass and no extra memory.
func pickSeed(paths []string) int {
	scores := make([]int, len(paths))
	bases := make([]uintptr, len(paths))
	for i, p := range paths {
		scores[i] = -1
		f, err := os.Open(p)
		if err != nil {
			continue
		}
		hdr := make([]byte, 0x1000)
		if _, err := f.ReadAt(hdr, 0); err != nil {
			f.Close()
			continue
		}
		// .text's RVA/VSIZE and the ImageBase come from the file's own header.
		var textRVA, textSize uint32
		if b, _, secs, ok := parseImageBuf(hdr); ok {
			bases[i] = b
			for _, s := range secs {
				if s.name == ".text" {
					textRVA, textSize = s.rva, s.vsize
				}
			}
		}
		if textSize == 0 {
			f.Close()
			continue
		}
		buf := make([]byte, 1<<22)
		score, off := 0, int64(textRVA)
		end := int64(textRVA) + int64(textSize)
		for off < end {
			n := int64(len(buf))
			if off+n > end {
				n = end - off
			}
			got, err := f.ReadAt(buf[:n], off)
			if got == 0 {
				break
			}
			for _, b := range buf[:got] {
				if b != 0 {
					score++
				}
			}
			off += int64(got)
			if err != nil {
				break
			}
		}
		f.Close()
		scores[i] = score
	}
	// Plurality ImageBase; ties broken by the best-covered candidate at each base.
	count, bestAt := map[uintptr]int{}, map[uintptr]int{}
	for i := range paths {
		if scores[i] < 0 {
			continue
		}
		count[bases[i]]++
		if s, ok := bestAt[bases[i]]; !ok || scores[i] > scores[s] {
			bestAt[bases[i]] = i
		}
	}
	var anchor uintptr
	bestCount := -1
	for b, n := range count {
		if n > bestCount || (n == bestCount && scores[bestAt[b]] > scores[bestAt[anchor]]) {
			anchor, bestCount = b, n
		}
	}
	if bestCount < 0 {
		return 0
	}
	return bestAt[anchor]
}

// sectionsDiffer reports the first mismatch between two section tables, or "" if identical.
// Matching name/RVA/VSIZE for all sections is what proves two dumps describe the same build
// laid out the same way — ImageBase equality never proved that and was never the right test.
func sectionsDiffer(a, b []mergeSec) string {
	if len(a) != len(b) {
		return fmt.Sprintf("%d sections vs %d", len(b), len(a))
	}
	for i := range a {
		if a[i].name != b[i].name || a[i].rva != b[i].rva || a[i].vsize != b[i].vsize {
			return fmt.Sprintf("%s@0x%X/0x%X vs %s@0x%X/0x%X",
				b[i].name, b[i].rva, b[i].vsize, a[i].name, a[i].rva, a[i].vsize)
		}
	}
	return ""
}

type mergeContrib struct {
	path     string
	base     uintptr
	filled   int // bytes this input newly filled (primary: its total non-zero = seed)
	pages    int // 4 KiB pages this input newly filled (default page-granular mode)
	primary  bool
	crossBase bool
	took     []string // sections accepted from this input
	skipped  []string // sections skipped (base-dependent) — cross-base inputs only
	conflict string   // per-section conflict report
	rejected string   // non-empty => input was not merged, and why
}

func cmdMergeDumps(outFile string, inputs []string) {
	// Flags may appear anywhere after the output file.
	sameBaseOnly, force, wholeImage := false, false, false
	var files []string
	for _, a := range inputs {
		switch strings.ToLower(a) {
		case "-samebaseonly", "--samebaseonly":
			sameBaseOnly = true
		case "-force", "--force":
			force = true
		case "-wholeimage", "--wholeimage":
			wholeImage = true
		default:
			files = append(files, a)
		}
	}
	inputs = files

	// A single directory arg expands (recursively) to every *.dump.exe under it, so
	// per-state dumps in subfolders (dumps/menu/, dumps/match/, …) are all found.
	//
	// Two exclusions, both of which used to bite. The output file itself is skipped so a
	// re-merge into the same tree doesn't fold itself in — and so is any `merged*` file,
	// because a previous merge output is a DERIVED artifact, not a capture: folding it back
	// in adds no coverage and, if it sorted first, would seed the new image from spliced data.
	//
	// SEED CHOICE. With an explicit input list the first file is the seed (unchanged). On a
	// directory walk the seed is the best-covered input AT THE MOST COMMON ImageBase, which is
	// two deliberate constraints, not one:
	//
	//   * best-covered, because in the default `.text`-only mode the seed is the sole source of
	//     `.rdata`/`.data`, so the richest capture should supply them. Leaving this to
	//     directory-walk order is what silently made `dumps/loadout` the seed of the historical
	//     merged.dump.exe — nobody chose it, the alphabet did.
	//   * at the most common base, because the seed also supplies the output's ImageBase, and a
	//     good deal of this project's offline tooling hardcodes `IMAGEBASE = 0x7FF6AF000000`
	//     (tools/re/offline_xref.py, offline_disasm.py, fk13img.py, cheat_impl_census.py, …).
	//     Seeding from a differently-based capture would keep every `.text` byte correct and
	//     silently shift every absolute pointer those tools read out of `.rdata`/`.data` — a
	//     failure that produces plausible wrong RVAs rather than an error. Anchoring on the
	//     corpus plurality keeps the canonical image where the tooling already points.
	//
	// The chosen seed and its base are printed and recorded in the manifest either way.
	if len(inputs) == 1 {
		if fi, err := os.Stat(inputs[0]); err == nil && fi.IsDir() {
			oabs, _ := filepath.Abs(outFile)
			var found []string
			filepath.WalkDir(inputs[0], func(p string, d os.DirEntry, err error) error {
				if err != nil || d.IsDir() || !strings.HasSuffix(p, ".dump.exe") {
					return nil
				}
				if strings.HasPrefix(strings.ToLower(filepath.Base(p)), "merged") {
					return nil
				}
				if abs, _ := filepath.Abs(p); abs != oabs {
					found = append(found, p)
				}
				return nil
			})
			sort.Strings(found)
			if best := pickSeed(found); best > 0 {
				found[0], found[best] = found[best], found[0]
			}
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
	var relocNote string

	for _, in := range inputs {
		data, err := os.ReadFile(in)
		if err != nil {
			fmt.Printf("  skip %s: %v\n", in, err)
			continue
		}
		base, soi, secs, rRVA, rSize, ok := parseImageBufFull(data)
		if !ok {
			fmt.Printf("  skip %s: not a valid dumpimage PE\n", in)
			continue
		}
		if acc == nil {
			acc, accBase, accSize, accSecs = data, base, soi, secs
			seed := countNonZero(acc, 0, len(acc))
			contribs = append(contribs, mergeContrib{path: in, base: base, filled: seed, primary: true})
			fmt.Printf("  primary %s  base 0x%X  %.2f%% non-zero\n",
				filepath.Base(in), base, 100*float64(seed)/float64(len(acc)))

			perSec, byType, outside, nEnt, rok := relocTargetsPerSection(acc, rRVA, rSize, accSecs)
			if rok {
				var parts []string
				for _, s := range accSecs {
					parts = append(parts, fmt.Sprintf("%s=%d", s.name, perSec[s.name]))
				}
				relocNote = fmt.Sprintf("base relocations: %d non-ABSOLUTE entries (types %v, %d outside all sections)\n  per section: %s",
					nEnt, byType, outside, strings.Join(parts, " "))
				fmt.Printf("  %s\n", relocNote)
			}
			continue
		}
		if len(data) != len(acc) {
			fmt.Printf("  skip %s: size 0x%X != primary 0x%X\n", in, len(data), len(acc))
			contribs = append(contribs, mergeContrib{path: in, base: base,
				rejected: fmt.Sprintf("size 0x%X != primary 0x%X", len(data), len(acc))})
			continue
		}

		// The section table must match exactly — that, not ImageBase, is what proves the two
		// files describe the same build laid out identically.
		if mismatch := sectionsDiffer(accSecs, secs); mismatch != "" {
			fmt.Printf("  skip %s: section table differs (%s)\n", in, mismatch)
			contribs = append(contribs, mergeContrib{path: in, base: base,
				rejected: "section table differs: " + mismatch})
			continue
		}

		cross := base != accBase
		if cross && sameBaseOnly {
			fmt.Printf("  skip %s: ImageBase 0x%X != primary 0x%X (-samebaseonly)\n", in, base, accBase)
			contribs = append(contribs, mergeContrib{path: in, base: base, crossBase: true,
				rejected: fmt.Sprintf("ImageBase 0x%X != primary 0x%X (-samebaseonly)", base, accBase)})
			continue
		}

		// Decide which sections this input may contribute.
		var ranges []mergeSec
		var took, skipped []string
		if !wholeImage {
			// DEFAULT: .text only, from every donor, whatever its base. Everything else is
			// either base-dependent or measured to gain nothing, and keeping the seed's
			// .rdata/.data is what makes them a coherent single-process snapshot.
			for _, s := range accSecs {
				if s.name == ".text" {
					ranges = append(ranges, s)
					took = append(took, s.name)
				} else {
					skipped = append(skipped, s.name)
				}
			}
		} else if !cross {
			// Same base: the whole image, exactly as before (headers included).
			ranges = []mergeSec{{name: "<whole image>", rva: 0, vsize: uint32(len(acc))}}
			for _, s := range accSecs {
				took = append(took, s.name)
			}
		} else {
			perSec, _, outside, _, rok := relocTargetsPerSection(data, rRVA, rSize, secs)
			if !rok {
				fmt.Printf("  skip %s: cross-base input with unreadable relocation directory\n", in)
				contribs = append(contribs, mergeContrib{path: in, base: base, crossBase: true,
					rejected: "cross-base and its .reloc directory could not be parsed"})
				continue
			}
			if outside > 0 {
				fmt.Printf("  note %s: %d relocation entries fall outside every section\n", in, outside)
			}
			for _, s := range accSecs {
				if perSec[s.name] == 0 {
					ranges = append(ranges, s)
					took = append(took, s.name)
				} else {
					skipped = append(skipped, fmt.Sprintf("%s(%d relocs)", s.name, perSec[s.name]))
				}
			}
		}

		// Positive control: on every accepted range, count positions where both images are
		// non-zero and disagree. Base-independent read-only data must give 0.
		var confParts []string
		totalConf := 0
		for _, s := range accSecs {
			accepted := false
			for _, r := range ranges {
				if r.name == "<whole image>" || r.name == s.name {
					accepted = true
					break
				}
			}
			if !accepted {
				continue
			}
			c := conflicts(acc, data, int(s.rva), int(s.vsize))
			totalConf += c
			if c > 0 {
				confParts = append(confParts, fmt.Sprintf("%s=%d", s.name, c))
			}
		}
		conf := "0 (clean)"
		if len(confParts) > 0 {
			conf = strings.Join(confParts, " ")
		}

		// A donor that disagrees with the accumulator where both hold data has violated the
		// premise that licenses merging it at all. Reject rather than splice. (In -wholeimage
		// mode a SAME-base donor may legitimately disagree in writable .data, so the gate only
		// binds on cross-base donors there.)
		if totalConf > 0 && !force && (cross || !wholeImage) {
			fmt.Printf("  REJECT %s: donor disagrees with the accumulator on %d overlapping non-zero bytes (%s)\n",
				filepath.Base(in), totalConf, conf)
			fmt.Printf("         the sections merged here are supposed to be identical across dumps — not splicing it. Use -force to override.\n")
			contribs = append(contribs, mergeContrib{path: in, base: base, crossBase: cross,
				conflict: conf, took: took, skipped: skipped,
				rejected: fmt.Sprintf("%d conflicting overlapping bytes", totalConf)})
			continue
		}

		filled, pagesFilled := 0, 0
		for _, r := range ranges {
			end := int(r.rva) + int(r.vsize)
			if end > len(acc) {
				end = len(acc)
			}
			if wholeImage {
				// Legacy byte-granular fill.
				for i := int(r.rva); i < end; i++ {
					if acc[i] == 0 && data[i] != 0 {
						acc[i] = data[i]
						filled++
					}
				}
				continue
			}
			// DEFAULT: page-granular. A 4 KiB page is copied whole or not at all, so bytes
			// from two donors can never interleave inside one page. Demand-decrypt works at
			// page granularity, so this loses nothing: measured, no .text page is ever
			// partially populated (min 963 non-zero bytes on a live page, 0 pages under 256).
			for p := int(r.rva); p < end; p += mergePageSize {
				q := p + mergePageSize
				if q > end {
					q = end
				}
				accZero, dataZero := true, true
				for i := p; i < q; i++ {
					if acc[i] != 0 {
						accZero = false
						break
					}
				}
				if !accZero {
					continue
				}
				for i := p; i < q; i++ {
					if data[i] != 0 {
						dataZero = false
						break
					}
				}
				if dataZero {
					continue
				}
				copy(acc[p:q], data[p:q])
				pagesFilled++
				filled += countNonZero(acc, p, q-p)
			}
		}
		contribs = append(contribs, mergeContrib{path: in, base: base, filled: filled,
			pages: pagesFilled, crossBase: cross, took: took, skipped: skipped, conflict: conf})
		tag := fmt.Sprintf("  [%d pages; took %s; overlap conflicts %s]",
			pagesFilled, strings.Join(took, ","), conf)
		if wholeImage {
			tag = ""
			if cross {
				tag = fmt.Sprintf("  [cross-base 0x%X: took %s; skipped %s; overlap conflicts %s]",
					base, strings.Join(took, ","), strings.Join(skipped, ","), conf)
			}
		}
		fmt.Printf("  merged %s  +%d bytes (%.2f MB)%s\n",
			filepath.Base(in), filled, float64(filled)/(1024*1024), tag)
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

	mode := ".text-only, page-granular, ImageBase-agnostic (default)"
	if wholeImage {
		mode = "-wholeimage: whole-image byte fill; cross-base donors restricted to reloc-free sections (pre-S121 semantics)"
	}
	if sameBaseOnly {
		mode += " +(-samebaseonly: cross-base donors rejected outright)"
	}
	writeMergeManifest(outFile+".txt", outFile, accBase, accSize, acc, accSecs, contribs, relocNote, mode)
	fmt.Printf("  wrote %s\n", outFile+".txt")
}

func writeMergeManifest(path, outFile string, base uintptr, sizeOfImage uint32,
	acc []byte, secs []mergeSec, contribs []mergeContrib, relocNote, mode string) {
	var b strings.Builder
	fmt.Fprintf(&b, "usmapdump mergedumps manifest\n")
	fmt.Fprintf(&b, "generated : %s\n", time.Now().Format("2006-01-02 15:04:05"))
	fmt.Fprintf(&b, "output    : %s (%.1f MB)\n", filepath.Base(outFile), float64(len(acc))/(1024*1024))
	fmt.Fprintf(&b, "base      : 0x%X   SizeOfImage 0x%X\n", base, sizeOfImage)
	if relocNote != "" {
		fmt.Fprintf(&b, "%s\n", relocNote)
	}
	fmt.Fprintf(&b, "\n")

	fmt.Fprintf(&b, "%-44s %-14s %s\n", "INPUT", "BASE", "BYTES CONTRIBUTED")
	for _, c := range contribs {
		tag := ""
		if c.primary {
			tag = " (primary/seed)"
		}
		if c.rejected != "" {
			fmt.Fprintf(&b, "%-44s 0x%-12X REJECTED — %s\n", filepath.Base(c.path), c.base, c.rejected)
			continue
		}
		if !c.primary && c.pages > 0 {
			tag = fmt.Sprintf(" in %d pages%s", c.pages, tag)
		}
		fmt.Fprintf(&b, "%-44s 0x%-12X %d (%.2f MB)%s\n",
			filepath.Base(c.path), c.base, c.filled, float64(c.filled)/(1024*1024), tag)
	}

	fmt.Fprintf(&b, "\nMerged coverage — TWO DIFFERENT METRICS, do not compare them to each other:\n")
	fmt.Fprintf(&b, "  NON-ZERO BYTES : sound for .text only. Legally-zero bytes elsewhere read as gaps.\n")
	fmt.Fprintf(&b, "  ALL-ZERO PAGES : 4 KiB granularity. For .text an all-zero page == never executed,\n")
	fmt.Fprintf(&b, "                   so 'pages non-zero' is the honest readability proxy.\n\n")
	fmt.Fprintf(&b, "%-10s %-12s %-12s %-22s %-16s %s\n",
		"SECTION", "RVA", "VSIZE", "NON-ZERO BYTES", "PAGES", "PAGES NON-ZERO")
	for _, s := range secs {
		cov := countNonZero(acc, int(s.rva), int(s.vsize))
		zp, tp := countZeroPages(acc, int(s.rva), int(s.vsize))
		pct, ppct := 0.0, 0.0
		if s.vsize > 0 {
			pct = 100 * float64(cov) / float64(s.vsize)
		}
		if tp > 0 {
			ppct = 100 * float64(tp-zp) / float64(tp)
		}
		fmt.Fprintf(&b, "%-10s 0x%-10X 0x%-10X %-22s %-16d %d (%.2f%%)\n",
			s.name, s.rva, s.vsize,
			fmt.Sprintf("%d (%.1f%%)", cov, pct), tp, tp-zp, ppct)
	}
	total := countNonZero(acc, 0, len(acc))
	fmt.Fprintf(&b, "overall   : %d / %d non-zero bytes (%.2f%%)\n",
		total, len(acc), 100*float64(total)/float64(len(acc)))

	fmt.Fprintf(&b, "\nNOTES\n")
	fmt.Fprintf(&b, "- MODE: %s\n", mode)
	fmt.Fprintf(&b, "- .text (read-only, demand-decrypted) is the exact, authoritative part of this image,\n")
	fmt.Fprintf(&b, "  and it is the only section merging exists for. MEASURED: 0 of 1,403,750 base\n")
	fmt.Fprintf(&b, "  relocations target .text, and .text is byte-identical across every pair of dumps on\n")
	fmt.Fprintf(&b, "  every page both decrypted — including pairs at different ImageBases. ImageBase is\n")
	fmt.Fprintf(&b, "  therefore NOT a merge precondition for .text; an identical section table is.\n")
	fmt.Fprintf(&b, "- In the default .text-only mode, .rdata/.data/.pdata/.rsrc/... come from the SEED\n")
	fmt.Fprintf(&b, "  ALONE and are a coherent single-process snapshot. Merging them would gain nothing\n")
	fmt.Fprintf(&b, "  (measured: +0 non-zero pages from every donor, every section) and would splice\n")
	fmt.Fprintf(&b, "  writable globals from different sessions into values that never simultaneously\n")
	fmt.Fprintf(&b, "  existed. Under -wholeimage that splicing DOES happen — treat that image's .data as\n")
	fmt.Fprintf(&b, "  incoherent and seed-order-dependent.\n")
	fmt.Fprintf(&b, "- Output keeps the seed's ImageBase 0x%X, so project 'base+RVA' addresses map 1:1.\n", base)

	if err := os.WriteFile(path, []byte(b.String()), 0644); err != nil {
		fmt.Println("WARN: merge manifest write failed:", err)
	}
}

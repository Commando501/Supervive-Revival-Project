// dis.go — module string search + x86-64 disassembly + RIP-relative xref scanning.
//
// For the native missions/content unlock we must locate non-exported C++ functions
// (UAssetManager::ScanPrimaryAssetTypesFromConfig / ScanPathsForPrimaryAssets) in the
// runtime-unpacked module image. Strategy: find a distinctive string the function
// references (ASCII or UTF-16) in the module, then scan the module's executable sections
// for a RIP-relative instruction that addresses that string; the containing function is
// our target (or a caller of it). All reads are RPM (read-only).
package main

import (
	"fmt"
	"os"
	"strings"

	"golang.org/x/arch/x86/x86asm"
)

// safeDecode wraps x86asm.Decode, which can panic (avx.go) on some byte sequences when
// sliding over arbitrary (non-instruction-aligned) bytes. Treat a panic as "no valid
// instruction here".
func safeDecode(b []byte) (inst x86asm.Inst, ok bool) {
	defer func() {
		if recover() != nil {
			ok = false
		}
	}()
	in, err := x86asm.Decode(b, 64)
	if err != nil || in.Len == 0 {
		return x86asm.Inst{}, false
	}
	return in, true
}

// safeGoSyntax formats an instruction, guarding against formatter panics.
func safeGoSyntax(inst x86asm.Inst, ip uint64) (s string) {
	defer func() {
		if recover() != nil {
			s = "(unformattable)"
		}
	}()
	return x86asm.GoSyntax(inst, ip, nil)
}

// moduleSections returns the executable and rdata-ish ranges of the main module from the
// live PE headers.
func moduleSections(r *reader, base uintptr) (text []section, all []section) {
	pe, err := parsePE(r, base)
	if err != nil {
		fmt.Println("ERROR PE parse:", err)
		os.Exit(1)
	}
	for _, s := range pe.sections {
		all = append(all, s)
		if s.exec {
			text = append(text, s)
		}
	}
	return
}

// findStringsInModule scans the module image [base,base+size) for ASCII and UTF-16LE
// occurrences of substr. Returns absolute addresses where the (full) string starts.
func findStringsInModule(r *reader, base uintptr, size uint32, substr string) (ascii, utf16 []uintptr) {
	end := base + uintptr(size)
	const chunk = 8 << 20
	asciiPat := []byte(substr)
	// UTF-16LE pattern: each ascii byte followed by 0x00.
	u16 := make([]byte, 0, len(substr)*2)
	for i := 0; i < len(substr); i++ {
		u16 = append(u16, substr[i], 0)
	}
	for chunkBase := base; chunkBase < end; chunkBase += chunk {
		ce := chunkBase + chunk + uintptr(len(u16))
		if ce > end {
			ce = end
		}
		buf := make([]byte, ce-chunkBase)
		got, _ := r.read(chunkBase, buf)
		if got <= 0 {
			continue
		}
		buf = buf[:got]
		for i := 0; i+len(asciiPat) <= len(buf); i++ {
			if buf[i] == asciiPat[0] && string(buf[i:i+len(asciiPat)]) == substr {
				ascii = append(ascii, chunkBase+uintptr(i))
			}
		}
		for i := 0; i+len(u16) <= len(buf); i++ {
			if buf[i] == u16[0] && string(buf[i:i+len(u16)]) == string(u16) {
				utf16 = append(utf16, chunkBase+uintptr(i))
			}
		}
	}
	return
}

// findQwordInModule finds every 8-aligned position in module readable regions whose
// qword == val. Page-tolerant chunked reads.
func findQwordInModule(r *reader, regions []region, val uintptr) []uintptr {
	var out []uintptr
	const chunk = 16 << 20
	const page = 0x1000
	for _, s := range regions {
		for cb := s.base; cb < s.base+s.size; {
			want := uintptr(chunk)
			if cb+want > s.base+s.size {
				want = s.base + s.size - cb
			}
			buf := readRegionChunk(r, cb, want)
			if buf == nil {
				cb += page
				continue
			}
			for i := 0; i+8 <= len(buf); i += 8 {
				if u64(buf[i:]) == val {
					out = append(out, cb+uintptr(i))
				}
			}
			cb += uintptr(len(buf))
		}
	}
	return out
}

// readWideAt reads a UTF-16LE string of up to max chars at addr (for context display).
func readWideAt(r *reader, addr uintptr, max int) string {
	buf := make([]byte, max*2)
	r.read(addr, buf)
	var sb strings.Builder
	for i := 0; i+1 < len(buf); i += 2 {
		c := uint16(buf[i]) | uint16(buf[i+1])<<8
		if c == 0 {
			break
		}
		if c < 0x20 || c > 0x7e {
			sb.WriteByte('.')
		} else {
			sb.WriteByte(byte(c))
		}
	}
	return sb.String()
}

func readAsciiAt(r *reader, addr uintptr, max int) string {
	buf := make([]byte, max)
	r.read(addr, buf)
	var sb strings.Builder
	for _, c := range buf {
		if c == 0 {
			break
		}
		if c < 0x20 || c > 0x7e {
			sb.WriteByte('.')
		} else {
			sb.WriteByte(c)
		}
	}
	return sb.String()
}

// moduleRegions returns committed regions within [base,base+size). execOnly filters to
// executable protections. Uses live VirtualQueryEx (regions()) — robust to the packer's
// actual page protections, unlike nominal PE section bounds (whose start page may be
// unreadable, making a single section-wide RPM fail).
func moduleRegions(r *reader, base uintptr, size uint32, execOnly bool) []region {
	lo, hi := base, base+uintptr(size)
	var out []region
	for _, rg := range r.regions() {
		if rg.base+rg.size <= lo || rg.base >= hi {
			continue
		}
		if !readable(rg.protect) {
			continue
		}
		if execOnly {
			const anyExec = 0x10 | 0x20 | 0x40 | 0x80
			if rg.protect&anyExec == 0 {
				continue
			}
		}
		out = append(out, rg)
	}
	return out
}

// readRegion reads an entire region in page-tolerant chunks (skips unreadable sub-pages),
// returning the bytes and the base they start at. Short reads advance to the next page.
func readRegionChunk(r *reader, base uintptr, want uintptr) []byte {
	buf := make([]byte, want)
	got, _ := r.read(base, buf)
	if got <= 0 {
		return nil
	}
	return buf[:got]
}

// xrefsTo scans executable regions for RIP-relative instructions whose computed target ==
// addr. Sliding-window decode (every byte offset) so it can't desync. Page-tolerant reads.
func xrefsTo(r *reader, regions []region, addr uintptr) []uintptr {
	var out []uintptr
	seen := map[uintptr]bool{}
	var decoded, ripRefs uint64
	defer func() {
		fmt.Fprintf(os.Stderr, "    [xrefsTo diag] target=0x%X decodedInsts=%d ripMemRefsSeen=%d found=%d\n", addr, decoded, ripRefs, len(out))
	}()
	const chunk = 16 << 20
	const overlap = 16
	const page = 0x1000
	for _, s := range regions {
		for cb := s.base; cb < s.base+s.size; {
			want := uintptr(chunk + overlap)
			if cb+want > s.base+s.size {
				want = s.base + s.size - cb
			}
			buf := readRegionChunk(r, cb, want)
			if buf == nil {
				cb += page // unreadable page; skip
				continue
			}
			limit := len(buf) - overlap
			if cb+uintptr(len(buf)) >= s.base+s.size {
				limit = len(buf)
			}
			for i := 0; i < limit; i++ {
				inst, ok := safeDecode(buf[i:])
				if !ok {
					continue
				}
				decoded++
				ip := cb + uintptr(i)
				for _, a := range inst.Args {
					if a == nil {
						break
					}
					if m, ok := a.(x86asm.Mem); ok && m.Base == x86asm.RIP {
						ripRefs++
						if ip+uintptr(inst.Len)+uintptr(int64(m.Disp)) == addr && !seen[ip] {
							seen[ip] = true
							out = append(out, ip)
						}
					}
				}
			}
			cb += uintptr(len(buf)) - overlap
			if uintptr(len(buf)) <= overlap {
				cb += page
			}
		}
	}
	return out
}

// isPrologue reports whether b starts with a recognizable x64 function prologue (MSVC).
func isPrologue(b []byte) bool {
	if len(b) < 4 {
		return false
	}
	// mov [rsp+disp8], reg : 48/4C 89 (44|4C|54|5C|74|7C) 24 disp8
	if (b[0] == 0x48 || b[0] == 0x4C) && b[1] == 0x89 && b[3] == 0x24 {
		switch b[2] & 0xC7 {
		case 0x44, 0x4C, 0x54, 0x5C, 0x64, 0x6C, 0x74, 0x7C:
			return true
		}
	}
	// sub rsp, imm8 : 48 83 EC xx ; sub rsp, imm32 : 48 81 EC ....
	if b[0] == 0x48 && b[1] == 0x83 && b[2] == 0xEC {
		return true
	}
	if b[0] == 0x48 && b[1] == 0x81 && b[2] == 0xEC {
		return true
	}
	// mov r11, rsp : 4C 8B DC  (MSVC frame)
	if b[0] == 0x4C && b[1] == 0x8B && b[2] == 0xDC {
		return true
	}
	// mov rax, rsp : 48 8B C4
	if b[0] == 0x48 && b[1] == 0x8B && b[2] == 0xC4 {
		return true
	}
	// push rbx/rbp/rsi/rdi/r1x then ... : optional REX 0x40/0x41 + 0x53..0x57
	i := 0
	if b[0] == 0x40 || b[0] == 0x41 || b[0] == 0x53 {
		// count a short run of push reg
		pushes := 0
		for i < len(b) && pushes < 6 {
			if b[i] == 0x41 && i+1 < len(b) && b[i+1] >= 0x50 && b[i+1] <= 0x57 {
				i += 2
				pushes++
			} else if b[i] >= 0x53 && b[i] <= 0x57 {
				i++
				pushes++
			} else if b[i] == 0x40 && i+1 < len(b) && b[i+1] >= 0x50 && b[i+1] <= 0x57 {
				i += 2
				pushes++
			} else {
				break
			}
		}
		if pushes > 0 && i+2 < len(b) {
			// followed by sub rsp / mov rbp,rsp / lea rbp
			if b[i] == 0x48 && (b[i+1] == 0x83 || b[i+1] == 0x81) && b[i+2] == 0xEC {
				return true
			}
			if b[i] == 0x48 && b[i+1] == 0x8B && (b[i+2] == 0xEC || b[i+2] == 0xE9) {
				return true
			}
			if b[i] == 0x48 && b[i+1] == 0x8D { // lea rbp,[rsp+x]
				return true
			}
			return true // standalone push-chain entry (leaf-ish)
		}
	}
	return false
}

// funcStartBefore walks backward from ip to find the function entry: the nearest address
// <= ip that (a) is preceded by int3 (0xCC) padding and (b) begins with a recognizable
// prologue. MSVC/PGO splits functions into int3-padded blocks, so we require a real
// prologue (not just any int3 boundary) and pick the closest one at/below ip.
func funcStartBefore(r *reader, ip uintptr) uintptr {
	const back = 0x4000
	lo := ip - back
	buf := make([]byte, back+16)
	r.read(lo, buf)
	best := uintptr(0)
	for i := 1; i < int(back); i++ {
		if buf[i-1] == 0xCC && buf[i] != 0xCC && isPrologue(buf[i:]) {
			cand := lo + uintptr(i)
			if cand <= ip {
				best = cand // keep the closest (largest) prologue <= ip
			}
		}
	}
	return best
}

// disasmRange prints n bytes of disassembly starting at addr (absolute). Annotates
// call/jmp targets and rip-relative loads with the absolute target.
func disasmRange(r *reader, addr uintptr, n int) {
	buf := make([]byte, n)
	got, _ := r.read(addr, buf)
	buf = buf[:got]
	for i := 0; i < len(buf); {
		inst, ok := safeDecode(buf[i:])
		ip := addr + uintptr(i)
		if !ok {
			fmt.Printf("    0x%X:  (bad) %02X\n", ip, buf[i])
			i++
			continue
		}
		txt := safeGoSyntax(inst, uint64(ip))
		annot := ""
		// resolve rel call/jmp + rip-relative
		for _, a := range inst.Args {
			if a == nil {
				break
			}
			if rel, ok := a.(x86asm.Rel); ok {
				tgt := ip + uintptr(inst.Len) + uintptr(int64(rel))
				annot = fmt.Sprintf("  -> 0x%X", tgt)
			}
			if m, ok := a.(x86asm.Mem); ok && m.Base == x86asm.RIP {
				tgt := ip + uintptr(inst.Len) + uintptr(int64(m.Disp))
				annot = fmt.Sprintf("  [rip]->0x%X", tgt)
			}
		}
		fmt.Printf("    0x%X:  %-36s%s\n", ip, txt, annot)
		i += inst.Len
		if inst.Op == x86asm.RET || inst.Op == x86asm.INT {
			// stop at a clean ret followed by padding
		}
	}
}

// cmdXref: find code references to an absolute address (e.g. a string literal), report
// the containing function start, and disassemble it. Usage:
//   usmapdump xref <proc> <hexAddrOrRVA>
// If the value is < module size it's treated as an RVA; otherwise an absolute address.
func cmdXref(name, hexv string) {
	r, pid, base, size := mustOpen(name)
	defer procCloseHandle.Call(r.h)
	v := parseHex(hexv)
	addr := v
	if v < uintptr(size) {
		addr = base + v
	}
	fmt.Printf("PID %d %q base=0x%X  xref target=0x%X (rva 0x%X)\n", pid, name, base, addr, addr-base)
	fmt.Printf("  target bytes: %q\n", readAsciiAt(r, addr, 48))
	execRegs := moduleRegions(r, base, size, true)
	readRegs := moduleRegions(r, base, size, false)
	for _, s := range execRegs {
		fmt.Printf("    exec region vaddr=0x%X size=0x%X prot=0x%X\n", s.base, s.size, s.protect)
	}
	fmt.Printf("  scanning %d exec regions for rip-relative refs to the string...\n", len(execRegs))
	refs := xrefsTo(r, execRegs, addr)
	if len(refs) == 0 {
		// Fallback: the string is referenced indirectly via an 8-byte pointer in data.
		// Find every qword in the module equal to addr, then xref those pointer SLOTS.
		fmt.Println("  no direct refs; searching module data for an 8-byte POINTER to the string...")
		ptrSlots := findQwordInModule(r, readRegs, addr)
		fmt.Printf("  %d pointer slot(s) hold 0x%X:\n", len(ptrSlots), addr)
		for _, ps := range ptrSlots {
			fmt.Printf("    slot@0x%X (rva 0x%X)\n", ps, ps-base)
		}
		for _, ps := range ptrSlots {
			rr := xrefsTo(r, execRegs, ps)
			fmt.Printf("    -> %d code ref(s) to slot 0x%X\n", len(rr), ps)
			refs = append(refs, rr...)
		}
	}
	fmt.Printf("  %d total xref(s):\n", len(refs))
	for i, ip := range refs {
		fs := funcStartBefore(r, ip)
		fmt.Printf("\n  [%d] ref@0x%X (rva 0x%X)  funcStart=0x%X (rva 0x%X)\n", i, ip, ip-base, fs, fs-base)
		if fs != 0 {
			disasmRange(r, fs, 0x140)
		}
		if i >= 6 {
			fmt.Printf("  ...(+%d more refs)\n", len(refs)-i-1)
			break
		}
	}
}

// cmdPeek dumps 0x40 bytes at an absolute address as qwords + the low int32s. Usage:
// usmapdump peek <proc> <absHex>
func cmdPeek(name, hexv string) {
	r, pid, base, _ := mustOpen(name)
	defer procCloseHandle.Call(r.h)
	addr := parseHex(hexv)
	fmt.Printf("PID %d base=0x%X peek @0x%X\n", pid, base, addr)
	buf := make([]byte, 0x40)
	got, _ := r.read(addr, buf)
	buf = buf[:got]
	for off := 0; off+8 <= len(buf); off += 8 {
		v := u64(buf[off:])
		fmt.Printf("    +0x%02X = 0x%-16X  (i32 lo=%d hi=%d)\n", off, v, int32(u32le(buf[off:])), int32(u32le(buf[off+4:])))
	}
}

// cmdDisasm disassembles 0x200 bytes at an address/RVA. Usage: usmapdump disasm <proc> <hex>
func cmdDisasm(name, hexv string) {
	r, pid, base, size := mustOpen(name)
	defer procCloseHandle.Call(r.h)
	v := parseHex(hexv)
	addr := v
	if v < uintptr(size) {
		addr = base + v
	}
	fmt.Printf("PID %d %q base=0x%X  disasm @0x%X (rva 0x%X)\n", pid, name, base, addr, addr-base)
	disasmRange(r, addr, 0x200)
}

func parseHex(s string) uintptr {
	s = strings.TrimPrefix(strings.TrimPrefix(s, "0x"), "0X")
	var v uintptr
	for _, c := range s {
		var d uintptr
		switch {
		case c >= '0' && c <= '9':
			d = uintptr(c - '0')
		case c >= 'a' && c <= 'f':
			d = uintptr(c-'a') + 10
		case c >= 'A' && c <= 'F':
			d = uintptr(c-'A') + 10
		default:
			continue
		}
		v = v<<4 | d
	}
	return v
}

// cmdWStrings lists wide (UTF-16) + ascii strings (>=6 printable chars) in a window
// [base+rva, +len]. Usage: usmapdump wstrings <proc> <rvaHex> <lenHex>
func cmdWStrings(name, rvaHex, lenHex string) {
	r, pid, base, size := mustOpen(name)
	defer procCloseHandle.Call(r.h)
	_ = size
	rva := parseHex(rvaHex)
	ln := parseHex(lenHex)
	start := base + rva
	buf := make([]byte, ln)
	got, _ := r.read(start, buf)
	buf = buf[:got]
	fmt.Printf("PID %d base=0x%X window rva=0x%X len=0x%X read=%d\n", pid, base, rva, ln, got)
	// wide strings
	fmt.Println("  -- UTF-16 strings --")
	i := 0
	for i+1 < len(buf) {
		// detect a run of ascii-range wide chars
		j := i
		var sb []byte
		for j+1 < len(buf) {
			c := uint16(buf[j]) | uint16(buf[j+1])<<8
			if c >= 0x20 && c <= 0x7e {
				sb = append(sb, byte(c))
				j += 2
			} else {
				break
			}
		}
		if len(sb) >= 6 {
			fmt.Printf("    0x%X (rva 0x%X)  %q\n", start+uintptr(i), rva+uintptr(i), string(sb))
			i = j + 2
		} else {
			i += 2
		}
	}
}

// cmdStrings: discovery — find a substring in the module image (ascii+utf16) and print
// matches with context. Usage: usmapdump strings <proc> <substr>
func cmdStrings(name, substr string) {
	r, pid, base, size := mustOpen(name)
	defer procCloseHandle.Call(r.h)
	fmt.Printf("PID %d %q base=0x%X size=0x%X  searching %q\n", pid, name, base, size, substr)
	ascii, utf16 := findStringsInModule(r, base, size, substr)
	fmt.Printf("  ASCII matches: %d\n", len(ascii))
	for i, a := range ascii {
		if i >= 40 {
			fmt.Printf("    ...(+%d more)\n", len(ascii)-40)
			break
		}
		fmt.Printf("    0x%X (rva 0x%X)  %q\n", a, a-base, readAsciiAt(r, a, 80))
	}
	fmt.Printf("  UTF-16 matches: %d\n", len(utf16))
	for i, a := range utf16 {
		if i >= 40 {
			fmt.Printf("    ...(+%d more)\n", len(utf16)-40)
			break
		}
		fmt.Printf("    0x%X (rva 0x%X)  %q\n", a, a-base, readWideAt(r, a, 80))
	}
}

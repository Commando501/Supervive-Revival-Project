// strings.go — needle search across the live process's committed memory.
//
// The shipping exe and runtime.dll are heavily packed (sections named packer0,
// packer1, ..., packer42 — confirmed via on-disk PE recon). Standard UE log
// strings ("Couldn't find pak signature file", "LogPakFile", etc.) are NOT
// present in the on-disk image; they only exist in unpacked private memory at
// runtime. This subcommand lets us find them externally via ReadProcessMemory.
//
// Usage:
//   usmapdump strings  <proc-or-pid> <needle>  [maxhits]   # ANSI bytes
//   usmapdump wstrings <proc-or-pid> <needle>  [maxhits]   # UTF-16 LE
//   usmapdump xrefstr  <proc-or-pid> <hexAddr> [maxhits]   # find code that
//                                                          # mov reg, <addr>
//                                                          # (rip-rel LEA)
//
// Output: for each hit, the virtual address + a short context dump so the
// operator can confirm it's the right string instance.

package main

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"os"
	"strconv"
	"strings"
)

// scanRegions yields every committed, readable region we should search through.
// Excludes guard pages. Includes both module-image and private memory — strings
// can live in either.
func (r *reader) scanRegions() []region {
	var out []region
	for _, rg := range r.regions() {
		if !readable(rg.protect) {
			continue
		}
		out = append(out, rg)
	}
	return out
}

// scanForNeedle reads each region in chunks and reports up to maxhits
// addresses where the needle is found. Chunks overlap by len(needle)-1 to
// avoid missing a hit straddling a chunk boundary.
func scanForNeedle(r *reader, needle []byte, maxhits int) []uintptr {
	const chunk = 1 << 20
	overlap := len(needle) - 1
	if overlap < 0 {
		overlap = 0
	}
	var hits []uintptr
	for _, rg := range r.scanRegions() {
		// Carve into overlapping chunks.
		for base := rg.base; base < rg.base+rg.size; base += chunk - uintptr(overlap) {
			n := chunk
			if uintptr(n) > rg.base+rg.size-base {
				n = int(rg.base + rg.size - base)
			}
			if n <= 0 {
				break
			}
			buf := make([]byte, n)
			got, _ := r.read(base, buf)
			if got <= 0 {
				continue
			}
			buf = buf[:got]
			start := 0
			for {
				idx := bytes.Index(buf[start:], needle)
				if idx < 0 {
					break
				}
				hits = append(hits, base+uintptr(start+idx))
				if len(hits) >= maxhits {
					return hits
				}
				start = start + idx + 1
			}
		}
	}
	return hits
}

// dumpContext reads bytes around addr and prints a hex+ASCII view, then both
// ASCII and UTF-16-decoded interpretations of what's there. Useful for sanity-
// checking that a hit is actually the string we wanted (not a fragment matching
// a longer string somewhere else, etc.).
func dumpContext(r *reader, addr uintptr, lead, total int) {
	// If the leading region isn't readable (different mapping ahead of addr),
	// fall back to reading from addr itself with no lead.
	start := addr
	actualLead := 0
	if uintptr(lead) <= addr {
		start = addr - uintptr(lead)
		actualLead = lead
	}
	buf := make([]byte, total)
	got, _ := r.read(start, buf)
	// If the leading region is unreadable (got==0) retry from addr itself.
	if got == 0 && start != addr {
		start = addr
		actualLead = 0
		got, _ = r.read(start, buf)
	}
	buf = buf[:got]
	fmt.Printf("    @0x%X (start=0x%X, %d bytes):\n", addr, start, got)
	for off := 0; off < got; off += 16 {
		end := off + 16
		if end > got {
			end = got
		}
		hex := ""
		asc := ""
		for i := off; i < end; i++ {
			hex += fmt.Sprintf("%02X ", buf[i])
			if buf[i] >= 0x20 && buf[i] < 0x7f {
				asc += string(buf[i])
			} else {
				asc += "."
			}
		}
		// Pad short last row so columns line up.
		for len(hex) < 48 {
			hex += "   "
		}
		fmt.Printf("    %08X  %s %s\n", uintptr(start)+uintptr(off), hex, asc)
	}
	// Decode the area starting at addr as UTF-16, helpful when the hit is a wide string.
	if actualLead > len(buf) {
		return
	}
	wbuf := buf[actualLead:]
	if len(wbuf) >= 2 {
		var sb strings.Builder
		for i := 0; i+1 < len(wbuf) && i < 128; i += 2 {
			c := uint16(wbuf[i]) | uint16(wbuf[i+1])<<8
			if c == 0 {
				break
			}
			if c >= 0x20 && c < 0x7f {
				sb.WriteRune(rune(c))
			} else {
				sb.WriteRune('.')
			}
		}
		fmt.Printf("    utf-16: %q\n", sb.String())
	}
}

func cmdStrings(proc, needle string, maxhits int, wide bool) {
	r, pid, base, size := mustOpen(proc)
	defer procCloseHandle.Call(r.h)
	fmt.Printf("PID %d  %q base=0x%X size=0x%X\n", pid, proc, base, size)

	var nb []byte
	if wide {
		nb = make([]byte, 0, len(needle)*2)
		for _, c := range needle {
			nb = append(nb, byte(c), byte(c>>8))
		}
		fmt.Printf("  searching UTF-16 LE needle %q (%d bytes)\n", needle, len(nb))
	} else {
		nb = []byte(needle)
		fmt.Printf("  searching ANSI needle %q (%d bytes)\n", needle, len(nb))
	}
	hits := scanForNeedle(r, nb, maxhits)
	fmt.Printf("  found %d hit(s):\n", len(hits))
	for _, h := range hits {
		dumpContext(r, h, 8, 80)
		// Module-RVA if it's inside the main exe.
		if h >= base && h < base+uintptr(size) {
			fmt.Printf("      mod-RVA: 0x%X\n", h-base)
		} else {
			fmt.Printf("      (outside main module)\n")
		}
	}
}

// xrefstr — find every place in executable memory that LOADS the address `target`
// via a 7-byte `lea reg, [rip+disp32]` instruction (the standard UE pattern for
// string literal references). Reports the code address + decoded LEA. Use this
// AFTER you have a string address from `strings`/`wstrings` to locate callers.
//
// Pattern: 48|4C 8D <reg|imm> <disp32>. We just scan executable regions for the
// 7-byte LEA whose computed RIP-relative target == `target`.
func cmdXrefStr(proc string, target uintptr, maxhits int) {
	r, pid, base, size := mustOpen(proc)
	defer procCloseHandle.Call(r.h)
	fmt.Printf("PID %d  %q base=0x%X size=0x%X\n", pid, proc, base, size)
	fmt.Printf("  searching exec memory for rip-rel LEA targeting 0x%X\n", target)

	const chunk = 1 << 20
	var hits []uintptr
	for _, rg := range r.regions() {
		if rg.protect&pageGuard != 0 {
			continue
		}
		// Only executable regions can hold instructions.
		if rg.protect&(pageExecuteRead|pageExecuteRW|pageExecuteWC) == 0 {
			continue
		}
		for off := uintptr(0); off < rg.size; off += chunk {
			n := chunk + 7
			if off+uintptr(n) > rg.size {
				n = int(rg.size - off)
			}
			if n < 7 {
				break
			}
			buf := make([]byte, n)
			got, _ := r.read(rg.base+off, buf)
			if got < 7 {
				continue
			}
			// scan
			for i := 0; i <= got-7; i++ {
				// REX.W (0x48 or 0x4C) + 0x8D = LEA r64,[mem]; modr/m must be RIP-relative
				// (mod=00, rm=101 → modr/m byte ends in 0x05 with reg field in middle).
				if (buf[i] != 0x48 && buf[i] != 0x4C) || buf[i+1] != 0x8D {
					continue
				}
				modrm := buf[i+2]
				if modrm&0xC7 != 0x05 {
					continue
				}
				disp := int32(binary.LittleEndian.Uint32(buf[i+3 : i+7]))
				rip := rg.base + off + uintptr(i) + 7 // address of next instr
				tgt := uintptr(int64(rip) + int64(disp))
				if tgt == target {
					hits = append(hits, rg.base+off+uintptr(i))
					if len(hits) >= maxhits {
						break
					}
				}
			}
			if len(hits) >= maxhits {
				break
			}
		}
		if len(hits) >= maxhits {
			break
		}
	}
	fmt.Printf("  %d hit(s):\n", len(hits))
	for _, h := range hits {
		buf := make([]byte, 16)
		r.read(h, buf)
		fmt.Printf("    @0x%X   bytes: % X", h, buf[:7])
		if h >= base && h < base+uintptr(size) {
			fmt.Printf("    mod-RVA: 0x%X", h-base)
		}
		fmt.Println()
	}
}

// cmdCallXref — find every direct CALL (E8 disp32) and JMP (E9 disp32)
// instruction whose target == `target`. Use this to find callers of a function
// whose entry RVA you already know.
//
// Note: misses indirect calls through vtables — pair with xrefstr/findptr on
// the entry address to cover those.
func cmdCallXref(proc string, target uintptr, maxhits int) {
	r, pid, base, size := mustOpen(proc)
	defer procCloseHandle.Call(r.h)
	fmt.Printf("PID %d  %q base=0x%X size=0x%X\n", pid, proc, base, size)
	fmt.Printf("  searching exec memory for E8/E9 disp32 calling 0x%X\n", target)

	const chunk = 1 << 20
	var hits []uintptr
	for _, rg := range r.regions() {
		if rg.protect&pageGuard != 0 {
			continue
		}
		if rg.protect&(pageExecuteRead|pageExecuteRW|pageExecuteWC) == 0 {
			continue
		}
		for off := uintptr(0); off < rg.size; off += chunk {
			n := chunk + 5
			if off+uintptr(n) > rg.size {
				n = int(rg.size - off)
			}
			if n < 5 {
				break
			}
			buf := make([]byte, n)
			got, _ := r.read(rg.base+off, buf)
			if got < 5 {
				continue
			}
			for i := 0; i <= got-5; i++ {
				b := buf[i]
				if b != 0xE8 && b != 0xE9 {
					continue
				}
				disp := int32(uint32(buf[i+1]) | uint32(buf[i+2])<<8 | uint32(buf[i+3])<<16 | uint32(buf[i+4])<<24)
				rip := rg.base + off + uintptr(i) + 5
				tgt := uintptr(int64(rip) + int64(disp))
				if tgt == target {
					hits = append(hits, rg.base+off+uintptr(i))
					if len(hits) >= maxhits {
						break
					}
				}
			}
			if len(hits) >= maxhits {
				break
			}
		}
		if len(hits) >= maxhits {
			break
		}
	}
	fmt.Printf("  %d hit(s):\n", len(hits))
	for _, h := range hits {
		buf := make([]byte, 5)
		r.read(h, buf)
		kind := "CALL"
		if buf[0] == 0xE9 {
			kind = "JMP"
		}
		mod := ""
		if h >= base && h < base+uintptr(size) {
			mod = fmt.Sprintf("    mod-RVA: 0x%X", h-base)
		}
		fmt.Printf("    @0x%X   %s  bytes: % X%s\n", h, kind, buf, mod)
	}
}

// cmdFindPtr — scan readable memory for any qword that equals `target`. Used to
// locate pointer-table slots that hold the address of a string literal (UE's
// __wstring__ pattern: `.rdata` slot holds the address, code does
// `lea rcx, [rip+disp]; mov rcx, [rcx]` to load the actual string ptr).
//
// Once such a slot is found, follow up with `xrefstr` against the slot's address
// to find the code that loads the slot.
func cmdFindPtr(proc string, target uintptr, maxhits int) {
	r, pid, base, size := mustOpen(proc)
	defer procCloseHandle.Call(r.h)
	fmt.Printf("PID %d  %q base=0x%X size=0x%X\n", pid, proc, base, size)
	fmt.Printf("  searching readable memory for qwords == 0x%X\n", target)

	tgt := make([]byte, 8)
	binary.LittleEndian.PutUint64(tgt, uint64(target))
	hits := scanForNeedle(r, tgt, maxhits)
	fmt.Printf("  %d hit(s) (8-byte aligned only — pointer tables are always aligned):\n", len(hits))
	for _, h := range hits {
		if h%8 != 0 {
			fmt.Printf("    @0x%X   (unaligned, skipped — likely false match in larger blob)\n", h)
			continue
		}
		buf := make([]byte, 32)
		r.read(h, buf)
		mod := ""
		if h >= base && h < base+uintptr(size) {
			mod = fmt.Sprintf("    mod-RVA: 0x%X", h-base)
		}
		fmt.Printf("    @0x%X   bytes: % X%s\n", h, buf[:24], mod)
	}
}

// parseHex accepts "0x1234" or "1234" (hex) and returns the uintptr.
func parseHex(s string) (uintptr, error) {
	s = strings.TrimPrefix(strings.TrimPrefix(s, "0x"), "0X")
	v, err := strconv.ParseUint(s, 16, 64)
	return uintptr(v), err
}

// parseMaxHits picks an optional maxhits arg; defaults to 20.
func parseMaxHits(args []string, idx, def int) int {
	if len(args) <= idx {
		return def
	}
	v, err := strconv.Atoi(args[idx])
	if err != nil || v <= 0 {
		fmt.Fprintf(os.Stderr, "  bad maxhits %q; using default %d\n", args[idx], def)
		return def
	}
	return v
}

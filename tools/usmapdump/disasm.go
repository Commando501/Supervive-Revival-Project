// disasm.go — x86-64 disassembly + peek for live process memory.
//
// Used to inspect call sites identified via xrefstr/findptr — we want to see
// the conditional branches before/after a UE_LOG call so we can identify a
// bypass flag (e.g., a bool the signature-check function reads to decide
// whether to skip validation).
//
// Usage:
//   usmapdump peek    <proc-or-pid> 0xADDR_OR_RVA [bytes]   # hex+ascii dump
//   usmapdump disasm  <proc-or-pid> 0xADDR_OR_RVA [bytes]   # x86-64 disasm
//
// ADDR_OR_RVA: an absolute VA (e.g., 0x7FF66171836D) or a module-relative
// offset starting with '+' (e.g., +0x204836D). Mod-RVAs are resolved against
// the main module's load base.

package main

import (
	"fmt"
	"strings"

	"golang.org/x/arch/x86/x86asm"
)

// resolveAddr returns an absolute VA given either a raw hex address or a
// "+offset" mod-RVA. Loads the main module base for the RVA case.
func resolveAddr(proc, s string) (uintptr, error) {
	if strings.HasPrefix(s, "+") {
		off, err := parseHex(s[1:])
		if err != nil {
			return 0, err
		}
		pid, err := findPID(proc)
		if err != nil {
			return 0, err
		}
		base, _, err := moduleBaseSize(pid, proc)
		if err != nil {
			return 0, err
		}
		return base + off, nil
	}
	return parseHex(s)
}

func cmdPeek(proc, addrStr string, nBytes int) {
	r, pid, base, size := mustOpen(proc)
	defer procCloseHandle.Call(r.h)

	addr, err := resolveAddr(proc, addrStr)
	if err != nil {
		fmt.Println("ERROR: bad address:", err)
		return
	}
	fmt.Printf("PID %d  base=0x%X size=0x%X   reading 0x%X +%d bytes\n", pid, base, size, addr, nBytes)
	buf := make([]byte, nBytes)
	got, _ := r.read(addr, buf)
	buf = buf[:got]
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
		for len(hex) < 48 {
			hex += "   "
		}
		fmt.Printf("  %X  %s %s\n", addr+uintptr(off), hex, asc)
	}
}

func cmdDisasm(proc, addrStr string, nBytes int) {
	r, pid, base, size := mustOpen(proc)
	defer procCloseHandle.Call(r.h)

	addr, err := resolveAddr(proc, addrStr)
	if err != nil {
		fmt.Println("ERROR: bad address:", err)
		return
	}
	fmt.Printf("PID %d  base=0x%X size=0x%X   disassembling 0x%X +%d bytes\n", pid, base, size, addr, nBytes)

	buf := make([]byte, nBytes)
	got, _ := r.read(addr, buf)
	buf = buf[:got]
	pc := uintptr(0)
	for pc < uintptr(len(buf)) {
		inst, err := x86asm.Decode(buf[pc:], 64)
		va := addr + pc
		modRVA := ""
		if va >= base && va < base+uintptr(size) {
			modRVA = fmt.Sprintf("  [+0x%X]", va-base)
		}
		if err != nil {
			fmt.Printf("  %X  %02X    <decode-err: %v>%s\n", va, buf[pc], err, modRVA)
			pc++
			continue
		}
		bs := buf[pc : pc+uintptr(inst.Len)]
		hex := ""
		for _, b := range bs {
			hex += fmt.Sprintf("%02X ", b)
		}
		for len(hex) < 24 {
			hex += "   "
		}
		// Use Intel syntax for readability.
		text := x86asm.IntelSyntax(inst, uint64(va), nil)
		fmt.Printf("  %X  %s  %s%s\n", va, hex, text, modRVA)
		pc += uintptr(inst.Len)
	}
}

// deobfimports.go — reconstruct imports for a VMProtect/Themida-style IMPORT-PROTECTED
// dump (SUPERVIVE). Unlike an unprotected binary (explorer), SUPERVIVE's IAT slots do NOT
// hold real export addresses — they point to obfuscated TRAMPOLINES in a packer-hidden
// region (not a registered module, so `reconstructiat`'s sidecar lookup misses them).
//
// Each trampoline computes the real API address at runtime and jmps to it, e.g.:
//     push rax
//     mov  rax, C1                 ; per-stub imm64
//     add  rax, [rip+disp]         ; + M (a per-launch data qword in the packer region)
//     rol  rax, 0x33
//     mov  r11, C2                 ; per-stub imm64
//     xor  r11, rax
//     pop  rax
//     jmp  r11                     ; -> real API
// So real = C2 ^ ROL64(C1 + M, 0x33). We recover it by EMULATING the stub rather than
// pattern-matching, so any obfuscation variant (different ops/rotates/junk) still resolves.
// Every recovered target is VERIFIED against the exports sidecar (exact address match), so a
// mis-emulated stub can only ever produce "unresolved", never a wrong name.
//
// Requires the SOURCE process alive (the stub code + its M data are read live; M is
// per-launch because it encodes the ASLR-relocated target). The exports sidecar
// (dumpimage's <stem>.exports.txt) supplies address->name for the real system DLLs.
package main

import (
	"encoding/binary"
	"fmt"
	"math/bits"
	"os"
	"path/filepath"

	"golang.org/x/arch/x86/x86asm"
)

// canonical 0..15 GPR index for 64- and 32-bit registers (sub-registers unused by these
// stubs). bits is 64 or 32; a 32-bit write zero-extends, matching x86 semantics.
var reg64 = map[x86asm.Reg]int{
	x86asm.RAX: 0, x86asm.RCX: 1, x86asm.RDX: 2, x86asm.RBX: 3,
	x86asm.RSP: 4, x86asm.RBP: 5, x86asm.RSI: 6, x86asm.RDI: 7,
	x86asm.R8: 8, x86asm.R9: 9, x86asm.R10: 10, x86asm.R11: 11,
	x86asm.R12: 12, x86asm.R13: 13, x86asm.R14: 14, x86asm.R15: 15,
}
var reg32 = map[x86asm.Reg]int{
	x86asm.EAX: 0, x86asm.ECX: 1, x86asm.EDX: 2, x86asm.EBX: 3,
	x86asm.ESP: 4, x86asm.EBP: 5, x86asm.ESI: 6, x86asm.EDI: 7,
	x86asm.R8L: 8, x86asm.R9L: 9, x86asm.R10L: 10, x86asm.R11L: 11,
	x86asm.R12L: 12, x86asm.R13L: 13, x86asm.R14L: 14, x86asm.R15L: 15,
}

func canonReg(r x86asm.Reg) (idx, width int, ok bool) {
	if i, k := reg64[r]; k {
		return i, 64, true
	}
	if i, k := reg32[r]; k {
		return i, 32, true
	}
	return 0, 0, false
}

// emu is a tiny straight-line integer machine — enough to run these arithmetic trampolines.
type emu struct {
	r     *reader
	regs  [16]uint64
	stack []uint64
}

func (e *emu) effAddr(m x86asm.Mem, nextRIP uintptr) (uintptr, bool) {
	var base uint64
	switch {
	case m.Base == x86asm.RIP:
		base = uint64(nextRIP)
	case m.Base != 0:
		i, _, ok := canonReg(m.Base)
		if !ok {
			return 0, false
		}
		base = e.regs[i]
	}
	var index uint64
	if m.Index != 0 {
		i, _, ok := canonReg(m.Index)
		if !ok {
			return 0, false
		}
		index = e.regs[i] * uint64(m.Scale)
	}
	return uintptr(base + index + uint64(m.Disp)), true
}

func (e *emu) readMem(addr uintptr) (uint64, bool) {
	var b [8]byte
	if n, _ := e.r.read(addr, b[:]); n < 8 {
		return 0, false
	}
	return binary.LittleEndian.Uint64(b[:]), true
}

func (e *emu) read(a x86asm.Arg, nextRIP uintptr) (uint64, bool) {
	switch v := a.(type) {
	case x86asm.Reg:
		i, w, ok := canonReg(v)
		if !ok {
			return 0, false
		}
		val := e.regs[i]
		if w == 32 {
			val &= 0xFFFFFFFF
		}
		return val, true
	case x86asm.Imm:
		return uint64(int64(v)), true
	case x86asm.Mem:
		addr, ok := e.effAddr(v, nextRIP)
		if !ok {
			return 0, false
		}
		return e.readMem(addr)
	}
	return 0, false
}

func (e *emu) writeReg(a x86asm.Arg, val uint64) bool {
	r, ok := a.(x86asm.Reg)
	if !ok {
		return false
	}
	i, w, ok := canonReg(r)
	if !ok {
		return false
	}
	if w == 32 {
		val &= 0xFFFFFFFF // 32-bit writes zero-extend the full 64-bit register
	}
	e.regs[i] = val
	return true
}

func aluOp(op x86asm.Op, a, b uint64) uint64 {
	switch op {
	case x86asm.ADD:
		return a + b
	case x86asm.SUB:
		return a - b
	case x86asm.XOR:
		return a ^ b
	case x86asm.AND:
		return a & b
	case x86asm.OR:
		return a | b
	case x86asm.ROL:
		return bits.RotateLeft64(a, int(b&63))
	case x86asm.ROR:
		return bits.RotateLeft64(a, -int(b&63))
	case x86asm.SHL:
		return a << (b & 63)
	case x86asm.SHR:
		return a >> (b & 63)
	case x86asm.SAR:
		return uint64(int64(a) >> (b & 63))
	}
	return a
}

// emulateStub runs the trampoline at stubVA and returns the address it jmps to.
func (r *reader) emulateStub(stubVA uintptr) (uintptr, bool) {
	code := make([]byte, 192)
	n, _ := r.read(stubVA, code)
	if n < 8 {
		return 0, false
	}
	code = code[:n]
	e := &emu{r: r}
	pc := stubVA
	for step := 0; step < 128; step++ {
		off := int(pc - stubVA)
		if off < 0 || off >= len(code) {
			return 0, false
		}
		inst, err := x86asm.Decode(code[off:], 64)
		if err != nil || inst.Op == 0 {
			return 0, false
		}
		next := pc + uintptr(inst.Len)
		switch inst.Op {
		case x86asm.PUSH:
			v, ok := e.read(inst.Args[0], next)
			if !ok {
				return 0, false
			}
			e.stack = append(e.stack, v)
		case x86asm.POP:
			if len(e.stack) == 0 {
				return 0, false
			}
			v := e.stack[len(e.stack)-1]
			e.stack = e.stack[:len(e.stack)-1]
			if !e.writeReg(inst.Args[0], v) {
				return 0, false
			}
		case x86asm.MOV:
			v, ok := e.read(inst.Args[1], next)
			if !ok || !e.writeReg(inst.Args[0], v) {
				return 0, false
			}
		case x86asm.LEA:
			m, ok := inst.Args[1].(x86asm.Mem)
			if !ok {
				return 0, false
			}
			addr, ok := e.effAddr(m, next)
			if !ok || !e.writeReg(inst.Args[0], uint64(addr)) {
				return 0, false
			}
		case x86asm.ADD, x86asm.SUB, x86asm.XOR, x86asm.AND, x86asm.OR,
			x86asm.ROL, x86asm.ROR, x86asm.SHL, x86asm.SHR, x86asm.SAR:
			dst, ok := e.read(inst.Args[0], next)
			src, ok2 := e.read(inst.Args[1], next)
			if !ok || !ok2 || !e.writeReg(inst.Args[0], aluOp(inst.Op, dst, src)) {
				return 0, false
			}
		case x86asm.NOT, x86asm.NEG, x86asm.BSWAP, x86asm.INC, x86asm.DEC:
			dst, ok := e.read(inst.Args[0], next)
			if !ok {
				return 0, false
			}
			var res uint64
			switch inst.Op {
			case x86asm.NOT:
				res = ^dst
			case x86asm.NEG:
				res = uint64(-int64(dst))
			case x86asm.BSWAP:
				res = bits.ReverseBytes64(dst)
			case x86asm.INC:
				res = dst + 1
			case x86asm.DEC:
				res = dst - 1
			}
			if !e.writeReg(inst.Args[0], res) {
				return 0, false
			}
		case x86asm.NOP:
			// no-op
		case x86asm.JMP:
			switch a := inst.Args[0].(type) {
			case x86asm.Reg:
				i, _, ok := canonReg(a)
				if !ok {
					return 0, false
				}
				return uintptr(e.regs[i]), true
			case x86asm.Mem:
				addr, ok := e.effAddr(a, next)
				if !ok {
					return 0, false
				}
				v, ok := e.readMem(addr)
				if !ok {
					return 0, false
				}
				return uintptr(v), true
			case x86asm.Rel:
				pc = next + uintptr(int64(a)) // follow an intra-stub relative jump
				continue
			}
			return 0, false
		default:
			return 0, false // unsupported instruction — give up (verified => never wrong)
		}
		pc = next
	}
	return 0, false
}

// cmdDeobfImports resolves an import-protected dump's IAT by emulating each trampoline
// against the live source process, then rebuilds the import table like reconstructiat.
func cmdDeobfImports(proc, dumpPath, outPath string) {
	r, pid, _, _ := mustOpen(proc)
	defer procCloseHandle.Call(r.h)

	expPath := findExportsSidecar(dumpPath)
	if expPath == "" {
		fmt.Println("ERROR: no *.exports.txt sidecar found beside the dump (dumpimage writes it).")
		os.Exit(1)
	}
	resolve, err := loadExportMap(expPath)
	if err != nil {
		fmt.Println("ERROR: reading exports sidecar:", err)
		os.Exit(1)
	}
	fmt.Printf("proc PID %d  exports: %s (%d entries)\n", pid, filepath.Base(expPath), len(resolve))

	var direct, emulated, undecodable, offTarget int
	var offSample []uintptr
	resolver := func(val uintptr) (imp, bool) {
		if im, ok := resolve[val]; ok { // some slots are unprotected (direct export ptr)
			direct++
			return im, true
		}
		target, ok := r.emulateStub(val)
		if !ok {
			undecodable++
			return imp{}, false
		}
		if im, ok := resolve[target]; ok {
			emulated++
			return im, true
		}
		offTarget++
		if len(offSample) < 8 {
			offSample = append(offSample, target)
		}
		return imp{}, false
	}

	writeReconstructed(dumpPath, outPath, resolver)

	fmt.Printf("  deobf: %d direct + %d emulated resolved; %d stubs undecodable; %d emulated targets not in sidecar\n",
		direct, emulated, undecodable, offTarget)
	if len(offSample) > 0 {
		fmt.Printf("  off-target sample: ")
		for _, a := range offSample {
			fmt.Printf("0x%X ", a)
		}
		fmt.Println()
	}
}

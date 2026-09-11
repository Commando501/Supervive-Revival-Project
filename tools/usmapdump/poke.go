// poke — write bytes into a target process via WriteProcessMemory.
//
// This is the ONE write-capable subcommand. Everything else in usmapdump is read-only.
// Use it to patch UObject fields, swap vtable slots, or replicate populator writes
// when the populator function itself can't be cheaply called.
//
// The handle is opened with VM_WRITE|VM_OPERATION|VM_READ — distinct from the read-only
// handle the other commands use. Per write, the tool:
//   1. Reads the existing N bytes at the target (printed as "BEFORE").
//   2. Calls WriteProcessMemory once with the full payload.
//   3. Reads back the same range (printed as "AFTER") and verifies it matches the
//      requested bytes.
//
// Usage: usmapdump poke <proc> <addr> <hex-bytes>
//   <addr>      absolute hex address (e.g. 0x16B77E50220) or +RVA form ("+0x12345").
//   <hex-bytes> space-OR-comma-separated hex bytes ("AA BB CC" or "AABBCC" or "AA,BB,CC").
//
// Game memory is volatile — if the AFTER read differs from intent (e.g. another thread
// raced and overwrote), the verify step surfaces it. No retry loop.
package main

import (
	"fmt"
	"os"
	"strings"
	"syscall"
	"unsafe"
)

const (
	processVMWrite     = 0x0020
	processVMOperation = 0x0008
)

var procWriteProcessMemory = kernel32.NewProc("WriteProcessMemory")

func (r *reader) write(addr uintptr, buf []byte) (int, error) {
	if len(buf) == 0 {
		return 0, nil
	}
	var n uintptr
	ok, _, e := procWriteProcessMemory.Call(r.h, addr,
		uintptr(unsafe.Pointer(&buf[0])), uintptr(len(buf)), uintptr(unsafe.Pointer(&n)))
	if ok == 0 && n == 0 {
		return 0, e
	}
	return int(n), nil
}

// mustOpenWritable opens the target with VM_READ + VM_WRITE + VM_OPERATION. Required for
// WriteProcessMemory; the default mustOpen handle is VM_READ only and will EACCES on write.
func mustOpenWritable(name string) (*reader, uint32, uintptr, uint32) {
	pid, err := findPID(name)
	if err != nil {
		fmt.Println("ERROR:", err)
		os.Exit(1)
	}
	h, _, e := procOpenProcess.Call(
		processVMRead|processVMWrite|processVMOperation|processQueryLimited,
		0, uintptr(pid))
	if h == 0 {
		fmt.Println("ERROR: OpenProcess(VM_READ|VM_WRITE|VM_OP) failed — run elevated:", e)
		os.Exit(1)
	}
	base, size, err := moduleBaseSize(pid, name)
	if err != nil {
		fmt.Println("ERROR:", err)
		os.Exit(1)
	}
	return &reader{h: h}, pid, base, size
}

// parseHexBytes accepts "AA BB CC", "AA,BB,CC", or "AABBCC" forms.
func parseHexBytes(s string) ([]byte, error) {
	// Normalize: drop spaces, commas, "0x" prefixes.
	s = strings.ReplaceAll(s, " ", "")
	s = strings.ReplaceAll(s, ",", "")
	s = strings.ReplaceAll(s, "0x", "")
	s = strings.ReplaceAll(s, "0X", "")
	if len(s)%2 != 0 {
		return nil, fmt.Errorf("odd hex length %d — must be even (two chars per byte)", len(s))
	}
	out := make([]byte, len(s)/2)
	for i := 0; i < len(out); i++ {
		var b uint8
		_, err := fmt.Sscanf(s[i*2:i*2+2], "%02x", &b)
		if err != nil {
			return nil, fmt.Errorf("bad hex byte %q at offset %d: %v", s[i*2:i*2+2], i*2, err)
		}
		out[i] = b
	}
	return out, nil
}

func cmdPoke(name, addrStr, hexBytes string) {
	r, pid, base, _ := mustOpenWritable(name)
	defer syscall.CloseHandle(syscall.Handle(r.h))

	// Resolve address (absolute hex or +RVA form, same as peek/disasm).
	addr, err := resolveAddr(name, addrStr)
	if err != nil {
		fmt.Println("ERROR: bad address:", err)
		os.Exit(1)
	}
	payload, err := parseHexBytes(hexBytes)
	if err != nil {
		fmt.Println("ERROR: bad hex bytes:", err)
		os.Exit(1)
	}
	if len(payload) == 0 {
		fmt.Println("ERROR: empty payload")
		os.Exit(1)
	}

	fmt.Printf("PID %d  base=0x%X  poke @0x%X  payload %d bytes\n",
		pid, base, addr, len(payload))

	// BEFORE: read current bytes for diagnostic context.
	before := make([]byte, len(payload))
	if n, err := r.read(addr, before); err != nil || n != len(payload) {
		fmt.Printf("ERROR: BEFORE read failed (n=%d): %v\n", n, err)
		os.Exit(1)
	}
	fmt.Printf("  BEFORE : % X\n", before)
	fmt.Printf("  PAYLOAD: % X\n", payload)

	// Write.
	n, werr := r.write(addr, payload)
	if werr != nil {
		fmt.Printf("ERROR: WriteProcessMemory failed (n=%d): %v\n", n, werr)
		os.Exit(1)
	}
	if n != len(payload) {
		fmt.Printf("WARN: short write — wrote %d of %d bytes\n", n, len(payload))
	}

	// AFTER: verify by re-reading.
	after := make([]byte, len(payload))
	if rn, err := r.read(addr, after); err != nil || rn != len(payload) {
		fmt.Printf("ERROR: AFTER read failed (n=%d): %v\n", rn, err)
		os.Exit(1)
	}
	fmt.Printf("  AFTER  : % X\n", after)

	mismatches := 0
	for i := range payload {
		if after[i] != payload[i] {
			mismatches++
		}
	}
	if mismatches == 0 {
		fmt.Printf("  VERIFY OK — wrote %d bytes\n", n)
	} else {
		fmt.Printf("  VERIFY FAIL — %d byte(s) differ between PAYLOAD and AFTER\n", mismatches)
		os.Exit(2)
	}
}


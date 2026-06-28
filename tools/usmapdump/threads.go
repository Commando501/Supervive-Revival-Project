// threads.go — enumerate threads in the live target, then locate GGameThreadId by
// scanning module data for any uint32 whose value equals one of those TIDs.
//
// Why: UE's check(IsInGameThread()) compares GetCurrentThreadId() to GGameThreadId.
// On a manually-mapped shim we must hijack THE thread whose id is in GGameThreadId, not
// the OS-initial thread (this build apparently dispatches the game loop on a spawned
// worker — the earliest-created thread hijack __fastfailed 0xC0000409).
//
// Strategy:
//   1. Snapshot all TIDs in the process (CreateToolhelp32Snapshot + Thread32Next).
//   2. Capture metadata per thread: creation time, start address (NtQueryInformation
//      ThreadQuerySetWin32StartAddress = info class 9), kernel/user time.
//   3. Scan module DATA regions for any 4-byte value equal to a live TID. Each hit is a
//      candidate global thread-id storage slot.
//   4. Print them in a way that lets us identify GGameThreadId (usually the only TID
//      stored in a module .data slot AT A LOW RVA range, surrounded by other globals).

package main

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"os"
	"sort"
	"syscall"
	"unsafe"

	"golang.org/x/arch/x86/x86asm"
)

var (
	ntdll                = syscall.NewLazyDLL("ntdll.dll")
	procNtQueryInfoThread = ntdll.NewProc("NtQueryInformationThread")
	procOpenThread       = kernel32.NewProc("OpenThread")
	procGetThreadTimes   = kernel32.NewProc("GetThreadTimes")
)

const (
	threadQueryInformation = 0x0040
	threadQueryLimited     = 0x0800
	threadQuerySetWin32StartAddress = 9
)

type threadEntry32 struct {
	Size            uint32
	Usage           uint32
	ThreadID        uint32
	OwnerProcessID  uint32
	BasePri         int32
	DeltaPri        int32
	Flags           uint32
}

type threadInfo struct {
	tid          uint32
	startAddr    uintptr
	createTimeNs uint64
	moduleHit    bool   // start addr lies inside main module
	moduleRVA    uintptr // start RVA if moduleHit
}

func enumThreads(pid uint32) []threadInfo {
	const TH32CS_SNAPTHREAD = 0x4
	snap, _, _ := procCreateToolhelp32Snap.Call(TH32CS_SNAPTHREAD, 0)
	if snap == 0 || snap == ^uintptr(0) {
		return nil
	}
	defer procCloseHandle.Call(snap)
	var te threadEntry32
	te.Size = uint32(unsafe.Sizeof(te))
	procThread32First := kernel32.NewProc("Thread32First")
	procThread32Next := kernel32.NewProc("Thread32Next")
	ret, _, _ := procThread32First.Call(snap, uintptr(unsafe.Pointer(&te)))
	var out []threadInfo
	for ret != 0 {
		if te.OwnerProcessID == pid {
			out = append(out, threadInfo{tid: te.ThreadID})
		}
		ret, _, _ = procThread32Next.Call(snap, uintptr(unsafe.Pointer(&te)))
	}
	return out
}

func annotateThreads(ts []threadInfo, base uintptr, size uint32) {
	for i := range ts {
		h, _, _ := procOpenThread.Call(threadQueryInformation, 0, uintptr(ts[i].tid))
		if h == 0 {
			h, _, _ = procOpenThread.Call(threadQueryLimited, 0, uintptr(ts[i].tid))
		}
		if h == 0 {
			continue
		}
		// GetThreadTimes for creation time.
		var c, e, k, u syscall.Filetime
		procGetThreadTimes.Call(h, uintptr(unsafe.Pointer(&c)), uintptr(unsafe.Pointer(&e)), uintptr(unsafe.Pointer(&k)), uintptr(unsafe.Pointer(&u)))
		ts[i].createTimeNs = (uint64(c.HighDateTime) << 32) | uint64(c.LowDateTime)
		// NtQueryInformationThread for start address.
		var startAddr uintptr
		var retLen uint32
		procNtQueryInfoThread.Call(h, threadQuerySetWin32StartAddress, uintptr(unsafe.Pointer(&startAddr)), uintptr(unsafe.Sizeof(startAddr)), uintptr(unsafe.Pointer(&retLen)))
		ts[i].startAddr = startAddr
		if startAddr >= base && startAddr < base+uintptr(size) {
			ts[i].moduleHit = true
			ts[i].moduleRVA = startAddr - base
		}
		procCloseHandle.Call(h)
	}
}

// findTidSlotsInModuleData finds qword-aligned 4-byte values in module readable regions
// whose value == a live TID. Returns slot -> tid map.
func findTidSlotsInModuleData(r *reader, regions []region, tidSet map[uint32]bool) map[uintptr]uint32 {
	out := map[uintptr]uint32{}
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
			// Scan with 4-byte alignment (uint32 slots).
			for i := 0; i+4 <= len(buf); i += 4 {
				v := binary.LittleEndian.Uint32(buf[i:])
				if tidSet[v] {
					out[cb+uintptr(i)] = v
				}
			}
			cb += uintptr(len(buf))
		}
	}
	_ = bytes.Index
	return out
}

// cmdFindGameTid: locate GGameThreadId by finding code patterns of the form:
//   call <iat slot for kernel32!GetCurrentThreadId>
//   cmp/mov reg, [rip+disp]    where the rip-relative address holds a uint32
// The disp+ip lands on the global TID. Histograms the unique target addresses across
// every such pattern site in the module — the most-referenced uint32 slot is GGameThreadId
// (every IsInGameThread / check call lands there).
func cmdFindGameTid(name string) {
	r, pid, base, size := mustOpen(name)
	defer procCloseHandle.Call(r.h)
	fmt.Printf("PID %d %q base=0x%X size=0x%X\n", pid, name, base, size)

	// We don't easily know the IAT slot for GetCurrentThreadId without parsing imports;
	// instead, look for ALL "call qword ptr [rip+disp]" instructions FOLLOWED CLOSELY by
	// a cmp/mov reading a 4-byte rip-relative value. That is the universal pattern.
	// Histogram the target address of the cmp/mov uint32 read. Module-data slots that
	// appear many times are thread-id globals; the dominant one is GGameThreadId.
	execRegs := moduleRegions(r, base, size, true)
	hits := map[uintptr]int{}
	const chunk = 16 << 20
	const overlap = 16
	const page = 0x1000
	var total uint64
	for _, s := range execRegs {
		for cb := s.base; cb < s.base+s.size; {
			want := uintptr(chunk + overlap)
			if cb+want > s.base+s.size {
				want = s.base + s.size - cb
			}
			buf := readRegionChunk(r, cb, want)
			if buf == nil {
				cb += page
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
				// Look for CMP reg, [rip+disp] (4-byte memory operand) or MOV r32, [rip+disp].
				// We want the 32-bit memory read forms specifically — 0x39/0x3B (cmp) or 0x8B (mov)
				// with mod==00, rm==101 in modrm. Easiest: filter by mnemonic + arg shapes.
				if inst.Op == 0 {
					continue
				}
				// Need a Mem arg with Base=RIP AND a 32-bit register arg.
				var memArg x86asm.Mem
				gotMem := false
				gotReg32 := false
				for _, a := range inst.Args {
					if a == nil {
						break
					}
					if m, ok := a.(x86asm.Mem); ok && m.Base == x86asm.RIP {
						memArg = m
						gotMem = true
					}
					if rg, ok := a.(x86asm.Reg); ok {
						// 32-bit regs: EAX..R15D ranges in x86asm.
						s := rg.String()
						if len(s) > 0 && (s[0] == 'E' || (s[0] == 'R' && len(s) >= 3 && s[len(s)-1] == 'D')) {
							gotReg32 = true
						}
					}
				}
				if !gotMem || !gotReg32 {
					continue
				}
				// Restrict to short instruction families that are realistic for IsInGameThread:
				// CMP / MOV / SUB / ADD / TEST.
				switch inst.Op {
				case x86asm.CMP, x86asm.MOV, x86asm.SUB, x86asm.ADD, x86asm.TEST, x86asm.XOR:
				default:
					continue
				}
				ip := cb + uintptr(i)
				target := ip + uintptr(inst.Len) + uintptr(int64(memArg.Disp))
				if target < base || target >= base+uintptr(size) {
					continue
				}
				hits[target]++
				total++
			}
			cb += uintptr(len(buf)) - overlap
			if uintptr(len(buf)) <= overlap {
				cb += page
			}
		}
	}
	fmt.Printf("  scanned %d 32-bit rip-rel reg<->mem ops; %d unique module data targets\n", total, len(hits))

	// Filter targets to those that currently hold a live TID, sort by hit count desc.
	ts := enumThreads(pid)
	tidSet := make(map[uint32]bool, len(ts))
	for _, t := range ts {
		tidSet[t.tid] = true
	}
	type cand struct {
		addr uintptr
		hits int
		tid  uint32
	}
	var cands []cand
	for a, h := range hits {
		var four [4]byte
		if n, _ := r.read(a, four[:]); n == 4 {
			v := uint32(four[0]) | uint32(four[1])<<8 | uint32(four[2])<<16 | uint32(four[3])<<24
			if tidSet[v] {
				cands = append(cands, cand{a, h, v})
			}
		}
	}
	sort.Slice(cands, func(i, j int) bool { return cands[i].hits > cands[j].hits })
	fmt.Printf("\n  top candidates (uint32 slot in module currently holding a live TID, by code-ref count):\n")
	for i, c := range cands {
		if i >= 25 {
			fmt.Printf("    ...(+%d more)\n", len(cands)-25)
			break
		}
		ord := -1
		for k, t := range ts {
			if t.tid == c.tid {
				ord = k
				break
			}
		}
		fmt.Printf("    rva 0x%-8X hits=%-6d tid=%-7d ord=%d\n", c.addr-base, c.hits, c.tid, ord)
	}
}

func cmdThreads(name string) {
	r, pid, base, size := mustOpen(name)
	defer procCloseHandle.Call(r.h)
	ts := enumThreads(pid)
	annotateThreads(ts, base, size)
	sort.Slice(ts, func(i, j int) bool { return ts[i].createTimeNs < ts[j].createTimeNs })

	fmt.Printf("PID %d module=0x%X size=0x%X  threads: %d\n", pid, base, size, len(ts))
	fmt.Println("  TID     ord   createNs            startAddr           inModule  startRVA")
	for i, t := range ts {
		mod := "no"
		rvaStr := ""
		if t.moduleHit {
			mod = "YES"
			rvaStr = fmt.Sprintf("0x%X", t.moduleRVA)
		}
		fmt.Printf("  %-7d %-5d 0x%-16X 0x%-18X %-9s %s\n", t.tid, i, t.createTimeNs, t.startAddr, mod, rvaStr)
	}

	// Find module-data slots holding any live TID.
	tidSet := make(map[uint32]bool, len(ts))
	for _, t := range ts {
		tidSet[t.tid] = true
	}
	// Module data regions = readable regions in the module range that are NOT executable.
	dataRegs := moduleRegions(r, base, size, false)
	// Filter to non-exec.
	const anyExec = 0x10 | 0x20 | 0x40 | 0x80
	var filtered []region
	for _, rg := range dataRegs {
		if rg.protect&anyExec == 0 {
			filtered = append(filtered, rg)
		}
	}
	slots := findTidSlotsInModuleData(r, filtered, tidSet)
	fmt.Printf("\n  %d module-data slots hold a live TID:\n", len(slots))
	type kv struct {
		slot uintptr
		tid  uint32
	}
	var rows []kv
	for k, v := range slots {
		rows = append(rows, kv{k, v})
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].slot < rows[j].slot })
	for i, row := range rows {
		if i >= 80 {
			fmt.Printf("    ...(+%d more)\n", len(rows)-80)
			break
		}
		// Annotate which thread this is (ordinal in create order).
		ord := -1
		for k, t := range ts {
			if t.tid == row.tid {
				ord = k
				break
			}
		}
		fmt.Printf("    slot rva 0x%-8X tid=%d (ord=%d createNs=0x%X)\n", row.slot-base, row.tid, ord, ts[ord].createTimeNs)
	}
	_ = os.Stderr
}

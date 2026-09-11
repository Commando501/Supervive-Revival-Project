// nameid.go — `usmapdump nameid <proc> <needle1[,needle2,...]> [maxhits-per-needle]`
//
// Walks every block of the live FNamePool, decodes each FNameEntry, and prints
// hits per needle. For each hit reports the 32-bit FName ComparisonIndex
// (= (block << 16) | (offset / fnameStride)) — the value you bake into a shim
// that wants to construct an FName for that pooled string without calling
// FName::FName().
//
// **Multi-needle batch.** Comma-separated needles are matched in one pool walk —
// pool discovery is the slow part (~30s scanning 4GB of pool storage), so a
// batch keeps each registration_shim.cpp build session to a single call.
//
// **Exact-match prefix.** A needle starting with `=` is matched exactly
// (case-sensitive). Without the prefix the needle matches case-insensitive
// substring. Use exact for common short tokens like `=Mission` / `=Hero` where
// substring would surface noise (Permission, HeroSelectPlayer, ...).
//
// Use case: building registration_shim.cpp's per-asset ID table. All cooked
// asset names ("Mission", "Hero", "DA_Mission_*", PascalCase hero codenames,
// "/Game/..." package FNames, etc.) live in the runtime NamePool — this command
// extracts their indices so the shim can construct FPrimaryAssetId /
// FSoftObjectPath without runtime name-construction machinery.
//
// Block size is treated as 4MB (the standard UE FNameAllocator block — verified
// by usmapdump names showing 128 allocated blocks); walk stops early on
// undecodable headers or a 0-length entry.

package main

import (
	"fmt"
	"os"
	"strings"
)

const fnameBlockBytes = 1 << 22 // 4 MB per FName allocator block (UE default)

type needleSpec struct {
	raw      string // original (with any `=` prefix), kept for printing
	cmp      string // comparison string (lowercased for substring; verbatim for exact)
	exact    bool
	hits     int
}

func cmdNameID(procName, needleArg string, maxHits int) {
	if needleArg == "" {
		fmt.Println("ERROR: empty needle")
		os.Exit(1)
	}
	r, pid, base, size := mustOpen(procName)
	defer procCloseHandle.Call(r.h)
	fmt.Printf("PID %d  %q base=0x%X size=0x%X\n", pid, procName, base, size)

	// Parse comma-separated needles + exact-match `=` prefix.
	parts := strings.Split(needleArg, ",")
	specs := make([]*needleSpec, 0, len(parts))
	for _, raw := range parts {
		s := raw
		if s == "" {
			continue
		}
		ns := &needleSpec{raw: s}
		if strings.HasPrefix(s, "=") {
			ns.exact = true
			ns.cmp = s[1:]
		} else {
			ns.cmp = strings.ToLower(s)
		}
		specs = append(specs, ns)
	}
	if len(specs) == 0 {
		fmt.Println("ERROR: no valid needles")
		os.Exit(1)
	}

	p, err := findNamePool(r)
	if err != nil {
		fmt.Println("ERROR:", err)
		os.Exit(1)
	}
	fmt.Printf("  &Blocks[0] @0x%X   blocks=%d   layout=%s\n", p.blocksAddr, len(p.blocks), p.layout)
	fmt.Printf("  searching pool for %d needle(s), maxhits=%d each:\n", len(specs), maxHits)
	for _, ns := range specs {
		mode := "substr"
		if ns.exact {
			mode = "exact"
		}
		fmt.Printf("    [%s] %q\n", mode, ns.cmp)
	}
	fmt.Println()

	for blockIdx, blockBase := range p.blocks {
		// Early exit if EVERY needle has saturated.
		anyHungry := false
		for _, ns := range specs {
			if ns.hits < maxHits {
				anyHungry = true
				break
			}
		}
		if !anyHungry {
			break
		}

		off := 0
		for off < fnameBlockBytes {
			s, sz, ok := r.decodeEntryAnsi(blockBase+uintptr(off), p.layout)
			if sz == 0 {
				break
			}
			if ok && s != "" {
				sLower := strings.ToLower(s)
				for _, ns := range specs {
					if ns.hits >= maxHits {
						continue
					}
					match := false
					if ns.exact {
						match = (s == ns.cmp)
					} else {
						match = strings.Contains(sLower, ns.cmp)
					}
					if match {
						id := (uint32(blockIdx) << fnameBlockOffsetBits) | uint32(off/fnameStride)
						fmt.Printf("  [%-20s] block=%-3d off=0x%-6X  id=0x%08X  %q\n",
							ns.raw, blockIdx, off, id, s)
						ns.hits++
					}
				}
			}
			off += align2(sz)
		}
	}

	fmt.Println()
	totalHits := 0
	for _, ns := range specs {
		fmt.Printf("  %-30s %d hit(s)\n", ns.raw, ns.hits)
		totalHits += ns.hits
	}
	fmt.Printf("\n  %d total hit(s) across %d needle(s)\n", totalHits, len(specs))
}

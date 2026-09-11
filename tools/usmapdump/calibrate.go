// calibrate.go — FK-14 (S116): resolve the FProperty sub-object offsets BY MEASUREMENT
// against the live process, print the score table, and refuse to emit rather than emit a
// mis-typed usmap.
//
// WHY THIS FILE EXISTS
// --------------------
// `extract.go` used to hardcode `offFFieldEmbeddedInner = 0x80` and read a container's
// inner property INLINE there. That address is one byte past the end of an
// FArrayProperty, so the tool captured whatever FField the heap allocator happened to
// place next. Adjacency is frozen inside one process instance and differs across
// launches — which is why three back-to-back extractions were byte-identical while two
// sessions a week apart disagreed on 326 property types. See docs/fk14-usmap-settled.md.
//
// The settlement's standing rule: **never infer a struct offset by homology from stock UE
// in this build; measure it, with a discriminator that dereferences the candidate and
// validates the target.** So every offset this tool depends on is decided here, at
// startup, against the process being dumped — which makes the fix its own permanent
// control and means a future engine update cannot silently re-break it.
//
// ★★ WHAT THE FIRST RUN OF THIS CALIBRATOR FOUND (2026-08-13, pid 50016)
// ----------------------------------------------------------------------
// It reproduced the settlement's headline numbers to the digit — 4,247 containers,
// 96.6 % at *(+0x78), 3.4 % at *(+0x70), 0.1 % inline at +0x80 — and then showed that the
// headline is a MIXTURE that must not be applied as one offset:
//
//	.array     3,548  ->  +0x78  100.0 %      (   0.0 % at +0x70)
//	.map       555    ->  +0x78  100.0 %  AND +0x70 100.0 % — two different slots
//	.set       142    ->  +0x70  100.0 %      (   0.0 % at +0x78)   <-- NOT +0x78
//	.optional  2      ->  +0x70  100.0 %      (   0.0 % at +0x78)   <-- NOT +0x78
//
// 3,548 + 555 = 4,103 = the settlement's 96.6 %; 142 + 2 = 144 = its "3.4 %". The residual
// the settlement read as measurement noise is **SetProperty and OptionalProperty sitting
// at a different offset**. Adopting the pooled winner would have mis-typed all 144 of them.
// So this file scores EVERY FAMILY SEPARATELY and the pooled row is report-only.
//
// It also settled the two offsets the settlement left explicitly UNMEASURED (§3.4), and
// both of its labelled-[I] guesses are wrong:
//
//	FEnumProperty::UnderlyingProp : +0x70  (guessed +0x78)  1,840/1,840 numeric FField
//	FEnumProperty::Enum           : +0x78  (guessed +0x80)  1,840/1,840 UEnum label
//
// §3.4's evidence that Enum is not at +0x70 was `labelPtr(*(f+0x70))` scoring 0/1,840 —
// which is TRUE and does not mean the slot is empty: it holds UnderlyingProp, an FField,
// which a UObject-only labeller cannot name. That is precisely the trap §11.3 warned
// about, one section earlier in the same document.
//
// The same seven offsets were measured independently, the same session, by a separate
// agent with a separate probe (scratchpad/fk14-probes/VERDICT.md) and agree to the digit,
// including the two the settlement left unmeasured. That work also settles §3.3's layout
// question, and the answer is NEITHER of its two candidates: sizeof(FProperty) == 0x70
// and +0x70 is uniformly the DERIVED class's first member — the "type-carrying vs
// container" split does not exist. Exactly ONE family deviates: FArrayProperty has an
// 8-byte hole at +0x70 with Inner pushed to +0x78. ⚠ That hole is UNIDENTIFIED; its
// values are high-entropy, so do NOT label it ArrayFlags.

package main

import (
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
)

// FField/FProperty offsets that are NOT calibrated (each already measured and in daily
// use by the working extractor: PropertyFlags@0x38 is load-bearing for the replication
// work and would be visibly wrong if this layout were off).
const (
	offFFieldOwner    = 0x10 // FField::Owner — UStruct*/FField* with low bit set if UObject-owned
	offFPropArrayDim  = 0x30 // FProperty::ArrayDim (int32). Self-validating: see gStats.
	calibCandidateCap = 4000 // per-family sample cap
	calibNameCap      = 400  // per (family, offset) cap for the name-relation histogram
	oldBuggyInline    = 0x80 // what the tool did before FK-14: an INLINE FField read here
)

// candidate offsets scored for every family (docs/fk14-usmap-settled.md §9).
var calibCandidates = []uintptr{0x68, 0x70, 0x78, 0x80, 0x88}

// numericPropTypes — legal types for FEnumProperty::UnderlyingProp.
var numericPropTypes = map[string]bool{
	"ByteProperty": true, "IntProperty": true, "Int8Property": true, "Int16Property": true,
	"Int64Property": true, "UInt16Property": true, "UInt32Property": true, "UInt64Property": true,
}

// fieldOffsets is the resolved layout this run will use. Nothing outside calibrate.go
// writes it. Note there is NO single "container" offset: that was the mistake.
type fieldOffsets struct {
	typeSlot       uintptr // UStruct*/UClass* for the type-carrying families
	arrayInner     uintptr // FArrayProperty::Inner
	setInner       uintptr // FSetProperty::ElementProp
	optionalInner  uintptr // FOptionalProperty::ValueProperty
	mapKey         uintptr // FMapProperty::KeyProp
	mapValue       uintptr // FMapProperty::ValueProp
	enumUnderlying uintptr // FEnumProperty::UnderlyingProp
	enumEnum       uintptr // FEnumProperty::Enum (a UEnum object)
	arrayDim       uintptr // FProperty::ArrayDim
	forceArrayDim1 bool    // arm D
	arm            string
	armWhy         string
	forcedNote     []string
}

var gOff = fieldOffsets{
	// Sub-object offsets deliberately start at 0. calibrateOffsets() must run before any
	// FField is read; a forgotten call then reads offset 0 and produces obvious garbage
	// rather than a plausible-looking wrong answer.
	arrayDim: offFPropArrayDim,
}

// gStats accumulates everything the run must PRINT rather than silently swallow. A run
// with a silent zero everywhere is the no-op tell.
var gStats struct {
	propsWalked      int
	arrayDimNot1     int
	arrayDimBad      int
	innerNilPtr      int
	innerBadType     int
	innerBadOwner    int
	innerOK          int
	enumObjResolved  int
	enumObjUnlabeled int
}

// ===== arm selection =====

// selectArm resolves which pre-registered control arm this binary runs as. Selection is
// by FK14_ARM if set, else by the executable's own filename — so ONE build copied to
// armF.exe / armW.exe / armD.exe / armE.exe behaves as four arms.
//
// ⚠ Those four files are BYTE-IDENTICAL by design. The project rule "never A/B two DLLs
// without diffing their .text sha256" exists because identical artifacts have shipped
// under different names; here that is deliberate and the differing variable is the
// filename, which is read at startup and PRINTED. An unprinted arm is an unmeasured arm.
func selectArm() (string, string) {
	if v := strings.TrimSpace(os.Getenv("FK14_ARM")); v != "" {
		return normalizeArm(v, "FK14_ARM env")
	}
	base := strings.ToLower(os.Args[0])
	if i := strings.LastIndexAny(base, `\/`); i >= 0 {
		base = base[i+1:]
	}
	// order matters: armw70 must be tested before armw
	for _, a := range []string{"armw70", "armw", "armd", "arme", "armf"} {
		if strings.Contains(base, a) {
			return normalizeArm(a[3:], "executable name "+base)
		}
	}
	return normalizeArm("F", "default")
}

func normalizeArm(v, why string) (string, string) {
	switch strings.ToUpper(v) {
	case "W", "WRONG":
		return "W", why
	case "W70":
		return "W70", why
	case "D", "DIM1":
		return "D", why
	case "E", "ENUMASSUME":
		return "E", why
	case "F", "FULL", "":
		return "F", why
	}
	fmt.Printf("[FK14] WARNING: unknown FK14_ARM %q — running as F\n", v)
	return "F", why + " (unrecognized, coerced to F)"
}

func envOffset(key string) (uintptr, bool) {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return 0, false
	}
	n, err := strconv.ParseUint(strings.TrimPrefix(strings.TrimPrefix(v, "0x"), "0X"), 16, 32)
	if err != nil {
		fmt.Printf("[FK14] WARNING: %s=%q is not a hex offset — ignored\n", key, v)
		return 0, false
	}
	return uintptr(n), true
}

// ===== sample collection =====

func calibFamily(t string) string {
	switch t {
	case "StructProperty", "ObjectProperty", "ClassProperty":
		// The only type-carrying families whose type object is MANDATORY non-null, so the
		// only ones that can score a type slot honestly. Byte/Interface/Soft/Weak/Lazy may
		// hold a legitimate null, which makes a miss there uninterpretable (§11.3): they
		// are REPORTED below, never scored.
		return "type"
	case "ByteProperty", "InterfaceProperty", "SoftObjectProperty", "SoftClassProperty",
		"WeakObjectProperty", "LazyObjectProperty":
		return "typeopt"
	case "ArrayProperty":
		return "array"
	case "SetProperty":
		return "set"
	case "MapProperty":
		return "map"
	case "OptionalProperty":
		return "optional"
	case "EnumProperty":
		return "enum"
	}
	return ""
}

func collectCalibSamples(r *reader, p *pool, objs []objref, buckets map[string][]uintptr) {
	for _, o := range objs {
		f := r.ptr(o.addr + offUStructChildProps)
		for i := 0; i < 4096 && f != 0; i++ {
			if fc := r.ptr(f + offFFieldClass); fc != 0 {
				if fam := calibFamily(decodeName(r, p, fc+offFFieldClassName)); fam != "" {
					if len(buckets[fam]) < calibCandidateCap {
						buckets[fam] = append(buckets[fam], f)
					}
				}
			}
			f = r.ptr(f + offFFieldNext)
		}
	}
}

// ===== discriminators =====

// innerAt dereferences *(f+off) and returns the target address if it is an FField that
//
//	(a) has a ClassPrivate naming a known property type [numeric, if numericOnly], and
//	(b) has Owner == f — proving it belongs to THIS property and not to a neighbour.
//
// (b) is the discriminator the old inline read could not express: an adjacent FField
// belonging to the same UStruct has the same Owner as the outer property, which is why
// the old owner guard was self-confirming, but no neighbour has the outer PROPERTY as its
// owner. Returns 0 on any failure.
func innerAt(r *reader, p *pool, f, off uintptr, numericOnly bool) uintptr {
	ip := r.ptr(f + off)
	if ip == 0 || !userspacePtr(ip) {
		return 0
	}
	fc := r.ptr(ip + offFFieldClass)
	if fc == 0 {
		return 0
	}
	tn := decodeName(r, p, fc+offFFieldClassName)
	if !knownPropTypes[tn] || (numericOnly && !numericPropTypes[tn]) {
		return 0
	}
	if r.ptr(ip+offFFieldOwner)&^1 != f {
		return 0
	}
	return ip
}

// scoreInner counts (structural, sameName). structural = innerAt succeeded; sameName =
// the target additionally carries the same FName as the outer property. Both are printed:
// sameName is the settlement's third discriminator, structural is what the extractor
// enforces at run time, and where they DISAGREE is exactly where a slot's identity
// (key vs value, underlying vs enum) is decided.
func scoreInner(r *reader, p *pool, fs []uintptr, off uintptr, numericOnly bool) (int, int) {
	structural, same := 0, 0
	for _, f := range fs {
		ip := innerAt(r, p, f, off, numericOnly)
		if ip == 0 {
			continue
		}
		structural++
		on, _ := r.u32(ip + offFFieldName)
		fn, _ := r.u32(f + offFFieldName)
		if on == fn && on != 0 {
			same++
		}
	}
	return structural, same
}

// scoreInlineOldBug reproduces EXACTLY what the pre-FK-14 tool did — treat f+0x80 as an
// inline FField — as a positive control that this instrument can see the old behaviour.
// The settlement measured 5/4,247 = 0.1 %.
func scoreInlineOldBug(r *reader, p *pool, fs []uintptr) int {
	hits := 0
	for _, f := range fs {
		ip := f + oldBuggyInline
		fc := r.ptr(ip + offFFieldClass)
		if fc == 0 {
			continue
		}
		if !knownPropTypes[decodeName(r, p, fc+offFFieldClassName)] {
			continue
		}
		if r.ptr(ip+offFFieldOwner)&^1 != f {
			continue
		}
		hits++
	}
	return hits
}

func scoreTypeSlot(r *reader, x *addrIndex, fs []uintptr, off uintptr, enumOnly bool) int {
	hits := 0
	for _, f := range fs {
		v := r.ptr(f + off)
		if v == 0 {
			continue
		}
		lbl := x.labelPtr(v)
		if lbl == "" {
			continue
		}
		if enumOnly && !strings.HasPrefix(lbl, "UEnum:") {
			continue
		}
		hits++
	}
	return hits
}

// nameRelation reports how the target's NAME relates to the outer property's name, as a
// histogram over the sample. UHT names a map's key property "<Name>_Key" and its value
// property "<Name>", and an enum's underlying property "<Name>_Underlying" — so the name
// is a self-labelling, directly observable statement of what the slot IS. Nothing here is
// assumed: the observed relations are printed and the decision rule below requires them.
func nameRelation(r *reader, p *pool, fs []uintptr, off uintptr, numericOnly bool) map[string]int {
	h := map[string]int{}
	n := 0
	for _, f := range fs {
		if n >= calibNameCap {
			break
		}
		ip := innerAt(r, p, f, off, numericOnly)
		if ip == 0 {
			continue
		}
		n++
		outer := decodeName(r, p, f+offFFieldName)
		inner := decodeName(r, p, ip+offFFieldName)
		switch {
		case inner == outer:
			h["<same>"]++
		case strings.HasPrefix(inner, outer+"_"):
			h["<outer>+\""+inner[len(outer):]+"\""]++
		default:
			h["<unrelated>"]++
		}
	}
	return h
}

func topRelation(h map[string]int) (string, int, int) {
	total, best, bn := 0, "", 0
	keys := make([]string, 0, len(h))
	for k := range h {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		total += h[k]
		if h[k] > bn {
			best, bn = k, h[k]
		}
	}
	return best, bn, total
}

// ===== the gate =====

// pickWinner: the best candidate must clear 90 % of the family's sample AND beat the
// runner-up 5:1. A mis-typed usmap is worse than no usmap because it looks plausible —
// the 33-entry knownPropTypes whitelist passes 83.1 % of the time on a bare type check,
// which is the false-positive engine that hid this bug for 60 sessions.
//
// Small-N exception: with fewer than 50 samples a rate cannot clear a statistical gate,
// but a UNANIMOUS result (best = N, every other candidate exactly 0) is still a
// measurement — under-powered, not absent. It is accepted and LABELLED as such, never
// silently filled in from a sibling family (that is homology, the reasoning this whole
// settlement exists to ban).
func pickWinner(n int, scores []int) (uintptr, bool, string) {
	if n == 0 {
		return 0, false, "no samples"
	}
	bi, best, runner := 0, -1, 0
	for i, s := range scores {
		if s > best {
			runner, best, bi = best, s, i
		} else if s > runner {
			runner = s
		}
	}
	if runner < 0 {
		runner = 0
	}
	win := calibCandidates[bi]
	if n < 50 {
		if best == n && runner == 0 {
			return win, true, fmt.Sprintf("UNANIMOUS-SMALL-N (%d/%d, all other offsets 0)", best, n)
		}
		return win, false, fmt.Sprintf("sample too small and not unanimous (%d/%d)", best, n)
	}
	if frac := float64(best) / float64(n); frac < 0.90 {
		return win, false, fmt.Sprintf("best %.1f%% < 90%% gate", frac*100)
	}
	if runner*5 > best {
		return win, false, fmt.Sprintf("runner-up %d vs %d — under 5:1", runner, best)
	}
	return win, true, ""
}

func pct(a, n int) string {
	if n == 0 {
		return "    -"
	}
	return fmt.Sprintf("%5.1f", float64(a)*100/float64(n))
}

type calibRow struct {
	label   string
	n       int
	a, b    []int // a = primary metric, b = secondary (nil if none)
	winner  uintptr
	pass    bool
	note    string
	scoring bool
}

func (rw *calibRow) print() {
	fmt.Printf("  %-22s %6d", rw.label, rw.n)
	for i := range calibCandidates {
		if rw.b != nil {
			fmt.Printf(" %5s|%-5s", pct(rw.a[i], rw.n), pct(rw.b[i], rw.n))
		} else {
			fmt.Printf(" %11s", pct(rw.a[i], rw.n))
		}
	}
	switch {
	case !rw.scoring:
		fmt.Printf("   -> (report only) %s\n", rw.note)
	case rw.pass && rw.note != "":
		fmt.Printf("   -> +0x%02X  PASS  %s\n", rw.winner, rw.note)
	case rw.pass:
		fmt.Printf("   -> +0x%02X  PASS\n", rw.winner)
	default:
		fmt.Printf("   -> +0x%02X  FAIL: %s\n", rw.winner, rw.note)
	}
}

// ===== entry point =====

// calibrateOffsets measures every offset the extractor depends on, prints the full score
// table, applies the selected control arm's forcings, and returns false if any SCORING
// family failed its gate (the caller must then refuse to write).
func calibrateOffsets(r *reader, p *pool, x *addrIndex, classes, structs []objref) bool {
	gOff.arm, gOff.armWhy = selectArm()

	fmt.Println("\n=== FK-14 offset calibration (measured live, on THIS process) ===")
	fmt.Printf("  arm: %s   (selected by %s)\n", gOff.arm, gOff.armWhy)
	switch gOff.arm {
	case "F":
		fmt.Println("       F = calibrated winners for every family (the fix)")
	case "W":
		fmt.Println("       W = every container inner FORCED to +0x78, map value to +0x80 — the")
		fmt.Println("           WRONG-DIRECTION control, and specifically THE PATCH THAT WOULD HAVE")
		fmt.Println("           SHIPPED: it is the settlement's pooled 96.6 % winner plus its [I] guess")
		fmt.Println("           for the map value. Fixes Array; makes Map read its VALUE as the KEY and")
		fmt.Println("           garbage as the value; leaves all 142 Sets + 2 Optionals broken. Every")
		fmt.Println("           part of that failure is SILENT except for the fallback counters.")
	case "W70":
		fmt.Println("       W70 = every container inner FORCED to +0x70 — second negative control.")
		fmt.Println("           Wrong for Array (3,548) and for the map VALUE; coincidentally CORRECT")
		fmt.Println("           for Set, Optional and the map KEY.")
	case "D":
		fmt.Println("       D = ArrayDim FORCED to 1 — control for the +0x30 read")
	case "E":
		fmt.Println("       E = enum offsets FORCED to the settlement's ASSUMED 0x78/0x80 instead of")
		fmt.Println("           calibrated — control for the one pair it left UNMEASURED")
	}

	buckets := map[string][]uintptr{}
	collectCalibSamples(r, p, classes, buckets)
	collectCalibSamples(r, p, structs, buckets)

	fmt.Printf("\n  cells = %% of that family's sampled FFields for which the candidate offset passes.\n")
	fmt.Printf("  inner rows print  structural|sameName  (see scoreInner).\n\n")
	fmt.Printf("  %-22s %6s", "family / slot", "N")
	for _, c := range calibCandidates {
		fmt.Printf(" %11s", fmt.Sprintf("+0x%02X", c))
	}
	fmt.Printf("   -> winner\n")

	mkInner := func(label string, fs []uintptr, numericOnly bool, scoring bool) calibRow {
		rw := calibRow{label: label, n: len(fs), scoring: scoring}
		for _, c := range calibCandidates {
			s, sm := scoreInner(r, p, fs, c, numericOnly)
			rw.a = append(rw.a, s)
			rw.b = append(rw.b, sm)
		}
		rw.winner, rw.pass, rw.note = pickWinner(rw.n, rw.a)
		return rw
	}

	// --- type-carrying families --------------------------------------------------
	typeFs := buckets["type"]
	rowType := calibRow{label: "type Struct/Obj/Cls", n: len(typeFs), scoring: true}
	for _, c := range calibCandidates {
		rowType.a = append(rowType.a, scoreTypeSlot(r, x, typeFs, c, false))
	}
	rowType.winner, rowType.pass, rowType.note = pickWinner(rowType.n, rowType.a)
	rowType.print()

	// --- containers, PER FAMILY (the pooled row is a mixture — see the header) ----
	rowArr := mkInner("array.inner", buckets["array"], false, true)
	rowSet := mkInner("set.inner", buckets["set"], false, true)
	rowOpt := mkInner("optional.inner", buckets["optional"], false, true)
	rowArr.print()
	rowSet.print()
	rowOpt.print()

	// Map has TWO inner slots and both pass the structural test, so the structural test
	// alone cannot say which is which. The NAME does: UHT names them "<Map>_Key" and
	// "<Map>". Scored as two rows filtered on that observed relation.
	mapFs := buckets["map"]
	rowMap := mkInner("map (either slot)", mapFs, false, false)
	rowMap.note = "two slots pass; identity decided by name below"
	rowMap.print()

	// --- enum: two slots, distinguishable by KIND (FField vs UObject) -------------
	enumFs := buckets["enum"]
	rowEU := mkInner("enum.underlying", enumFs, true, true)
	rowEU.print()
	rowEE := calibRow{label: "enum.enum (UEnum)", n: len(enumFs), scoring: true}
	for _, c := range calibCandidates {
		rowEE.a = append(rowEE.a, scoreTypeSlot(r, x, enumFs, c, true))
	}
	rowEE.winner, rowEE.pass, rowEE.note = pickWinner(rowEE.n, rowEE.a)
	rowEE.print()

	// --- pooled row: report only, and a replication check against the settlement --
	var pooled []uintptr
	for _, fam := range []string{"array", "set", "map", "optional"} {
		pooled = append(pooled, buckets[fam]...)
	}
	rowPool := mkInner("POOLED containers", pooled, false, false)
	rowPool.note = "MIXTURE — never adopt this winner"
	rowPool.print()
	fmt.Printf("  %-22s %6d %11s   <- positive control: this is the OLD tool's read\n",
		"inline @+0x80 (old bug)", len(pooled), pct(scoreInlineOldBug(r, p, pooled), len(pooled)))

	// --- name relations: what each slot calls itself ------------------------------
	fmt.Println("\n  name relation of the accepted target to its outer property (self-labelling):")
	type nrq struct {
		label string
		fs    []uintptr
		off   uintptr
		num   bool
	}
	var mapKeyOff, mapValOff uintptr
	{
		// the two offsets at which map samples structurally pass
		var passing []uintptr
		for i, c := range calibCandidates {
			if rowMap.n > 0 && float64(rowMap.a[i])/float64(rowMap.n) >= 0.90 {
				passing = append(passing, c)
			}
		}
		for _, off := range passing {
			h := nameRelation(r, p, mapFs, off, false)
			rel, cnt, tot := topRelation(h)
			fmt.Printf("    map    @+0x%02X : %-24s %d/%d\n", off, rel, cnt, tot)
			if rel == "<same>" && cnt*10 >= tot*9 {
				mapValOff = off
			}
			if strings.HasPrefix(rel, "<outer>+") && strings.Contains(strings.ToLower(rel), "key") && cnt*10 >= tot*9 {
				mapKeyOff = off
			}
		}
		if len(passing) != 2 {
			fmt.Printf("    ⚠ expected exactly 2 structurally-passing map slots, found %d\n", len(passing))
		}
	}
	for _, q := range []nrq{
		{"array.inner", buckets["array"], rowArr.winner, false},
		{"set.inner", buckets["set"], rowSet.winner, false},
		{"optional.inner", buckets["optional"], rowOpt.winner, false},
		{"enum.underlying", enumFs, rowEU.winner, true},
	} {
		if q.off == 0 {
			continue
		}
		rel, cnt, tot := topRelation(nameRelation(r, p, q.fs, q.off, q.num))
		fmt.Printf("    %-6s @+0x%02X : %-24s %d/%d\n", q.label, q.off, rel, cnt, tot)
	}

	// --- self-check: what IS in the enum underlying slot -------------------------
	//
	// This is deliberately measured with the numeric filter OFF, so it can fail. The
	// extractor's own deref() requires a numeric type, which would make "100 % numeric" a
	// tautology; here we take whatever the slot points at and report its type histogram.
	// Correct offset => ~100 % numeric. The old +0x80 inline read scored ~28.5 % legal.
	fmt.Println("\n  enum UnderlyingProp self-check (numeric filter OFF, so this CAN fail):")
	for _, off := range []uintptr{rowEU.winner, 0x78, oldBuggyInline} {
		if off == 0 {
			continue
		}
		hist := map[string]int{}
		numeric, named, seen := 0, 0, 0
		for _, f := range enumFs {
			var ip uintptr
			if off == oldBuggyInline {
				ip = f + oldBuggyInline // the old tool's INLINE read, reproduced exactly
			} else {
				ip = r.ptr(f + off)
				if ip == 0 || !userspacePtr(ip) {
					continue
				}
			}
			fc := r.ptr(ip + offFFieldClass)
			if fc == 0 {
				continue
			}
			tn := decodeName(r, p, fc+offFFieldClassName)
			if !knownPropTypes[tn] {
				continue
			}
			seen++
			hist[tn]++
			if numericPropTypes[tn] {
				numeric++
			}
			if seen <= calibNameCap && decodeName(r, p, ip+offFFieldName) == "UnderlyingType" {
				named++
			}
		}
		kinds := make([]string, 0, len(hist))
		for k := range hist {
			kinds = append(kinds, k)
		}
		sort.Slice(kinds, func(i, j int) bool { return hist[kinds[i]] > hist[kinds[j]] })
		if len(kinds) > 6 {
			kinds = kinds[:6]
		}
		parts := make([]string, 0, len(kinds))
		for _, k := range kinds {
			parts = append(parts, fmt.Sprintf("%s %d", k, hist[k]))
		}
		tag := fmt.Sprintf("*(f+0x%02X)", off)
		if off == oldBuggyInline {
			tag = "inline@+0x80 (old bug)"
		}
		fmt.Printf("    %-22s legal-typed %d/%d, numeric %s %%, named \"UnderlyingType\" %d  [%s]\n",
			tag, seen, len(enumFs), pct(numeric, len(enumFs)), named, strings.Join(parts, " / "))
	}

	// --- report-only: the optional-null type families at the type winner ---------
	if rowType.pass {
		optFs := buckets["typeopt"]
		hit := scoreTypeSlot(r, x, optFs, rowType.winner, false)
		fmt.Printf("\n  [report only, decides nothing] Byte/Interface/Soft/Weak/Lazy at +0x%02X: %d/%d = %s %%\n",
			rowType.winner, hit, len(optFs), pct(hit, len(optFs)))
		fmt.Println("  Those families may hold a legitimate null, so a miss is uninterpretable and this")
		fmt.Println("  number is EVIDENCE, not a score. Applying the winner to them is an INFERENCE [I].")
	}

	// --- decide -------------------------------------------------------------------
	ok := true
	need := func(rw calibRow) uintptr {
		if !rw.pass {
			ok = false
		}
		return rw.winner
	}
	gOff.typeSlot = need(rowType)
	gOff.arrayInner = need(rowArr)
	gOff.setInner = need(rowSet)
	gOff.optionalInner = need(rowOpt)
	gOff.enumUnderlying = need(rowEU)
	gOff.enumEnum = need(rowEE)
	gOff.mapKey, gOff.mapValue = mapKeyOff, mapValOff
	if mapKeyOff == 0 || mapValOff == 0 || mapKeyOff == mapValOff {
		fmt.Println("\n  ⚠ MAP SLOTS NOT RESOLVED: could not identify a \"<Map>_Key\"-named slot and a")
		fmt.Println("    same-named slot. Refusing to guess which pointer is the key.")
		ok = false
	}

	// --- arm forcings (each bypasses that family's gate — a control arm is defined by
	//     being wrong, so its failure is the point) --------------------------------
	note := func(s string) { gOff.forcedNote = append(gOff.forcedNote, s) }
	switch gOff.arm {
	case "W":
		gOff.arrayInner, gOff.setInner, gOff.optionalInner = 0x78, 0x78, 0x78
		gOff.mapKey, gOff.mapValue = 0x78, 0x80
		note("arm W: containers FORCED to +0x78 uniformly, map value +0x80 — the patch that would have shipped; gate bypassed")
		ok = rowType.pass && rowEU.pass && rowEE.pass
	case "W70":
		gOff.arrayInner, gOff.setInner, gOff.optionalInner = 0x70, 0x70, 0x70
		gOff.mapKey, gOff.mapValue = 0x70, 0x70
		note("arm W70: containers FORCED to +0x70 uniformly — second negative control; gate bypassed")
		ok = rowType.pass && rowEU.pass && rowEE.pass
	case "D":
		gOff.forceArrayDim1 = true
		note("arm D: ArrayDim FORCED to 1 — the +0x30 read is still taken and counted, then discarded")
	case "E":
		gOff.enumUnderlying, gOff.enumEnum = 0x78, 0x80
		note("arm E: enum offsets FORCED to +0x78/+0x80, the settlement's UNMEASURED assumption; gate bypassed")
		ok = rowType.pass && rowArr.pass && rowSet.pass && rowOpt.pass && mapKeyOff != 0 && mapValOff != 0
	}

	// explicit env overrides win over everything, including the arm
	for _, o := range []struct {
		key   string
		field *uintptr
	}{
		{"FK14_OFF_TYPE", &gOff.typeSlot},
		{"FK14_OFF_ARRAY", &gOff.arrayInner},
		{"FK14_OFF_SET", &gOff.setInner},
		{"FK14_OFF_OPTIONAL", &gOff.optionalInner},
		{"FK14_OFF_MAPKEY", &gOff.mapKey},
		{"FK14_OFF_MAPVALUE", &gOff.mapValue},
		{"FK14_OFF_ENUMUNDER", &gOff.enumUnderlying},
		{"FK14_OFF_ENUMENUM", &gOff.enumEnum},
	} {
		if v, okv := envOffset(o.key); okv {
			*o.field = v
			note(fmt.Sprintf("env %s: FORCED +0x%02X (gate bypassed)", o.key, v))
			ok = true
		}
	}
	if os.Getenv("FK14_ARRAYDIM_FORCE1") != "" {
		gOff.forceArrayDim1 = true
		note("env FK14_ARRAYDIM_FORCE1: ArrayDim FORCED to 1")
	}

	fmt.Printf("\n  RESOLVED  type=+0x%02X  array=+0x%02X  set=+0x%02X  optional=+0x%02X  mapKey=+0x%02X  mapValue=+0x%02X  enumUnder=+0x%02X  enumEnum=+0x%02X  arrayDim=+0x%02X\n",
		gOff.typeSlot, gOff.arrayInner, gOff.setInner, gOff.optionalInner,
		gOff.mapKey, gOff.mapValue, gOff.enumUnderlying, gOff.enumEnum, gOff.arrayDim)
	if len(gOff.forcedNote) == 0 {
		fmt.Println("  (no forcings — every offset above was measured on this process, this run)")
	}
	for _, s := range gOff.forcedNote {
		fmt.Println("  ! " + s)
	}
	return ok
}

// printExtractStats dumps every fallback counter. Per the settlement: a run with a silent
// zero everywhere is the no-op tell, so these are printed unconditionally.
func printExtractStats() {
	fmt.Println("\n=== FK-14 extraction counters (all printed; zeros are meaningful) ===")
	fmt.Printf("  properties walked            : %d\n", gStats.propsWalked)
	fmt.Printf("  ArrayDim != 1                : %d of %d properties (%.4f %%)\n",
		gStats.arrayDimNot1, gStats.propsWalked,
		100*float64(gStats.arrayDimNot1)/float64(max1(gStats.propsWalked)))
	fmt.Printf("      The UHT oracle counts 66 such records. Compare the COUNT, not the rate: the\n")
	fmt.Printf("      oracle's 75,907-record population includes UFunction parameters, which this\n")
	fmt.Printf("      walk skips, so the denominators are different populations. A count in the\n")
	fmt.Printf("      dozens with values like 2/3/12/61 is ArrayDim; a count in the thousands, or\n")
	fmt.Printf("      near zero, means +0x%02X is the wrong slot — THE READ VALIDATES ITSELF.\n", gOff.arrayDim)
	fmt.Printf("  ArrayDim out of range        : %d  (coerced to 1)\n", gStats.arrayDimBad)
	fmt.Printf("  inner slot null/unmapped     : %d\n", gStats.innerNilPtr)
	fmt.Printf("  inner rejected: bad type     : %d\n", gStats.innerBadType)
	fmt.Printf("  inner rejected: owner != self: %d\n", gStats.innerBadOwner)
	fmt.Printf("  inner accepted               : %d\n", gStats.innerOK)
	fmt.Printf("  EnumProperty enum resolved   : %d\n", gStats.enumObjResolved)
	fmt.Printf("  EnumProperty enum unlabeled  : %d\n", gStats.enumObjUnlabeled)
}

func max1(n int) int {
	if n < 1 {
		return 1
	}
	return n
}

#!/usr/bin/env python3
"""text_digest.py -- the `.text` digest instrument for this project's shim DLLs.

Every A/B in this project is gated on "diff the `.text` HASH, never the size": `play` and
`play-earlywalk` once shared an identical whole-file AND `.text` size, `botspawn`/`botteam`
share a `.text` size of 182,272 B, and `dismount`/`dismount-podland` share 126,976 B. Docs
quote 16-hex digests for ~60 build variants and treat them as regression gates. Until S136
the RECIPE lived nowhere on disk -- `build.ps1` emits no digest and `verify_dll.py` prints no
section hash -- so every gate check had a hash-METHOD failure mode (method-rules S134-d, where
an inline re-implementation reported a four-way false regression).

=====================================================================================
TWO RECIPES ARE IN USE. BOTH ARE ON DISK. THEY DIFFER ONLY IN THE ALIGNMENT TAIL.  [M]
=====================================================================================

  RAW         sha256( file[PointerToRawData : PointerToRawData + SizeOfRawData] )[:16]
              ON DISK AT:
                configs/fk24-stage.ps1  `Get-TextHash` (the deployed-vs-build staleness gate)
                configs/fk7-ab-run.ps1  `Get-TextHash` -- and it EMITS the value into the A/B
                                        CSV column `probe_text_sha`, so every fk7-ab campaign
                                        row on disk is a RAW digest
              Both PowerShell copies read the section header's `+16` dword (SizeOfRawData) and
              `+20` (PointerToRawData) and hash that whole span.

  VIRTUALSIZE sha256( file[PointerToRawData : PointerToRawData + min(VirtualSize, SizeOfRawData)] )[:16]
              ON DISK AT:
                docs/method-rules.md:213 (S134-d) records this as the recipe of the throwaway
                inline reader, together with the four values it produced; and it is the recipe
                the S135 inline hasher used to produce the bot-arm gates in CLAUDE.md.

THEY INDUCE THE SAME EQUIVALENCE RELATION -- MEASURED, AND IT IS A PROOF, NOT A COINCIDENCE
-------------------------------------------------------------------------------------------
Over all 306 shim DLLs on disk (162 in build/, 144 deployed):

  * the file-alignment tail between VirtualSize and SizeOfRawData is ALL-ZERO in 301 of 301
    non-degenerate files (5 files have VirtualSize == SizeOfRawData and no tail at all);
  * `SizeOfRawData == roundup(VirtualSize, FileAlignment)` in 306 of 306, FileAlignment == 512
    in 306 of 306.

So RAW == VIRTUALSIZE-content followed by a run of zeros whose LENGTH is a function of the
content length. Equal content => equal VirtualSize => equal SizeOfRawData => equal raw bytes,
and different content => different under both. Confirmed empirically: `--dupes` finds the SAME
7 duplicate groups over the SAME 16 artifact names under both recipes.

=> NEITHER RECIPE IS MORE DISCRIMINATING. The choice is purely a bookkeeping convention, and
   the only thing at stake is which recorded gates keep reproducing.

WHICH RECORDED GATES EACH RECIPE REPRODUCES (S137 cross-table; gate corpus = CLAUDE.md +
docs/ + configs/, excluding the S136/S137 recipe-investigation docs that print both columns)
-------------------------------------------------------------------------------------------
  RAW reproduces         51 recorded gate values, across 55 artifacts
  VIRTUALSIZE reproduces  6 recorded gate values (+1 published diagnostic, not a gate)
  both (degenerate file)  1  (`droppod_pe_force`, VirtualSize == SizeOfRawData)

The six VIRTUALSIZE-only values are:
    botspawn            e48c90bc6cf17c93   CLAUDE.md:1125  <- a real shipping gate
    botteam             0c16652dc0338d33   CLAUDE.md:1126  <- a real shipping gate
    play                76e5c1093c390536   docs/method-rules.md:213  (S134-d differential)
    dismount            7fbe025cad6e7ca3   docs/method-rules.md:213  (S134-d differential)
    droppod_pe_cdopoke  93e4b8b7d5c7aac6   docs/method-rules.md:213  (S134-d differential)
    dropplane_b1only    a6d3a70949baec20   docs/method-rules.md:213  (S134-d differential)
Four of the six are S134-d's own BEFORE/AFTER differential values, and all four of those
artifacts ALSO carry a RAW gate in CLAUDE.md that reproduces -- so only TWO shipping gates
(`botspawn`, `botteam`) are exclusively VIRTUALSIZE.
(`botspawn_readonly d96480ad64c1a403` is a VIRTUALSIZE value quoted in CLAUDE.md:1251, but it
is the DIAGNOSTIC S136 printed while explaining that artifact's NEITHER case -- its recorded
gate is `f5f9896feeac45dc`, which neither recipe reproduces. Do not count it as a seventh.)

RECOMMENDATION: RAW IS CANONICAL.
  * it is the recipe both SHIPPED SCRIPTS implement, and the one already serialised into every
    fk7-ab campaign CSV -- i.e. it is the only one with an audit trail;
  * it is 51 gates vs 6, so adopting it costs 6 re-recordings and adopting the other costs 51;
  * `SizeOfRawData`/`PointerToRawData` are the two fields that describe the bytes actually on
    disk, so the digest is "what is in the file", with no derived quantity in the recipe.
The cost of adopting it: `botspawn` and `botteam` must be re-recorded to their RAW values
`1a8fa5fe06f87019` and `160f067d697b545b`, and method-rules.md:213's four values must be
annotated as VIRTUALSIZE (they are already labelled there as a hash-method artifact, so this
is a footnote, not a retraction). This script does NOT edit those files.

RECORDED GATES THAT NEITHER RECIPE REPRODUCES -- these are ARTIFACT changes, not recipe bugs:
    botspawn            ae89d06b91164e5f   CLAUDE.md:1064   (superseded pair, rebuilt)
    botspawn_readonly   f5f9896feeac45dc   CLAUDE.md:1064   (superseded pair, rebuilt)
    botai               c55cb560cc602e31   CLAUDE.md:1124   (S136 rebuilt it; CLAUDE.md:1235
                                                             records the new RAW 5e47c13cf7f0a158)
A digest that reproduces under NEITHER recipe means the binary moved. A digest that reproduces
under the OTHER recipe means your hasher moved. Telling those two apart is the whole point of
printing both columns, and `--verify` labels them MATCH-RAW / MATCH-VSIZE / NEITHER for exactly
that reason.

WHICH TIER A GATE WAS RECORDED AGAINST -- and why `--verify build/` exits 1 today
---------------------------------------------------------------------------------
`build/` and the deployed directory beside it are two tiers on purpose, and they drift (S111
measured 10 drifted of 142). The embedded table is keyed by artifact NAME, so it cannot know
which tier a gate was taken from. MEASURED S137, running `--verify` on each tier separately:

  build/     52 MATCH-RAW  9 MATCH-VSIZE  5 NEITHER
  deployed/   9 MATCH-RAW  1 MATCH-VSIZE  2 NEITHER

The 5 build-tier NEITHERs are gates recorded against the DEPLOYED artifact, which still
matches: `fo` fa184b20934cc4b0, `sp` 4285c0dd22ae9976, `play_novtguard` 7bb7c67e371f3f1e,
`play_testactor` 321c71de3346c205, `play_textpatch` 433cf7d8f6a0770f. So `--verify build/`
exits 1 today for a KNOWN and correct reason -- read the per-file lines, not the exit code
alone, and check the other tier before concluding a binary moved.
The 2 deployed-tier NEITHERs are `play_nopimutex`, whose deployed copy predates the build
copy (vsize 162128 vs 163200) -- ordinary staleness.

DUPLICATE DIGESTS -- `--dupes`, and why it exists
-------------------------------------------------
"An A/B against a copy of itself burns a live run" is a recorded rule in CLAUDE.md, and the
hazard is LIVE. Over all 306 DLLs there are **7 duplicate groups covering 16 artifact names**,
IDENTICAL under both recipes (which is the empirical half of the equivalence argument above):

  expected, by construction (4)
    play_funcswap_one == play_gcroot == play_pres123_gcroot_archived   build.ps1:162
    poolspawn         == poolspawn_cdoctrl                             build.ps1:633 + KPDCDOPOKE default 0
    droppod_pe        == droppod_pe_cdoctrl                            build.ps1:380 + KPDCDOPOKE default 0
    ds_hybrid         == ds_hybrid_spectator                           build.ps1:826-828 says so
  DEGENERATE ARM -- mechanism understood, arm measures NOTHING (1)
    play == play_nopimutex == play_strictroot
  legacy, no build.ps1 variant produces either name (2)
    shim_mirror == shim_watch          (shim_mirror has no .cpp at all; it is a copy)
    loadout_fix_prerenderA == loadout_fix_rt

The `cdoctrl` collisions are FINE: the real A/B pair is `cdopoke` vs `cdoctrl`, and those two
DO differ. The `play` group is not fine -- see DEGENERATE_ARMS below for the measured mechanism
and its positive controls.

USAGE
  python tools/sigbypass-mod/text_digest.py <dll|exe|glob|dir> [...]
  python tools/sigbypass-mod/text_digest.py build/tutorial_launch_*.dll
  python tools/sigbypass-mod/text_digest.py --verify build/ .
  python tools/sigbypass-mod/text_digest.py --dupes build/ .
  python tools/sigbypass-mod/text_digest.py --full --altrecipes build/tutorial_launch_play.dll

  --full          print complete 64-char sha256s instead of the 16-char gates
  --recipe R      raw | vsize | both   (default both -- print both columns)
  --dupes         group by digest and LOUDLY flag any digest shared by differently-named
                  variants. A control arm byte-identical to its treatment is a burned live run.
  --verify[=FILE] compare against recorded gates; reports MATCH-RAW / MATCH-VSIZE / NEITHER.
                  With no FILE, uses the embedded S137 cross-table below. A FILE is
                  `<name> <digest>` per line, `#` comments and blanks ignored.
                  Names match loosely: case-insensitive, `-` == `_`, `tutorial_launch_`
                  prefix optional on either side.
                  ONLY the attached `--verify=FILE` form takes a value: a bare `--verify`
                  followed by a path must never eat that path as its table (argparse
                  `nargs='?'` does exactly that, and it silently parsed a DLL as a digest
                  table on the first run of this script -- hence the manual pre-pass).
  --altrecipes    also print whole-file and `.rdata` digests, as discriminating controls
                  (neither reproduces any recorded gate).

Read-only, stdlib only, no dependencies. Never opens a process, never writes a byte.

EXIT CODES
  0  every file parsed (and, under --verify, every KNOWN gate matched under some recipe)
  1  a file has no .text section, is not a PE, or a --verify gate is NEITHER
  2  bad arguments / nothing to do
"""
import argparse
import collections
import glob
import hashlib
import os
import struct
import sys

GATE_LEN = 16

# The S137 cross-table: every 16-hex token found in CLAUDE.md / docs/ / configs/ that a DLL on
# disk reproduces, tagged with WHICH recipe reproduces it and where it is recorded. Keys are the
# on-disk artifact name minus `tutorial_launch_` and minus the extension, lowercase, `-` -> `_`.
# Generated by joining both digests of all 306 shim DLLs against a scoped token harvest; the
# recipe-investigation docs (next-session-prompt-s136/s137, s136-ai-controller-settled) are
# EXCLUDED from the corpus because they print both columns by construction and would make every
# value "recorded", destroying the discrimination.
KNOWN_GATES = {
    "catalog_store_fix":            [("2b0a5406fc20f0b5", "RAW", "docs/s111-jz-dropped-shipping.md:17")],
    "catalog_store_fix_jzpatch":    [("21e62f50f6d40c8d", "RAW", "docs/s111-jz-dropped-shipping.md:18")],
    "gft_ready_fix":                [("6b2fe2c2a747c19f", "RAW", "docs/s111-FK7-HANDOFF.md:151")],
    "botai":                        [("5e47c13cf7f0a158", "RAW", "CLAUDE.md:1235")],
    "botfight_castalive_dash_mana10_cdocharge1_naturalinput":
                                    [("366e8ef09afa8cb9", "RAW", "docs/s147-natural-input-build-evidence.md")],
    "botfight_bind_only":         [("f7765063941de93a", "RAW", "docs/s149-bind-bootstrap-flight1.md")],
    "botfight_damage_self_cal":    [("7c6be77666e2083d", "RAW", "docs/s148-self-damage-build-evidence.md"),
                                     ("8549bb0acd8d785d", "RAW", "docs/s148-self-damage-flight2.md"),
                                     ("1be00cb993cab717", "RAW", "docs/s148-self-damage-flight3.md"),
                                     ("c46fb598d0850f24", "RAW", "docs/s148-self-damage-flight4.md")],
    "botspawn":                     [("e48c90bc6cf17c93", "VSIZE", "CLAUDE.md:1125")],
    "botspawn_readonly":            [("319ac875af229f46", "RAW", "CLAUDE.md:1250"),
                                     ("d96480ad64c1a403", "VSIZE", "CLAUDE.md:1251 (diagnostic, not a gate)")],
    "botteam":                      [("0c16652dc0338d33", "VSIZE", "CLAUDE.md:1126")],
    "cheatmgr":                     [("7f89f671592824ac", "RAW", "docs/fk22-dropphase-reachability.md:1404")],
    "cheatmgr_any_verify":          [("4507e376d099a3b5", "RAW", "CLAUDE.md:2918")],
    "dismount":                     [("53483e6181bb3583", "RAW", "CLAUDE.md:2058"),
                                     ("7fbe025cad6e7ca3", "VSIZE", "docs/method-rules.md:213")],
    "dismount_appendonly":          [("b3b932579a8a6c07", "RAW", "docs/s132-dismount-settled.md:571")],
    "dismount_landstart":           [("0d5fa554edac53c5", "RAW", "CLAUDE.md:2059")],
    "dismount_podland":             [("6019eb5fb1122617", "RAW", "docs/s132-dismount-settled.md:572")],
    "dismount_readonly":            [("16c00d0a16e5b496", "RAW", "docs/s132-dismount-settled.md:570")],
    "dropmarkers":                  [("d3c07c32f7a699eb", "RAW", "docs/fk22-dropphase-reachability.md:1409")],
    "dropmarkers_gateonly":         [("778990b2e3379ade", "RAW", "docs/fk22-dropphase-reachability.md:1411")],
    "dropmarkers_nogat":            [("25ca6075bf015e84", "RAW", "docs/fk22-dropphase-reachability.md:1415")],
    "dropmarkers_norestore":        [("7ac4bf24298c53d9", "RAW", "docs/fk22-dropphase-reachability.md:1414")],
    "dropmarkers_outparm":          [("b80c7455acd8df51", "RAW", "docs/fk22-dropphase-reachability.md:1412")],
    "dropmarkers_readonly":         [("74857749ef264d1e", "RAW", "docs/fk22-dropphase-reachability.md:1410")],
    "dropmarkers_s125repro":        [("3c00d10be6369382", "RAW", "docs/fk22-dropphase-reachability.md:1413")],
    "dropplane":                    [("a0f6f2e54b5ac01e", "RAW", "docs/fk22-dropphase-reachability.md:1400")],
    "dropplane_b1only":             [("5b4467b0105dec1a", "RAW", "CLAUDE.md:2221"),
                                     ("a6d3a70949baec20", "VSIZE", "docs/method-rules.md:213")],
    "dropplane_handler":            [("f88918f0935d3f44", "RAW", "docs/fk22-dropphase-reachability.md:1401")],
    "droppod":                      [("9e8148635b2ddcf5", "RAW", "docs/fk22-dropphase-reachability.md:1937")],
    "droppod_newest":               [("54445f1330ed2b4a", "RAW", "docs/fk22-dropphase-reachability.md:1940")],
    "droppod_noprespawn":           [("a08f99d8632a88dd", "RAW", "docs/fk22-dropphase-reachability.md:1939")],
    "droppod_pe":                   [("61fd0745c23e89f0", "RAW", "CLAUDE.md:1264")],
    "droppod_pe_cdoctrl":           [("61fd0745c23e89f0", "RAW", "CLAUDE.md:1264")],
    "droppod_pe_cdopoke":           [("249a3cd2190eb334", "RAW", "CLAUDE.md:2221"),
                                     ("93e4b8b7d5c7aac6", "VSIZE", "docs/method-rules.md:213")],
    "droppod_pe_ctrl":              [("ac5b4584066cd927", "RAW", "docs/fk22-dropphase-reachability.md:1941")],
    "droppod_pe_force":             [("d895bccb2ab8ba36", "RAW", "docs/fk22-dropphase-reachability.md:1943")],
    "droppod_readonly":             [("9fd364cbc16f9aaf", "RAW", "docs/fk22-dropphase-reachability.md:1938")],
    "fo":                           [("fa184b20934cc4b0", "RAW", "docs/next-session-prompt-s130.md:98")],
    "phaseladder":                  [("8d1821f8c0ddbd63", "RAW", "docs/fk22-dropphase-reachability.md:1403")],
    "phaseladder_a5":               [("ef0615e76343bce0", "RAW", "docs/fk22-dropphase-reachability.md:1177")],
    "play":                         [("9bc10a4552c596e1", "RAW", "CLAUDE.md:1262"),
                                     ("76e5c1093c390536", "VSIZE", "docs/method-rules.md:213")],
    "play_a827ef9_archived":        [("513c6277c3ae88f3", "RAW", "CLAUDE.md:556")],
    "play_atlanding":               [("0e816d359e5d09c5", "RAW", "CLAUDE.md:2158")],
    "play_atlanding_walk":          [("944a27728053359e", "RAW", "CLAUDE.md:2165")],
    "play_funcswap_one":            [("5151621d2154e454", "RAW", "CLAUDE.md:3456")],
    "play_gcroot":                  [("5151621d2154e454", "RAW", "CLAUDE.md:3456")],
    "play_nopimutex":               [("9bc10a4552c596e1", "RAW", "CLAUDE.md:1262"),
                                     ("76e5c1093c390536", "VSIZE", "docs/method-rules.md:213")],
    "play_novtguard":               [("7bb7c67e371f3f1e", "RAW", "docs/fk24-writer-probe.md:194")],
    "play_pres123_gcroot_archived": [("5151621d2154e454", "RAW", "CLAUDE.md:3456")],
    "play_strictroot":              [("9bc10a4552c596e1", "RAW", "CLAUDE.md:1262"),
                                     ("76e5c1093c390536", "VSIZE", "docs/method-rules.md:213")],
    "play_testactor":               [("321c71de3346c205", "RAW", "docs/s108-fk24-instrument-corrected.md:288")],
    "play_textpatch":               [("433cf7d8f6a0770f", "RAW", "CLAUDE.md:3461")],
    "poolspawn":                    [("85f3cee44c31b1cd", "RAW", "CLAUDE.md:1263")],
    "poolspawn_cdoctrl":            [("85f3cee44c31b1cd", "RAW", "CLAUDE.md:1263")],
    "poolspawn_cdopoke":            [("efe8db553bf511ba", "RAW", "CLAUDE.md:2383")],
    "poolspawn_collmatch":          [("365fce2091dbddb0", "RAW", "docs/fk22-dropphase-reachability.md:2281")],
    "poolspawn_compwco":            [("6ed1a3c3d0165e13", "RAW", "docs/fk22-dropphase-reachability.md:2282")],
    "poolspawn_ctrl":               [("87e5fa023e0ec999", "RAW", "docs/fk22-dropphase-reachability.md:2276")],
    "poolspawn_deferred":           [("545cb94912e8c8fa", "RAW", "docs/fk22-dropphase-reachability.md:2277")],
    "poolspawn_nondef":             [("8f1e776f8e78558c", "RAW", "docs/fk22-dropphase-reachability.md:2278")],
    "poolspawn_readonly":           [("68a369686870185a", "RAW", "docs/fk22-dropphase-reachability.md:2275")],
    "poolspawn_ref":                [("151af52792cf9de8", "RAW", "docs/fk22-dropphase-reachability.md:2279")],
    "rideable":                     [("dd2281adce965add", "RAW", "CLAUDE.md:2280")],
    "sp":                           [("4285c0dd22ae9976", "RAW", "configs/fk24-stage.ps1:70")],
}

# Recorded gates that reproduce under NEITHER recipe: the ARTIFACT changed. Printed by --verify
# so a successor does not re-derive the question. Keys are norm_key()s.
SUPERSEDED = {
    "botspawn":          [("ae89d06b91164e5f", "CLAUDE.md:1064 -- superseded pair, rebuilt")],
    "botspawn_readonly": [("f5f9896feeac45dc", "CLAUDE.md:1064 -- superseded pair, rebuilt")],
    "botai":             [("c55cb560cc602e31", "CLAUDE.md:1124 -- S135 build, rebuilt in S136")],
}

# Duplicate groups that are CORRECT BY CONSTRUCTION, from build.ps1's own flag table. A group
# listed here is expected to collapse; anything else is a hazard. Sets of norm_key()s.
EXPECTED_DUPES = [
    (frozenset({"play_funcswap_one", "play_gcroot", "play_pres123_gcroot_archived"}),
     "CLAUDE.md asserts play-gcroot reproduces 5151621d2154e454 exactly; build.ps1:162 records "
     "that play-gcroot carried IDENTICAL flags to play"),
    (frozenset({"poolspawn", "poolspawn_cdoctrl"}),
     "build.ps1:633 -- cdoctrl is plain poolspawn + -DKPDCDOPOKE=0, and KPDCDOPOKE DEFAULTS to 0 "
     "(tutorial_launch.cpp:9626). The real A/B pair is cdopoke vs cdoctrl, which DO differ."),
    (frozenset({"droppod_pe", "droppod_pe_cdoctrl"}),
     "build.ps1:380 -- same KPDCDOPOKE=0 default as above. cdopoke vs cdoctrl DO differ."),
    (frozenset({"ds_hybrid", "ds_hybrid_spectator"}),
     "build.ps1:826-828 states it: KMODE defaults to MODE_SPECTATOR_CAM, so the plain build and "
     "'spectator' are the same binary"),
]

# Groups whose MECHANISM is understood but which are still USELESS AS ARMS: the knob the variant
# sets guards code that is not linked into that run mode, so the "control" is the treatment.
# `static const int kRunMode = KRUNMODE` (tutorial_launch.cpp:173) makes every `kRunMode==RM_x`
# test a compile-time constant, so the unreached arms are folded and /OPT:REF drops their callees.
DEGENERATE_ARMS = [
    (frozenset({"play", "play_nopimutex"}),
     "KPIMUTEX guards HookLock(), reached only via InstallHook(). RM_PLAY has not installed the "
     "PI hook since S112 (KFUNCSWAP), so InstallHook is dead-stripped and KPIMUTEX is inert. "
     "MEASURED with a passing positive control: the literal `SuperviveMissionsPIHook` is present "
     "in exactly the 11 of 87 tutorial_launch variants whose run mode calls InstallHook "
     "(fo, sp, puppet, topdowncam, drivechain, makemesh, play_textpatch, ...) and absent from "
     "play, play_nopimutex and play_strictroot alike."),
    (frozenset({"play", "play_strictroot"}),
     "KGCROOTSTRICT selects between two arms of the root-bit corroboration, and that whole "
     "function is only reached when KGCROOT != 0 -- which has DEFAULTED TO 0 since S123 "
     "(tutorial_launch.cpp:1532). MEASURED with a passing positive control: the label literal "
     "`FREQ` is present in play_gcroot (KGCROOT=1) and absent from both play and "
     "play_strictroot. So this control arm has been degenerate since S123."),
]


def norm_key(name):
    """Loose artifact key: case-insensitive, `-` == `_`, optional tutorial_launch_ prefix."""
    k = os.path.basename(name)
    for ext in (".dll", ".exe"):
        if k.lower().endswith(ext):
            k = k[: -len(ext)]
            break
    k = k.lower().replace("-", "_")
    if k.startswith("tutorial_launch_"):
        k = k[len("tutorial_launch_"):]
    return k


def sections(data):
    """[(name, VirtualSize, VirtualAddress, SizeOfRawData, PointerToRawData), ...].

    Raises ValueError on anything that is not a PE -- a wrong file type must be a loud error,
    never a silently-empty digest.
    """
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ValueError("not a PE (no MZ signature)")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if len(data) < pe + 24 or data[pe:pe + 4] != b"PE\x00\x00":
        raise ValueError("not a PE (no PE signature at e_lfanew)")
    nsec, = struct.unpack_from("<H", data, pe + 6)
    optsz, = struct.unpack_from("<H", data, pe + 20)
    tbl = pe + 24 + optsz
    out = []
    for i in range(nsec):
        b = tbl + i * 40
        if b + 40 > len(data):
            raise ValueError("truncated section table")
        nm = data[b:b + 8].rstrip(b"\x00").decode("latin1")
        vsz, va, rsz, raw = struct.unpack_from("<IIII", data, b + 8)
        out.append((nm, vsz, va, rsz, raw))
    return out


def section_raw(data, secs, want):
    """(raw bytes, VirtualSize, SizeOfRawData, PointerToRawData) or None if absent."""
    for nm, vsz, va, rsz, raw in secs:
        if nm == want:
            if raw + rsz > len(data):
                raise ValueError("%s raw range %#x+%#x runs past EOF (%d bytes)"
                                 % (want, raw, rsz, len(data)))
            return data[raw:raw + rsz], vsz, rsz, raw
    return None


def text_digest(path):
    """BOTH recipes for one PE, plus the fields that distinguish them.

    `degenerate` means VirtualSize == SizeOfRawData: there is no alignment tail, so the two
    recipes hash the SAME BYTES and that file can never discriminate between them.
    """
    with open(path, "rb") as f:
        data = f.read()
    secs = sections(data)
    hit = section_raw(data, secs, ".text")
    if hit is None:
        names = ", ".join(s[0] for s in secs) or "<none>"
        raise ValueError("no .text section (sections present: %s)" % names)
    body, vsz, rsz, raw = hit
    trunc = data[raw:raw + min(vsz, rsz)]
    tail = data[raw + min(vsz, rsz):raw + rsz]
    return dict(raw_digest=hashlib.sha256(body).hexdigest(),
                vs_digest=hashlib.sha256(trunc).hexdigest(),
                rawsize=rsz, vsize=vsz, rawptr=raw, filesize=len(data),
                degenerate=(vsz == rsz), padlen=len(tail),
                pad_all_zero=(not tail or set(tail) == {0}),
                secnames=[s[0] for s in secs], data=data, secs=secs)


def alt_recipes(r):
    """Discriminating controls: neither reproduces any recorded gate."""
    data, secs = r["data"], r["secs"]
    out = [("wholefile", hashlib.sha256(data).hexdigest()[:GATE_LEN])]
    rd = section_raw(data, secs, ".rdata")
    out.append((".rdata", hashlib.sha256(rd[0]).hexdigest()[:GATE_LEN] if rd else "-"))
    return out


def expand(args):
    """Files, globs and directories -> sorted, de-duplicated file list."""
    out = []
    for a in args:
        if os.path.isdir(a):
            hits = sorted(glob.glob(os.path.join(a, "*.dll")) +
                          glob.glob(os.path.join(a, "*.exe")))
        else:
            hits = sorted(glob.glob(a))
            if not hits and os.path.exists(a):
                hits = [a]                # a literal path containing glob metacharacters
        if not hits:
            print("  !! no match: %s" % a, file=sys.stderr)
        out.extend(hits)
    seen, uniq = set(), []
    for p in out:
        rp = os.path.normcase(os.path.abspath(p))
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    return uniq


def load_table(path):
    """`<name> <digest>` per line -> {key: [(digest, "FILE", src)]}; `#` comments ignored."""
    tbl = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.replace(",", " ").split()
            if len(parts) < 2:
                print("  !! %s:%d: expected `<name> <digest>`" % (path, lineno), file=sys.stderr)
                continue
            tbl.setdefault(norm_key(parts[0]), []).append(
                (parts[1].strip().lower(), "FILE", "%s:%d" % (os.path.basename(path), lineno)))
    return tbl


def split_verify(argv):
    """Pull --verify / --verify=FILE out of argv BEFORE argparse sees it.

    argparse's nargs='?' consumes the next separate token, so a bare `--verify a.dll` parses
    a.dll as the digest TABLE and then measures nothing. Only the attached form may carry a
    value. Returns (rest, verify) where verify is None | "" (embedded) | path.
    """
    rest, verify = [], None
    for tok in argv:
        if tok == "--verify":
            verify = ""
        elif tok.startswith("--verify="):
            verify = tok.split("=", 1)[1]
        else:
            rest.append(tok)
    return rest, verify


def measure(files):
    """[(path, result|None, error|None)] -- parse every file once, share it across the modes."""
    out = []
    for p in files:
        try:
            out.append((p, text_digest(p), None))
        except (ValueError, OSError) as e:
            out.append((p, None, str(e)))
    return out


def build_variant_names(script_dir):
    """Lowercased text of build.ps1, or None. Used ONLY to LABEL a duplicate group.

    A duplicate between two names build.ps1 does not produce is a stale legacy copy, not a
    live A/B hazard -- `shim_mirror` has no .cpp at all and is a copy of an older
    `shim_watch` build. Deriving that from build.ps1 rather than hardcoding a whitelist means
    the label cannot go stale when a variant is added or removed (S133-e: when a record can
    go stale, derive the answer from the artifacts).
    """
    p = os.path.join(script_dir, "build.ps1")
    try:
        return open(p, "r", encoding="utf-8", errors="replace").read().lower()
    except OSError:
        return None


def report_dupes(measured, recipe, buildps1=None):
    """Group by digest; flag any digest shared by DIFFERENTLY-NAMED variants.

    build/ and deployed/ copies of one artifact sharing a digest is the normal, desired case
    and is NOT a hazard -- grouping is by artifact NAME, so those collapse silently.
    """
    per_recipe = {}
    for key, label in (("raw_digest", "RAW"), ("vs_digest", "VIRTUALSIZE")):
        if recipe == "raw" and key != "raw_digest":
            continue
        if recipe == "vsize" and key != "vs_digest":
            continue
        hazards = legacy = degen = 0
        groups = collections.defaultdict(set)
        for p, r, err in measured:
            if r:
                groups[r[key][:GATE_LEN]].add(norm_key(p))
        dup = {d: sorted(v) for d, v in groups.items() if len(v) > 1}
        print("== duplicate groups under %s: %d groups over %d artifact names =="
              % (label, len(dup), sum(len(v) for v in dup.values())))
        for d, names in sorted(dup.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            why = None
            for expected, reason in EXPECTED_DUPES:
                if set(names) <= expected:
                    why = reason
                    break
            if why:
                print("  %s  %-18s (%d)  %s" % (d, "expected", len(names), " | ".join(names)))
                print("      reason: %s" % why)
                continue
            hits = [(reason, sorted(pair & set(names)))
                    for pair, reason in DEGENERATE_ARMS if len(pair & set(names)) > 1]
            if hits:
                degen += 1
                print("  %s  %-18s (%d)  %s"
                      % (d, "DEGENERATE ARM", len(names), " | ".join(names)))
                for reason, pair in hits:
                    print("      %s: %s" % (" == ".join(pair), reason))
                print("      => the knob is inert in this run mode; the arm measures NOTHING. "
                      "Do not fly it.")
                continue
            # Is either name something build.ps1 actually produces? If not, it is a legacy
            # copy rather than a live A/B arm.
            live = None
            if buildps1 is not None:
                live = any(n in buildps1 or n.replace("_", "-") in buildps1 for n in names)
            if live is False:
                legacy += 1
                print("  %s  %-18s (%d)  %s" % (d, "legacy", len(names), " | ".join(names)))
                print("      no build.ps1 variant produces either name -- stale copies, not a "
                      "live A/B pair. Verify before reusing either as an arm.")
                continue
            hazards += 1
            print("  %s  %-18s (%d)  %s" % (d, "*** HAZARD ***", len(names), " | ".join(names)))
            print("      A CONTROL ARM BYTE-IDENTICAL TO ITS TREATMENT IS A BURNED LIVE RUN.")
            print("      Check build.ps1's flags for these variants and the #ifdef defaults")
            print("      they select -- a knob whose default already equals the arm's value")
            print("      compiles to the same bytes and the A/B measures nothing.")
        print("   %s: %d HAZARD, %d DEGENERATE ARM, %d legacy, %d expected"
              % (label, hazards, degen, legacy, len(dup) - hazards - degen - legacy))
        per_recipe[label] = hazards
        print()
    if buildps1 is None:
        print("   (build.ps1 not found beside this script -- every unexplained group is shown "
              "as a HAZARD, including legacy copies)")
    for label, n in per_recipe.items():
        if n:
            print("!! %s: %d duplicate group(s) are NOT explained by build.ps1 -- treat as hazards"
                  % (label, n))
    return max(per_recipe.values()) if per_recipe else 0


def main():
    argv, verify = split_verify(sys.argv[1:])
    ap = argparse.ArgumentParser(
        prog="text_digest.py",
        description="`.text` digests for this project's shim DLLs, under BOTH recipes in use: "
                    "RAW (PointerToRawData..+SizeOfRawData -- what fk24-stage.ps1 and "
                    "fk7-ab-run.ps1 implement, RECOMMENDED) and VIRTUALSIZE "
                    "(..+min(VirtualSize,SizeOfRawData) -- method-rules.md:213 / the S135 "
                    "inline hasher). See the module docstring for why they are equivalent.",
        epilog="Read-only, stdlib only.")
    ap.add_argument("paths", nargs="*", help="PE files, globs, or directories")
    ap.add_argument("--full", action="store_true",
                    help="print complete 64-char sha256s instead of the 16-char gates")
    ap.add_argument("--recipe", choices=("raw", "vsize", "both"), default="both",
                    help="which column(s) to print (default: both)")
    ap.add_argument("--dupes", action="store_true",
                    help="group by digest and flag digests shared by differently-named variants")
    ap.add_argument("--verify", action="store_true",
                    help="compare against recorded gates -> MATCH-RAW / MATCH-VSIZE / NEITHER; "
                         "--verify=FILE uses a table file (handled before argparse -- only the "
                         "attached form takes a value)")
    ap.add_argument("--altrecipes", action="store_true",
                    help="also print whole-file and .rdata digests, as controls")
    a = ap.parse_args(argv)
    a.verify = verify

    if not a.paths:
        ap.print_help()
        return 2
    files = expand(a.paths)
    if not files:
        print("nothing to do", file=sys.stderr)
        return 2

    measured = measure(files)
    rc = 0

    table = None
    if a.verify is not None:
        table = load_table(a.verify) if a.verify else {k: list(v) for k, v in KNOWN_GATES.items()}
        print("# verifying against %s (%d artifact keys, %d recorded values)"
              % (a.verify if a.verify else "the embedded S137 cross-table",
                 len(table), sum(len(v) for v in table.values())))

    print("# RAW   = sha256(.text[PointerToRawData : +SizeOfRawData])%s"
          % ("" if a.full else "[:%d]" % GATE_LEN))
    print("#         configs/fk24-stage.ps1 Get-TextHash; configs/fk7-ab-run.ps1 Get-TextHash "
          "(-> CSV probe_text_sha)   <- RECOMMENDED CANONICAL")
    print("# VSIZE = sha256(.text[PointerToRawData : +min(VirtualSize,SizeOfRawData)])%s"
          % ("" if a.full else "[:%d]" % GATE_LEN))
    print("#         docs/method-rules.md:213 (S134-d inline reader) / the S135 inline hasher")
    print()

    width = max(len(os.path.basename(p)) for p in files)
    n_ok = n_raw = n_vs = n_neither = n_unknown = n_degen = n_padnz = 0

    for p, r, err in measured:
        name = os.path.basename(p)
        if err:
            print("%-*s  ** %s" % (width, name, err))
            rc = 1
            continue
        n_ok += 1
        if r["degenerate"]:
            n_degen += 1
        if not r["pad_all_zero"]:
            n_padnz += 1
        cut = None if a.full else GATE_LEN
        cols = []
        if a.recipe in ("raw", "both"):
            cols.append("RAW=%s" % r["raw_digest"][:cut])
        if a.recipe in ("vsize", "both"):
            cols.append("VSIZE=%s" % r["vs_digest"][:cut])
        line = "%-*s  %s  rawsize=%d vsize=%d pad=%d%s" % (
            width, name, "  ".join(cols), r["rawsize"], r["vsize"], r["padlen"],
            "  DEGENERATE(recipes identical)" if r["degenerate"] else "")
        if table is not None:
            k = norm_key(name)
            ents = table.get(k)
            if not ents:
                line += "   (no recorded gate)"
                n_unknown += 1
            else:
                verdicts = []
                any_match = False
                for want, rec, src in ents:
                    n = len(want)
                    if r["raw_digest"][:n] == want:
                        v, any_match = "MATCH-RAW  ", True
                    elif r["vs_digest"][:n] == want:
                        v, any_match = "MATCH-VSIZE", True
                    else:
                        v = "NEITHER    "
                    verdicts.append("%s %s [recorded-as:%s] (%s)" % (v, want, rec, src))
                    if v.strip() == "MATCH-RAW":
                        n_raw += 1
                    elif v.strip() == "MATCH-VSIZE":
                        n_vs += 1
                    else:
                        n_neither += 1
                pad = "\n%-*s     " % (width, "")
                line += pad + pad.join(verdicts)
                if not any_match:
                    rc = 1
                for sup, why in SUPERSEDED.get(k, []):
                    line += pad + "SUPERSEDED  %s (%s) -- reproduces under neither recipe" % (sup, why)
        print(line)
        if a.altrecipes:
            print("%-*s     control: %s" % (width, "", "  ".join(
                "%s=%s" % (nm, v) for nm, v in alt_recipes(r))))

    print()
    print("parsed %d file(s); %d degenerate (VirtualSize == SizeOfRawData -> the two recipes are "
          "the same bytes and cannot discriminate)" % (n_ok, n_degen))
    if n_padnz:
        print("!! %d file(s) have a NON-ZERO .text alignment tail -- the equivalence argument in "
              "the docstring assumed all-zero padding; RE-CHECK IT." % n_padnz)
    elif n_ok:
        print("all alignment tails all-zero => RAW == VSIZE-content + deterministic zero pad, so "
              "the two recipes induce the SAME equivalence relation")

    if table is not None:
        print("verify: %d MATCH-RAW  %d MATCH-VSIZE  %d NEITHER  %d file(s) with no recorded gate"
              % (n_raw, n_vs, n_neither, n_unknown))
        seen = {norm_key(p) for p in files}
        missing = sorted(set(table) - seen)
        if missing:
            shown = missing[:12]
            print("gates not exercised by these paths (%d): %s%s"
                  % (len(missing), ", ".join(shown),
                     " ... +%d more" % (len(missing) - len(shown)) if len(missing) > len(shown) else ""))

    if a.dupes:
        print()
        # Hazards are reported loudly but do not change the exit code: a duplicate is a design
        # question about build.ps1's flags, not a parse failure or a broken gate.
        report_dupes(measured, a.recipe,
                     build_variant_names(os.path.dirname(os.path.abspath(__file__))))
    return rc


if __name__ == "__main__":
    sys.exit(main())

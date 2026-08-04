#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
name_addrs.py -- validate + name every project-recorded code address using strxref.

Reads  index/harvest.json      (from harvest_addrs.py)
Writes docs/symbols.csv        (the symbol database)
       index/symbols.json      (same, structured, for tooling)

For each recorded RVA it establishes, BY MEASUREMENT:
  * which section it is in, and whether its 4 KB page is decrypted in the dump
  * the containing function entry (strxref func_of, MED tier) and the offset into it
  * every string that function references
and then produces, BY INFERENCE (labelled as such):
  * proposed_name        -- from the strings, ranked by how diagnostic each string is
  * verdict              -- does the string evidence agree with what the record claims?

VERDICTS (all measured except where noted)
  ENTRY-OK        recorded RVA is itself a function entry
  INTERIOR        recorded RVA is inside a function -- expected for patch/gate sites,
                  a WARNING for anything the record calls a call target
  NOT-CODE        recorded RVA is not in .text (vtable / CDO / data pointer)
  UNVERIFIABLE    recorded RVA is in .text but its page is all-zero in this dump
                  (never decrypted) -- absence of evidence, not evidence of absence
  NO-ENTRY        in a decrypted page but no function entry at/before it

  name check:  AGREES / DISAGREES / NO-NAME-EVIDENCE / NO-RECORDED-NAME
"""

import bisect
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strxref                                                 # noqa: E402

ROOT = r"G:\git\Supervive Revival Project"
HARVEST = os.path.join(HERE, "index", "harvest.json")
OUT_CSV = os.path.join(ROOT, "docs", "symbols.csv")
OUT_JSON = os.path.join(HERE, "index", "symbols.json")

PAGE = 0x1000

QUALIFIED = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*::[A-Za-z_~][A-Za-z0-9_]*$")
HAS_QUAL = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{2,})::([A-Za-z_~][A-Za-z0-9_]{2,})")
IDENT_ONLY = re.compile(r"^[A-Z][A-Za-z0-9_]{4,}$")
CPPFILE = re.compile(r"([A-Za-z0-9_]+)\.(?:cpp|h|inl)$", re.I)
WORDS = re.compile(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]+|[a-z0-9]+")

GENERIC_WORDS = set("""get set is has on new old init the a of to and or for with from by
loki u a f s bp wbp b p c d e t k obj object class name id ptr fn func value data type
enum struct array map list item info state mode flags flag num count index idx size len
error warning log verbose display fatal true false null none void int32 int64 uint8 float
double string text str name""".split())


def split_words(s):
    return [w.lower() for w in WORDS.findall(s)]


def symbol_shaped(t):
    """Is this token plausibly a recorded FUNCTION name?

    Measured need: the raw hint ranking happily returned ALL-CAPS log markers
    ('REJECT', 'SCAN', 'MISS', 'BAIL', 'ZEROES', 'INSTRUCTION') and shim-local
    variable names ('keepStub', 'modBase', 'stockRva', 'kKeepRetRva') as the
    "recorded name", which then manufactured ~20 bogus DISAGREES verdicts.
    A name is symbol-shaped iff it is qualified, or it is UpperCamelCase.
    """
    if "::" in t:
        return True
    if not t[:1].isupper():
        return False                       # lowerCamel / k-prefixed => local var
    if not any(c.islower() for c in t):
        return False                       # ALL-CAPS => log marker
    return any(c.isupper() for c in t[1:]) or len(t) >= 8


def is_zero_page(d, rva):
    p = rva & ~(PAGE - 1)
    return d[p:p + PAGE] == b"\0" * PAGE


def sec_of(idx, rva):
    for s in idx.sections:
        name, va, vs = s[0], s[1], s[2]
        if va <= rva < va + vs:
            return name
    return "?"


# --------------------------------------------------------------------------
# how diagnostic is a string, as a name for the function that references it?
# --------------------------------------------------------------------------
def str_score(txt, nfuncs):
    """nfuncs = how many distinct functions reference this string (rarity)."""
    t = txt.strip()
    s = 0
    if QUALIFIED.match(t):
        s = 100
    elif HAS_QUAL.search(t):
        s = 78
    elif IDENT_ONLY.match(t):
        s = 62
    elif CPPFILE.search(t):
        s = 46
    elif "%" in t and len(t) > 12:
        s = 34
    elif len(t) > 8:
        s = 18
    else:
        s = 6
    # rarity: a string only this function touches is far more diagnostic
    if nfuncs == 1:
        s += 22
    elif nfuncs == 2:
        s += 10
    elif nfuncs > 8:
        s -= 25
    if len(t) > 160:
        s -= 15
    return s


def propose_name(refs_txt, nfunc_map):
    """refs_txt: [(sidx, text)]. Returns (name, confidence, why, cls) -- INFERRED."""
    if not refs_txt:
        return "", "", "", ""
    scored = sorted(((str_score(t, nfunc_map.get(si, 1)), si, t) for si, t in refs_txt),
                    reverse=True)

    # 1. a dominant Class::Method family -- strongest possible evidence.
    #    CAVEAT, measured: a '&Class::Method' literal is a DELEGATE BINDING
    #    (__FUNCTION__ of the bound callback), so it names the class reliably but
    #    names the ENCLOSING function only if the enclosing function IS that
    #    method.  0x587BE90 is the proof: it is UPartyModel::SetParty and the only
    #    string it touches is '&UPartyModel::OnMemberXPBoostUpdated'.  So the
    #    class is promoted to HIGH and the method is demoted whenever every
    #    qualified hit is '&'-prefixed.
    fam, amp = Counter(), Counter()
    for _s, si, t in scored:
        m = HAS_QUAL.search(t)
        if m and nfunc_map.get(si, 1) <= 6:
            fam[(m.group(1), m.group(2))] += 1
            if t.lstrip().startswith("&") or ("&" + m.group(1)) in t:
                amp[(m.group(1), m.group(2))] += 1
    if fam:
        (cls, meth), n = fam.most_common(1)[0]
        tot = sum(fam.values())
        all_amp = all(amp.get(k, 0) == v for k, v in fam.items())
        if all_amp:
            return ("%s::<binds %s>" % (cls, meth), "CLASS-ONLY",
                    "all %d qualified refs are &delegate literals -- class certain, "
                    "method NOT the enclosing fn" % tot, cls)
        conf = "HIGH" if (n >= 2 or tot == n) else "MED"
        return "%s::%s" % (cls, meth), conf, "%d/%d qualified-name refs" % (n, tot), cls

    # 2. a single rare identifier string
    top = scored[0]
    if top[0] >= 70:
        return top[2].strip(), "MED", "rare identifier string, score %d" % top[0], ""

    # 3. shared token across several rare strings -> subsystem, not exact name
    tok = Counter()
    for s, si, t in scored[:14]:
        if nfunc_map.get(si, 1) > 6:
            continue
        for w in set(split_words(t)):
            if w not in GENERIC_WORDS and len(w) > 3:
                tok[w] += 1
    if tok:
        w, n = tok.most_common(1)[0]
        if n >= 3:
            return "<%s-related>" % w, "LOW", "%d refs share token %r" % (n, w), ""
    if top[0] >= 40:
        return top[2].strip()[:60], "LOW", "best string, score %d" % top[0], ""
    return "", "LOW", "no diagnostic string", ""


# --------------------------------------------------------------------------
def main():
    idx = strxref.Index.load(strxref.INDEX_PATH)
    d = idx._dump()
    with open(HARVEST, encoding="utf-8") as f:
        H = json.load(f)

    # UE reflection symbols (uereflect.py): 16,998 Z_Construct_UFunction stubs,
    # each name independently verified through the FFunctionParams chain, and the
    # whole table cross-checked against 1,557 live-captured FunctionFlags.
    UE = {}
    up = os.path.join(HERE, "index", "uesymbols.json")
    if os.path.exists(up):
        with open(up, encoding="utf-8") as f:
            UE = {int(k, 16): v for k, v in json.load(f)["symbols"].items()}
    ue_rvas = sorted(UE)

    # how many DISTINCT functions reference each string (rarity denominator)
    nfunc_map = defaultdict(set)
    for i in range(len(idx.rf_site)):
        b, _e = strxref.true_func(idx.rf_site[i])
        if b is None:
            b = idx.func_of(idx.rf_site[i])[0]
        nfunc_map[idx.rf_str[i]].add(b)
    nfunc_map = {k: len(v) for k, v in nfunc_map.items()}

    # data-driven generic-hint filter: a hint token attached to MANY different
    # addresses is project vocabulary, not that address's name.
    df = Counter()
    for e in H:
        seen = set()
        for c in e["ctx"]:
            seen.update(c["hints"])
        df.update(seen)
    NGENERIC = 25

    rows = []
    for e in H:
        rva = e["rva"]
        sec = sec_of(idx, rva)
        in_text = idx.text_va <= rva < idx.text_end

        # ---- recorded name (from the docs; heuristic ranking) ----
        hc = Counter()
        for c in e["ctx"]:
            for h in c["hints"]:
                hc[h] += 1
        cand = [(n / (1.0 + df[h] / 4.0), h) for h, n in hc.items()
                if df[h] <= NGENERIC and symbol_shaped(h)]
        cand.sort(reverse=True)
        recorded = cand[0][1] if cand else ""
        rec_alts = [h for _s, h in cand[1:4]]

        srcs = sorted({c["file"] for c in e["ctx"]})
        kinds = e["kind"]

        row = {
            "rva": "0x%07X" % rva,
            "section": sec,
            "recorded_name": recorded,
            "recorded_alts": ";".join(rec_alts),
            "proposed_name": "",
            "proposed_class": "",
            "confidence": "",
            "verdict": "",
            "name_check": "",
            "fn_entry": "",
            "fn_offset": "",
            "fn_tier": "",
            "fn_extent": "",
            "n_strings": 0,
            "evidence": "",
            "why": "",
            "record_kind": ",".join(kinds),
            "n_sources": e["nsrc"],
            "sources": ";".join(srcs[:6]),
            "sample_context": e["ctx"][0]["text"][:200] if e["ctx"] else "",
        }

        if not in_text:
            row["verdict"] = "NOT-CODE"
            row["name_check"] = "n/a"
            row["why"] = "address is in %s, not .text" % sec
            rows.append(row)
            continue

        # ---- exact UE reflection hit: a real, verified symbol ----
        if rva in UE:
            u = UE[rva]
            names = u["names"]
            # MSVC /OPT:ICF folds byte-identical functions, so ONE address can be
            # the registered entry for SEVERAL UFunctions.  Measured: 469 of 15,068
            # exec thunks (3.1%) carry >1 name, and folding is independently
            # confirmed (306 short thunks sampled -> only 284 distinct bodies, one
            # body shared 7 ways).  Comparing the record against names[0] alone
            # manufactured three false "record bugs" in docs/tutorial-playability-
            # plan.md (GetTrainingManager, TryShowPrompt, GetSkillState) -- every
            # one of them IS present, just not first.  Always compare against ALL.
            row["proposed_name"] = "%s::%s" % (u["class"] or "?", names[0]) + (
                "  [ICF-folded with: %s]" % ", ".join(names[1:8]) if len(names) > 1 else "")
            row["proposed_class"] = u["class"]
            row["confidence"] = "EXACT" if len(names) == 1 else "EXACT-AMBIG"
            row["verdict"] = "ENTRY-OK"
            row["why"] = ("UE reflection %s; name verified via FFunctionParams"
                          % u["kind"]) + (" (flags %s)" % u["flags"] if u.get("flags") else "")
            row["evidence"] = " | ".join(names[:8])
            rw = {w for w in split_words(recorded) if w not in GENERIC_WORDS and len(w) > 2}
            allw = set(split_words(" ".join(names) + " " + (u["class"] or "")))
            row["name_check"] = ("NO-RECORDED-NAME" if not rw else
                                 "AGREES" if rw & allw else "DISAGREES")
            rows.append(row)
            continue

        if is_zero_page(d, rva):
            row["verdict"] = "UNVERIFIABLE"
            row["name_check"] = "n/a"
            row["why"] = "page 0x%07X is all-zero in this dump (never decrypted)" % (
                rva & ~(PAGE - 1))
            rows.append(row)
            continue

        # EXACT bounds from the unwind table recovered out of crash minidumps
        # (382,282 functions).  Prefer them absolutely: the heuristic extent is a
        # "next candidate entry" UPPER BOUND, and using it attributed neighbouring
        # functions' strings to the query -- that is what produced the bogus
        # "ProcessEvent 0x1344150 -> 'Failed to find function %s in %s'"
        # contradiction (its true extent is 48 bytes and it touches no literal).
        tb, te = strxref.true_func(rva)
        ent, flags, tier, end = idx.func_of(rva)
        if tb is not None:
            row["fn_tier"] = "pdata-EXACT"
            ent, end = tb, te
        elif ent is None:
            row["verdict"] = "NO-ENTRY"
            row["name_check"] = "n/a"
            row["why"] = "decrypted page, no MED+ heuristic entry and no unwind entry"
            rows.append(row)
            continue
        else:
            row["fn_tier"] = strxref.TIER_NAME[tier] + "-heuristic"

        row["fn_entry"] = "0x%07X" % ent
        row["fn_offset"] = "+0x%X" % (rva - ent)
        row["fn_extent"] = "%d" % (end - ent)
        row["verdict"] = "ENTRY-OK" if ent == rva else "INTERIOR"

        refs = idx.refs_in(ent, end)
        seen, refs_txt = set(), []
        for _site, si, _kind in refs:
            if si in seen:
                continue
            seen.add(si)
            refs_txt.append((si, idx.text_of(si, d)))
        row["n_strings"] = len(refs_txt)

        name, conf, why, pcls = propose_name(refs_txt, nfunc_map)
        row["proposed_name"] = name
        row["proposed_class"] = pcls
        row["confidence"] = conf
        row["why"] = why
        # the containing function may itself be a named UE stub
        k = bisect.bisect_right(ue_rvas, rva) - 1
        if k >= 0 and ue_rvas[k] == ent:
            u = UE[ent]
            row["proposed_name"] = "%s::%s" % (u["class"], u["names"][0])
            row["proposed_class"] = u["class"]
            row["confidence"] = "EXACT"
            row["why"] = "containing fn is a verified UE Z_Construct stub"

        ev = sorted(refs_txt, key=lambda p: -str_score(p[1], nfunc_map.get(p[0], 1)))[:6]
        row["evidence"] = " | ".join(t.strip().replace("\n", " ")[:70] for _si, t in ev)

        # ---- name check: does the record's own name appear in the strings? ----
        if not recorded:
            row["name_check"] = "NO-RECORDED-NAME"
        else:
            rw = {w for w in split_words(recorded) if w not in GENERIC_WORDS and len(w) > 2}
            blob = " ".join(t for _si, t in refs_txt).lower()
            if not rw:
                row["name_check"] = "NO-RECORDED-NAME"
            elif recorded.lower() in blob:
                row["name_check"] = "AGREES"
            elif rw and len(rw & set(re.findall(r"[a-z0-9]+", blob))) >= max(1, len(rw) - 1):
                row["name_check"] = "AGREES"
            elif not refs_txt:
                row["name_check"] = "NO-NAME-EVIDENCE"
            elif name and rw & {w for w in split_words(name)}:
                row["name_check"] = "AGREES"
            elif conf == "CLASS-ONLY":
                # every qualified string is a '&Class::Method' delegate literal.
                # It pins the CLASS but says nothing about which method of that
                # class we are standing in, so it can confirm but never refute.
                row["name_check"] = ("CLASS-CONFIRMED"
                                     if pcls and pcls.lower() in recorded.lower()
                                     else "CLASS-ONLY-EVIDENCE")
            elif not any(nfunc_map.get(si, 1) <= 6 and str_score(t, nfunc_map.get(si, 1)) >= 46
                         for si, t in refs_txt):
                # every string this function touches is shared with many other
                # functions (UE boilerplate: allocator messages, struct-chain
                # asserts).  Boilerplate cannot contradict a name -- calling that
                # DISAGREES manufactures false alarms, which is precisely how
                # FK-3/FK-4 were born.  0x5794480 CheckAccountPassChanges is the
                # example: its only literal is a shared UStruct assert.
                row["name_check"] = "NO-NAME-EVIDENCE"
            else:
                row["name_check"] = "DISAGREES"
        rows.append(row)

    rows.sort(key=lambda r: int(r["rva"], 16))

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    cols = ["rva", "section", "recorded_name", "proposed_name", "proposed_class",
            "confidence", "verdict",
            "name_check", "fn_entry", "fn_offset", "fn_tier", "fn_extent", "n_strings",
            "evidence", "why", "record_kind", "n_sources", "sources", "recorded_alts",
            "sample_context"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1)

    v = Counter(r["verdict"] for r in rows)
    n = Counter(r["name_check"] for r in rows)
    c = Counter(r["confidence"] for r in rows if r["proposed_name"])
    print("rows: %d" % len(rows))
    print("verdict     : %s" % dict(v))
    print("name_check  : %s" % dict(n))
    print("proposed    : %d  (%s)" % (sum(1 for r in rows if r["proposed_name"]), dict(c)))
    print("-> %s" % OUT_CSV)


if __name__ == "__main__":
    main()

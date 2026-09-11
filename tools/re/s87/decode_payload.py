#!/usr/bin/env python3
"""
S88 — decode the stub's ServerAuthConfig SPLICED BLOCK (LSB-first) END-TO-END:
the content-block header (WITH the S87 N=11 injected field) + NumPayloadBits +
the GameFeatureToggles TArray<bool> payload as a RepLayout property stream.

Purpose: verify the stub's own wire is self-consistent (the payload consumes
EXACTLY NumPayloadBits) and print the exact bit layout, so across the seed sweep
(0/1/75/151) we can see how the payload length scales with element count and
compute where the client's read diverges (fixed offset vs per-element).

Usage:
  decode_payload.py <stublog>            # extract the last 'SPLICED BLOCK' line from a stub -abslog
  decode_payload.py --hex "61 8C ..."    # decode a raw LSB-first hex byte string
  decode_payload.py --hex "..." --inject 0   # override the injected-field width (default 11)

Wire model — stock UE5.4, verified from
  RepLayout.cpp:2744-2789 (SendProperties_r dynamic-array) + :2947 (object terminator)
  DataChannel.cpp (ReadContentBlockHeader / payload length):
    content-block header (LSB-first):
      bit0   bHasRepLayout
      bit1   bIsActor
      GUID   SerializeIntPacked64          (subobject NetGUID.ObjectId, 8-bit groups)
      +N     injected bits                 (S87 empirical fix, default 11)
      1 bit  bStablyNamed / stable
      NumPayloadBits  SerializeIntPacked    (payload length in bits)
    payload (exactly NumPayloadBits bits):
      GameFeatureToggles (TArray<bool>):
        arrayHandle  SerializeIntPacked      (the array property's RepLayout handle)
        ArrayNum     uint16 = 16 RAW bits    (Writer << uint16 — NOT packed; UE quirk)
        per element: elemHandle SerializeIntPacked + 1 bit (bool NetSerializeItem)
        array-end    handle 0  SerializeIntPacked
      object-end     handle 0  SerializeIntPacked
"""
import sys, re

# ---- built-in sample: the S86 full-151 capture (header had NO inject → use --inject 0) ----
SAMPLE_HEX = ("61 8C C3 60 70 09 20 90 A0 41 84 0A 19 3A 84 28 91 A2 45 8C 1A 39 7A 04 29 92 A4 49 94 2A 59 BA "
              "84 29 93 A6 4D 9C 3A 79 FA 04 2A 94 A8 51 A4 4A 99 3A 85 2A 95 AA 55 AC 5A B9 7A 05 2B 96 AC 59 "
              "B4 6A D9 BA 85 2B 97 AE 5D BC 7A F9 FA 05 2C 98 B0 61 C4 8A 19 3B 86 2C 99 B2 65 CC 9A 39 7B 06 "
              "2D 9A B4 69 D4 AA 59 BB 86 2D 9B B6 6D DC BA 79 FB 06 2E 9C B8 71 E4 CA 99 3B 87 2E 9D BA 75 EC "
              "DA B9 7B 07 2F 9E BC 79 F4 EA D9 BB 87 2F 9F BE 7D FC FA F9 FB 0F 10 38 20 B0 40 E0 81 C0 04 81 "
              "0B 02 1B 04 3E 08 8C 10 38 21 B0 42 E0 85 C0 0C 81 1B 02 3B 04 7E 08 0C 11 38 22 B0 44 E0 89 C0 "
              "14 81 2B 02 5B 04 BE 08 04 00 00")


class BitReader:
    """LSB-first bit reader over a byte buffer (matches UE FBitReader bit order)."""
    def __init__(self, data):
        self.data = data
        self.nbits = len(data) * 8
        self.pos = 0

    def bit(self):
        p = self.pos
        if p >= self.nbits:
            raise EOFError("read past end")
        self.pos += 1
        return (self.data[p >> 3] >> (p & 7)) & 1

    def raw(self, n):
        """n raw bits, LSB-first (used for the uint16 ArrayNum and injected field)."""
        v = 0
        for i in range(n):
            v |= self.bit() << i
        return v

    def packed(self, maxgroups=10):
        """UE SerializeIntPacked: 8-bit groups, bit0=continuation, bits1..7 = 7 data bits."""
        val = 0
        shift = 0
        for _ in range(maxgroups):
            byte = self.raw(8)
            cont = byte & 1
            val |= (byte >> 1) << shift
            shift += 7
            if not cont:
                break
        return val


def decode(data, inject=11):
    r = BitReader(data)
    print(f"total bits = {r.nbits}  (bytes={len(data)})  injectWidth={inject}")

    b_has_rep = r.bit()
    b_is_actor = r.bit()
    guid = r.packed()
    guid_end = r.pos
    inj = r.raw(inject) if inject > 0 else 0
    stable_pos = r.pos
    stable = r.bit()
    npb_start = r.pos
    npb = r.packed()
    payload_start = r.pos
    print(f"HEADER: bHasRepLayout={b_has_rep} bIsActor={b_is_actor} GUID={guid} "
          f"(ends bit {guid_end}) inject[{inject}b]=0x{inj:X} stableBit@{stable_pos}={stable} "
          f"NumPayloadBits={npb} (payload starts bit {payload_start})")

    if stable != 1:
        print("  !! stable bit is not 1 — header framing is off; not walking payload.")
        return
    if npb <= 0 or payload_start + npb > r.nbits:
        print(f"  !! NumPayloadBits={npb} inconsistent with buffer (have {r.nbits - payload_start} left).")
        return

    # ---- walk the payload as a RepLayout property stream ----
    # LEADING BIT: a Development *editor* build (the stub) has ENABLE_PROPERTY_CHECKSUMS on, so
    # FRepLayout::SendProperties writes one bDoChecksum bit (=0, RepLayout.cpp:2932) at payload start
    # BEFORE the handle stream — and the client reads it symmetrically (the GameState's 43 props
    # replicated fine WITH this bit). Consume it so the handle stream aligns.
    try:
        lead = r.bit()
        print(f"  leadChecksumBit={lead}  (ENABLE_PROPERTY_CHECKSUMS editor-build bit; client agrees)")
        arr_handle = r.packed()
        arr_num = r.raw(16)
        print(f"PAYLOAD: arrayHandle={arr_handle}  ArrayNum(uint16)={arr_num}")
        elems = []
        # read (handle, bool) until the array terminator handle 0
        while True:
            h = r.packed()
            if h == 0:
                break
            bval = r.bit()
            elems.append((h, bval))
            if len(elems) > arr_num + 8:      # runaway guard
                print("  !! element loop overran ArrayNum+8 — array framing desync in the STUB's own wire.")
                break
        obj_term = r.packed()
        payload_end = r.pos
        consumed = payload_end - payload_start
        handles = [h for h, _ in elems]
        contiguous = handles == list(range(1, len(handles) + 1))
        print(f"  elements read = {len(elems)} (ArrayNum said {arr_num})  "
              f"handlesContiguous1..N={contiguous}  objTerminator={obj_term}")
        if handles:
            print(f"  first handles: {handles[:6]}{' ...' if len(handles) > 6 else ''}  last: {handles[-3:]}")
        print(f"  payload consumed = {consumed} bits vs NumPayloadBits = {npb}  "
              f"{'MATCH' if consumed == npb else f'MISMATCH (delta {consumed - npb})'}")

        # element-cost breakdown (what the STUB wrote — the reference the client's read is compared against)
        if elems:
            # recompute per-element bit cost from handle magnitudes
            def packed_bits(v):
                g = 1
                t = v >> 7
                while t:
                    g += 1
                    t >>= 7
                return g * 8
            elem_bits = sum(packed_bits(h) + 1 for h in handles)
            print(f"  array-header bits: handle={packed_bits(arr_handle)} + ArrayNum=16 = {packed_bits(arr_handle)+16}")
            print(f"  element bits total = {elem_bits}  (avg {elem_bits/len(elems):.2f}/elem for {len(elems)} elems)")
            print(f"  terminators: arrayEnd=8 + objEnd=8 = 16")
    except EOFError:
        print("  !! ran off the end walking the payload — buffer truncated or framing wrong.")


def hex_to_bytes(s):
    return bytes(int(b, 16) for b in s.split())


def extract_from_log(path):
    """Pull the last 'SPLICED BLOCK' hex from a stub -abslog. Also grabs the SPLICE line for context."""
    hex_line = None
    splice_line = None
    with open(path, "r", errors="ignore") as f:
        for line in f:
            if "SPLICED BLOCK" in line:
                m = re.search(r"bytes\(LSB\):\s*([0-9A-Fa-f ]+)", line)
                if m:
                    hex_line = m.group(1).strip()
            elif "SPLICE (S87" in line:
                splice_line = line.strip()
    if splice_line:
        print("SPLICE:", re.sub(r"^\[[^]]*\]\[[^]]*\]", "", splice_line))
    return hex_line


if __name__ == "__main__":
    inject = 11
    args = sys.argv[1:]
    if "--inject" in args:
        i = args.index("--inject")
        inject = int(args[i + 1])
        del args[i:i + 2]

    if args and args[0] == "--hex":
        data = hex_to_bytes(args[1])
    elif args:
        h = extract_from_log(args[0])
        if not h:
            print(f"No 'SPLICED BLOCK' line found in {args[0]}")
            sys.exit(1)
        data = hex_to_bytes(h)
    else:
        print("(no arg — decoding the built-in S86 full-151 sample with --inject 0)\n")
        data = hex_to_bytes(SAMPLE_HEX)
        inject = 0

    decode(data, inject=inject)

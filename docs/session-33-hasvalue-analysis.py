#!/usr/bin/env python3
"""Test whether UE has-value bits interpretation fits the captured data.

UE 5.4 FRepLayout::ReceivePropertiesForRPC (non-InternalAck):
    for each Parent (top-level param):
        if BoolProperty: read 1 bit (the value itself)
        else: read 1 bit (has-value flag); if 1, read the property data

For our 40-param signature, non-Bool params are:
  AActor* (1) + 5 FStrings + 5 uint32 + 5 uint8 = 16 has-value bits total.

Test: given the observed straight-through decode works exactly, verify that
adding has-value bits produces a mismatch.
"""

BUNCH_HEX = (
    "8E 90 78 EB 45 16 00 8C 0B 00 00 C0 CB 51 58 5B "
    "D9 0B D3 DB 5A DA 4B 53 18 DC DC 0B D3 9B 98 58 "
    "9E 95 CC 0B 93 15 D3 17 D3 9B 98 58 9E 95 CC 17 "
    "54 98 1C 5D 5E 53 99 5B 1D 00 00 00 00 00 80 C1 "
    "01 00 00 78 39 0A 6B 2B 7B 61 7A 5B 4B 7B 69 0A "
    "83 9B 7B 61 7A 13 13 CB B3 92 79 61 B2 62 FA 62 "
    "7A 13 13 CB B3 92 F9 42 2A 93 7B 9B 2A 63 2B 1B "
    "A3 FB 9A 5A CB 63 0B 73 23 9B 03 00 00 00 00 00 "
    "30 2F 00 00 00 2F 47 61 6D 65 2F 4C 6F 6B 69 2F "
    "4D 61 70 73 2F 4C 6F 62 62 79 56 32 2F 4C 56 4C "
    "5F 4C 6F 62 62 79 56 32 5F 42 61 74 74 6C 65 50 "
    "61 73 73 00 00 00 00 00 00 A6 05 00 00 E0 E5 28 "
    "AC AD EC 85 E9 6D 2D ED A5 29 0C 6E EE 85 E9 4D "
    "4C 2C CF 4A E6 85 C9 8A E9 8B E9 4D 4C 2C CF 4A "
    "E6 8B 29 ED 0C 8D 2E CD ED 0C 00 00 00 00 00 C0 "
    "AC 00 00 00 BC 1C 85 B5 95 BD 30 BD AD A5 BD 34 "
    "85 C1 CD BD 30 BD 89 89 E5 59 C9 BC 30 59 31 7D "
    "31 BD 89 89 E5 59 C9 7C 05 C9 B5 BD C9 E5 01 00 "
    "00 00 00 00 00"
)
buf = bytes.fromhex(BUNCH_HEX.replace(" ", "").replace("\n", ""))
SUB_START = 41
SUB_MAX = 2298

def bit(pos):
    return (buf[pos // 8] >> (pos % 8)) & 1

def read_bits(start, n):
    v = 0
    for i in range(n):
        v |= bit(start + i) << i
    return v

# Simulate FRepLayout::ReceivePropertiesForRPC (non-InternalAck) walk
# with 40 params: AActor*, bool×3, then 5× (FString, uint32, uint8, bool×5)
# except last element has bool×1.

Pos = 0  # bit offset within sub-reader

def consume(n, label):
    global Pos
    v = read_bits(SUB_START + Pos, n) if n > 0 else 0
    print(f"  Pos={Pos:4d} +={n:4d}  {label}  value=0x{v:X}")
    Pos += n
    return v

def consume_hasvalue(label):
    """Read 1 has-value bit. If 1, follow with property."""
    global Pos
    b = bit(SUB_START + Pos)
    print(f"  Pos={Pos:4d} +=   1  has-value({label}) = {b}")
    Pos += 1
    return b

def consume_fstring(label):
    """FString: int32 count + count*8 chars."""
    count = read_bits(SUB_START + Pos, 32)
    if count < 0 or count > 300:
        print(f"  Pos={Pos:4d} +=  32  FString.count({label}) = {count}  UNREASONABLE")
        return
    chars = bytes(read_bits(SUB_START + Pos + 32 + i*8, 8) for i in range(count))
    text = chars[:-1].decode('ascii', errors='replace') if chars and chars[-1] == 0 else "?"
    consume(32, f"FString.count({label})={count}")
    consume(count*8, f"FString.chars({label})=\"{text}\"")

print("=== Hypothesis A: STRAIGHT-THROUGH (no has-value bits) ===")
Pos = 0
consume(18, "AActor* NewViewTarget (skip 18 bits)")
consume(1, "bool PadBit1")
consume(1, "bool PadBit2")
consume(1, "bool PadBit3")
for i in range(1, 6):
    consume_fstring(f"Map{i}_Name")
    consume(32, f"Map{i}_U32")
    consume(8, f"Map{i}_U8")
    nbools = 5 if i < 5 else 1
    for b in range(nbools):
        consume(1, f"Map{i}_B{b}")
print(f"  END Pos={Pos} Expected={SUB_MAX} Leftover={SUB_MAX - Pos}")

print()
print("=== Hypothesis B: STOCK UE 5.4 non-InternalAck (has-value bits) ===")
Pos = 0
# AActor* NewViewTarget — has-value bit then data
consume_hasvalue("AActor*")
consume(18, "AActor* NewViewTarget data (17 bits after has-value)")  # if has-value already used 1
# Actually if AActor* consumed 18 bits total in session 30 including has-value...
# let me try: 1 has-value + 17 NetGUID = 18 total
consume(1, "bool PadBit1 (no has-value)")
consume(1, "bool PadBit2")
consume(1, "bool PadBit3")
for i in range(1, 6):
    consume_hasvalue(f"Map{i}_Name")
    consume_fstring(f"Map{i}_Name (payload)")
    consume_hasvalue(f"Map{i}_U32")
    # If uint32 value is 0, has-value=0, no payload; if non-zero, has-value=1 + 32 bits
    # For our data, all state values are 0, so has-value should = 0
    # But wait — has-value SHOULD equal 0 for default. Let's just consume 0 more bits.
    consume_hasvalue(f"Map{i}_U8")
    nbools = 5 if i < 5 else 1
    for b in range(nbools):
        consume(1, f"Map{i}_B{b}")
print(f"  END Pos={Pos} Expected={SUB_MAX} Leftover={SUB_MAX - Pos}")

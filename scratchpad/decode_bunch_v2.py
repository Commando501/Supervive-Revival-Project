#!/usr/bin/env python3
"""Session 25 bunch decoder.

INPUT: 293-byte bunch dump captured by LokiActorChannel::ReceivedBunch
       (from stub-s25a.log line 1153, timestamp 06.14.25:107)

The bunch is at Bunch.GetPosBits()=0 (fresh bunch). Its total NumBits=2339.
UE's ProcessBunch then processes it as:
  1. Content block header:
     - bOutHasRepLayout (1 bit) = 0
     - bIsActor (1 bit) = 1 (this bunch is for the actor, not sub-object)
  2. Content block payload NumPayloadBits (SerializeIntPacked)
  3. NumPayloadBits worth of Object payload (FObjectReplicator::ReceivedBunch)

Inside Object payload:
  4. Field header for each field:
     - RepIndex (SerializeInt(ClassCache->GetMaxIndex() + 1))
     - NumPayloadBits for this field (SerializeIntPacked)
     - Payload bits (the RPC arg struct)

Goal: extract the RPC arg struct bytes for ServerVerifyViewTarget and
identify its parameter list.
"""

# Session-25 capture (stub-s25a.log line 1153, 06.14.25:107)
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

TOTAL_BITS = 2339

buf = bytes.fromhex(BUNCH_HEX.replace(" ", "").replace("\n", ""))
print(f"Bunch: {len(buf)} bytes = {len(buf)*8} bits (usable NumBits={TOTAL_BITS})\n")


class BitReader:
    def __init__(self, b, max_bits=None):
        self.b = b
        self.pos = 0
        self.max_bits = max_bits if max_bits is not None else len(b) * 8

    def remaining(self):
        return self.max_bits - self.pos

    def read_bit(self):
        if self.pos >= self.max_bits:
            raise EOFError()
        v = (self.b[self.pos // 8] >> (self.pos % 8)) & 1
        self.pos += 1
        return v

    def read_bits(self, n):
        v = 0
        for i in range(n):
            v |= self.read_bit() << i
        return v

    def read_int_packed(self):
        """UE FBitReader::SerializeIntPacked."""
        v = 0
        shift = 0
        for _ in range(5):
            byte = self.read_bits(8)
            v |= ((byte >> 1) & 0x7F) << shift
            shift += 7
            if not (byte & 1):
                break
        return v

    def read_int_wrapped(self, max_val):
        """UE FBitReader::SerializeInt(Value, ValueMax)."""
        v = 0
        m = 1
        while (m + v) < max_val and m > 0:
            if self.read_bit():
                v |= m
            m <<= 1
        return v

    def extract_bits_to_bytes(self, num_bits):
        """Read num_bits and return them as a bytes object (LSB-first bit packing)."""
        n_bytes = (num_bits + 7) // 8
        out = bytearray(n_bytes)
        for i in range(num_bits):
            bit = self.read_bit()
            out[i // 8] |= bit << (i % 8)
        return bytes(out)


r = BitReader(buf, max_bits=TOTAL_BITS)

# === Content block header ===
b_has_rep_layout = r.read_bit()
b_is_actor = r.read_bit()
print(f"=== Content block header (2 bits) ===")
print(f"  bOutHasRepLayout = {b_has_rep_layout}")
print(f"  bIsActor         = {b_is_actor}")
print(f"  Reader at bit {r.pos}\n")

# === NumPayloadBits (content block payload size) ===
outer_num_payload_bits = r.read_int_packed()
print(f"=== Outer SerializeIntPacked NumPayloadBits ===")
print(f"  NumPayloadBits = {outer_num_payload_bits}")
print(f"  Reader at bit {r.pos}, remaining bunch = {r.remaining()}\n")

# === RPC field header ===
# APlayerController class cache MaxIndex is unknown but likely small.
# UE FBitReader::SerializeInt(Value, ValueMax) reads bits one at a time.
# For AActor + APlayerController, MaxIndex is often ~200-400 for the class
# cache combining properties + RPCs. Try a range.

# Actually — GetMaxIndex+1 is a specific value. Let's try common values.
# For UE 5.4 stock APlayerController I estimate ~130-200.
# The SerializeInt reads log2(ValueMax) bits max.

# Try reading assuming MaxIndex is between 128-256:
saved_pos = r.pos
for try_max in [64, 100, 128, 200, 256, 300, 512]:
    r.pos = saved_pos
    rep_idx = r.read_int_wrapped(try_max + 1)
    print(f"  If MaxIndex={try_max}: RepIndex={rep_idx}, reader at bit {r.pos}")
r.pos = saved_pos

# Use best guess — assume MaxIndex ~256 (APlayerController has many RPCs)
# But since we know the total remaining budget, we can just try each and
# pick the one where the sub-reader's NumPayloadBits + Payload + header
# consumes exactly the remaining bunch bits.

print()
print(f"=== Trial: for each MaxIndex guess, decode field header ===")
for try_max in [64, 100, 128, 200, 256, 300, 512, 1024]:
    r.pos = saved_pos
    try:
        rep_idx = r.read_int_wrapped(try_max + 1)
        header_bits_consumed = r.pos - saved_pos
        inner_num_payload_bits = r.read_int_packed()
        int_packed_bits = r.pos - saved_pos - header_bits_consumed
        total_field_header_bits = r.pos - saved_pos
        remaining_after_field_header = TOTAL_BITS - r.pos
        matches = (inner_num_payload_bits == remaining_after_field_header)
        marker = " <-- MATCH" if matches else ""
        print(f"  MaxIdx={try_max:4d}: RepIndex={rep_idx:4d} ({header_bits_consumed} bits), "
              f"IntPacked NumPayload={inner_num_payload_bits} ({int_packed_bits} bits), "
              f"remaining={remaining_after_field_header}{marker}")
    except EOFError:
        print(f"  MaxIdx={try_max}: EOF")

# Pick the winning MaxIndex and extract the RPC payload bytes
print(f"\n=== Trial hypothesis: MaxIndex where inner_num_payload matches remaining ===")
r.pos = saved_pos
# Try the one that matched
BEST_MAXIDX = None
for try_max in [64, 100, 128, 200, 256, 300, 512, 1024]:
    r.pos = saved_pos
    rep_idx = r.read_int_wrapped(try_max + 1)
    inner_num_payload_bits = r.read_int_packed()
    remaining = TOTAL_BITS - r.pos
    if inner_num_payload_bits == remaining:
        BEST_MAXIDX = try_max
        print(f"  Best: MaxIndex={try_max}, RepIndex={rep_idx}, NumPayloadBits={inner_num_payload_bits}")
        break

if BEST_MAXIDX is None:
    print("  No exact match found. Trying MaxIndex=256 as default.")
    BEST_MAXIDX = 256

r.pos = saved_pos
rep_idx = r.read_int_wrapped(BEST_MAXIDX + 1)
num_payload_bits = r.read_int_packed()

print(f"\n  RepIndex = {rep_idx}")
print(f"  NumPayloadBits = {num_payload_bits}")
print(f"  Reader at bit {r.pos}, remaining bunch = {r.remaining()}")

# Extract RPC payload
rpc_bytes = r.extract_bits_to_bytes(num_payload_bits)
print(f"\n=== RPC payload ({num_payload_bits} bits, {len(rpc_bytes)} bytes) ===")
for i in range(0, len(rpc_bytes), 16):
    chunk = rpc_bytes[i:i+16]
    hex_str = " ".join(f"{b:02X}" for b in chunk)
    ascii_str = "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in chunk)
    print(f"  {i:04X}: {hex_str:<48} {ascii_str}")

# Search for FString within RPC payload
target = b"/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_BattlePass"
idx = rpc_bytes.find(target)
print(f"\n=== FString search ===")
print(f"  Target: {target.decode()!r}")
print(f"  Found at RPC payload byte offset: 0x{idx:X} ({idx})")
if idx >= 4:
    count_bytes = rpc_bytes[idx-4:idx]
    count = int.from_bytes(count_bytes, "little", signed=True)
    print(f"  Preceding int32 LE (FString count): {count}")
    print(f"  Preceding 4 bytes: {count_bytes.hex(' ').upper()}")

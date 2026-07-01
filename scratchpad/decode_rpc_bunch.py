#!/usr/bin/env python3
"""Session 24 UE 5.4 packet bit-level parser.

Input: 362-byte inner packet from session-23 stub-s23c.log
       (post-wrapper-strip Channel-3 reliable bunch).

Output: parse out
  1. FNetPacketNotify header (32-bit packed + N history words)
  2. bHasPacketInfoPayload bit + optional 10-bit JitterClock
  3. Bunches — for each: bunch header + payload
  4. Within the target Channel-3 bunch: RPC dispatch loop
     (FieldHeader + SerializeIntPacked NumPayloadBits + payload)
  5. Isolate the exact bits of the ServerVerifyViewTarget RPC arg struct
"""

# Captured 2026-07-01 05.22.25:265 from stub-s23c.log
PACKET_HEX = (
    "1C 88 05 29 C6 3F 00 00 C0 DB D2 00 25 66 1E 49 8E 90 78 EB 45 16 00 8C "
    "0B 00 00 C0 CB 51 58 5B D9 0B D3 DB 5A DA 4B 53 18 DC DC 0B D3 9B 98 58 "
    "9E 95 CC 0B 93 15 D3 17 D3 9B 98 58 9E 95 CC 17 54 98 1C 5D 5E 53 99 5B "
    "1D 00 00 00 00 00 80 C1 01 00 00 78 39 0A 6B 2B 7B 61 7A 5B 4B 7B 69 0A "
    "83 9B 7B 61 7A 13 13 CB B3 92 79 61 B2 62 FA 62 7A 13 13 CB B3 92 F9 42 "
    "2A 93 7B 9B 2A 63 2B 1B A3 FB 9A 5A CB 63 0B 73 23 9B 03 00 00 00 00 00 "
    "30 2F 00 00 00 2F 47 61 6D 65 2F 4C 6F 6B 69 2F 4D 61 70 73 2F 4C 6F 62 "
    "62 79 56 32 2F 4C 56 4C 5F 4C 6F 62 62 79 56 32 5F 42 61 74 74 6C 65 50 "
    "61 73 73 00 00 00 00 00 00 A6 05 00 00 E0 E5 28 AC AD EC 85 E9 6D 2D ED "
    "A5 29 0C 6E EE 85 E9 4D 4C 2C CF 4A E6 85 C9 8A E9 8B E9 4D 4C 2C CF 4A "
    "E6 8B 29 ED 0C 8D 2E CD ED 0C 00 00 00 00 00 C0 AC 00 00 00 BC 1C 85 B5 "
    "95 BD 30 BD AD A5 BD 34 85 C1 CD BD 30 BD 89 89 E5 59 C9 BC 30 59 31 7D "
    "31 BD 89 89 E5 59 C9 7C 05 C9 B5 BD C9 E5 01 00 00 00 00 00 20 00 52 FC "
    "2F 80 13 2E 44 00 00 00 9E C4 D4 CA C6 E8 A4 CA E0 D8 D2 C6 C2 E8 DE E4 "
    "A4 CA C6 CA D2 EC CA C8 84 EA DC C6 D0 8C C2 D2 D8 00 0A 02 40 C5 FF 02 "
    "00 20"
)

data = bytes.fromhex(PACKET_HEX.replace(" ", "").replace("\n", ""))


class BitReader:
    """LSB-first bit reader matching UE's FBitReader.

    UE serializes bits MSB->LSB within a byte but bytes low-address first.
    Actually: FBitReader stores bits in Buffer[byte_idx] where the LOWEST bit
    written first goes into bit 0 of byte 0, next bit is bit 1 of byte 0, etc.
    So a byte 0x03 read as 2 bits gives 1,1 (LSB first).
    """
    def __init__(self, buf: bytes, max_bits: int = None):
        self.buf = buf
        self.pos = 0  # bit position
        self.max_bits = max_bits if max_bits is not None else len(buf) * 8

    def remaining(self) -> int:
        return self.max_bits - self.pos

    def read_bit(self) -> int:
        if self.pos >= self.max_bits:
            raise EOFError("BitReader exhausted")
        b = self.buf[self.pos // 8]
        v = (b >> (self.pos % 8)) & 1
        self.pos += 1
        return v

    def read_bits(self, n: int) -> int:
        """Read n bits, returning as integer (LSB-first within stream)."""
        v = 0
        for i in range(n):
            v |= self.read_bit() << i
        return v

    def peek_bits(self, n: int) -> int:
        save = self.pos
        v = self.read_bits(n)
        self.pos = save
        return v

    def read_int_packed(self) -> int:
        """UE FBitReader::SerializeIntPacked — 8-bit packed uint32.

        Format: each byte's LOW bit is 'more' flag, upper 7 bits are payload.
        Actually UE's SerializeIntPacked encodes/decodes as:
          - loop up to 5 iterations, each reads 8 bits
          - bit 0 (LSB of the byte) = 'has next byte' flag
          - bits 1-7 = 7-bit payload shifted into result
        """
        v = 0
        shift = 0
        for _ in range(5):
            byte = self.read_bits(8)
            payload = (byte >> 1) & 0x7F
            v |= payload << shift
            shift += 7
            if not (byte & 1):
                break
        return v

    def read_int_wrapped(self, max_val: int) -> int:
        """FBitReader::SerializeInt(Value, ValueMax) — writes value as bits
        one at a time, LSB first, up to ceil(log2(ValueMax)) bits.

        Reads bit-by-bit until adding the next bit's contribution would
        exceed ValueMax; if bit is 1 it's set and mask doubled.
        See FBitReader::SerializeInt in UE source.
        """
        v = 0
        m = 1
        while (m + v) < max_val and m > 0:
            bit = self.read_bit()
            if bit:
                v |= m
            m <<= 1
        return v


def format_bits(reader: BitReader, n: int) -> str:
    save = reader.pos
    bits = []
    for _ in range(n):
        bits.append(str(reader.read_bit()))
    reader.pos = save
    return ''.join(bits)


# =============== PARSE START ================

print(f"Total packet: {len(data)} bytes = {len(data)*8} bits\n")

# WAIT — the "post-wrapper-strip" bytes we captured from LokiStatelessConnect
# is the INNER packet AFTER the 8-byte TheoryCraft wrapper is removed. But is
# it before or after the PacketHandler chain (StatelessConnectHandlerComponent
# etc.)?
#
# Looking at LokiStatelessConnect: it strips the wrapper THEN calls
# StatelessConnectHandlerComponent::Incoming, which is a HandlerComponent in
# the PacketHandler chain. So our dump happens BEFORE any HandlerComponent
# processing.
#
# After all HandlerComponents run, UNetConnection::ReceivedPacket receives
# the packet with its FNetPacketNotify header + bunches.
#
# HOWEVER — the StatelessConnect + magic-header + trailing bits might strip
# more from the packet. In our config, net.MagicHeader is empty and
# net.VerifyMagicHeader=0, so no magic. StatelessConnect only affects
# handshake packets, not established-connection ones. So our 362 bytes
# SHOULD be the payload UNetConnection sees.
#
# But there's a "termination bit" at the end of every UE packet — the last
# byte contains the terminator. Let me leave that for later analysis.

reader = BitReader(data)

# --- StatelessConnectHandlerComponent prefix ---
# When handshake version >= SessionClientId, StatelessConnect::Incoming reads:
#   SessionID (2 bits) + ClientID (3 bits) + bHandshakePacket (1 bit) = 6 bits
# Then the rest is the actual packet UNetConnection::ReceivedPacket sees.
session_id = reader.read_bits(2)
client_id = reader.read_bits(3)
b_handshake_packet = reader.read_bit()
print(f"=== StatelessConnect prefix (6 bits) ===")
print(f"  SessionID={session_id}  ClientID={client_id}  bHandshakePacket={b_handshake_packet}")
print(f"  Reader position after SC prefix: bit {reader.pos}\n")

# --- FNetPacketNotify header ---
print("=== FNetPacketNotify header ===")
packed_header = reader.read_bits(32)
seq = (packed_header >> 18) & 0x3FFF
acked_seq = (packed_header >> 4) & 0x3FFF
hist_word_count = (packed_header & 0xF) + 1  # stored value is count-1
print(f"  PackedHeader: 0x{packed_header:08X}")
print(f"    Seq = {seq}")
print(f"    AckedSeq = {acked_seq}")
print(f"    HistoryWordCount = {hist_word_count} (raw {hist_word_count-1})")

# History data: hist_word_count * 32 bits
hist_data = []
for i in range(hist_word_count):
    hist_data.append(reader.read_bits(32))
print(f"  HistoryWords: {[hex(w) for w in hist_data]}")
print(f"  Reader position after header: bit {reader.pos}")

# --- bHasPacketInfoPayload + JitterClock ---
b_has_payload = reader.read_bit()
print(f"\n=== bHasPacketInfoPayload = {b_has_payload} ===")
if b_has_payload:
    jitter = reader.read_bits(10)  # NumBitsForJitterClockTimeInHeader = 10
    print(f"  JitterClockTime = {jitter}")
print(f"  Reader position after packet info: bit {reader.pos}")

# --- Bunches loop ---
print("\n=== Bunches ===")
MAX_CHIDX_UPPER = 32768
MAX_CHSEQUENCE = 1024
MAX_PACKET_BITS = 1024 * 8  # UE default MaxPacket = 1024 bytes = 8192 bits

CHTYPE_NONE = 0
CHTYPE_Control = 1
CHTYPE_Actor = 2
CHTYPE_File = 3
CHTYPE_Voice = 4

bunch_idx = 0
while reader.remaining() > 8:  # heuristic — at least 8 bits for a bunch
    incoming_start_pos = reader.pos
    print(f"\n--- Bunch #{bunch_idx} @ bit {incoming_start_pos} ---")

    try:
        b_is_open_or_close = reader.read_bit()
        b_open = 0
        b_close = 0
        close_reason = 0
        if b_is_open_or_close:
            b_open = reader.read_bit()
            b_close = reader.read_bit()
            if b_close:
                close_reason = reader.read_int_wrapped(15 + 1)  # MAX=15 → readInt Max=15+1?

        b_is_replication_paused = reader.read_bit()
        b_reliable = reader.read_bit()

        # SerializeIntPacked for ChIndex
        ch_index = reader.read_int_packed()

        b_has_pkgmap_exports = reader.read_bit()
        b_has_must_be_mapped_guids = reader.read_bit()
        b_partial = reader.read_bit()

        ch_sequence = 0
        if b_reliable:  # !IsInternalAck() is true for normal connections
            ch_sequence = reader.read_int_wrapped(MAX_CHSEQUENCE)

        b_partial_initial = 0
        b_partial_final = 0
        if b_partial:
            b_partial_initial = reader.read_bit()
            b_partial_final = reader.read_bit()

        b_is_open_or_reliable = b_open or b_reliable
        ch_name = None
        if b_is_open_or_reliable:
            # UPackageMap::StaticSerializeName — could be int for hardcoded
            # names or a full string. For established connections most bunches
            # target NAME_Actor which serializes as a small int.
            # Let's read carefully:
            # StaticSerializeName format:
            #  1 bit bHardcoded
            #  if bHardcoded: read EName ID (int)
            #  else: full FName serialization
            b_hardcoded = reader.read_bit()
            if b_hardcoded:
                # HardcodedName = SerializeInt(MAX_NETWORKED_HARDCODED_NAME + 1)
                # MAX_NETWORKED_HARDCODED_NAME = 410 (UE5.4)
                ename_id = reader.read_int_wrapped(410 + 1)
                ch_name = f"HardcodedEName({ename_id})"
            else:
                # Full name: bit for bIsWithinPacket / etc — too complex to
                # decode here without full FName table.
                ch_name = "FullFNameSerialization (unhandled)"

        # BunchDataBits — WriteIntWrapped(NumBits, MaxPacket*8)
        bunch_data_bits = reader.read_int_wrapped(MAX_PACKET_BITS)
        header_pos = reader.pos

        header_bytes = (header_pos - incoming_start_pos) / 8.0
        payload_bytes = bunch_data_bits / 8.0
        print(f"  bOpen={b_open} bClose={b_close} bReliable={b_reliable} bPartial={b_partial}")
        print(f"  ChIndex={ch_index} ChSequence={ch_sequence} ChName={ch_name}")
        print(f"  b_hasPkgMapExports={b_has_pkgmap_exports} bHasMustBeMappedGUIDs={b_has_must_be_mapped_guids}")
        print(f"  BunchDataBits={bunch_data_bits} ({payload_bytes:.1f} bytes)")
        print(f"  ===> Size {header_bytes:.1f}+{payload_bytes:.1f}")

        # Read the payload
        payload_start = reader.pos
        payload_bits = []
        for _ in range(bunch_data_bits):
            payload_bits.append(reader.read_bit())

        # Reassemble payload into bytes
        payload_bytes_arr = bytearray()
        for i in range(0, len(payload_bits), 8):
            byte = 0
            for j in range(8):
                if i + j < len(payload_bits):
                    byte |= payload_bits[i + j] << j
            payload_bytes_arr.append(byte)
        payload = bytes(payload_bytes_arr)

        # If this is our target bunch on channel 3 with the right size, deep-parse it
        if ch_index == 3 and bunch_data_bits > 100:
            print(f"\n  *** CHANNEL 3 RPC BUNCH — deep-parsing ***")
            print(f"  Payload ({len(payload)} bytes): {payload[:64].hex(' ').upper()}...")

            # Look for ASCII strings in payload
            for offset in range(len(payload) - 4):
                n = int.from_bytes(payload[offset:offset+4], 'little', signed=True)
                if 1 <= n <= 100 and offset + 4 + n <= len(payload):
                    s = payload[offset+4:offset+4+n]
                    if all(0x20 <= b <= 0x7E or b == 0 for b in s):
                        printable = s.rstrip(b'\x00').decode('ascii', errors='replace')
                        if len(printable) >= 4:
                            print(f"    @{offset:04X} possible FString count={n}: \"{printable}\"")

        bunch_idx += 1
    except EOFError:
        print(f"  EOF at bit {reader.pos}")
        break
    except Exception as e:
        print(f"  ERROR: {e}")
        break

print(f"\n=== End of bunches: reader at bit {reader.pos} / {len(data)*8} ===")

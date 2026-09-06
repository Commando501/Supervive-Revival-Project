#!/usr/bin/env python3
# Decode the captured ServerAuthConfig content block (LSB-first) and find the read-offset
# that reproduces the client's phantom class GUID 134524993 with bStablyNamed=0.
hexstr = ("61 8C C3 60 70 09 20 90 A0 41 84 0A 19 3A 84 28 91 A2 45 8C 1A 39 7A 04 29 92 A4 49 94 2A 59 BA "
          "84 29 93 A6 4D 9C 3A 79 FA 04 2A 94 A8 51 A4 4A 99 3A 85 2A 95 AA 55 AC 5A B9 7A 05 2B 96 AC 59 "
          "B4 6A D9 BA 85 2B 97 AE 5D BC 7A F9 FA 05 2C 98 B0 61 C4 8A 19 3B 86 2C 99 B2 65 CC 9A 39 7B 06 "
          "2D 9A B4 69 D4 AA 59 BB 86 2D 9B B6 6D DC BA 79 FB 06 2E 9C B8 71 E4 CA 99 3B 87 2E 9D BA 75 EC "
          "DA B9 7B 07 2F 9E BC 79 F4 EA D9 BB 87 2F 9F BE 7D FC FA F9 FB 0F 10 38 20 B0 40 E0 81 C0 04 81 "
          "0B 02 1B 04 3E 08 8C 10 38 21 B0 42 E0 85 C0 0C 81 1B 02 3B 04 7E 08 0C 11 38 22 B0 44 E0 89 C0 "
          "14 81 2B 02 5B 04 BE 08 04 00 00")
data = bytes(int(b,16) for b in hexstr.split())
NBITS = len(data)*8

def bit(p):
    return (data[p>>3] >> (p&7)) & 1

def read_packed(pos, is64=True):
    # UE SerializeIntPacked / SerializeIntPacked64: groups of 8 bits, LSB-first;
    # each group: bit0 = continuation, bits1..7 = 7 data bits. value accumulates 7 bits/group.
    val = 0; shift = 0; p = pos
    maxit = 10 if is64 else 5
    for _ in range(maxit):
        if p+8 > NBITS:
            return None, p
        byte = 0
        for k in range(8):
            byte |= bit(p+k) << k
        p += 8
        cont = byte & 1
        val |= (byte >> 1) << shift
        shift += 7
        if not cont:
            break
    return val, p

TARGET = 134524993
print(f"total bits={NBITS}")
# --- stock read ---
p = 0
bHasRep = bit(p); p+=1
bIsActor = bit(p); p+=1
guid, p = read_packed(p, True)
stable_pos = p
stable = bit(p); p_after_stable = p+1
print(f"STOCK: bHasRepLayout={bHasRep} bIsActor={bIsActor} GUID={guid} stableBitPos={stable_pos} stableBit={stable}")
npb, p2 = read_packed(p_after_stable, False)
print(f"STOCK: NumPayloadBits={npb} (payloadStart bit {p2}); header+len ends at bit {p2}")

# --- search: client reads E extra bits after the GUID, then bStablyNamed, [destroy?], class GUID ---
post_guid = stable_pos  # bit right after GUID (=stock stable bit position)
print(f"\npost-GUID bit index = {post_guid}")
print("bits after GUID:", ''.join(str(bit(post_guid+i)) for i in range(24)))
found=[]
for extra in range(0, 12):
    sp = post_guid + extra          # bStablyNamed position
    if sp+1 > NBITS: break
    bstab = bit(sp)
    for destroy in (0,1):           # EngineNetVer-gated destroy bit may or may not be read
        cp = sp+1+destroy           # class-GUID read start
        cls,_ = read_packed(cp, True)
        if bstab==0 and cls==TARGET:
            found.append((extra,destroy,sp,cls))
    # also show the decode for visibility
    cls0,_ = read_packed(sp+1, True)
    cls1,_ = read_packed(sp+2, True)
    print(f" extra={extra:2d} bStablyNamed@{sp}={bstab}  classIfNoDestroy={cls0}  classIfDestroy={cls1}")

print("\nMATCHES (extra_bits, destroyBit, stablyNamedPos, class):", found)

# CLAIM D verification, done my own way, at PAGE granularity (the report only quoted 11 bytes).
IMGS={"merged11":"dumps/merged11.dump.exe","s136":"dumps/s136-botai/SUPERVIVE-Win64-Shipping.dump.exe",
      "merged12":"dumps/merged12.dump.exe"}
TGT={"APawn::SpawnDefaultController":0x3BBF3C0,"AController::Possess":0x36E2B60,
     "SpawnAIFromClass":0x4631C50,"fold 0x0F7EB50":0x0F7EB50,"fold 0x0F7EC20":0x0F7EC20,
     "SpawnBot":0x556D910,"MakeNewBotController":0x5563660}
D={k:open(v,"rb").read() for k,v in IMGS.items()}
print("file sizes:", {k:len(v) for k,v in D.items()})
print("\n=== byte-level (file offset == RVA in these images) ===")
for n,rva in TGT.items():
    row=f"  {n:32s} 0x{rva:08X}"
    for k in ("merged11","s136","merged12"):
        row+=f"  {k}={D[k][rva:rva+11].hex()}"
    print(row)
print("\n=== PAGE-level: how much of the 0x1000 page is non-zero? (the report never checked this) ===")
for n,rva in TGT.items():
    pg=rva & ~0xFFF
    row=f"  {n:32s} page 0x{pg:08X}"
    for k in ("merged11","s136","merged12"):
        b=D[k][pg:pg+0x1000]; row+=f"  {k}={sum(1 for x in b if x):4d}/4096"
    print(row)
print("\n=== WHAT ELSE IS ON SpawnDefaultController's PAGE 0x3BBF000? ===")
pg=0x3BBF000
m11=D["merged11"][pg:pg+0x1000]; s=D["s136"][pg:pg+0x1000]
print(f"  merged11 non-zero bytes: {sum(1 for x in m11 if x)}/4096")
print(f"  s136     non-zero bytes: {sum(1 for x in s if x)}/4096")
print(f"  -> merged11 page is {'ENTIRELY ZERO' if not any(m11) else 'PARTIALLY LIT'}")
# how many 16-byte-aligned candidate function starts in the page look like prologues?
import re
proL=[m.start() for m in re.finditer(rb'\x40\x55|\x48\x89\x5c\x24|\x48\x83\xec|\x40\x53|\x48\x8b\xc4',bytes(s))]
print(f"  s136: {len(proL)} prologue-shaped byte sequences in the page => the page hosts MANY functions,")
print(f"        so 'page went lit' localises execution to the PAGE, not to this one function.")

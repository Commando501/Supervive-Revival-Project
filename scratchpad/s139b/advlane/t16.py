import io,sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
print("=== ULokiCMC::TickComponent aligned from start 0x055C2B90 ===")
dump(0x055C2B90,0x055C2C40)
print()
print("=== ULokiCMC::PerformMovement 0x055B8370..0x055B8420 (page nz=%d) ==="%pnz(0x055B8370))
dump(0x055B8370,0x055B8420)

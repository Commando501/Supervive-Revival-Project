import io,sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
print("=== ULokiCMC::StartNewPhysics 0x055C2430 (page nz=%d) ==="%pnz(0x055C2430))
dump(0x055C2430,0x055C24A0)

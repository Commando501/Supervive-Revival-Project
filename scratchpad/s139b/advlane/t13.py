import io,sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
print("=== BLOCK B 0x055B8E30..0x055B8F36 ===")
dump(0x055B8E30,0x055B8F36)
print()
print("=== BLOCK C 0x055B8F36..0x055B9070 ===")
dump(0x055B8F36,0x055B9070)

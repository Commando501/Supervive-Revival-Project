import io,sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
print("FMT:", wstr(0x07FC0670,300))
print("FILE:", wstr(0x07FBFEF0,200))
print("line=%d verbosity=%d" % (dd(0x07FC0658), dd(0x07FC065C)))
print()
print("=== engine PhysFalling gravity region 0x035ECBF0..0x035ECD20 ===")
dump(0x035ECBF0,0x035ECD20)

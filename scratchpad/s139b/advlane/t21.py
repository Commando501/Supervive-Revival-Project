import io,sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
r=0x088DFE70
for k in range(6):
    v=qq(r+8*k); tag=''
    if BASE<=v<BASE+0xA9E1000:
        t=v2r(v); tag=' RVA %08X  wide=%r'%(t,wstr(t,40))
    print("+%02X %016X%s"%(8*k,v,tag))
print()
print("=== 0x052F01E0 (lazy StaticClass) ===")
dump(0x052F01E0,0x052F0230)
print()
print("engine slot247(+0x7B8)=%08X  slot248(+0x7C0)=%08X"%(v2r(qq(0x07FBED58+0x7B8)),v2r(qq(0x07FBED58+0x7C0))))
dump(0x035E3B80,0x035E3BE0)

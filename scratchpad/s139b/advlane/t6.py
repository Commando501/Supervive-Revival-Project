import io,sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
r=0x07FC0648
for k in range(8):
    v=qq(r+8*k)
    tag=''
    if BASE<=v<BASE+0xA9E1000:
        t=v2r(v); tag=' -> RVA %08X wide=%r ansi=%r'%(t,wstr(t,90),cstr(t,60))
    print("+%02X %016X%s"%(8*k,v,tag))

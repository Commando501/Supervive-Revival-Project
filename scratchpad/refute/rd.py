import sys
d=open(r"dumps/merged12.dump.exe",'rb').read()
for a in sys.argv[1:]:
    rva=int(a,16)
    print(hex(rva), d[rva:rva+64].hex())

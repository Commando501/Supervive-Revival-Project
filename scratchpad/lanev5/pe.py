import struct, sys

PATH = r"dumps/merged12.dump.exe"

def load():
    with open(PATH,'rb') as f:
        data = f.read()
    return data

def pehdr(data):
    e_lfanew = struct.unpack_from('<I', data, 0x3C)[0]
    assert data[e_lfanew:e_lfanew+4] == b'PE\0\0', data[e_lfanew:e_lfanew+4]
    coff = e_lfanew+4
    machine, nsec, timestamp, symptr, nsym, optsz, chars = struct.unpack_from('<HHIIIHH', data, coff)
    opt = coff+20
    magic = struct.unpack_from('<H', data, opt)[0]
    assert magic == 0x20b, hex(magic)
    imagebase = struct.unpack_from('<Q', data, opt+24)[0]
    secs=[]
    st = opt+optsz
    for i in range(nsec):
        off = st+i*40
        name = data[off:off+8].rstrip(b'\0').decode('latin1')
        vsize, vaddr, rawsize, rawptr = struct.unpack_from('<IIII', data, off+8)
        chars_s = struct.unpack_from('<I', data, off+36)[0]
        secs.append(dict(name=name, vsize=vsize, vaddr=vaddr, rawsize=rawsize, rawptr=rawptr, chars=chars_s))
    return imagebase, secs

if __name__ == '__main__':
    data = load()
    ib, secs = pehdr(data)
    print("filesize", len(data))
    print("ImageBase 0x%X" % ib)
    for s in secs:
        print("%-10s vaddr=0x%08X vsize=0x%08X rawptr=0x%08X rawsize=0x%08X chars=0x%08X" % (
            s['name'], s['vaddr'], s['vsize'], s['rawptr'], s['rawsize'], s['chars']))

import struct
from vimg import VImg, IMAGEBASE
im=VImg(); buf=im.buf
VT=0x088F8570
print("ULokiCMC vtable at .rdata 0x%08X" % VT)
for disp,label in [(0x4C0,'IsSimulatingPhysics(on UpdatedComponent, not this vt)'),
                   (0x3D0,'TickComponent'),(0x6B8,'HasValidData'),(0x720,'StartNewPhysics'),
                   (0x890,'ControlledCharacterMove'),(0xA38,'ConstrainInputAcceleration'),
                   (0xA48,'? (pre-OnMovementUpdated)'),(0xA50,'LF-13 target'),
                   (0xAA8,'PerformMovement'),(0x830,'PhysFalling'),(0x610,'IsMovingOnGround'),
                   (0x608,'?'),(0xB70,'?'),(0x518,'?'),(0x530,'?'),(0x710,'?'),(0x708,'?')]:
    va, = struct.unpack_from('<Q', buf, VT+disp)
    rva = va - IMAGEBASE
    ok = 0x1000 <= rva < 0x0764A000
    pz = im.page_nonzero(rva) if ok else -1
    b = " ".join("%02x"%x for x in im.read(rva,8)) if ok else ""
    print("  disp 0x%03X slot %-3d -> VA 0x%X  rva 0x%08X  in.text=%s page_nz=%-5d  %-22s %s"
          % (disp, disp//8, va, rva, ok, pz, b, label))
print()
print("=== does slot 0xAA8 == ULokiCMC::PerformMovement 0x055B8370 ? ===")
va, = struct.unpack_from('<Q', buf, VT+0xAA8)
print("   slot 0xAA8 rva = 0x%08X   expected 0x055B8370   MATCH=%s" % (va-IMAGEBASE, (va-IMAGEBASE)==0x055B8370))
va, = struct.unpack_from('<Q', buf, VT+0x720)
print("   slot 0x720 rva = 0x%08X   expected 0x055C2430   MATCH=%s" % (va-IMAGEBASE, (va-IMAGEBASE)==0x055C2430))
va, = struct.unpack_from('<Q', buf, VT+0xA50)
print("   slot 0xA50 rva = 0x%08X   LF-13 says 0x0530ABF0  MATCH=%s" % (va-IMAGEBASE, (va-IMAGEBASE)==0x0530ABF0))
print("   bytes at slot 0xA50 target:", " ".join("%02x"%x for x in im.read(va-IMAGEBASE, 32)))

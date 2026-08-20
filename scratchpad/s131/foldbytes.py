import sys
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
for dn,p in [("merged4",r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe"),
             ("merged3",r"G:\git\Supervive Revival Project\dumps\merged3.dump.exe"),
             ("s131-rideable-live",r"G:\git\Supervive Revival Project\dumps\s131-rideable-live\SUPERVIVE-Win64-Shipping.dump.exe"),
             ("tuthero",r"G:\git\Supervive Revival Project\dumps\tutorial-hero\SUPERVIVE-Win64-Shipping.dump.exe")]:
    img=fkdis.Img(p)
    b50=img.read(0xF7EB50,8); bc20=img.read(0xF7EC20,8)
    w=img.read(0x55CD572,5)   # the call at the wall
    print("%-20s 0xF7EB50=%s  0xF7EC20=%s  call@0x55CD572=%s"%(dn,b50.hex(' '),bc20.hex(' '),w.hex(' ')))

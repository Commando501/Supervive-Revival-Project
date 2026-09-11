# List ALL modules in a minidump + flag non-Windows-system ones (candidate anti-cheat/anti-tamper/packer modules).
import struct, sys
d = open(sys.argv[1],'rb').read()
_, nstreams, dirrva = struct.unpack_from('<III', d, 4)
streams={}
for i in range(nstreams):
    stype,dsize,rva = struct.unpack_from('<III', d, dirrva+i*12); streams.setdefault(stype,(dsize,rva))
sep=chr(92)
def rd_str(rva):
    if rva<=0 or rva+4>len(d): return "?"
    ln=struct.unpack_from('<I',d,rva)[0]
    if ln<=0 or ln>2048 or rva+4+ln>len(d): return "?"
    return d[rva+4:rva+4+ln].decode('utf-16-le','replace')
_,mrva=streams[4]; nmod=struct.unpack_from('<I',d,mrva)[0]
# common windows system dll names to de-emphasize
sysdll=set("""ntdll kernel32 kernelbase user32 gdi32 gdi32full advapi32 msvcrt ole32 oleaut32 shell32 shlwapi
combase rpcrt4 sechost ws2_32 nsi bcrypt bcryptprimitives crypt32 wintrust ncrypt msvcp140 vcruntime140 vcruntime140_1
ucrtbase win32u imm32 setupapi cfgmgr32 dwmapi uxtheme dcomp d3d11 d3d12 d3d12core dxgi dxcore d2d1 dwrite windowscodecs
wldp devobj powrprof profapi kernel.appcore msctf dbghelp version winmm winmmbase avrt hid.dll ksuser mmdevapi audioses
mfplat mf mfreadwrite rtworkq nvwgf2umx nvcuda nvapi64 nvd3dumx wtsapi32 iphlpapi dnsapi winnsi mswsock napinsp nlaapi
winhttp webio wininet urlmon schannel sspicli dpapi ntasn1 msasn1 cryptsp rsaenh cryptbase gpapi userenv ntmarta
wkscli netutils dhcpcsvc dhcpcsvc6 fwpuclnt rasadhlp winsta wevtapi comctl32 comdlg32 clbcatq propsys coremessaging
coreuicomponents textinputframework twinapi twinapi.appcore windows.storage windows.ui wldap32 imagehlp resourcepolicyclient
uianimation d3dcompiler_47 dxil dstorage dstoragecore amsi wsock32 xinput1_4 xinput9_1_0 inputhost secur32 mswsock
directml deviceassociation ncryptsslp msvcp_win netprofm cryptdll ntdsapi framedynos""".split())
print("total modules:", nmod)
print("\n--- NON-standard-system modules (candidate game/anti-cheat/packer/overlay) ---")
for i in range(nmod):
    m=mrva+4+i*108; b,s=struct.unpack_from('<QI',d,m); nm=rd_str(struct.unpack_from('<I',d,m+20)[0]).split(sep)[-1]
    key=nm.lower().replace('.dll','')
    if key not in sysdll:
        print("  %-34s base=0x%X size=0x%X" % (nm, b, s))

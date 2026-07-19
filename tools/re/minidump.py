# Capture a single MiniDumpNormal (thread stacks + module list) of a live process.
# Feeds tools/re/dump_all_threads.py. ONE dump (not a loop) so the brief suspend-all
# doesn't perturb the connection. usage: minidump.py <pid> <out.dmp>
import sys, ctypes as C
from ctypes import wintypes as W

pid = int(sys.argv[1]); out = sys.argv[2]
k = C.WinDLL('kernel32', use_last_error=True)
dbg = C.WinDLL('dbghelp', use_last_error=True)
PROCESS_ALL = 0x1F0FFF
GENERIC_WRITE = 0x40000000
CREATE_ALWAYS = 2
k.OpenProcess.restype = W.HANDLE; k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k.CreateFileW.restype = W.HANDLE
k.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE]
dbg.MiniDumpWriteDump.restype = W.BOOL
dbg.MiniDumpWriteDump.argtypes = [W.HANDLE, W.DWORD, W.HANDLE, W.DWORD, C.c_void_p, C.c_void_p, C.c_void_p]

hp = k.OpenProcess(PROCESS_ALL, False, pid)
if not hp: print("OpenProcess failed %d" % C.get_last_error()); sys.exit(1)
hf = k.CreateFileW(out, GENERIC_WRITE, 0, None, CREATE_ALWAYS, 0, None)
if hf == W.HANDLE(-1).value or not hf: print("CreateFile failed %d" % C.get_last_error()); sys.exit(1)
MiniDumpNormal = 0x00000000
MiniDumpWithThreadInfo = 0x00001000
ok = dbg.MiniDumpWriteDump(hp, pid, hf, MiniDumpNormal | MiniDumpWithThreadInfo, None, None, None)
k.CloseHandle(hf); k.CloseHandle(hp)
if not ok: print("MiniDumpWriteDump failed %d" % C.get_last_error()); sys.exit(1)
print("wrote %s" % out)

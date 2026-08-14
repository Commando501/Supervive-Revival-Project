# S118 FINAL -- notif enum -> Lobby delegate slot -> bound/unbound -> subscriber.
# Candidate delegate offsets come from THREE independent instruction shapes in the
# case body; every candidate is then validated by the STRONG live test:
#   bound   := ptr -> allocation whose first qword is a module-range vtable, size>0
#   unbound := ptr == 0 and size == 0
# anything else is rejected as a decode artifact and printed as such.
import ctypes,sys,json
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); LOBBY=int(sys.argv[3],16)
MODHI=BASE+0xA9E1000
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def i32(b,o): return int.from_bytes(b[o:o+4],"little",signed=True)
def fstring(p):
    hd=rpm(p,16)
    if not hd: return None
    q,num=u64(hd,0),u32(hd,8)
    if not q or not(0<num<200): return None
    d=rpm(q,num*2)
    return "".join(chr(d[i*2]|(d[i*2+1]<<8)) for i in range(num)).rstrip("\x00") if d else None
def grade(off):
    b=rpm(LOBBY+off,16)
    if not b: return ("unreadable",0,0)
    p,s=u64(b,0),i32(b,8)
    if p==0 and s==0: return ("unbound",0,0)
    if p and s>0:
        inst=rpm(p,8)
        if inst and BASE<=u64(inst,0)<MODHI: return ("BOUND",p,s)
    return ("artifact",p,s)
subs={r["off"]:r for r in json.load(open("scratchpad/s118/subscribers.json"))}
tbl=rpm(BASE+0x4B04978,132); rvas=[u32(tbl,i*4) for i in range(33)]
bnds=sorted(set(rvas))
VOCAB=["connectNotif","disconnectNotif","partyLeaveNotif","partyInviteNotif","partyGetInvitedNotif",
"partyJoinNotif","partyRejectNotif","partyKickNotif","partyDataUpdateNotif","partyConnectNotif",
"partyDisconnectNotif","partyNotif","personalChatNotif","partyChatNotif","channelChatNotif",
"userStatusNotif","messageNotif","userBannedNotification","userUnbannedNotification","matchmakingNotif",
"setReadyConsentNotif","setRejectConsentNotif","rematchmakingNotif","dsNotif","acceptFriendsNotif",
"requestFriendsNotif","unfriendNotif","cancelFriendsNotif","rejectFriendsNotif","blockPlayerNotif",
"unblockPlayerNotif","errorNotif","messageSessionNotif"]
rows=[]
for i,rva in enumerate(rvas):
    end=next((b for b in bnds if b>rva), rva+0x300); n=min(end-rva,0x300)
    body=rpm(BASE+rva,n) or b""
    typ=None; cand=set(); j=0
    while j<len(body)-3:
        b0,b1,b2=body[j],body[j+1],body[j+2]
        if b0==0x48 and b1==0x8D and b2==0x0D and j+7<=len(body):
            s=fstring(BASE+rva+j+7+i32(body,j+3))
            if s and typ is None: typ=s
            j+=7; continue
        if b0==0x44 and b1==0x39 and b2==0xAF and j+7<=len(body): cand.add(i32(body,j+3)-8); j+=7; continue
        if b0==0x48 and b1==0x8B and b2==0x8F and j+7<=len(body): cand.add(i32(body,j+3)); j+=7; continue
        if b0 in (0x48,0x4C) and b1==0x8D and b2 in (0x97,0x8F,0x87) and j+7<=len(body): cand.add(i32(body,j+3)); j+=7; continue
        j+=1
    graded=[(c,)+grade(c) for c in sorted(cand) if c>=0]
    keep=[g for g in graded if g[1] in ("BOUND","unbound")]
    rej=[g for g in graded if g[1]=="artifact"]
    rows.append(dict(enum=i+1,name=VOCAB[i],bodyRVA=hex(rva),typeStr=typ,
        slots=[dict(off=hex(g[0]),state=g[1],size=g[3]) for g in keep],
        rejected=[hex(g[0]) for g in rej]))
print(f"{'#':>3} {'notif type':26} {'delegate':>8} {'state':8} subscriber")
nb=0
for r in rows:
    if not r["slots"]:
        print(f"{r['enum']:3d} {r['name']:26} {'-':>8} {'?':8} (no delegate ref decoded in body +{r['bodyRVA']})"); continue
    for s in r["slots"]:
        sub=subs.get(s["off"])
        who=f"{sub['objClass']}::fn@+{sub['methodRVA']}" if sub else ("" if s["state"]=="unbound" else "BOUND but not in subscriber map")
        if s["state"]=="BOUND": nb+=1
        m=" [type-str MEASURED]" if r["typeStr"]==r["name"] else ""
        print(f"{r['enum']:3d} {r['name']:26} {s['off']:>8} {s['state']:8} {who}{m}")
    if r["rejected"]: print(f"    (rejected decode artifacts: {', '.join(r['rejected'])})")
json.dump(rows,open("scratchpad/s118/notifmap.json","w"),indent=1)
print(f"\nBOUND notif delegates: {nb}")

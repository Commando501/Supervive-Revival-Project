# S118 HALF 2 -- notif type -> AccelByteModels payload struct -> field list, from
# tools/usmapdump/schema.txt (reflected structs = ground truth for NAMES and SCALARS).
#
# FK-14 (settled S116): container INNER types and enum UNDERLYING types in any
# usmap/schema this project produced are ~70% WRONG, deterministically.  Field
# NAMES, scalar types, StructProperty type names and super links are trustworthy.
# So every Array/Set/Map/Enum-typed field is printed with its type SUPPRESSED and
# flagged, rather than presented as fact.
import re,sys,json
SCHEMA="tools/usmapdump/schema.txt"
# mapping is [I] -- AccelByte UE SDK v1 classic-lobby naming convention, matched
# against the struct table.  The three starred rows are additionally corroborated
# by a type-name FString read LIVE out of the case body (see casemap).
MAP={
 "connectNotif":"AccelByteModelsLobbySessionId","disconnectNotif":"AccelByteModelsDisconnectNotif",
 "partyLeaveNotif":"AccelByteModelsLeavePartyNotice","partyInviteNotif":"AccelByteModelsInvitationNotice",
 "partyGetInvitedNotif":"AccelByteModelsPartyGetInvitedNotice","partyJoinNotif":"AccelByteModelsPartyJoinNotice",
 "partyRejectNotif":"AccelByteModelsPartyRejectNotice","partyKickNotif":"AccelByteModelsGotKickedFromPartyNotice",
 "partyDataUpdateNotif":"AccelByteModelsPartyDataNotif","partyConnectNotif":"AccelByteModelsPartyMemberConnectionNotice",
 "partyDisconnectNotif":"AccelByteModelsPartyMemberConnectionNotice","partyNotif":"AccelByteModelsPartyNotif",
 "personalChatNotif":"AccelByteModelsPersonalMessageNotice","partyChatNotif":"AccelByteModelsPartyMessageNotice",
 "channelChatNotif":"AccelByteModelsChannelMessageNotice","userStatusNotif":"AccelByteModelsUsersPresenceNotice",
 "messageNotif":"AccelByteModelsNotificationMessage","userBannedNotification":"AccelByteModelsUserBannedNotification",
 "userUnbannedNotification":"AccelByteModelsUserBannedNotification","matchmakingNotif":"AccelByteModelsMatchmakingNotice",
 "setReadyConsentNotif":"AccelByteModelsReadyConsentNotice","setRejectConsentNotif":"AccelByteModelsRejectConsentNotice",
 "rematchmakingNotif":"AccelByteModelsRematchmakingNotice","dsNotif":"AccelByteModelsDsNotice",
 "acceptFriendsNotif":"AccelByteModelsAcceptFriendsNotif","requestFriendsNotif":"AccelByteModelsRequestFriendsNotif",
 "unfriendNotif":"AccelByteModelsUnfriendNotif","cancelFriendsNotif":"AccelByteModelsCancelFriendsNotif",
 "rejectFriendsNotif":"AccelByteModelsRejectFriendsNotif","blockPlayerNotif":"AccelByteModelsBlockPlayerNotif",
 "unblockPlayerNotif":"AccelByteModelsUnblockPlayerNotif","errorNotif":None,
 "messageSessionNotif":"AccelByteModelsSessionNotificationMessage",
}
lines=open(SCHEMA,encoding="utf-8",errors="replace").read().split("\n")
HDR=re.compile(r"^  (\S+) : (\S*)\s+\((\d+) props, (\d+) replicated\)")
structs={}; cur=None
for ln in lines:
    m=HDR.match(ln)
    if m:
        cur=m.group(1); structs[cur]={"super":m.group(2),"declared":int(m.group(3)),"props":[]}
    elif cur and ln.startswith("      "):
        parts=ln.strip().split(None,1)
        if len(parts)==2: structs[cur]["props"].append((parts[0],parts[1]))
# CONTROL: a struct known to exist with a known prop count must reproduce
assert "AccelByteModelsDsNotice" in structs and structs["AccelByteModelsDsNotice"]["declared"]==12, "CTRL failed"
assert len(structs)>11000, f"CTRL failed: only {len(structs)} structs parsed"
print(f"[CTRL] parsed {len(structs)} structs; AccelByteModelsDsNotice declared=12  PASS\n")
UNSAFE=("ArrayProperty","SetProperty","MapProperty","EnumProperty","OptionalProperty","ByteProperty")
out=[]
for t,s in MAP.items():
    if s is None or s not in structs:
        print(f"### {t}\n    STRUCT NOT FOUND (searched schema.txt for AccelByteModels*{t[:1].upper()+t[1:]}, "
              f"*Notice/*Notif/*Notification variants)\n")
        out.append({"type":t,"struct":s,"found":False,"fields":[]}); continue
    st=structs[s]; fields=[]
    print(f"### {t}  ->  F{s}"+(f"  : F{st['super']}" if st["super"] else "")+f"  ({st['declared']} props)")
    for nm,ty in st["props"]:
        flag=any(ty.startswith(u) for u in UNSAFE)
        base=ty.split("<")[0].split(" ")[0]
        if flag: print(f"    {nm:34} {base}   <-- TYPE-UNVERIFIED (FK-14: inner/underlying type unreliable)")
        else:    print(f"    {nm:34} {ty}")
        fields.append({"name":nm,"type":ty,"typeUnverified":flag})
    print()
    out.append({"type":t,"struct":s,"found":True,"super":st["super"],"fields":fields})
json.dump(out,open("scratchpad/s118/payloads.json","w"),indent=1)
print("[SAVED] scratchpad/s118/payloads.json")

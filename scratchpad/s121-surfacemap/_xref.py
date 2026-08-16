import json,os,re,collections
ROOT=r"G:\git\Supervive Revival Project\tools\extractor\out"
# assets hosting a toggle instance for a SERVED key + their nav parents
targets = {
 "WBP_UI_Storefront_Root_C":"exchangetokens/storefrontcheats",
 "WBP_ProfileScreen_C":"leaderboards",
 "WBP_UI_AccountSettingsPanel_C":"discord",
 "WBP_UI_SocialFriendsBar_C":"discord",
 "WBP_UI_UserInterface_SettingsPanel_C":"discord",
 "WBP_UI_HeroInfo_Party_C":"mastery",
 "WBP_UI_HeroPortrait_C":"mastery",
 "WBP_UI_PartyHeroSelect_C":"mastery",
 "WBP_UI_ArmoryCardSmall_Base_C":"ArmoryItemProgression",
 "WBP_UI_Collection_Screen_C":"ArmoryItemProgression",
 "WBP_UI_HUD_Currencies_C":"ArmoryItemProgression",
 "WBP_UI_HUD_Screen_EOG_V3_C":"ArmoryItemProgression",
 "WBP_UI_HUD_Screen_PlacementAnnounce_v2_C":"ArmoryItemProgression",
 "WBP_UI_PlayerStatLine_C":"ArmoryItemProgression",
 "WBP_UI_SkylandsShop_C":"ArmoryItemProgression",
 "WBP_UI_Collection_ModalV2_C":"ArmoryItemProgression(sp)",
 "WBP_UI_GameItemTooltip_C":"ArmoryItemProgression(sp)",
 "WBP_UI_RewardRoll_Base_C":"ArmoryItemProgression(sp)",
 "WBP_Loadout_StyleScreen_VariantPicker_C":"CosmeticEffectsOverride",
 "WBP_UI_PredropScreen_PlayerEntry_C":"DropScreenTitles",
 "WBP_UI_MainMenu_NormalMainMenu_C":"NeLobbyEventBtn/DebugBattlepass",
 "WBP_UI_RegionSelect_Entry_C":"ServerSelect*",
}
needles = {t.encode():t for t in targets}
refs = collections.defaultdict(set)
paths = {}
n=0
for dp,dn,fn in os.walk(ROOT):
    for f in fn:
        if not f.endswith('.json'): continue
        p=os.path.join(dp,f); base=f[:-5]
        try: b=open(p,'rb').read()
        except Exception: continue
        n+=1
        for nb,t in needles.items():
            if nb in b and base+'_C'!=t:
                refs[t].add(base)
print("files scanned:",n)
for t in sorted(targets):
    r=sorted(refs[t])
    r=[x for x in r if x != t[:-2]]
    print(f"\n### {t}   ({targets[t]})   referenced by {len(r)} other asset(s)")
    for x in r: print("    ",x)

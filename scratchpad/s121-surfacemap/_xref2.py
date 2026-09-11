import os,collections
ROOT=r"G:\git\Supervive Revival Project\tools\extractor\out"
targets=["Comp_PlayerController_ArmoryOnboarding_C","Comp_PlayerController_ArmoryOnboardingNoProgression_C",
         "WBP_UI_Menus_MessageOfTheDay_C","WBP_UI_LobbyRewards_C","Comp_MainMenu_Onboarding_C",
         "WBP_UI_RegionSelect_Modal_C","WBP_UI_SettingsPanel_C","WBP_LobbyEventEntryBtn_C",
         "WBP_UI_Loadout_StyleScreen_C","WBP_PredropScreen_TeamEntry_C","WBP_UI_Armory_Vault_C",
         "WBP_PartyHeroSelect_Screen_C","WBP_UI_HeroPortrait_Lobby_C","WBP_Leaderboard_Screens_C",
         "WBP_UI_Discord_AuthorizeButton_C","WBP_UI_Inventory_Storage_C","WBP_UI_Storefront_Packs_C"]
needles={t.encode():t for t in targets}
refs=collections.defaultdict(set)
for dp,dn,fn in os.walk(ROOT):
    for f in fn:
        if not f.endswith('.json'): continue
        try: b=open(os.path.join(dp,f),'rb').read()
        except Exception: continue
        base=f[:-5]
        for nb,t in needles.items():
            if nb in b and base+'_C'!=t: refs[t].add(base)
for t in targets:
    r=sorted(x for x in refs[t] if x!='assetregistry_candidates_Blueprint')
    print(f"\n### {t}  <- {len(r)} refs")
    for x in r: print("   ",x)

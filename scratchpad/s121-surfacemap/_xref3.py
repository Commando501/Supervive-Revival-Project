import os,collections
ROOT=r"G:\git\Supervive Revival Project\tools\extractor\out"
targets=["WBP_UI_RewardRoll_Screen_C","WBP_UI_Collection_ItemsGrid_C","WBP_UI_PredropScreen_C",
         "WBP_UI_TopRightWidget_C","WBP_UI_HUD_GameFlow_StateMachine_C","WBP_UI_MainMenu_MenuRootV2_C",
         "WBP_ActivityPickerScreen_C","WBP_UI_Loadout_CustomizationScreen_C","WBP_HeroPicker_C",
         "WBP_UI_Menus_DialogOptions_C","WBP_UI_Armory_Vault_C","WBP_BattlepassScreen_C"]
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
    print(f"### {t}  <- {len(r)}: {r}")

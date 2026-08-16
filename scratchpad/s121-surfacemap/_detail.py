import json
rows=json.load(open('scratchpad/s121-surfacemap/toggle_instances.json',encoding='utf-8'))
served=['motd','LobbyRewards','ArmoryOnboarding','exchangetokens','storefrontcheats','leaderboards','discord','mastery','ArmoryItemProgression','ArmoryItemProgression ','CosmeticEffectsOverride','DropScreenTitles','NeLobbyEventBtn','ServerSelectRegionRoutes','ServerSelectNetworkAcceleration','DebugBattlepass']
for k in served:
    rs=[r for r in rows if r['featureKey']==k]
    print(f"\n########## {k!r}  declarative sites = {len(rs)}")
    for r in rs:
        print(f"  asset={r['asset']}")
        print(f"    instance = {r['instance']}")
        print(f"    IsEnabledByDefault = {r['isEnabledByDefault']}   ConfigKey={r['configKey']}")
        print(f"    wraps    = {r['wraps']}")
        print(f"    slot     = {r['slot']}")
        print(f"    props    = {r['allprops']}")

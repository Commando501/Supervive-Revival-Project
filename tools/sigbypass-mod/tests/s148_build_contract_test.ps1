param(
    [string]$OutDir = (Join-Path $PSScriptRoot '..\build\s148-contract-test')
)

$ErrorActionPreference = 'Stop'
$shimRoot = Split-Path -Parent $PSScriptRoot
$build = Join-Path $shimRoot 'build.ps1'
$sourcePath = Join-Path $shimRoot 'tutorial_launch.cpp'

$source = [IO.File]::ReadAllText($sourcePath)
$buildSource = [IO.File]::ReadAllText($build)
if (-not $buildSource.Contains('$PSNativeCommandArgumentPassing = ''Legacy''')) {
    throw 'build.ps1 must preserve quoted string-valued -D macros under PowerShell 7'
}
$requiredSource = @(
    'static bool BfS148DoneLoad()',
    'static void BfS148DoneStore()',
    'static bool BfS148InHookLoad()',
    'static bool BfS148InHookTryEnter()',
    'static void BfS148InHookExit()',
    'static bool BfS148TakeObjectSnapshot',
    'static bool BfS148ObjectSnapshotStable',
    'static void BfS148FreeObjectSnapshot',
    'static bool BfS148LocalPlayersSnapshotStable',
    'static bool BfS148LocalPlayersCensusStable',
    'static bool BfS148SpawnedCensusStable',
    'static bool BfS148SelectedArraysStable',
    'static BfS148PropertyFindResult BfS148StrictFindProperty',
    'static bool BfS148ExactDirectClass',
    'static bool BfS148ResolveExactStructPayload',
    'static void BfS148FsEnter()',
    'static void BfS148FsExit()',
    'g_s148FsTls=TlsAlloc()',
    '(observed&BF_S148_FS_DRAINING)&&depth==0',
    'InterlockedOr(&g_s148FsState,BF_S148_FS_DRAINING)',
    'InterlockedCompareExchange(&g_s148FsState,BF_S148_FS_RESTORING,',
    'BfS148FsActiveCount(observed)==0&&!BfS148InHookLoad()',
    'static BfS148ChainResult BfS148ExactChain',
    'S148ClassChainFailure* diagnostic=nullptr',
    'S148_CLASS_CHAIN_NODE_POINTER_INVALID',
    'S148_CLASS_CHAIN_NODE_NOT_LIVE',
    'S148_CLASS_CHAIN_CYCLE',
    'S148_CLASS_CHAIN_NAME_DECODE_FAILED',
    'S148_CLASS_CHAIN_OUTPUT_BUFFER_EXHAUSTED',
    'S148_CLASS_CHAIN_SUPER_CELL_UNREADABLE',
    'S148_CLASS_CHAIN_SUPER_POINTER_INVALID',
    'S148_CLASS_CHAIN_DEPTH_LIMIT',
    'S148_CLASS_CHAIN_MARKER_FORMAT',
    'static bool BfS148ResolveObjectProperty',
    'static bool BfS148ResolveArrayObjectProperty',
    'static bool BfS148CountSetRegistrations',
    'bool chainComplete=(f==0);',
    'PropOffsetSuper(giClass,"LocalPlayers")',
    'PropOffsetSuper(levelClass,"OwningWorld")',
    'PropOffsetSuper(worldClass,"OwningGameInstance")',
    'chosenHealthStruct,"GameplayAttributeData"',
    'maxStructName,"GameplayAttributeData"',
    'chosenHealthOwner,"LokiAttributeSetHealth"',
    'maxOwner,"LokiAttributeSetHealth"',
    '"Pawn","Controller","Pawn"',
    '"Controller","Pawn","Controller"',
    '"AbilitySystemComponentStorage","LokiCharacter","LokiAbilitySystemComponent"',
    '"AvatarActor","AbilitySystemComponent","Actor"',
    '"SpawnedAttributes","AbilitySystemComponent","AttributeSet"',
    'BfS148ExactChain(memberClass,"AttributeSet"',
    't.facts.ascInstanceOwned',
    't.facts.avatarBindingValid',
    't.facts.spawnedMemberTypesValid',
    't.facts.attributeLayoutValid',
    't.facts.censusClosureValid',
    't.facts.structPayloadValid',
    't.setPropertiesSize',
    'healthRangeValid&&maxRangeValid&&rangesDisjoint',
    'healthStruct==maxStruct',
    '(max==0&&data==0)||(max>0&&LooksLikePtr(data)',
    'chosenHealthOff>=t.setSuperPropertiesSize',
    'maxOff>=t.setSuperPropertiesSize',
    'BfS148ResolveHealthTarget(0,0,0,true,&seeded,true)',
    'BfS148ResolveHealthTarget(0,0,0,true,&immediate,true)',
    'BfS148ResolveHealthTarget(0,0,0,true,&preSeed,true)',
    'matchArrayDim==1',
    'BfS148ExactChain(adjustClass,"Function"',
    'BfS148ExactDirectClass(adjustOwner,"LokiAbilitySystemComponent")',
    # S153 thunkExact fix: `adjustThunk == impl RVA 0x5516610` is unsatisfiable by UE
    # construction (reflected Func @+0xE0 for a UHT-emitted exec wrapper on a reflected
    # native with parameters points to the WRAPPER at 0x5294270, not the impl). The
    # corrected check requires the wrapper AND its tail call at wrapper+0x6F to resolve
    # to the impl. See CLAUDE.md S152 §5 / docs/move4-external-poke-PREREGISTERED.txt.
    'bool wrapperExact=adjustThunk==g_modBase+0x5294270',
    'tailReachesImpl=tgt==(g_modBase+0x5516610)',
    'bool thunkExact=wrapperExact&&tailReachesImpl',
    'BF_S148_INITIAL)!=BF_S148_INITIAL',
    '[S148] SETUP_TIMEOUT RESULT=SETUP_TIMEOUT',
    '[S148] DELIVERY_REFUSED RESULT=DELIVERY_REFUSED',
    '[S148] CALL_IN_FLIGHT_WAIT',
    '[S148] funcswap drain complete; no admitted FsThunk body/OnPI overlaps restoration',
    '#if !KBFSELFCAL'
)
foreach ($needle in $requiredSource) {
    if (-not $source.Contains($needle)) {
        throw "S148 source is missing a required safety contract: $needle"
    }
}

$directChainCalls = [regex]::Matches(
    $source,
    'BfS148ExactChain\s*\([^;]*,&(?:gi|member|lp|pc)ChainFailure\)'
).Count
if ($directChainCalls -ne 5) {
    throw "S148 source must pass a fresh diagnostic to all 5 direct owner-chain traversals; found $directChainCalls"
}
$conditionalChainAttachments = [regex]::Matches(
    $source,
    'BF_S148_CHAIN_MALFORMED\?&(?:gi|member|lp|pc)ChainFailure:nullptr'
).Count
if ($conditionalChainAttachments -ne 4 -or
    -not $source.Contains('(uint64_t)(int32_t)giChain,&giChainFailure);')) {
    throw 'S148 source must attach diagnostics only for each direct MALFORMED owner refusal'
}

& $build -Name tutorial_launch -Variant botfight-damage-self-cal -OutDir $OutDir -Toolchain clang
if ($LASTEXITCODE -ne 0) {
    throw "S148 build failed with exit code $LASTEXITCODE"
}

$dll = Join-Path $OutDir 'tutorial_launch_botfight_damage_self_cal.dll'
if (-not (Test-Path -LiteralPath $dll)) {
    throw "S148 artifact missing: $dll"
}

$ascii = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($dll))
$required = @(
    '[S148] PREFLIGHT_REFUSED',
    '[S148] PRESEED_REVALIDATION',
    '[S148] PRESEED_REFUSED',
    '[S148] SEED_REFUSED',
    '[S148] ADJUST_UNRESOLVED',
    '[S148] ADJUST_FAULTED',
    '[S148] IMMEDIATE_MISMATCH',
    '[S148] LATER_IDENTITY_CHANGED',
    '[S148] LATER_MISMATCH',
    '[S148] LATER_TIMEOUT',
    '[S148] SETUP_TIMEOUT',
    '[S148] DELIVERY_REFUSED',
    '[S148] CALL_IN_FLIGHT_WAIT',
    '[S148] funcswap drain complete',
    '[S148] CALL_ISSUED AdjustHealth',
    '[S148] OWNER_REFUSAL phase=',
    'reason=%s code=%u pass=%d objIndex=%d census=%d li=%d',
    'candidates=%d retained=%d numEl=%d chunks=%d',
    '[S148] CHAIN_REFUSAL leaf=',
    '[S148] CHAIN_REFUSAL leaf=%s code=%u depth=%d node=0x%llX addr=0x%llX d0=0x%llX d1=0x%llX',
    'depth=%d node=0x%llX addr=0x%llX',
    'NODE_POINTER_INVALID',
    'NODE_NOT_LIVE',
    'CYCLE',
    'NAME_DECODE_FAILED',
    'OUTPUT_BUFFER_EXHAUSTED',
    'SUPER_CELL_UNREADABLE',
    'SUPER_POINTER_INVALID',
    'DEPTH_LIMIT',
    'GUOBJECT_ITEM_CHANGED',
    'LOCAL_PLAYERS_SNAPSHOT_MEMBER_CHANGED',
    'SCHEMA_LOOKUP_MALFORMED',
    'SCHEMA_INNER_CLASS_INVALID',
    'CONTROLLER_PLAYER_MISMATCH',
    'CENSUS_MEMBER_CHANGED',
    'CANDIDATE_COUNT_MULTIPLE',
    'UNCLASSIFIED_FAILURE',
    '[S148] owner scan REFUSED: incomplete',
    '[S148] registration scan',
    '[S148] active owner GI=',
    'chainComplete=%s',
    'arrayDim=%u',
    'PropertiesSize=%u',
    'AvatarActor@0x%X',
    'avatarBound=%u',
    'ascOwned=%u',
    'memberTypes=%u',
    'superPropertiesSize=%u',
    'setPropertiesSize=%u',
    'layoutValid=%u',
    'HealthStructPtr=0x%llX',
    'censusClosure=%u',
    'structPayload=%u',
    'ownerExact=%s',
    'thunkExact=%s',
    'GameplayAttributeData',
    'innerType=ObjectProperty',
    '[S148] RESULT=SELF_DAMAGE_CALIBRATED'
)
foreach ($needle in $required) {
    if (-not $ascii.Contains($needle)) {
        throw "S148 artifact is missing required runtime result marker: $needle"
    }
}

$forbidden = @(
    '[BF] ---- K_SPAWN:',
    '[BF] ---- K_BIND:',
    '[BF] ---- K_GRANT',
    '[BF] ---- K_ACTIVATE:',
    '[BF] ---- K_WIREBOT:',
    '[BF] ---- K_DAMAGE:',
    '[BF] ---- K_ALIVE',
    '[BF] ---- K_GASATTR'
)
foreach ($needle in $forbidden) {
    if ($ascii.Contains($needle)) {
        throw "S148 artifact unexpectedly contains a disabled existing arm: $needle"
    }
}

Write-Output 'PASS s148_build_contract_test'

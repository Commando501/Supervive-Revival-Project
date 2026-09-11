import pickle, collections
bm=open('dumps/merged5.dump.exe.textbm','rb').read(); NP=len(bm); TEXT=0x1000
ma=pickle.load(open('scratchpad/lane1/modattr.pkl','rb')); assign=ma['assign']; tot=ma['tot']; dkm=ma['dark']
EDITOR=set("""MeshModelingTools MeshModelingToolsExp ModelingComponents ModelingOperators InteractiveToolsFramework
GeometryScriptingCore GeometryFramework MeshDescription StaticMeshDescription SkeletalMeshDescription
PCG PCGGeometryScriptInterop OptimusCore OptimusSettings SequencerScripting MovieRenderPipelineCore
MovieRenderPipelineRenderPasses MovieRenderPipelineSettings MovieSceneCapture ConsoleVariablesEditorRuntime
ThumbnailGenerator DebugFunctionLibrary DataflowEngine DataflowEnginePlugin SubstanceCore
TypedElementFramework PropertyPath TakeMovieScene""".split())
NOTONROUTE=set("""BuildPatchServices UdpMessaging TcpMessaging ImgMedia MediaAssets OpenColorIO WebBrowserWidget
Paper2D HeadMountedDisplay MRMesh GeometryCache GeometryCacheTracks ApexDestruction ChaosCaching ChaosCloth
ClothingSystemRuntimeCommon ClothingSystemRuntimeInterface HairStrandsCore HairStrandsDeformer ChaosNiagara
CableComponent Foliage FieldSystemEngine GeometryCollectionEngine ActorSequence LevelSequence MovieScene
MovieSceneTracks CinematicCamera ControlRig RigVM IKRig AnimationSharing ACLPlugin ComputeFramework
AudioCapture AudioLinkCore WwiseAudioLinkRuntime WwiseSimpleExternalSource WwisePackaging ProceduralMeshComponent
ImageCache DiscordPartnerSDK Sentry Agones""".split())
MATCH=set("""Loki GameplayAbilities Niagara NiagaraShader AIModule NavigationSystem ReplicationGraph IrisCore NetCore
OnlineSubsystem OnlineSubsystemUtils OnlineSubsystemSteam AccelByteUe4Sdk AccelByteUe4SdkCustomization
AnimGraphRuntime PhysicsCore ChaosSolverEngine Constraints GameEventRouter GameplayCameras MinimapPlugin
AkAudio AudioMixer GameplayTags ModularGameplay GameFeatures""".split())
def buck(m):
    n=m.rsplit('/',1)[-1]
    if n in EDITOR: return 'R0 editor/authoring-only'
    if n in NOTONROUTE: return 'R1 runtime, not on this route'
    if n in MATCH: return 'R2 gameplay/net/AI (real match)'
    return 'R3 engine/UI/core shared'
b_d=collections.Counter(); b_t=collections.Counter()
for m,t in tot.items():
    b=buck(m); b_t[b]+=t; b_d[b]+=dkm.get(m,0)
# unattributed
FIRST=(0x0F7E000-TEXT)//0x1000; LAST=(0x6ABC000-TEXT)//0x1000
una=[p for p in range(NP) if p not in assign]
low=[p for p in una if p<FIRST]; hi=[p for p in una if p>LAST]; mid=[p for p in una if FIRST<=p<=LAST]
def dd(x): return sum(1 for p in x if bm[p]==0)
b_t['U1 low SIMD/ISPC block (RVA<0x0F7E000)']=len(low); b_d['U1 low SIMD/ISPC block (RVA<0x0F7E000)']=dd(low)
b_t['U2 inter-module gaps (non-UObject engine C++)']=len(mid); b_d['U2 inter-module gaps (non-UObject engine C++)']=dd(mid)
b_t['U3 high 3rd-party tail (ICU/OpenEXR/Substance/crashpad/OpenSSL/Oodle, RVA>0x6ABC000)']=len(hi); b_d['U3 high 3rd-party tail (ICU/OpenEXR/Substance/crashpad/OpenSSL/Oodle, RVA>0x6ABC000)']=dd(hi)
print(f"{'darkpg':>7} {'totalpg':>8} {'%dark':>6} {'darkMB':>7} {'%of all dark':>13}  bucket")
S=13592
for b,_ in sorted(b_d.items(), key=lambda kv:-kv[1]):
    print(f"{b_d[b]:7d} {b_t[b]:8d} {100.0*b_d[b]/b_t[b]:5.1f}% {b_d[b]*4/1024:6.2f}M {100.0*b_d[b]/S:12.1f}%  {b}")
print(f"{sum(b_d.values()):7d} {sum(b_t.values()):8d}                          TOTAL")

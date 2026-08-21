import pickle, collections
ft=pickle.load(open('scratchpad/lane1/ft.pkl','rb')); BEG,END,PHB=ft['BEG'],ft['END'],ft['PHB']
ma=pickle.load(open('scratchpad/lane1/modattr.pkl','rb')); assign=ma['assign']
import importlib.util,sys
spec=importlib.util.spec_from_file_location("ru","scratchpad/lane1/rollup.py")
TEXT=0x1000; bm=open('dumps/merged5.dump.exe.textbm','rb').read(); NP=len(bm); TEND=TEXT+NP*0x1000
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
FIRST=(0x0F7E000-TEXT)//0x1000; LAST=(0x6ABC000-TEXT)//0x1000
def buck(p):
    m=assign.get(p)
    if m is None:
        return 'U1 low SIMD block' if p<FIRST else ('U3 high 3rd-party tail' if p>LAST else 'U2 inter-module gaps')
    n=m.rsplit('/',1)[-1]
    if n in EDITOR: return 'R0 editor/authoring-only'
    if n in NOTONROUTE: return 'R1 runtime, not on this route'
    if n in MATCH: return 'R2 gameplay/net/AI (real match)'
    return 'R3 engine/UI/core shared'
nd=collections.Counter(); rd=collections.Counter()
for i in range(len(BEG)):
    b=BEG[i] if END[i] else PHB[i]
    if not (TEXT<=b<TEND): continue
    k=buck((b-TEXT)//0x1000)
    (rd if END[i] else nd)[k]+=1
print(f"{'never-dec':>10} {'decrypted':>10} {'%never':>7}  bucket")
T=sum(nd.values())
for k,_ in sorted(nd.items(), key=lambda kv:-kv[1]):
    t=nd[k]+rd[k]
    print(f"{nd[k]:10d} {rd[k]:10d} {100.0*nd[k]/t:6.1f}%  {k}  ({100.0*nd[k]/T:.1f}% of all never-decrypted)")
print(f"{T:10d} {sum(rd.values()):10d}  TOTAL (524,439 RUNTIME_FUNCTION slots)")

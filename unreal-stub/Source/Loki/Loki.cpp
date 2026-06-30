// Loki module implementation — declares this as the project's primary game
// module so the engine can find an entry point at server startup.
//
// Session 10: NetCL override. Session 9 proved the SUPERVIVE client
// successfully sends UDP handshake packets to the stub server, but the
// StatelessConnect handshake parser rejected them with
// "IncomingConnectionless: Error reading handshake packet" because the
// server's network checksum (derived from UE5.4.4's NetCL=33043543) differs
// from the client's (derived from NetCL=0). The fix: override both the
// LocalNetworkVersion (so the server REPORTS the same checksum the client
// reports) AND the IsNetworkCompatible check (belt-and-suspenders permissive
// fallback). The client's captured checksum is 3716198887 (from session 5's
// v10 hook capture of LogNetVersion: "NetCL: 0, EngineNetworkVersion: 34,
// GameNetworkVersion: 0 (Checksum: 3716198887)").

#include "Loki.h"
#include "Modules/ModuleManager.h"
#include "Misc/NetworkVersion.h"

DEFINE_LOG_CATEGORY_STATIC(LogLokiStub, Log, All);

// Captured from the SUPERVIVE client at LobbyV2 browse — the network
// checksum the client computes for itself and expects to match. Composed
// of NetCL=0 + EngineNetworkVersion=34 + GameNetworkVersion=0 + project
// "Loki 1.0.0.0". By overriding the server's locally computed version
// with this exact value, the StatelessConnect handshake's checksum
// comparison succeeds.
static constexpr uint32 kLokiClientNetworkChecksum = 3716198887U;

class FLokiModule : public FDefaultGameModuleImpl
{
public:
    virtual void StartupModule() override
    {
        FDefaultGameModuleImpl::StartupModule();

        // Force the local network version (which is what gets reported in
        // the StatelessConnect handshake) to the client's captured checksum.
        FNetworkVersion::GetLocalNetworkVersionOverride.BindStatic(
            &FLokiModule::GetLocalNetworkVersion);

        // Belt-and-suspenders: also accept any remote version. This catches
        // future client builds that may compute a different checksum, and
        // makes the handshake more forgiving during recon iterations.
        FNetworkVersion::IsNetworkCompatibleOverride.BindStatic(
            &FLokiModule::IsNetworkCompatible);

        // Force a rehash on next handshake to pick up our override.
        FNetworkVersion::InvalidateNetworkChecksum();

        UE_LOG(LogLokiStub, Display,
               TEXT("Loki stub: NetCL overrides bound. Local checksum forced to %u; "
                    "IsNetworkCompatible accepts any remote."),
               kLokiClientNetworkChecksum);
    }

    virtual void ShutdownModule() override
    {
        FNetworkVersion::GetLocalNetworkVersionOverride.Unbind();
        FNetworkVersion::IsNetworkCompatibleOverride.Unbind();
        FDefaultGameModuleImpl::ShutdownModule();
    }

private:
    static uint32 GetLocalNetworkVersion()
    {
        return kLokiClientNetworkChecksum;
    }

    static bool IsNetworkCompatible(uint32 LocalVersion, uint32 RemoteVersion)
    {
        UE_LOG(LogLokiStub, Verbose,
               TEXT("IsNetworkCompatible(local=%u, remote=%u) -> true (override)"),
               LocalVersion, RemoteVersion);
        return true;
    }
};

IMPLEMENT_PRIMARY_GAME_MODULE(FLokiModule, Loki, "Loki");

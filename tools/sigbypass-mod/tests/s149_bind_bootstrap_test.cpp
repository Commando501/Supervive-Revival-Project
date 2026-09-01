// Offline behavioral policy test for the S149 bind-only bootstrap witness.
//
// Build from tools/sigbypass-mod/tests:
//   clang++ -std=c++17 -O2 s149_bind_bootstrap_test.cpp -o s149_bind_bootstrap_test.exe
#include "../s149_bind_bootstrap.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>

static void Require(bool condition, const char* message) {
    if (!condition) {
        std::fprintf(stderr, "FAIL: %s\n", message);
        std::exit(1);
    }
}

static S149BindWitnessFacts ReadyFacts() {
    S149BindWitnessFacts facts{};
    facts.callCount = 1;
    facts.setupFaulted = 0;
    facts.initFaulted = 0;
    facts.terminalRevalidated = 1;
    facts.localAuthorityStable = 1;
    facts.pcLive = 1;
    facts.possessedHeroStable = 1;
    facts.heroLive = 1;
    facts.ascLive = 1;
    facts.ascStorageResolved = 1;
    facts.ascStorageReadable = 1;
    facts.ascStable = 1;
    facts.avatarPropertyResolved = 1;
    facts.avatarSlotReadable = 1;
    facts.avatarLive = 1;
    facts.avatarMatchesHero = 1;
    facts.ownerPropertyResolved = 1;
    facts.ownerSlotReadable = 1;
    facts.ownerLive = 1;
    facts.ownerMatchesCarrier = 1;
    facts.carrierPropertyResolved = 1;
    facts.carrierSlotReadable = 1;
    facts.carrierLive = 1;
    facts.carrierStable = 1;
    facts.carrierAscPropertyResolved = 1;
    facts.carrierAscSlotReadable = 1;
    facts.carrierAscStable = 1;
    return facts;
}

static S149BindCleanupFacts ReadyCleanup() {
    S149BindCleanupFacts facts{};
    facts.restoreCountExact = 1;
    facts.repairScanComplete = 1;
    facts.verifyScanComplete = 1;
    facts.callbacksSealed = 1;
    facts.cleanupFaulted = 0;
    facts.postRestoreQuiesced = 1;
    facts.swapped = 10;
    facts.restored = 10;
    facts.residualRepaired = 0;
    facts.residualRemaining = 0;
    facts.postRestoreEntries = 0;
    facts.entryPendingRemaining = 0;
    facts.parkedRemaining = 0;
    facts.activeRemaining = 0;
    facts.mutationRootsRemaining = 0;
    return facts;
}

static void TestExactPolicy() {
    Require(S149BindPolicyIssues(0x02u, false, false) == S149_BIND_POLICY_NONE,
            "the isolated K_BIND arm must be the only admissible bind policy");
    Require((S149BindPolicyIssues(0x03u, false, false) &
             S149_BIND_POLICY_ARM_MASK) != 0,
            "the legacy spawn+bind artifact must be rejected as too broad");
    Require((S149BindPolicyIssues(0x00u, false, false) &
             S149_BIND_POLICY_ARM_MASK) != 0,
            "an artifact with no bind arm must be rejected");
    Require((S149BindPolicyIssues(0xCEu, false, false) &
             S149_BIND_POLICY_ARM_MASK) != 0,
            "the grant/alive/GAS/activation artifact must be rejected");
    Require((S149BindPolicyIssues(0x02u, true, false) &
             S149_BIND_POLICY_NATURAL_INPUT) != 0,
            "natural input must be forbidden from the setup artifact");
    Require((S149BindPolicyIssues(0x02u, false, true) &
             S149_BIND_POLICY_SELF_CALIBRATION) != 0,
            "S148 calibration must be forbidden from the setup artifact");
}

static void TestWitnessIssues() {
    S149BindWitnessFacts facts = ReadyFacts();
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_NONE &&
                S149BindWitnessReady(facts),
            "one fault-free stable live ASC/avatar binding must pass");

    facts = ReadyFacts(); facts.initFaulted = 1;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_INIT_FAULTED,
            "a faulting InitAbilityActorInfo call must refuse");
    facts = ReadyFacts(); facts.setupFaulted = 1;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_SETUP_FAULTED,
            "an SEH-contained setup fault outside InitAbilityActorInfo must refuse distinctly");
    facts = ReadyFacts(); facts.localAuthorityStable = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_LOCAL_AUTHORITY_DRIFT,
            "the unique LocalPlayer/controller membership must be freshly stable after binding");
    facts = ReadyFacts(); facts.terminalRevalidated = 0;
    Require((S149BindWitnessIssues(facts) &
             S149_BIND_ISSUE_TERMINAL_NOT_REVALIDATED) != 0,
            "a witness captured before the triggering ProcessInternal return must refuse");
    facts = ReadyFacts(); facts.callCount = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_CALL_COUNT,
            "a pre-bound state with no issued call must not masquerade as setup success");
    facts = ReadyFacts(); facts.callCount = 2;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_CALL_COUNT,
            "more than one InitAbilityActorInfo call must refuse");
    facts = ReadyFacts(); facts.pcLive = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_PC_NOT_LIVE,
            "a stale selected controller must refuse");
    facts = ReadyFacts(); facts.possessedHeroStable = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_POSSESSION_DRIFT,
            "a changed PC.Pawn identity must refuse");
    facts = ReadyFacts(); facts.heroLive = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_HERO_NOT_LIVE,
            "a stale selected hero must refuse");
    facts = ReadyFacts(); facts.ascLive = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_ASC_NOT_LIVE,
            "a stale selected ASC must refuse");
    facts = ReadyFacts(); facts.ascStorageResolved = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_ASC_STORAGE_UNRESOLVED,
            "an unresolved AbilitySystemComponentStorage property must refuse");
    facts = ReadyFacts(); facts.ascStorageReadable = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_ASC_STORAGE_UNREADABLE,
            "an unreadable AbilitySystemComponentStorage slot must refuse");
    facts = ReadyFacts(); facts.ascStable = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_ASC_IDENTITY_DRIFT,
            "a changed hero ASC identity must refuse");
    facts = ReadyFacts(); facts.avatarPropertyResolved = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_AVATAR_PROPERTY_UNRESOLVED,
            "an unresolved AvatarActor property must refuse");
    facts = ReadyFacts(); facts.avatarSlotReadable = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_AVATAR_SLOT_UNREADABLE,
            "an unreadable AvatarActor slot must refuse distinctly from null");
    facts = ReadyFacts(); facts.avatarLive = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_AVATAR_NOT_LIVE,
            "a stale AvatarActor pointer must refuse");
    facts = ReadyFacts(); facts.avatarMatchesHero = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_AVATAR_MISMATCH,
            "AvatarActor must equal the same selected possessed hero");
    facts = ReadyFacts(); facts.ownerPropertyResolved = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_OWNER_PROPERTY_UNRESOLVED,
            "an unresolved OwnerActor property must refuse");
    facts = ReadyFacts(); facts.ownerSlotReadable = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_OWNER_SLOT_UNREADABLE,
            "an unreadable OwnerActor slot must refuse");
    facts = ReadyFacts(); facts.ownerLive = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_OWNER_NOT_LIVE,
            "a stale OwnerActor pointer must refuse");
    facts = ReadyFacts(); facts.ownerMatchesCarrier = 0;
    Require(S149BindWitnessIssues(facts) == S149_BIND_ISSUE_OWNER_MISMATCH,
            "OwnerActor must equal the exact carrier passed to InitAbilityActorInfo");
    facts = ReadyFacts(); facts.carrierPropertyResolved = 0;
    Require((S149BindWitnessIssues(facts) &
             S149_BIND_ISSUE_CARRIER_PROPERTY_UNRESOLVED) != 0,
            "the final witness must resolve PlayerState.HeroAffiliatedObject exactly");
    facts = ReadyFacts(); facts.carrierSlotReadable = 0;
    Require((S149BindWitnessIssues(facts) &
             S149_BIND_ISSUE_CARRIER_SLOT_UNREADABLE) != 0,
            "an unreadable final HeroAffiliatedObject slot must refuse");
    facts = ReadyFacts(); facts.carrierLive = 0;
    Require((S149BindWitnessIssues(facts) & S149_BIND_ISSUE_CARRIER_NOT_LIVE) != 0,
            "the saved exact carrier class must still be live after callback drain");
    facts = ReadyFacts(); facts.carrierStable = 0;
    Require((S149BindWitnessIssues(facts) & S149_BIND_ISSUE_CARRIER_DRIFT) != 0,
            "PlayerState.HeroAffiliatedObject must still equal the selected carrier");
    facts = ReadyFacts(); facts.carrierAscPropertyResolved = 0;
    Require((S149BindWitnessIssues(facts) &
             S149_BIND_ISSUE_CARRIER_ASC_PROPERTY_UNRESOLVED) != 0,
            "the final carrier ASC relation must retain exact property provenance");
    facts = ReadyFacts(); facts.carrierAscSlotReadable = 0;
    Require((S149BindWitnessIssues(facts) &
             S149_BIND_ISSUE_CARRIER_ASC_SLOT_UNREADABLE) != 0,
            "an unreadable final carrier ASC slot must refuse");
    facts = ReadyFacts(); facts.carrierAscStable = 0;
    Require((S149BindWitnessIssues(facts) & S149_BIND_ISSUE_CARRIER_ASC_DRIFT) != 0,
            "the carrier must still reference the exact selected ASC after callback drain");

    facts = ReadyFacts();
    facts.initFaulted = 1;
    facts.avatarSlotReadable = 0;
    Require(S149BindWitnessIssues(facts) ==
                (S149_BIND_ISSUE_INIT_FAULTED |
                 S149_BIND_ISSUE_AVATAR_SLOT_UNREADABLE),
            "independent failures must accumulate without hiding the first or later fault");
    Require(!S149BindWitnessReady(facts),
            "any witness issue must keep the setup gate closed");
}

static void TestCleanupIssues() {
    S149BindWitnessFacts witness = ReadyFacts();
    S149BindCleanupFacts cleanup = ReadyCleanup();
    Require(S149BindCleanupIssues(cleanup) == S149_BIND_ISSUE_NONE,
            "an exact restore, complete zero-residual verification, and quiescence must pass");
    Require(S149BindAdmissionIssues(witness, true, cleanup) == S149_BIND_ISSUE_NONE,
            "terminal admission must combine the published witness and cleanup proof");

    cleanup = ReadyCleanup(); cleanup.restoreCountExact = 0; cleanup.restored = 0;
    Require((S149BindCleanupIssues(cleanup) & S149_BIND_ISSUE_RESTORE_COUNT_MISMATCH) != 0,
            "restored=0 of N must never be admitted as an expected GC shortfall");
    cleanup = ReadyCleanup(); cleanup.repairScanComplete = 0;
    Require((S149BindCleanupIssues(cleanup) & S149_BIND_ISSUE_REPAIR_SCAN_INCOMPLETE) != 0,
            "an incomplete residual-repair census must refuse");
    cleanup = ReadyCleanup(); cleanup.verifyScanComplete = 0;
    Require((S149BindCleanupIssues(cleanup) & S149_BIND_ISSUE_VERIFY_SCAN_INCOMPLETE) != 0,
            "an incomplete second verification census must refuse");
    cleanup = ReadyCleanup(); cleanup.residualRemaining = 1;
    Require((S149BindCleanupIssues(cleanup) & S149_BIND_ISSUE_FUNCS_REMAIN) != 0,
            "any remaining S149 FsThunk pointer must refuse");
    cleanup = ReadyCleanup(); cleanup.postRestoreQuiesced = 0; cleanup.parkedRemaining = 1;
    Require((S149BindCleanupIssues(cleanup) & S149_BIND_ISSUE_POST_RESTORE_NOT_QUIESCED) != 0,
            "a parked or active post-restore callback must refuse terminal readiness");
    cleanup = ReadyCleanup(); cleanup.callbacksSealed = 0;
    Require((S149BindCleanupIssues(cleanup) &
             S149_BIND_ISSUE_CALLBACKS_NOT_SEALED) != 0,
            "terminal readiness must require an irreversible no-dispatch thunk phase");
    cleanup = ReadyCleanup(); cleanup.cleanupFaulted = 1;
    Require((S149BindCleanupIssues(cleanup) & S149_BIND_ISSUE_CLEANUP_FAULTED) != 0,
            "an SEH-contained restoration/census fault must refuse");
    cleanup = ReadyCleanup(); cleanup.mutationRootsRemaining = 1;
    Require((S149BindCleanupIssues(cleanup) &
             S149_BIND_ISSUE_POST_RESTORE_NOT_QUIESCED) != 0,
            "a pre-seal mutation-capable thunk root must block the terminal witness");
    Require((S149BindAdmissionIssues(witness, false, ReadyCleanup()) &
             S149_BIND_ISSUE_WITNESS_NOT_PUBLISHED) != 0,
            "cleanup cannot substitute for a published post-bind witness");
}

static void TestThunkSealProtocol() {
    Require(S149BindThunkRunsSetup(S149_BIND_THUNK_ACTIVE),
            "the active phase alone may run the bind setup");
    Require(S149BindThunkRunsOriginal(S149_BIND_THUNK_ACTIVE) &&
                S149BindThunkRunsOriginal(S149_BIND_THUNK_PASS_THROUGH),
            "tracked pre-seal roots may finish the original dispatcher");
    Require(!S149BindThunkRunsSetup(S149_BIND_THUNK_PASS_THROUGH),
            "released restoration roots must never run bind setup again");
    Require(!S149BindThunkRunsSetup(S149_BIND_THUNK_SEALED) &&
                !S149BindThunkRunsOriginal(S149_BIND_THUNK_SEALED),
            "a prefetched thunk that resumes after sealing must be a no-op");
    Require(!S149BindTerminalCallbackSafe(S149_BIND_THUNK_PASS_THROUGH, 0, 0),
            "a quiet interval in pass-through mode cannot prove no prefetched thunk remains");
    Require(!S149BindTerminalCallbackSafe(S149_BIND_THUNK_SEALED, 1, 0) &&
                !S149BindTerminalCallbackSafe(S149_BIND_THUNK_SEALED, 0, 1),
            "sealing must wait for both phase-handshake and mutation-capable roots");
    Require(S149BindTerminalCallbackSafe(S149_BIND_THUNK_SEALED, 0, 0),
            "only sealed mode with no pre-seal roots admits a fresh terminal witness");
}

static void TestMarkerBoundary() {
    char marker[512]{};
    int written = std::snprintf(
        marker, sizeof(marker), S149_BIND_WITNESS_MARKER_FORMAT,
        4242ul, 0x0123456789ABCDEFull,
        1u, 0u, 0u, 1u, 1u, 1u, 1u, 1u, 1u, 1u, 1u, 1u, 1u, 1u, 1u, 1u,
        0x1111222233334444ull, 0x5555666677778888ull,
        0x9999AAAABBBBCCCCull, 0x5555666677778888ull);
    Require(written > 0 && written < static_cast<int>(sizeof(marker)),
            "the complete post-bind witness must fit the runtime marker buffer");
    Require(std::strstr(marker, "callCount=1 setupFaulted=0 initFaulted=0 terminalRevalidated=1") != nullptr &&
                std::strstr(marker, "localAuthorityStable=1") != nullptr &&
                std::strstr(marker, "pcLive=1 possessedHeroStable=1") != nullptr &&
                std::strstr(marker, "avatarPropertyResolved=1 avatarSlotReadable=1") != nullptr &&
                std::strstr(marker, "hero=0x5555666677778888") != nullptr &&
                std::strstr(marker, "avatar=0x5555666677778888") != nullptr,
            "the marker must expose every admission fact and the equality-check identities");
    Require(marker[written - 2] == '\r' && marker[written - 1] == '\n' &&
                marker[written] == '\0',
            "the post-bind witness marker must retain its CRLF terminator");

    char ownerMarker[512]{};
    int ownerWritten = std::snprintf(
        ownerMarker, sizeof(ownerMarker), S149_BIND_OWNER_MARKER_FORMAT,
        4242ul, 0x0123456789ABCDEFull,
        1u, 1u, 1u, 1u, 1u, 1u, 1u, 1u, 1u, 1u, 1u,
        0xAAAABBBBCCCCDDDDull, 0xAAAABBBBCCCCDDDDull);
    Require(ownerWritten > 0 && ownerWritten < static_cast<int>(sizeof(ownerMarker)) &&
                std::strstr(ownerMarker, "ownerPropertyResolved=1 ownerSlotReadable=1") != nullptr &&
                std::strstr(ownerMarker, "carrierPropertyResolved=1 carrierSlotReadable=1") != nullptr &&
                std::strstr(ownerMarker, "carrierAscPropertyResolved=1 carrierAscSlotReadable=1 carrierAscStable=1") != nullptr &&
                std::strstr(ownerMarker, "carrier=0xAAAABBBBCCCCDDDD owner=0xAAAABBBBCCCCDDDD") != nullptr,
            "the split owner witness must fit and expose its independent provenance/equality facts");

    char cleanupMarker[512]{};
    int cleanupWritten = std::snprintf(
        cleanupMarker, sizeof(cleanupMarker), S149_BIND_CLEANUP_MARKER_FORMAT,
        1u, 1u, 1u, 1u, 0u, 1u,
        10ul, 10ul, 0ul, 0ul, 0ul, 0ul, 0ul, 0ul, 0ul);
    Require(cleanupWritten > 0 && cleanupWritten < static_cast<int>(sizeof(cleanupMarker)) &&
                std::strstr(cleanupMarker, "restoreCountExact=1 repairScanComplete=1") != nullptr &&
                std::strstr(cleanupMarker, "residualRemaining=0") != nullptr &&
                std::strstr(cleanupMarker, "callbacksSealed=1 cleanupFaulted=0") != nullptr &&
                std::strstr(cleanupMarker, "postRestoreQuiesced=1") != nullptr,
            "the complete restoration/quiescence proof must fit the runtime marker buffer");
}

int main() {
    TestExactPolicy();
    TestWitnessIssues();
    TestCleanupIssues();
    TestThunkSealProtocol();
    TestMarkerBoundary();
    std::puts("PASS s149_bind_bootstrap_test");
    return 0;
}

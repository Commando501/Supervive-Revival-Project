#pragma once

#include <cstdint>

constexpr uint32_t S149_BIND_REQUIRED_ARMS = 0x02u;
constexpr uint32_t S149_BIND_FORBIDDEN_ARMS = 0xFDu;

enum S149BindPolicyIssue : uint32_t {
    S149_BIND_POLICY_NONE = 0,
    S149_BIND_POLICY_ARM_MASK = 1u << 0,
    S149_BIND_POLICY_NATURAL_INPUT = 1u << 1,
    S149_BIND_POLICY_SELF_CALIBRATION = 1u << 2,
};

inline uint32_t S149BindPolicyIssues(uint32_t arms, bool naturalInput,
                                     bool selfCalibration) {
    uint32_t issues = S149_BIND_POLICY_NONE;
    if (arms != S149_BIND_REQUIRED_ARMS) issues |= S149_BIND_POLICY_ARM_MASK;
    if (naturalInput) issues |= S149_BIND_POLICY_NATURAL_INPUT;
    if (selfCalibration) issues |= S149_BIND_POLICY_SELF_CALIBRATION;
    return issues;
}

struct S149BindWitnessFacts {
    uint8_t callCount;
    uint8_t setupFaulted;
    uint8_t initFaulted;
    uint8_t terminalRevalidated;
    uint8_t localAuthorityStable;
    uint8_t pcLive;
    uint8_t possessedHeroStable;
    uint8_t heroLive;
    uint8_t ascLive;
    uint8_t ascStorageResolved;
    uint8_t ascStorageReadable;
    uint8_t ascStable;
    uint8_t avatarPropertyResolved;
    uint8_t avatarSlotReadable;
    uint8_t avatarLive;
    uint8_t avatarMatchesHero;
    uint8_t ownerPropertyResolved;
    uint8_t ownerSlotReadable;
    uint8_t ownerLive;
    uint8_t ownerMatchesCarrier;
    uint8_t carrierPropertyResolved;
    uint8_t carrierSlotReadable;
    uint8_t carrierLive;
    uint8_t carrierStable;
    uint8_t carrierAscPropertyResolved;
    uint8_t carrierAscSlotReadable;
    uint8_t carrierAscStable;
};

struct S149BindCleanupFacts {
    uint8_t restoreCountExact;
    uint8_t repairScanComplete;
    uint8_t verifyScanComplete;
    uint8_t callbacksSealed;
    uint8_t cleanupFaulted;
    uint8_t postRestoreQuiesced;
    uint32_t swapped;
    uint32_t restored;
    uint32_t residualRepaired;
    uint32_t residualRemaining;
    uint32_t postRestoreEntries;
    uint32_t entryPendingRemaining;
    uint32_t parkedRemaining;
    uint32_t activeRemaining;
    uint32_t mutationRootsRemaining;
};

enum S149BindThunkPhase : uint32_t {
    S149_BIND_THUNK_ACTIVE = 0,
    S149_BIND_THUNK_PASS_THROUGH = 1,
    S149_BIND_THUNK_SEALED = 2,
};

inline bool S149BindThunkRunsSetup(uint32_t phase) {
    return phase == S149_BIND_THUNK_ACTIVE;
}

inline bool S149BindThunkRunsOriginal(uint32_t phase) {
    return phase != S149_BIND_THUNK_SEALED;
}

// `entryPending` is the phase-load handshake: a root increments it before reading
// the phase, then either becomes a counted mutation-capable root or observes SEALED.
// This closes the read-phase/increment-root race. A caller preempted before its first
// thunk instruction later observes SEALED and performs no engine dispatch.
inline bool S149BindTerminalCallbackSafe(uint32_t phase,
                                         uint32_t entryPending,
                                         uint32_t mutationRoots) {
    return phase == S149_BIND_THUNK_SEALED && entryPending == 0 &&
           mutationRoots == 0;
}

enum S149BindWitnessIssue : uint32_t {
    S149_BIND_ISSUE_NONE = 0,
    S149_BIND_ISSUE_INIT_FAULTED = 1u << 0,
    S149_BIND_ISSUE_PC_NOT_LIVE = 1u << 1,
    S149_BIND_ISSUE_POSSESSION_DRIFT = 1u << 2,
    S149_BIND_ISSUE_HERO_NOT_LIVE = 1u << 3,
    S149_BIND_ISSUE_ASC_NOT_LIVE = 1u << 4,
    S149_BIND_ISSUE_ASC_STORAGE_UNRESOLVED = 1u << 5,
    S149_BIND_ISSUE_ASC_STORAGE_UNREADABLE = 1u << 6,
    S149_BIND_ISSUE_ASC_IDENTITY_DRIFT = 1u << 7,
    S149_BIND_ISSUE_AVATAR_PROPERTY_UNRESOLVED = 1u << 8,
    S149_BIND_ISSUE_AVATAR_SLOT_UNREADABLE = 1u << 9,
    S149_BIND_ISSUE_AVATAR_NOT_LIVE = 1u << 10,
    S149_BIND_ISSUE_AVATAR_MISMATCH = 1u << 11,
    S149_BIND_ISSUE_CALL_COUNT = 1u << 12,
    S149_BIND_ISSUE_OWNER_PROPERTY_UNRESOLVED = 1u << 13,
    S149_BIND_ISSUE_OWNER_SLOT_UNREADABLE = 1u << 14,
    S149_BIND_ISSUE_OWNER_NOT_LIVE = 1u << 15,
    S149_BIND_ISSUE_OWNER_MISMATCH = 1u << 16,
    S149_BIND_ISSUE_WITNESS_NOT_PUBLISHED = 1u << 17,
    S149_BIND_ISSUE_SETUP_FAULTED = 1u << 18,
    S149_BIND_ISSUE_LOCAL_AUTHORITY_DRIFT = 1u << 19,
    S149_BIND_ISSUE_RESTORE_COUNT_MISMATCH = 1u << 20,
    S149_BIND_ISSUE_REPAIR_SCAN_INCOMPLETE = 1u << 21,
    S149_BIND_ISSUE_VERIFY_SCAN_INCOMPLETE = 1u << 22,
    S149_BIND_ISSUE_FUNCS_REMAIN = 1u << 23,
    S149_BIND_ISSUE_POST_RESTORE_NOT_QUIESCED = 1u << 24,
    S149_BIND_ISSUE_TERMINAL_NOT_REVALIDATED = 1u << 25,
    S149_BIND_ISSUE_CALLBACKS_NOT_SEALED = 1u << 26,
    S149_BIND_ISSUE_CLEANUP_FAULTED = 1u << 27,
    S149_BIND_ISSUE_CARRIER_RELATION = 1u << 28,
    // The marker retains the individual leaves; the compact 32-bit terminal mask
    // intentionally groups them under one carrier-relation admission bit.
    S149_BIND_ISSUE_CARRIER_PROPERTY_UNRESOLVED = S149_BIND_ISSUE_CARRIER_RELATION,
    S149_BIND_ISSUE_CARRIER_SLOT_UNREADABLE = S149_BIND_ISSUE_CARRIER_RELATION,
    S149_BIND_ISSUE_CARRIER_NOT_LIVE = S149_BIND_ISSUE_CARRIER_RELATION,
    S149_BIND_ISSUE_CARRIER_DRIFT = S149_BIND_ISSUE_CARRIER_RELATION,
    S149_BIND_ISSUE_CARRIER_ASC_PROPERTY_UNRESOLVED = S149_BIND_ISSUE_CARRIER_RELATION,
    S149_BIND_ISSUE_CARRIER_ASC_SLOT_UNREADABLE = S149_BIND_ISSUE_CARRIER_RELATION,
    S149_BIND_ISSUE_CARRIER_ASC_DRIFT = S149_BIND_ISSUE_CARRIER_RELATION,
};

inline uint32_t S149BindWitnessIssues(const S149BindWitnessFacts& facts) {
    uint32_t issues = S149_BIND_ISSUE_NONE;
    if (facts.callCount != 1) issues |= S149_BIND_ISSUE_CALL_COUNT;
    if (facts.setupFaulted) issues |= S149_BIND_ISSUE_SETUP_FAULTED;
    if (facts.initFaulted) issues |= S149_BIND_ISSUE_INIT_FAULTED;
    if (!facts.terminalRevalidated)
        issues |= S149_BIND_ISSUE_TERMINAL_NOT_REVALIDATED;
    if (!facts.localAuthorityStable) issues |= S149_BIND_ISSUE_LOCAL_AUTHORITY_DRIFT;
    if (!facts.pcLive) issues |= S149_BIND_ISSUE_PC_NOT_LIVE;
    if (!facts.possessedHeroStable) issues |= S149_BIND_ISSUE_POSSESSION_DRIFT;
    if (!facts.heroLive) issues |= S149_BIND_ISSUE_HERO_NOT_LIVE;
    if (!facts.ascLive) issues |= S149_BIND_ISSUE_ASC_NOT_LIVE;
    if (!facts.ascStorageResolved) issues |= S149_BIND_ISSUE_ASC_STORAGE_UNRESOLVED;
    if (!facts.ascStorageReadable) issues |= S149_BIND_ISSUE_ASC_STORAGE_UNREADABLE;
    if (!facts.ascStable) issues |= S149_BIND_ISSUE_ASC_IDENTITY_DRIFT;
    if (!facts.avatarPropertyResolved) issues |= S149_BIND_ISSUE_AVATAR_PROPERTY_UNRESOLVED;
    if (!facts.avatarSlotReadable) issues |= S149_BIND_ISSUE_AVATAR_SLOT_UNREADABLE;
    if (!facts.avatarLive) issues |= S149_BIND_ISSUE_AVATAR_NOT_LIVE;
    if (!facts.avatarMatchesHero) issues |= S149_BIND_ISSUE_AVATAR_MISMATCH;
    if (!facts.ownerPropertyResolved) issues |= S149_BIND_ISSUE_OWNER_PROPERTY_UNRESOLVED;
    if (!facts.ownerSlotReadable) issues |= S149_BIND_ISSUE_OWNER_SLOT_UNREADABLE;
    if (!facts.ownerLive) issues |= S149_BIND_ISSUE_OWNER_NOT_LIVE;
    if (!facts.ownerMatchesCarrier) issues |= S149_BIND_ISSUE_OWNER_MISMATCH;
    if (!facts.carrierPropertyResolved || !facts.carrierSlotReadable ||
        !facts.carrierLive || !facts.carrierStable ||
        !facts.carrierAscPropertyResolved || !facts.carrierAscSlotReadable ||
        !facts.carrierAscStable)
        issues |= S149_BIND_ISSUE_CARRIER_RELATION;
    return issues;
}

inline uint32_t S149BindCleanupIssues(const S149BindCleanupFacts& facts) {
    uint32_t issues = S149_BIND_ISSUE_NONE;
    if (!facts.restoreCountExact || facts.swapped == 0 ||
        facts.restored != facts.swapped)
        issues |= S149_BIND_ISSUE_RESTORE_COUNT_MISMATCH;
    if (!facts.repairScanComplete)
        issues |= S149_BIND_ISSUE_REPAIR_SCAN_INCOMPLETE;
    if (!facts.verifyScanComplete)
        issues |= S149_BIND_ISSUE_VERIFY_SCAN_INCOMPLETE;
    if (facts.residualRemaining != 0)
        issues |= S149_BIND_ISSUE_FUNCS_REMAIN;
    if (!facts.callbacksSealed)
        issues |= S149_BIND_ISSUE_CALLBACKS_NOT_SEALED;
    if (facts.cleanupFaulted)
        issues |= S149_BIND_ISSUE_CLEANUP_FAULTED;
    if (!facts.postRestoreQuiesced || facts.entryPendingRemaining != 0 ||
        facts.parkedRemaining != 0 ||
        facts.activeRemaining != 0 || facts.mutationRootsRemaining != 0)
        issues |= S149_BIND_ISSUE_POST_RESTORE_NOT_QUIESCED;
    return issues;
}

inline uint32_t S149BindAdmissionIssues(const S149BindWitnessFacts& witness,
                                        bool witnessPublished,
                                        const S149BindCleanupFacts& cleanup) {
    uint32_t issues = witnessPublished ? S149BindWitnessIssues(witness) :
        static_cast<uint32_t>(S149_BIND_ISSUE_WITNESS_NOT_PUBLISHED);
    return issues | S149BindCleanupIssues(cleanup);
}

inline bool S149BindWitnessReady(const S149BindWitnessFacts& facts) {
    return S149BindWitnessIssues(facts) == S149_BIND_ISSUE_NONE;
}

inline const char* S149BindOutcomeName(uint32_t issues) {
    return issues == S149_BIND_ISSUE_NONE ? "BIND_READY" : "BIND_REFUSED";
}

#define S149_BIND_POLICY_MARKER_FORMAT \
    "[S149] BIND_ONLY pid=%lu run=%016llX arms=0x02 forbidden=0xFD " \
    "naturalInput=0 selfCal=0 ownerMode=0\r\n"

#define S149_BIND_WITNESS_MARKER_FORMAT \
    "[S149] POST_BIND pid=%lu run=%016llX callCount=%u setupFaulted=%u " \
    "initFaulted=%u terminalRevalidated=%u localAuthorityStable=%u pcLive=%u " \
    "possessedHeroStable=%u " \
    "heroLive=%u ascLive=%u ascStorageResolved=%u " \
    "ascStorageReadable=%u ascStable=%u avatarPropertyResolved=%u " \
    "avatarSlotReadable=%u avatarLive=%u avatarMatchesHero=%u pc=0x%llX " \
    "hero=0x%llX asc=0x%llX avatar=0x%llX\r\n"

#define S149_BIND_OWNER_MARKER_FORMAT \
    "[S149] POST_BIND_OWNER pid=%lu run=%016llX ownerPropertyResolved=%u " \
    "ownerSlotReadable=%u ownerLive=%u ownerMatchesCarrier=%u " \
    "carrierPropertyResolved=%u carrierSlotReadable=%u carrierLive=%u " \
    "carrierStable=%u carrierAscPropertyResolved=%u carrierAscSlotReadable=%u " \
    "carrierAscStable=%u carrier=0x%llX " \
    "owner=0x%llX\r\n"

#define S149_BIND_CLEANUP_MARKER_FORMAT \
    "[S149] CLEANUP restoreCountExact=%u repairScanComplete=%u verifyScanComplete=%u " \
    "callbacksSealed=%u cleanupFaulted=%u postRestoreQuiesced=%u swapped=%lu " \
    "restored=%lu residualRepaired=%lu " \
    "residualRemaining=%lu postRestoreEntries=%lu entryPendingRemaining=%lu " \
    "parkedRemaining=%lu activeRemaining=%lu mutationRootsRemaining=%lu\r\n"

#define S149_BIND_RESULT_MARKER_FORMAT \
    "[S149] RESULT pid=%lu run=%016llX outcome=%s issues=0x%08X " \
    "funcsRestoreVerified=%s postRestoreQuiesced=%s residualRemaining=%lu " \
    "postRestoreEntries=%lu\r\n"

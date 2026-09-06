#pragma once

#include <windows.h>
#include <cstdint>

// Shared, offline-testable policy for S147. tutorial_launch.cpp owns all Unreal memory access; this
// header owns only lifecycle transitions and classification of already-captured raw scalar samples.

enum S147NaturalLifecycle : LONG {
    S147_DISABLED = 0,
    S147_SETUP_OWNS_CDO = 1,
    S147_SETUP_ARMED = 2,
    S147_SETUP_ABORT_REQUESTED = 3,
    S147_WAIT_NEXT_DISPATCH = 4,
    S147_ABORT_UNWOUND = 5,
    S147_WINDOW_OPEN = 6,
    S147_FINISHING = 7,
    S147_FINISHED = 8,
};

// A swapped ProcessInternal call may recursively dispatch another swapped UFunction. Only the
// call that entered before setup was published may certify that the setup callback unwound; a
// nested call that entered while S147_SETUP_ARMED must never advance the lifecycle on its return.
static inline bool S147OwnsSetupReturn(LONG stateAtThunkEntry, LONG stateAfterOnPI,
                                       bool enteredOnGameThread, bool reentrantAtEntry) {
    bool terminalPublication=stateAfterOnPI==S147_SETUP_ARMED||
                             stateAfterOnPI==S147_SETUP_ABORT_REQUESTED;
    return enteredOnGameThread && !reentrantAtEntry && stateAtThunkEntry == S147_DISABLED &&
           terminalPublication;
}

static inline bool S147MarkSetupCallbackReturned(volatile LONG* state) {
    if(InterlockedCompareExchange(state,S147_WAIT_NEXT_DISPATCH,S147_SETUP_ARMED)==S147_SETUP_ARMED)
        return true;
    return InterlockedCompareExchange(state,S147_ABORT_UNWOUND,S147_SETUP_ABORT_REQUESTED)==
           S147_SETUP_ABORT_REQUESTED;
}

static inline bool S147OpenAtLaterDispatch(volatile LONG* state) {
    return InterlockedCompareExchange(state, S147_WINDOW_OPEN, S147_WAIT_NEXT_DISPATCH) ==
           S147_WAIT_NEXT_DISPATCH;
}

static inline bool S147IsReady(LONG state) { return state == S147_WINDOW_OPEN; }

static inline bool S147SafeToFinalize(LONG state) {
    return state==S147_DISABLED||state==S147_WAIT_NEXT_DISPATCH||
           state==S147_ABORT_UNWOUND||state==S147_WINDOW_OPEN||state==S147_FINISHING;
}

enum S147SetupDeadlineKind : uint8_t {
    S147_SETUP_DEADLINE_NONE = 0,
    S147_SETUP_DEADLINE_PRE_RESERVATION = 1,
    S147_SETUP_DEADLINE_POST_RESERVATION = 2,
};

struct S147SetupDeadlineClock {
    ULONGLONG preReservationStart;
    ULONGLONG postReservationStart;
};

// Setup has two distinct safety intervals. Slow game-thread preparation before the CDO tuple is
// claimed must not consume the much tighter claim-to-unwind budget. Once any owned state is seen,
// the post-reservation clock is latched exactly once and remains authoritative through unwind.
static inline S147SetupDeadlineKind S147SetupDeadlineFor(S147SetupDeadlineClock* clock, LONG state,
                                                         ULONGLONG now,
                                                         ULONGLONG preReservationLimit,
                                                         ULONGLONG postReservationLimit) {
    if (!clock) return S147_SETUP_DEADLINE_NONE;
    if (state == S147_DISABLED) {
        return now - clock->preReservationStart >= preReservationLimit
                   ? S147_SETUP_DEADLINE_PRE_RESERVATION
                   : S147_SETUP_DEADLINE_NONE;
    }
    if (clock->postReservationStart == 0) clock->postReservationStart = now;
    return now - clock->postReservationStart >= postReservationLimit
               ? S147_SETUP_DEADLINE_POST_RESERVATION
               : S147_SETUP_DEADLINE_NONE;
}

enum S147NodeKind : uint8_t {
    S147_NODE_OTHER = 0,
    S147_NODE_TOGGLE_MAP = 1,
    S147_NODE_ABILITY3 = 2,
};

static inline S147NodeKind S147ClassifyNode(uintptr_t node, uintptr_t toggleMapNode,
                                            uintptr_t ability3Node) {
    if (node && node == toggleMapNode) return S147_NODE_TOGGLE_MAP;
    if (node && node == ability3Node) return S147_NODE_ABILITY3;
    return S147_NODE_OTHER;
}

enum S147SampleIssue : uint32_t {
    S147_ISSUE_NONE = 0,
    S147_ISSUE_UNREADABLE = 1u << 0,
    S147_ISSUE_ASC_HEADER_CHANGED = 1u << 1,
    S147_ISSUE_SPEC_MISSING = 1u << 2,
    S147_ISSUE_SPEC_AMBIGUOUS = 1u << 3,
    S147_ISSUE_PRIMARY_MISSING = 1u << 4,
    S147_ISSUE_PRIMARY_REPLACED = 1u << 5,
    S147_ISSUE_PRIMARY_WRONG_CLASS = 1u << 6,
    S147_ISSUE_MANA_SET_MISSING = 1u << 7,
    S147_ISSUE_MANA_SET_REPLACED = 1u << 8,
    S147_ISSUE_SPAWNED_HEADER_CHANGED = 1u << 9,
    S147_ISSUE_MANA_SET_AMBIGUOUS = 1u << 10,
    S147_ISSUE_INPUT_ID_CHANGED = 1u << 11,
};

struct S147RawSample {
    uint8_t valid;
    uint8_t specPresent;
    uint8_t primaryPresent;
    uint8_t primaryIdentityMatches;
    uint8_t manaSetPresent;
    uint8_t specFlags;
    uint8_t activeCount;
    uint8_t primary408;
    uint8_t primary409;
    uint8_t primary40A;
    uint8_t reserved0[2];
    int32_t inputID;
    int32_t primaryCharge;
    int32_t cdoCharge;
    uint32_t manaCurrentBits;
    uint32_t manaBaseBits;
    uint32_t issueMask;
    uint32_t toggleMapEvents;
    uint32_t ability3Events;
};

enum S147Receipt : uint32_t {
    S147_RECEIPT_NONE = 0,
    S147_RECEIPT_INPUT_PRESSED = 1u << 0,
    S147_RECEIPT_ACTIVE_COUNT = 1u << 1,
    S147_RECEIPT_PRIMARY_408 = 1u << 2,
    S147_RECEIPT_PRIMARY_409 = 1u << 3,
    S147_RECEIPT_PRIMARY_40A = 1u << 4,
    S147_RECEIPT_PRIMARY_CHARGE = 1u << 5,
    S147_RECEIPT_CDO_CHARGE = 1u << 6,
    S147_RECEIPT_MANA_CURRENT = 1u << 7,
    S147_RECEIPT_MANA_BASE = 1u << 8,
};

static inline bool S147SampleIdentityValid(const S147RawSample& sample) {
    return sample.valid && sample.issueMask == S147_ISSUE_NONE && sample.specPresent &&
           sample.primaryPresent && sample.primaryIdentityMatches && sample.manaSetPresent;
}

static inline bool S147SampleMatchesInputID(const S147RawSample& sample,int32_t expectedInputID) {
    return S147SampleIdentityValid(sample)&&sample.inputID==expectedInputID;
}

static inline uint32_t S147ReceiptMask(const S147RawSample& baseline,
                                      const S147RawSample& current) {
    if (!S147SampleIdentityValid(baseline) || !S147SampleIdentityValid(current)) return 0;
    uint32_t mask = 0;
    if (!(baseline.specFlags & 1u) && (current.specFlags & 1u))
        mask |= S147_RECEIPT_INPUT_PRESSED;
    if (baseline.activeCount == 0 && current.activeCount != 0)
        mask |= S147_RECEIPT_ACTIVE_COUNT;
    if (baseline.primary408 != current.primary408) mask |= S147_RECEIPT_PRIMARY_408;
    if (baseline.primary409 != current.primary409) mask |= S147_RECEIPT_PRIMARY_409;
    if (baseline.primary40A != current.primary40A) mask |= S147_RECEIPT_PRIMARY_40A;
    if (baseline.primaryCharge != current.primaryCharge) mask |= S147_RECEIPT_PRIMARY_CHARGE;
    if (baseline.cdoCharge != current.cdoCharge) mask |= S147_RECEIPT_CDO_CHARGE;
    if (baseline.manaCurrentBits != current.manaCurrentBits) mask |= S147_RECEIPT_MANA_CURRENT;
    if (baseline.manaBaseBits != current.manaBaseBits) mask |= S147_RECEIPT_MANA_BASE;
    return mask;
}

static inline bool S147WindowComplete(uint32_t receiptMask, bool deadlineReached,
                                      bool sawShiftDown, bool sawShiftUp,
                                      bool sampledAfterShiftUp) {
    if (deadlineReached) return true;
    return receiptMask != 0 && sawShiftDown && sawShiftUp && sampledAfterShiftUp;
}

static inline bool S147PositiveResultEligible(uint32_t postShiftReceipt,uint32_t preShiftReceipt,
                                              uint32_t toggleMapEvents,bool controlsOrderedBeforeShift,
                                              uint32_t ability3Events,bool ability3AfterShift) {
    return postShiftReceipt!=0&&preShiftReceipt==0&&toggleMapEvents==2&&
           controlsOrderedBeforeShift&&ability3Events>=1&&ability3AfterShift;
}

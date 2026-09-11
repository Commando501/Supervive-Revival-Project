// Offline behavioral control for S147's natural-input lifecycle and receipt policy.
//
// Build from tools/sigbypass-mod/tests:
//   clang++ -std=c++17 -O2 s147_natural_state_test.cpp -o s147_natural_state_test.exe
//
// This includes the production header used by tutorial_launch.cpp. It deliberately exercises the
// two safety boundaries that matter without needing a game process: READY cannot precede a later
// dispatch, and a Blueprint event alone is not an activation receipt.
#include "../s147_natural_state.h"

#include <cstdio>
#include <cstdlib>

static void Require(bool condition, const char* message) {
    if (!condition) {
        std::fprintf(stderr, "FAIL: %s\n", message);
        std::exit(1);
    }
}

static S147RawSample Baseline() {
    S147RawSample s{};
    s.valid = 1;
    s.specPresent = 1;
    s.primaryPresent = 1;
    s.primaryIdentityMatches = 1;
    s.manaSetPresent = 1;
    s.inputID = 5;
    s.primaryCharge = 1;
    s.cdoCharge = 1;
    s.manaCurrentBits = 0x41200000u; // 10.0f, hand-derived IEEE-754 literal
    s.manaBaseBits = 0x41200000u;
    return s;
}

int main() {
    Require(S147OwnsSetupReturn(S147_DISABLED, S147_SETUP_ARMED, true, false),
            "the dispatch that published setup must own the unwind transition");
    Require(!S147OwnsSetupReturn(S147_SETUP_ARMED, S147_SETUP_ARMED, true, false),
            "a nested dispatch entered after setup publication must not claim the outer unwind");
    Require(!S147OwnsSetupReturn(S147_DISABLED, S147_SETUP_ARMED, false, false),
            "a non-game-thread dispatch must not claim game-thread setup publication");
    Require(!S147OwnsSetupReturn(S147_DISABLED, S147_SETUP_ARMED, true, true),
            "a reentrant game-thread dispatch must not claim its outer callback unwind");

    volatile LONG abortLifecycle = S147_SETUP_ABORT_REQUESTED;
    Require(S147MarkSetupCallbackReturned(&abortLifecycle),
            "the setup owner must publish that an aborting callback unwound");
    Require(abortLifecycle == S147_ABORT_UNWOUND,
            "an abort request must become worker-safe only after callback return");
    Require(!S147SafeToFinalize(S147_SETUP_OWNS_CDO),
            "the worker must not restore while setup may still write the CDO");
    Require(!S147SafeToFinalize(S147_SETUP_ARMED),
            "the worker must not restore before the armed setup callback returns");
    Require(S147SafeToFinalize(S147_ABORT_UNWOUND),
            "the worker may restore an aborted setup after unwind is proven");

    S147SetupDeadlineClock setupClock{1000, 0};
    Require(S147SetupDeadlineFor(&setupClock, S147_DISABLED, 11000, 60000, 10000) ==
                S147_SETUP_DEADLINE_NONE,
            "the post-claim deadline must not run while setup is still pre-reservation");
    Require(setupClock.postReservationStart == 0,
            "pre-reservation waiting must not start the post-claim clock");
    Require(S147SetupDeadlineFor(&setupClock, S147_DISABLED, 61000, 60000, 10000) ==
                S147_SETUP_DEADLINE_PRE_RESERVATION,
            "the separate pre-reservation deadline must bound a setup that never claims");

    setupClock = {1000, 0};
    Require(S147SetupDeadlineFor(&setupClock, S147_SETUP_OWNS_CDO, 12000, 60000, 10000) ==
                S147_SETUP_DEADLINE_NONE,
            "observing ownership must start, not immediately expire, the post-claim clock");
    Require(setupClock.postReservationStart == 12000,
            "the post-claim clock must begin on the first owned-state observation");
    Require(S147SetupDeadlineFor(&setupClock, S147_SETUP_ARMED, 21999, 60000, 10000) ==
                S147_SETUP_DEADLINE_NONE,
            "the full post-claim unwind budget must remain available");
    Require(S147SetupDeadlineFor(&setupClock, S147_WAIT_NEXT_DISPATCH, 22000, 60000, 10000) ==
                S147_SETUP_DEADLINE_POST_RESERVATION,
            "the post-claim deadline must expire only after its own full interval");
    Require(S147SetupDeadlineFor(&setupClock, S147_WINDOW_OPEN, 22000, 60000, 10000) ==
                S147_SETUP_DEADLINE_POST_RESERVATION,
            "WINDOW_OPEN at the expired boundary must time out instead of publishing READY");

    volatile LONG lifecycle = S147_SETUP_ARMED;
    Require(!S147IsReady(lifecycle), "setup publication must not be READY");
    Require(S147MarkSetupCallbackReturned(&lifecycle),
            "the setup thunk must publish that its real ProcessInternal call returned");
    Require(lifecycle == S147_WAIT_NEXT_DISPATCH,
            "callback return must wait for a distinct later dispatch");
    Require(!S147IsReady(lifecycle), "callback return alone must not be READY");
    Require(S147OpenAtLaterDispatch(&lifecycle), "a later dispatch must open the input window");
    Require(S147IsReady(lifecycle), "the later dispatch is the first READY state");
    Require(!S147OpenAtLaterDispatch(&lifecycle), "the open transition must be one-shot");

    const uintptr_t toggleNode = 0x1000;
    const uintptr_t ability3Node = 0x2000;
    Require(S147ClassifyNode(toggleNode, toggleNode, ability3Node) == S147_NODE_TOGGLE_MAP,
            "Toggle Map must be identified by exact resolved node identity");
    Require(S147ClassifyNode(ability3Node, toggleNode, ability3Node) == S147_NODE_ABILITY3,
            "Ability3 must be identified by exact resolved node identity");
    Require(S147ClassifyNode(0x3000, toggleNode, ability3Node) == S147_NODE_OTHER,
            "an unrelated Blueprint node must not be counted");

    const S147RawSample baseline = Baseline();
    Require(S147SampleMatchesInputID(baseline, 5),
            "the fresh exact spec must carry canonical Ability3 InputID 5");
    S147RawSample wrongInput = baseline;
    wrongInput.inputID = -1;
    Require(!S147SampleMatchesInputID(wrongInput, 5),
            "a stale INDEX_NONE spec must fail the final natural-input identity gate");
    S147RawSample current = baseline;
    current.ability3Events = 1;
    Require(S147ReceiptMask(baseline, current) == S147_RECEIPT_NONE,
            "an Ability3 Blueprint event alone must not count as activation");

    current = baseline;
    current.specFlags = 1;
    Require((S147ReceiptMask(baseline, current) & S147_RECEIPT_INPUT_PRESSED) != 0,
            "InputPressed bit 0 transition must be a receipt");

    current = baseline;
    current.activeCount = 1;
    Require((S147ReceiptMask(baseline, current) & S147_RECEIPT_ACTIVE_COUNT) != 0,
            "ActiveCount transition must be a receipt");

    current = baseline;
    current.primary408 = 1;
    Require((S147ReceiptMask(baseline, current) & S147_RECEIPT_PRIMARY_408) != 0,
            "primary +0x408 transition must be a receipt");
    current = baseline;
    current.primary409 = 1;
    Require((S147ReceiptMask(baseline, current) & S147_RECEIPT_PRIMARY_409) != 0,
            "primary +0x409 transition must be a receipt");
    current = baseline;
    current.primary40A = 1;
    Require((S147ReceiptMask(baseline, current) & S147_RECEIPT_PRIMARY_40A) != 0,
            "primary +0x40A transition must be a receipt");

    current = baseline;
    current.primaryCharge = 0;
    Require((S147ReceiptMask(baseline, current) & S147_RECEIPT_PRIMARY_CHARGE) != 0,
            "primary charge decrement must be a receipt");
    current = baseline;
    current.cdoCharge = 0;
    Require((S147ReceiptMask(baseline, current) & S147_RECEIPT_CDO_CHARGE) != 0,
            "CDO charge decrement must be a receipt");
    current = baseline;
    current.manaCurrentBits = 0x41100000u; // 9.0f
    Require((S147ReceiptMask(baseline, current) & S147_RECEIPT_MANA_CURRENT) != 0,
            "current Mana delta must be a receipt");
    current = baseline;
    current.manaBaseBits = 0x41100000u;
    Require((S147ReceiptMask(baseline, current) & S147_RECEIPT_MANA_BASE) != 0,
            "base Mana delta must be a receipt");

    current = baseline;
    current.valid = 0;
    current.issueMask = S147_ISSUE_UNREADABLE;
    current.specFlags = 1;
    Require(S147ReceiptMask(baseline, current) == S147_RECEIPT_NONE,
            "an invalid sample must never manufacture a receipt");

    Require(!S147WindowComplete(S147_RECEIPT_INPUT_PRESSED, false, true, false, false),
            "a receipt while LeftShift is held must wait for a post-key-up sample");
    Require(!S147WindowComplete(S147_RECEIPT_NONE, false, true, true, true),
            "key-up without a receipt must keep sampling");
    Require(S147WindowComplete(S147_RECEIPT_INPUT_PRESSED, false, true, true, true),
            "receipt plus a post-key-up sample must complete the window");
    Require(S147WindowComplete(S147_RECEIPT_NONE, true, false, false, false),
            "the deadline must always complete the bounded window");

    Require(S147PositiveResultEligible(S147_RECEIPT_INPUT_PRESSED, 0, 2, true, 1, true),
            "a post-Shift GAS receipt with two ordered controls and Ability3 is positive");
    Require(!S147PositiveResultEligible(S147_RECEIPT_INPUT_PRESSED, 0, 1, false, 1, true),
            "a missing Tab close control must void the activation classification");
    Require(!S147PositiveResultEligible(S147_RECEIPT_INPUT_PRESSED, 0, 2, true, 0, false),
            "a missing Ability3 node must not be called natural-input activation");
    Require(!S147PositiveResultEligible(S147_RECEIPT_INPUT_PRESSED,
                                        S147_RECEIPT_PRIMARY_CHARGE, 2, true, 1, true),
            "pre-Shift state drift must void later attribution");

    std::puts("PASS s147_natural_state_test");
    return 0;
}

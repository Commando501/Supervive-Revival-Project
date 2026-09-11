// Offline behavioral policy test for S148A's self-owned ASC damage calibration.
//
// Build from tools/sigbypass-mod/tests:
//   clang++ -std=c++17 -O2 s148_damage_calibration_test.cpp -o s148_damage_calibration_test.exe
#include "../s148_damage_calibration.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>

static void Require(bool condition, const char* message) {
    if (!condition) {
        std::fprintf(stderr, "FAIL: %s\n", message);
        std::exit(1);
    }
}

static S148HealthFacts LiveFacts() {
    S148HealthFacts facts{};
    facts.ownerScanComplete = 1;
    facts.gameInstanceMembershipValid = 1;
    facts.worldIdentityValid = 1;
    facts.reflectedProvenanceValid = 1;
    facts.registrationScanComplete = 1;
    facts.registrationOwnerValid = 1;
    facts.registrationCount = 1;
    facts.ascValid = 1;
    facts.ascInstanceOwned = 1;
    facts.avatarBindingValid = 1;
    facts.spawnedHeaderValid = 1;
    facts.spawnedMemberTypesValid = 1;
    facts.attributeLayoutValid = 1;
    facts.censusClosureValid = 1;
    facts.structPayloadValid = 1;
    facts.healthCandidateCount = 1;
    facts.candidateReadable = 1;
    facts.candidateWritable = 1;
    facts.candidateClassExact = 1;
    facts.maxHealthPresent = 1;
    facts.maxHealthReadable = 1;
    facts.originalBaseBits = 0x447A0000u;    // 1000.0f
    facts.originalCurrentBits = 0x447A0000u;
    facts.maxBaseBits = 0x44FA0000u;         // 2000.0f
    facts.maxCurrentBits = 0x44FA0000u;
    return facts;
}

static void TestOwnerScanFailureRecorder() {
    S148OwnerScanFailure failure{};
    Require(failure.reason == S148_OWNER_SCAN_NONE,
            "a fresh owner-scan diagnostic must not report a failure");

    S148RecordOwnerScanFailure(&failure, S148_OWNER_SCAN_PHASE_ENUM_OBJECT,
                               S148_OWNER_SCAN_OBJECT_CLASS_INVALID,
                               137, 4, 2, 1, 0x1111222233334444ull,
                               0x2222333344445555ull, 0x5555666677778888ull,
                               0x9999AAAABBBBCCCCull);
    Require(failure.phase == S148_OWNER_SCAN_PHASE_ENUM_OBJECT &&
            failure.reason == S148_OWNER_SCAN_OBJECT_CLASS_INVALID &&
            failure.snapshotIndex == 137 && failure.censusIndex == 4 &&
            failure.localIndex == 2 && failure.pass == 1 &&
            failure.object == 0x1111222233334444ull &&
            failure.address == 0x2222333344445555ull &&
            failure.detail0 == 0x5555666677778888ull &&
            failure.detail1 == 0x9999AAAABBBBCCCCull,
            "the first owner-scan failure must retain its exact branch and context");
    Require(std::strcmp(S148OwnerScanPhaseName(failure.phase),
                        "ENUM_OBJECT") == 0,
            "the owner-scan phase name must be stable for the runtime marker");
    Require(std::strcmp(S148OwnerScanReasonName(failure.reason),
                        "OBJECT_CLASS_INVALID") == 0,
            "the owner-scan reason name must be stable for the runtime marker");

    S148RecordOwnerScanFailure(&failure, S148_OWNER_SCAN_PHASE_CENSUS_REVALIDATE,
                               S148_OWNER_SCAN_CENSUS_DATA_CHANGED,
                               999, 8, 7, 6, 5, 4, 3, 2);
    Require(failure.phase == S148_OWNER_SCAN_PHASE_ENUM_OBJECT &&
            failure.reason == S148_OWNER_SCAN_OBJECT_CLASS_INVALID &&
            failure.snapshotIndex == 137 && failure.censusIndex == 4 &&
            failure.localIndex == 2 && failure.pass == 1 &&
            failure.object == 0x1111222233334444ull &&
            failure.address == 0x2222333344445555ull &&
            failure.detail0 == 0x5555666677778888ull &&
            failure.detail1 == 0x9999AAAABBBBCCCCull,
            "a later failure must not overwrite the first causal owner-scan failure");

    S148OwnerScanFailure ignored{};
    S148RecordOwnerScanFailure(&ignored, S148_OWNER_SCAN_PHASE_ENUM_OBJECT,
                               S148_OWNER_SCAN_NONE,
                               1, 2, 3, 4, 5, 6, 7, 8);
    Require(ignored.reason == S148_OWNER_SCAN_NONE,
            "recording NONE must leave the owner-scan diagnostic empty");
    Require(std::strcmp(S148OwnerScanReasonName(
                            static_cast<S148OwnerScanReason>(0xFFFFFFFFu)),
                        "UNKNOWN") == 0,
            "an unknown owner-scan reason must have an explicit fallback name");
}

static void TestClassChainFailureRecorder() {
    S148ClassChainFailure failure{};
    Require(failure.reason == S148_CLASS_CHAIN_NONE,
            "a fresh class-chain diagnostic must not report a failure");

    S148RecordClassChainFailure(&failure, S148_CLASS_CHAIN_SUPER_POINTER_INVALID,
                                7, 0x1111222233334444ull,
                                0x2222333344445555ull, 0xDEADBEEFCAFEBABEull,
                                0x9999AAAABBBBCCCCull);
    Require(failure.reason == S148_CLASS_CHAIN_SUPER_POINTER_INVALID &&
            failure.depth == 7 &&
            failure.node == 0x1111222233334444ull &&
            failure.address == 0x2222333344445555ull &&
            failure.detail0 == 0xDEADBEEFCAFEBABEull &&
            failure.detail1 == 0x9999AAAABBBBCCCCull,
            "the first class-chain failure must retain its exact leaf and scalars");
    Require(std::strcmp(S148ClassChainFailureName(failure.reason),
                        "SUPER_POINTER_INVALID") == 0,
            "the class-chain failure name must be stable for the runtime marker");

    S148RecordClassChainFailure(&failure, S148_CLASS_CHAIN_DEPTH_LIMIT,
                                31, 5, 4, 3, 2);
    Require(failure.reason == S148_CLASS_CHAIN_SUPER_POINTER_INVALID &&
            failure.depth == 7 &&
            failure.node == 0x1111222233334444ull &&
            failure.address == 0x2222333344445555ull &&
            failure.detail0 == 0xDEADBEEFCAFEBABEull &&
            failure.detail1 == 0x9999AAAABBBBCCCCull,
            "a later class-chain failure must not overwrite the first failing leaf");

    S148ClassChainFailure ignored{};
    S148RecordClassChainFailure(&ignored, S148_CLASS_CHAIN_NONE,
                                1, 2, 3, 4, 5);
    Require(ignored.reason == S148_CLASS_CHAIN_NONE,
            "recording a NONE leaf must leave the class-chain diagnostic empty");

    const char* expectedNames[] = {
        "NONE",
        "NODE_POINTER_INVALID",
        "NODE_NOT_LIVE",
        "CYCLE",
        "NAME_DECODE_FAILED",
        "OUTPUT_BUFFER_EXHAUSTED",
        "SUPER_CELL_UNREADABLE",
        "SUPER_POINTER_INVALID",
        "DEPTH_LIMIT",
    };
    static_assert(sizeof(expectedNames) / sizeof(expectedNames[0]) ==
                      S148_CLASS_CHAIN_FAILURE_COUNT,
                  "the class-chain name fixture must cover every leaf");
    for (uint32_t reason = 0; reason < S148_CLASS_CHAIN_FAILURE_COUNT; ++reason) {
        Require(std::strcmp(S148ClassChainFailureName(
                                static_cast<S148ClassChainFailureReason>(reason)),
                            expectedNames[reason]) == 0,
                "every in-range class-chain leaf must retain its exact marker name");
    }
    Require(std::strcmp(S148ClassChainFailureName(
                            static_cast<S148ClassChainFailureReason>(0xFFFFFFFFu)),
                        "UNKNOWN") == 0,
            "an unknown class-chain leaf must have an explicit fallback name");
}

static void TestOwnerFailureCapturesClassChainFailure() {
    S148ClassChainFailure chain{};
    S148RecordClassChainFailure(&chain, S148_CLASS_CHAIN_NAME_DECODE_FAILED,
                                3, 0x1111111122222222ull,
                                0x3333333344444444ull, 0x55667788ull, 0x99AABBCCull);

    S148OwnerScanFailure owner{};
    S148RecordOwnerScanFailure(&owner, S148_OWNER_SCAN_PHASE_ENUM_OBJECT,
                               S148_OWNER_SCAN_GAME_INSTANCE_CHAIN_MALFORMED,
                               107033, 1, -1, -1,
                               0x5555555566666666ull, 0,
                               0x7777777788888888ull, 0xFFFFFFFFFFFFFFFFull,
                               &chain);
    Require(owner.reason == S148_OWNER_SCAN_GAME_INSTANCE_CHAIN_MALFORMED &&
            owner.chain.reason == S148_CLASS_CHAIN_NAME_DECODE_FAILED &&
            owner.chain.depth == 3 &&
            owner.chain.node == 0x1111111122222222ull &&
            owner.chain.address == 0x3333333344444444ull &&
            owner.chain.detail0 == 0x55667788ull &&
            owner.chain.detail1 == 0x99AABBCCull,
            "the first owner refusal must carry the exact nested class-chain failure");

    S148ClassChainFailure later{};
    S148RecordClassChainFailure(&later, S148_CLASS_CHAIN_DEPTH_LIMIT,
                                32, 9, 8, 7, 6);
    S148RecordOwnerScanFailure(&owner, S148_OWNER_SCAN_PHASE_SELECTION,
                               S148_OWNER_SCAN_CANDIDATE_COUNT_ZERO,
                               9, 8, 7, 6, 5, 4, 3, 2, &later);
    Require(owner.reason == S148_OWNER_SCAN_GAME_INSTANCE_CHAIN_MALFORMED &&
            owner.chain.reason == S148_CLASS_CHAIN_NAME_DECODE_FAILED &&
            owner.chain.depth == 3 &&
            owner.chain.node == 0x1111111122222222ull &&
            owner.chain.address == 0x3333333344444444ull &&
            owner.chain.detail0 == 0x55667788ull &&
            owner.chain.detail1 == 0x99AABBCCull,
            "a later owner refusal must not overwrite nested class-chain provenance");

    S148OwnerScanFailure ordinaryFirst{};
    S148RecordOwnerScanFailure(&ordinaryFirst, S148_OWNER_SCAN_PHASE_CAPTURE,
                               S148_OWNER_SCAN_GUOBJECT_HEADER_INVALID,
                               1, 2, 3, 4, 5, 6, 7, 8);
    S148RecordOwnerScanFailure(&ordinaryFirst, S148_OWNER_SCAN_PHASE_ENUM_OBJECT,
                               S148_OWNER_SCAN_GAME_INSTANCE_CHAIN_MALFORMED,
                               9, 10, 11, 12, 13, 14, 15, 16, &chain);
    Require(ordinaryFirst.reason == S148_OWNER_SCAN_GUOBJECT_HEADER_INVALID &&
            ordinaryFirst.chain.reason == S148_CLASS_CHAIN_NONE &&
            ordinaryFirst.chain.depth == 0 && ordinaryFirst.chain.node == 0 &&
            ordinaryFirst.chain.address == 0 && ordinaryFirst.chain.detail0 == 0 &&
            ordinaryFirst.chain.detail1 == 0,
            "a later chain failure must not contaminate an ordinary first owner refusal");
}

static void TestClassChainMarkerBound() {
    char representative[512]{};
    int representativeWritten = std::snprintf(
        representative, sizeof(representative), S148_CLASS_CHAIN_MARKER_FORMAT,
        "NAME_DECODE_FAILED", 4u, 3,
        0x1111222233334444ull, 0x5555666677778888ull,
        0x99AABBCCDDEEFF00ull, 0x123456789ABCDEF0ull);
    Require(representativeWritten > 0 &&
                std::strcmp(
                    representative,
                    "[S148] CHAIN_REFUSAL leaf=NAME_DECODE_FAILED code=4 depth=3 "
                    "node=0x1111222233334444 addr=0x5555666677778888 "
                    "d0=0x99AABBCCDDEEFF00 d1=0x123456789ABCDEF0\r\n") == 0,
            "the class-chain marker must preserve field names, order, bases, and terminator");

    for (uint32_t reason = 0; reason < S148_CLASS_CHAIN_FAILURE_COUNT; ++reason) {
        char marker[512]{};
        int written = std::snprintf(
            marker, sizeof(marker), S148_CLASS_CHAIN_MARKER_FORMAT,
            S148ClassChainFailureName(
                static_cast<S148ClassChainFailureReason>(reason)),
            0xFFFFFFFFu, -2147483647 - 1,
            0xFFFFFFFFFFFFFFFFull, 0xFFFFFFFFFFFFFFFFull,
            0xFFFFFFFFFFFFFFFFull, 0xFFFFFFFFFFFFFFFFull);
        Require(written > 1 && written < static_cast<int>(sizeof(marker)),
                "every class-chain refusal marker must fit Markerf's 512-byte buffer");
        Require(marker[written - 2] == '\r' && marker[written - 1] == '\n' &&
                    marker[written] == '\0',
                "every class-chain refusal marker must retain its CRLF terminator");
    }
}

static void TestOwnerScanMarkerBound() {
    for (uint32_t phase = 0; phase < S148_OWNER_SCAN_PHASE_COUNT; ++phase) {
        for (uint32_t reason = 0; reason < S148_OWNER_SCAN_REASON_COUNT; ++reason) {
            char marker[512]{};
            int written = std::snprintf(
                marker, sizeof(marker), S148_OWNER_SCAN_MARKER_FORMAT,
                S148OwnerScanPhaseName(static_cast<S148OwnerScanPhase>(phase)),
                S148OwnerScanReasonName(static_cast<S148OwnerScanReason>(reason)),
                0xFFFFFFFFu, -2147483647 - 1, -2147483647 - 1,
                -2147483647 - 1, -2147483647 - 1,
                0xFFFFFFFFFFFFFFFFull, 0xFFFFFFFFFFFFFFFFull,
                0xFFFFFFFFFFFFFFFFull, 0xFFFFFFFFFFFFFFFFull,
                -2147483647 - 1, -2147483647 - 1,
                -2147483647 - 1, -2147483647 - 1);
            Require(written > 1 && written < static_cast<int>(sizeof(marker)),
                    "every owner-refusal marker must fit Markerf's 512-byte buffer");
            Require(marker[written - 2] == '\r' && marker[written - 1] == '\n' &&
                        marker[written] == '\0',
                    "every owner-refusal marker must retain its CRLF terminator");
        }
    }
}

static S148LocalPlayersSchemaFacts ValidLocalPlayersSchemaFacts() {
    S148LocalPlayersSchemaFacts facts{};
    facts.classValid = 1;
    facts.lookupResult = 1;
    facts.propertyPointerValid = 1;
    facts.convenienceOffsetValid = 1;
    facts.offsetsMatch = 1;
    facts.requiredOffsetMatches = 1;
    facts.outerElementSizeValid = 1;
    facts.outerArrayDimValid = 1;
    facts.outerTypeValid = 1;
    facts.outerOwnerValid = 1;
    facts.innerPointerValid = 1;
    facts.innerElementSizeValid = 1;
    facts.innerArrayDimValid = 1;
    facts.innerTypeValid = 1;
    facts.innerClassValid = 1;
    return facts;
}

static void TestLocalPlayersSchemaReasons() {
    S148LocalPlayersSchemaFacts facts = ValidLocalPlayersSchemaFacts();
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_NONE,
            "an exact LocalPlayers array schema must not report a diagnostic failure");

    facts = ValidLocalPlayersSchemaFacts(); facts.classValid = 0;
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_SCHEMA_CLASS_INVALID,
            "an invalid schema class must name the class branch");
    facts = ValidLocalPlayersSchemaFacts(); facts.lookupResult = -1;
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_SCHEMA_LOOKUP_MALFORMED,
            "a malformed strict lookup must not look like property absence");
    facts = ValidLocalPlayersSchemaFacts(); facts.lookupResult = 0;
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_SCHEMA_LOOKUP_NO_MATCH,
            "an honest strict lookup miss must have its own reason");
    facts = ValidLocalPlayersSchemaFacts(); facts.propertyPointerValid = 0;
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_SCHEMA_PROPERTY_POINTER_INVALID,
            "an invalid reflected property pointer must name the pointer branch");
    facts = ValidLocalPlayersSchemaFacts(); facts.convenienceOffsetValid = 0;
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_SCHEMA_CONVENIENCE_OFFSET_INVALID,
            "a missing convenience offset must be distinguishable");
    facts = ValidLocalPlayersSchemaFacts(); facts.offsetsMatch = 0;
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_SCHEMA_OFFSET_MISMATCH,
            "convenience and reflected offset disagreement must be distinguishable");
    facts = ValidLocalPlayersSchemaFacts(); facts.requiredOffsetMatches = 0;
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_SCHEMA_REQUIRED_OFFSET_MISMATCH,
            "a required fixed offset mismatch must be distinguishable");
    facts = ValidLocalPlayersSchemaFacts(); facts.outerElementSizeValid = 0;
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_SCHEMA_OUTER_ELEMENT_SIZE_INVALID,
            "an invalid outer element size must name its branch");
    facts = ValidLocalPlayersSchemaFacts(); facts.outerArrayDimValid = 0;
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_SCHEMA_OUTER_ARRAY_DIM_INVALID,
            "an invalid outer ArrayDim must name its branch");
    facts = ValidLocalPlayersSchemaFacts(); facts.outerTypeValid = 0;
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_SCHEMA_OUTER_TYPE_INVALID,
            "an invalid outer property type must name its branch");
    facts = ValidLocalPlayersSchemaFacts(); facts.outerOwnerValid = 0;
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_SCHEMA_OUTER_OWNER_INVALID,
            "an invalid declaring owner must name its branch");
    facts = ValidLocalPlayersSchemaFacts(); facts.innerPointerValid = 0;
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_SCHEMA_INNER_POINTER_INVALID,
            "an invalid Inner pointer must name its branch");
    facts = ValidLocalPlayersSchemaFacts(); facts.innerElementSizeValid = 0;
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_SCHEMA_INNER_ELEMENT_SIZE_INVALID,
            "an invalid Inner element size must name its branch");
    facts = ValidLocalPlayersSchemaFacts(); facts.innerArrayDimValid = 0;
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_SCHEMA_INNER_ARRAY_DIM_INVALID,
            "an invalid Inner ArrayDim must name its branch");
    facts = ValidLocalPlayersSchemaFacts(); facts.innerTypeValid = 0;
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_SCHEMA_INNER_TYPE_INVALID,
            "an invalid Inner type must name its branch");
    facts = ValidLocalPlayersSchemaFacts(); facts.innerClassValid = 0;
    Require(S148LocalPlayersSchemaReason(facts) == S148_OWNER_SCAN_SCHEMA_INNER_CLASS_INVALID,
            "an invalid Inner PropertyClass must name its branch");
}

int main() {
    TestOwnerScanFailureRecorder();
    TestOwnerScanMarkerBound();
    TestClassChainFailureRecorder();
    TestOwnerFailureCapturesClassChainFailure();
    TestClassChainMarkerBound();
    TestLocalPlayersSchemaReasons();

    S148HealthFacts facts = LiveFacts();
    Require(S148PreflightIssues(facts) == S148_ISSUE_NONE,
            "one exact live non-shared writable Health set with MaxHealth >= 1000 must pass");

    facts = LiveFacts(); facts.ownerScanComplete = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_OWNER_SCAN_INCOMPLETE) != 0,
            "a partial global owner scan must refuse before mutation");
    facts = LiveFacts(); facts.gameInstanceMembershipValid = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_GAME_INSTANCE_MEMBERSHIP) != 0,
            "a LocalPlayer outside an exact active GameInstance.LocalPlayers membership must refuse");
    facts = LiveFacts(); facts.worldIdentityValid = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_WORLD_IDENTITY) != 0,
            "a controller or hero outside the selected GameInstance world must refuse");
    facts = LiveFacts(); facts.reflectedProvenanceValid = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_PROPERTY_PROVENANCE) != 0,
            "an unproved reflected property owner/type/shape must refuse before mutation");
    facts = LiveFacts(); facts.registrationScanComplete = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_SET_REGISTRATION) != 0,
            "an incomplete global ASC registration scan must refuse before mutation");
    facts = LiveFacts(); facts.registrationCount = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_SET_REGISTRATION) != 0,
            "a Health set absent from all live ASC registrations must refuse");
    facts = LiveFacts(); facts.registrationCount = 2;
    Require((S148PreflightIssues(facts) & S148_ISSUE_SET_REGISTRATION) != 0,
            "a Health set registered in multiple ASCs must refuse as shared");
    facts = LiveFacts(); facts.registrationOwnerValid = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_SET_REGISTRATION) != 0,
            "a uniquely registered Health set must belong to the selected ASC");
    facts = LiveFacts(); facts.ascValid = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_ASC_INVALID) != 0,
            "a missing or stale ASC must refuse before mutation");
    facts = LiveFacts(); facts.ascInstanceOwned = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_ASC_OWNERSHIP) != 0,
            "a CDO or default-subobject ASC must refuse before mutation");
    facts = LiveFacts(); facts.avatarBindingValid = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_AVATAR_BINDING) != 0,
            "the selected ASC must have reflected AvatarActor equal to the possessed hero");
    facts = LiveFacts(); facts.spawnedHeaderValid = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_SPAWNED_HEADER_INVALID) != 0,
            "an invalid SpawnedAttributes header must refuse before mutation");
    facts = LiveFacts(); facts.spawnedMemberTypesValid = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_SPAWNED_MEMBER_TYPE) != 0,
            "every non-null SpawnedAttributes member must be a complete AttributeSet chain");
    facts = LiveFacts(); facts.attributeLayoutValid = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_ATTRIBUTE_LAYOUT) != 0,
            "Health and MaxHealth must be class-size bounded and non-overlapping");
    facts = LiveFacts(); facts.censusClosureValid = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_CENSUS_CLOSURE) != 0,
            "all owner/registration containers must remain exact through census completion");
    facts = LiveFacts(); facts.structPayloadValid = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_STRUCT_PAYLOAD) != 0,
            "Health and MaxHealth must share one exact live GameplayAttributeData UScriptStruct");
    facts = LiveFacts(); facts.healthCandidateCount = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_HEALTH_COUNT) != 0,
            "zero registered Health sets must refuse");
    facts = LiveFacts(); facts.healthCandidateCount = 2;
    Require((S148PreflightIssues(facts) & S148_ISSUE_HEALTH_COUNT) != 0,
            "ambiguous registered Health sets must refuse");
    facts = LiveFacts(); facts.candidateReadable = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_CANDIDATE_INVALID) != 0,
            "an unreadable candidate must refuse");
    facts = LiveFacts(); facts.candidateWritable = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_HEALTH_NOT_WRITABLE) != 0,
            "unwritable Health Base/Current fields must refuse");
    facts = LiveFacts(); facts.candidateClassExact = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_HEALTH_CLASS) != 0,
            "a health-bearing set of the wrong class must refuse");
    facts = LiveFacts(); facts.candidateIsCdo = 1;
    Require((S148PreflightIssues(facts) & S148_ISSUE_SHARED_CDO) != 0,
            "a class default Health set must refuse");
    facts = LiveFacts(); facts.candidateHasCdoOuter = 1;
    Require((S148PreflightIssues(facts) & S148_ISSUE_SHARED_CDO) != 0,
            "a default subobject owned through a CDO outer chain must refuse");
    facts = LiveFacts(); facts.originalCurrentBits = 0x7FC00000u; // quiet NaN
    Require((S148PreflightIssues(facts) & S148_ISSUE_HEALTH_NONFINITE) != 0,
            "a non-finite original Health value must refuse");
    facts = LiveFacts(); facts.originalBaseBits = 0xBF800000u; // -1.0f
    Require((S148PreflightIssues(facts) & S148_ISSUE_HEALTH_OUT_OF_RANGE) != 0,
            "negative original Health must refuse before mutation");
    facts = LiveFacts(); facts.originalCurrentBits = 0x453B8000u; // 3000.0f > MaxHealth 2000
    Require((S148PreflightIssues(facts) & S148_ISSUE_HEALTH_OUT_OF_RANGE) != 0,
            "original Health above the matching MaxHealth snapshot must refuse");
    facts = LiveFacts(); facts.maxHealthPresent = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_MAX_HEALTH_INVALID) != 0,
            "missing MaxHealth must refuse because the seed clamp is unknown");
    facts = LiveFacts(); facts.maxHealthReadable = 0;
    Require((S148PreflightIssues(facts) & S148_ISSUE_MAX_HEALTH_INVALID) != 0,
            "unreadable MaxHealth must refuse because the seed clamp is unknown");
    facts = LiveFacts(); facts.maxCurrentBits = 0x4479C000u; // 999.0f
    Require((S148PreflightIssues(facts) & S148_ISSUE_MAX_HEALTH_BELOW_SEED) != 0,
            "MaxHealth Current below 1000 must refuse the 1000 seed");
    facts = LiveFacts(); facts.maxBaseBits = 0xFF800000u; // -infinity
    Require((S148PreflightIssues(facts) & S148_ISSUE_MAX_HEALTH_INVALID) != 0,
            "non-finite MaxHealth must refuse");

    Require(S148SeedExact(0x447A0000u, 0x447A0000u),
            "both Health values at exact 1000 bits must certify the seed");
    Require(!S148SeedExact(0x443B8000u, 0x447A0000u),
            "a partial Base/Current seed must not certify the write");

    Require(S148ImmediateReceipt(true, false, true, 0x443B8000u),
            "one resolved non-faulting call with stable identity and Current 750 must receipt");
    Require(!S148ImmediateReceipt(false, false, true, 0x443B8000u),
            "an unresolved AdjustHealth function must not receipt");
    Require(!S148ImmediateReceipt(true, true, true, 0x443B8000u),
            "a faulted AdjustHealth call must not receipt");
    Require(!S148ImmediateReceipt(true, false, false, 0x443B8000u),
            "immediate target-identity drift must not receipt");
    Require(!S148ImmediateReceipt(true, false, true, 0x447A0000u),
            "a returned call with unchanged Current 1000 must not receipt");

    Require(S148LaterReceipt(true, true, 0x443B8000u),
            "an immediate receipt plus stable delayed Current 750 must complete calibration");
    Require(!S148LaterReceipt(false, true, 0x443B8000u),
            "a delayed 750 cannot rescue a missing immediate receipt");
    Require(!S148LaterReceipt(true, false, 0x443B8000u),
            "a delayed identity change must void durability");
    Require(!S148LaterReceipt(true, true, 0x447A0000u),
            "a delayed rebound to 1000 must fail durability");

    std::puts("PASS s148_damage_calibration_test");
    return 0;
}

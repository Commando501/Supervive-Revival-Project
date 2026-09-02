#pragma once

#include <cstdint>

// Offline-testable scalar policy for S148A. tutorial_launch.cpp owns every Unreal pointer walk,
// reflected lookup, and write; this header decides whether already-captured facts are safe enough
// to mutate and whether the immediate/delayed scalar observations constitute a receipt.

constexpr uint32_t S148_HEALTH_SEED_BITS = 0x447A0000u;     // 1000.0f
constexpr uint32_t S148_HEALTH_EXPECTED_BITS = 0x443B8000u; //  750.0f

// Marker line the runtime emits once at the start of the S148 self-damage flight to record the
// owner-census class-chain policy. Presence in the DLL is a contract asserted by the S148 build
// test; the exact wording matches historical Flight 3/4 evidence at docs/tutorial-launch-marker.
// s148-self-damage-flight4-*.txt line 8 and every other s148-move4-* / move4-poke-* / crashwatch.
// s148-* marker file, so any change to the wording must be paired with docs updates. Restored to
// the main worktree in S153 (missing definition since commit 0b1ad5d, S150-drop, 2026-09-01).
#define S148_OWNER_CENSUS_CHAIN_MODE_MARKER \
    "[S148] owner-census class-chain mode=CLASSIFY_ONLY directChecks=5\r\n"

// Diagnostic-only provenance for the unique local-owner census. The runtime latches the first
// failure into POD scalars, then renders the enum names only while emitting the final refusal line.
// None of these values participates in admission or mutation policy.
enum S148OwnerScanPhase : uint32_t {
    S148_OWNER_SCAN_PHASE_NONE = 0,
    S148_OWNER_SCAN_PHASE_CAPTURE,
    S148_OWNER_SCAN_PHASE_ENUM_OBJECT,
    S148_OWNER_SCAN_PHASE_GI_CAPTURE,
    S148_OWNER_SCAN_PHASE_CANDIDATE_VALIDATE,
    S148_OWNER_SCAN_PHASE_GI_POSTCHECK,
    S148_OWNER_SCAN_PHASE_SELECTED_REVALIDATE,
    S148_OWNER_SCAN_PHASE_CENSUS_REVALIDATE,
    S148_OWNER_SCAN_PHASE_GUOBJECT_REVALIDATE,
    S148_OWNER_SCAN_PHASE_SELECTION,
    S148_OWNER_SCAN_PHASE_COUNT,
};

enum S148OwnerScanReason : uint32_t {
    S148_OWNER_SCAN_NONE = 0,
    S148_OWNER_SCAN_OWNER_TARGET_NULL,
    S148_OWNER_SCAN_SNAPSHOT_OUTPUT_NULL,
    S148_OWNER_SCAN_GUOBJECT_HEADER_UNREADABLE,
    S148_OWNER_SCAN_GUOBJECT_HEADER_INVALID,
    S148_OWNER_SCAN_SNAPSHOT_ALLOCATION_FAILED,
    S148_OWNER_SCAN_GUOBJECT_CHUNK_CELL_UNREADABLE,
    S148_OWNER_SCAN_GUOBJECT_CHUNK_POINTER_INVALID,
    S148_OWNER_SCAN_GUOBJECT_ITEM_CELL_UNREADABLE,
    S148_OWNER_SCAN_GUOBJECT_SAVED_STATE_INVALID,
    S148_OWNER_SCAN_GUOBJECT_OBJECTS_POINTER_CHANGED,
    S148_OWNER_SCAN_GUOBJECT_MAX_CHANGED,
    S148_OWNER_SCAN_GUOBJECT_NUM_CHANGED,
    S148_OWNER_SCAN_GUOBJECT_CHUNK_CHANGED,
    S148_OWNER_SCAN_GUOBJECT_ITEM_CHANGED,
    S148_OWNER_SCAN_CENSUS_ALLOCATION_FAILED,
    S148_OWNER_SCAN_OBJECT_POINTER_INVALID,
    S148_OWNER_SCAN_OBJECT_CLASS_INVALID,
    S148_OWNER_SCAN_GAME_INSTANCE_CHAIN_MALFORMED,
    S148_OWNER_SCAN_GAME_INSTANCE_CDO_UNKNOWN,
    S148_OWNER_SCAN_GAME_INSTANCE_CENSUS_CAPACITY,
    S148_OWNER_SCAN_DUPLICATE_GAME_INSTANCE,
    S148_OWNER_SCAN_LOCAL_PLAYER_CONTROLLER_CELL_UNREADABLE,
    S148_OWNER_SCAN_LOCAL_PLAYERS_TARGET_NULL,
    S148_OWNER_SCAN_GAME_INSTANCE_NOT_LIVE,
    S148_OWNER_SCAN_GAME_INSTANCE_CLASS_INVALID,
    S148_OWNER_SCAN_GAME_INSTANCE_CHAIN_NO_MATCH,
    S148_OWNER_SCAN_GAME_INSTANCE_IS_CDO,
    S148_OWNER_SCAN_LOCAL_PLAYERS_SCHEMA_INVALID,
    S148_OWNER_SCAN_SCHEMA_CLASS_INVALID,
    S148_OWNER_SCAN_SCHEMA_LOOKUP_NO_MATCH,
    S148_OWNER_SCAN_SCHEMA_LOOKUP_MALFORMED,
    S148_OWNER_SCAN_SCHEMA_PROPERTY_POINTER_INVALID,
    S148_OWNER_SCAN_SCHEMA_CONVENIENCE_OFFSET_INVALID,
    S148_OWNER_SCAN_SCHEMA_OFFSET_MISMATCH,
    S148_OWNER_SCAN_SCHEMA_REQUIRED_OFFSET_MISMATCH,
    S148_OWNER_SCAN_SCHEMA_OUTER_ELEMENT_SIZE_INVALID,
    S148_OWNER_SCAN_SCHEMA_OUTER_ARRAY_DIM_INVALID,
    S148_OWNER_SCAN_SCHEMA_OUTER_TYPE_INVALID,
    S148_OWNER_SCAN_SCHEMA_OUTER_OWNER_INVALID,
    S148_OWNER_SCAN_SCHEMA_INNER_POINTER_INVALID,
    S148_OWNER_SCAN_SCHEMA_INNER_ELEMENT_SIZE_INVALID,
    S148_OWNER_SCAN_SCHEMA_INNER_ARRAY_DIM_INVALID,
    S148_OWNER_SCAN_SCHEMA_INNER_TYPE_INVALID,
    S148_OWNER_SCAN_SCHEMA_INNER_CLASS_INVALID,
    S148_OWNER_SCAN_LOCAL_PLAYERS_NUM_NEGATIVE,
    S148_OWNER_SCAN_LOCAL_PLAYERS_NUM_OVER_CAP,
    S148_OWNER_SCAN_LOCAL_PLAYERS_MAX_BELOW_NUM,
    S148_OWNER_SCAN_LOCAL_PLAYERS_MAX_OVER_CAP,
    S148_OWNER_SCAN_LOCAL_PLAYERS_EMPTY_DATA_INVALID,
    S148_OWNER_SCAN_LOCAL_PLAYERS_DATA_POINTER_INVALID,
    S148_OWNER_SCAN_LOCAL_PLAYERS_DATA_UNREADABLE,
    S148_OWNER_SCAN_LOCAL_PLAYERS_MEMBER_CELL_UNREADABLE,
    S148_OWNER_SCAN_LOCAL_PLAYERS_MEMBER_NOT_LIVE,
    S148_OWNER_SCAN_LOCAL_PLAYERS_MEMBER_CLASS_INVALID,
    S148_OWNER_SCAN_LOCAL_PLAYER_CHAIN_NO_MATCH,
    S148_OWNER_SCAN_LOCAL_PLAYER_CHAIN_MALFORMED,
    S148_OWNER_SCAN_LOCAL_PLAYERS_MEMBER_DUPLICATE,
    S148_OWNER_SCAN_LOCAL_PLAYERS_SNAPSHOT_GI_INVALID,
    S148_OWNER_SCAN_LOCAL_PLAYERS_SNAPSHOT_OFFSET_INVALID,
    S148_OWNER_SCAN_LOCAL_PLAYERS_SNAPSHOT_HEADER_UNREADABLE,
    S148_OWNER_SCAN_LOCAL_PLAYERS_SNAPSHOT_DATA_CHANGED,
    S148_OWNER_SCAN_LOCAL_PLAYERS_SNAPSHOT_NUM_CHANGED,
    S148_OWNER_SCAN_LOCAL_PLAYERS_SNAPSHOT_MAX_CHANGED,
    S148_OWNER_SCAN_LOCAL_PLAYERS_SNAPSHOT_MEMBER_CELL_UNREADABLE,
    S148_OWNER_SCAN_LOCAL_PLAYERS_SNAPSHOT_MEMBER_CHANGED,
    S148_OWNER_SCAN_CONTROLLER_TARGET_NULL,
    S148_OWNER_SCAN_CONTROLLER_LOCAL_PLAYER_NOT_LIVE,
    S148_OWNER_SCAN_CONTROLLER_NOT_LIVE,
    S148_OWNER_SCAN_CONTROLLER_GAME_INSTANCE_NOT_LIVE,
    S148_OWNER_SCAN_CONTROLLER_LOCAL_PLAYER_CLASS_INVALID,
    S148_OWNER_SCAN_CONTROLLER_CLASS_INVALID,
    S148_OWNER_SCAN_CONTROLLER_LOCAL_PLAYER_CHAIN_NO_MATCH,
    S148_OWNER_SCAN_CONTROLLER_LOCAL_PLAYER_CHAIN_MALFORMED,
    S148_OWNER_SCAN_CONTROLLER_CHAIN_NO_MATCH,
    S148_OWNER_SCAN_CONTROLLER_CHAIN_MALFORMED,
    S148_OWNER_SCAN_LOCAL_PLAYER_CONTROLLER_MISMATCH,
    S148_OWNER_SCAN_CONTROLLER_PLAYER_CELL_UNREADABLE,
    S148_OWNER_SCAN_CONTROLLER_PLAYER_MISMATCH,
    S148_OWNER_SCAN_LOCAL_PLAYERS_MEMBERSHIP_ZERO,
    S148_OWNER_SCAN_LOCAL_PLAYERS_MEMBERSHIP_MULTIPLE,
    S148_OWNER_SCAN_CENSUS_GAME_INSTANCE_CLASS_CHANGED,
    S148_OWNER_SCAN_CENSUS_OFFSET_CHANGED,
    S148_OWNER_SCAN_CENSUS_DATA_CHANGED,
    S148_OWNER_SCAN_CENSUS_NUM_CHANGED,
    S148_OWNER_SCAN_CENSUS_MAX_CHANGED,
    S148_OWNER_SCAN_CENSUS_MEMBER_CHANGED,
    S148_OWNER_SCAN_CANDIDATE_COUNT_ZERO,
    S148_OWNER_SCAN_CANDIDATE_COUNT_MULTIPLE,
    S148_OWNER_SCAN_UNCLASSIFIED_FAILURE,
    S148_OWNER_SCAN_REASON_COUNT,
};

// A malformed exact UClass::SuperStruct traversal is itself fail-closed. These leaf codes explain
// why the traversal refused without changing its MATCH / NO_MATCH / MALFORMED result.
enum S148ClassChainFailureReason : uint32_t {
    S148_CLASS_CHAIN_NONE = 0,
    S148_CLASS_CHAIN_NODE_POINTER_INVALID,
    S148_CLASS_CHAIN_NODE_NOT_LIVE,
    S148_CLASS_CHAIN_CYCLE,
    S148_CLASS_CHAIN_NAME_DECODE_FAILED,
    S148_CLASS_CHAIN_OUTPUT_BUFFER_EXHAUSTED,
    S148_CLASS_CHAIN_SUPER_CELL_UNREADABLE,
    S148_CLASS_CHAIN_SUPER_POINTER_INVALID,
    S148_CLASS_CHAIN_DEPTH_LIMIT,
    S148_CLASS_CHAIN_FAILURE_COUNT,
};

constexpr char S148_OWNER_SCAN_MARKER_FORMAT[] =
    "[S148] OWNER_REFUSAL phase=%s reason=%s code=%u pass=%d objIndex=%d census=%d li=%d "
    "obj=0x%llX addr=0x%llX d0=0x%llX d1=0x%llX candidates=%d retained=%d numEl=%d chunks=%d\r\n";

constexpr char S148_CLASS_CHAIN_MARKER_FORMAT[] =
    "[S148] CHAIN_REFUSAL leaf=%s code=%u depth=%d node=0x%llX addr=0x%llX "
    "d0=0x%llX d1=0x%llX\r\n";

struct S148ClassChainFailure {
    S148ClassChainFailureReason reason;
    int32_t depth;
    uint64_t node;
    uint64_t address;
    uint64_t detail0;
    uint64_t detail1;
};

struct S148OwnerScanFailure {
    S148OwnerScanPhase phase;
    S148OwnerScanReason reason;
    int32_t snapshotIndex;
    int32_t censusIndex;
    int32_t localIndex;
    int32_t pass;
    uint64_t object;
    uint64_t address;
    uint64_t detail0;
    uint64_t detail1;
    S148ClassChainFailure chain;
};

struct S148LocalPlayersSchemaFacts {
    uint8_t classValid;
    int8_t lookupResult;
    uint8_t propertyPointerValid;
    uint8_t convenienceOffsetValid;
    uint8_t offsetsMatch;
    uint8_t requiredOffsetMatches;
    uint8_t outerElementSizeValid;
    uint8_t outerArrayDimValid;
    uint8_t outerTypeValid;
    uint8_t outerOwnerValid;
    uint8_t innerPointerValid;
    uint8_t innerElementSizeValid;
    uint8_t innerArrayDimValid;
    uint8_t innerTypeValid;
    uint8_t innerClassValid;
};

static inline S148OwnerScanReason S148LocalPlayersSchemaReason(
    const S148LocalPlayersSchemaFacts& facts) {
    if (!facts.classValid) return S148_OWNER_SCAN_SCHEMA_CLASS_INVALID;
    if (facts.lookupResult < 0 || facts.lookupResult > 1)
        return S148_OWNER_SCAN_SCHEMA_LOOKUP_MALFORMED;
    if (facts.lookupResult == 0) return S148_OWNER_SCAN_SCHEMA_LOOKUP_NO_MATCH;
    if (!facts.propertyPointerValid) return S148_OWNER_SCAN_SCHEMA_PROPERTY_POINTER_INVALID;
    if (!facts.convenienceOffsetValid) return S148_OWNER_SCAN_SCHEMA_CONVENIENCE_OFFSET_INVALID;
    if (!facts.offsetsMatch) return S148_OWNER_SCAN_SCHEMA_OFFSET_MISMATCH;
    if (!facts.requiredOffsetMatches) return S148_OWNER_SCAN_SCHEMA_REQUIRED_OFFSET_MISMATCH;
    if (!facts.outerElementSizeValid) return S148_OWNER_SCAN_SCHEMA_OUTER_ELEMENT_SIZE_INVALID;
    if (!facts.outerArrayDimValid) return S148_OWNER_SCAN_SCHEMA_OUTER_ARRAY_DIM_INVALID;
    if (!facts.outerTypeValid) return S148_OWNER_SCAN_SCHEMA_OUTER_TYPE_INVALID;
    if (!facts.outerOwnerValid) return S148_OWNER_SCAN_SCHEMA_OUTER_OWNER_INVALID;
    if (!facts.innerPointerValid) return S148_OWNER_SCAN_SCHEMA_INNER_POINTER_INVALID;
    if (!facts.innerElementSizeValid) return S148_OWNER_SCAN_SCHEMA_INNER_ELEMENT_SIZE_INVALID;
    if (!facts.innerArrayDimValid) return S148_OWNER_SCAN_SCHEMA_INNER_ARRAY_DIM_INVALID;
    if (!facts.innerTypeValid) return S148_OWNER_SCAN_SCHEMA_INNER_TYPE_INVALID;
    if (!facts.innerClassValid) return S148_OWNER_SCAN_SCHEMA_INNER_CLASS_INVALID;
    return S148_OWNER_SCAN_NONE;
}

static inline void S148RecordClassChainFailure(
    S148ClassChainFailure* failure, S148ClassChainFailureReason reason,
    int32_t depth, uint64_t node, uint64_t address,
    uint64_t detail0, uint64_t detail1) {
    if (!failure || failure->reason != S148_CLASS_CHAIN_NONE ||
        reason == S148_CLASS_CHAIN_NONE)
        return;
    failure->reason = reason;
    failure->depth = depth;
    failure->node = node;
    failure->address = address;
    failure->detail0 = detail0;
    failure->detail1 = detail1;
}

static inline void S148RecordOwnerScanFailure(
    S148OwnerScanFailure* failure, S148OwnerScanPhase phase,
    S148OwnerScanReason reason, int32_t snapshotIndex, int32_t censusIndex,
    int32_t localIndex, int32_t pass, uint64_t object, uint64_t address,
    uint64_t detail0, uint64_t detail1,
    const S148ClassChainFailure* chain = nullptr) {
    if (!failure || failure->reason != S148_OWNER_SCAN_NONE ||
        reason == S148_OWNER_SCAN_NONE)
        return;
    failure->phase = phase;
    failure->reason = reason;
    failure->snapshotIndex = snapshotIndex;
    failure->censusIndex = censusIndex;
    failure->localIndex = localIndex;
    failure->pass = pass;
    failure->object = object;
    failure->address = address;
    failure->detail0 = detail0;
    failure->detail1 = detail1;
    if (chain && chain->reason != S148_CLASS_CHAIN_NONE)
        failure->chain = *chain;
}

static inline const char* S148ClassChainFailureName(
    S148ClassChainFailureReason reason) {
    switch (reason) {
    case S148_CLASS_CHAIN_NONE: return "NONE";
    case S148_CLASS_CHAIN_NODE_POINTER_INVALID: return "NODE_POINTER_INVALID";
    case S148_CLASS_CHAIN_NODE_NOT_LIVE: return "NODE_NOT_LIVE";
    case S148_CLASS_CHAIN_CYCLE: return "CYCLE";
    case S148_CLASS_CHAIN_NAME_DECODE_FAILED: return "NAME_DECODE_FAILED";
    case S148_CLASS_CHAIN_OUTPUT_BUFFER_EXHAUSTED: return "OUTPUT_BUFFER_EXHAUSTED";
    case S148_CLASS_CHAIN_SUPER_CELL_UNREADABLE: return "SUPER_CELL_UNREADABLE";
    case S148_CLASS_CHAIN_SUPER_POINTER_INVALID: return "SUPER_POINTER_INVALID";
    case S148_CLASS_CHAIN_DEPTH_LIMIT: return "DEPTH_LIMIT";
    default: return "UNKNOWN";
    }
}

static inline const char* S148OwnerScanPhaseName(S148OwnerScanPhase phase) {
    switch (phase) {
    case S148_OWNER_SCAN_PHASE_NONE: return "NONE";
    case S148_OWNER_SCAN_PHASE_CAPTURE: return "CAPTURE";
    case S148_OWNER_SCAN_PHASE_ENUM_OBJECT: return "ENUM_OBJECT";
    case S148_OWNER_SCAN_PHASE_GI_CAPTURE: return "GI_CAPTURE";
    case S148_OWNER_SCAN_PHASE_CANDIDATE_VALIDATE: return "CANDIDATE_VALIDATE";
    case S148_OWNER_SCAN_PHASE_GI_POSTCHECK: return "GI_POSTCHECK";
    case S148_OWNER_SCAN_PHASE_SELECTED_REVALIDATE: return "SELECTED_REVALIDATE";
    case S148_OWNER_SCAN_PHASE_CENSUS_REVALIDATE: return "CENSUS_REVALIDATE";
    case S148_OWNER_SCAN_PHASE_GUOBJECT_REVALIDATE: return "GUOBJECT_REVALIDATE";
    case S148_OWNER_SCAN_PHASE_SELECTION: return "SELECTION";
    default: return "UNKNOWN";
    }
}

static inline const char* S148OwnerScanReasonName(S148OwnerScanReason reason) {
    switch (reason) {
    case S148_OWNER_SCAN_NONE: return "NONE";
    case S148_OWNER_SCAN_OWNER_TARGET_NULL: return "OWNER_TARGET_NULL";
    case S148_OWNER_SCAN_SNAPSHOT_OUTPUT_NULL: return "SNAPSHOT_OUTPUT_NULL";
    case S148_OWNER_SCAN_GUOBJECT_HEADER_UNREADABLE: return "GUOBJECT_HEADER_UNREADABLE";
    case S148_OWNER_SCAN_GUOBJECT_HEADER_INVALID: return "GUOBJECT_HEADER_INVALID";
    case S148_OWNER_SCAN_SNAPSHOT_ALLOCATION_FAILED: return "SNAPSHOT_ALLOCATION_FAILED";
    case S148_OWNER_SCAN_GUOBJECT_CHUNK_CELL_UNREADABLE: return "GUOBJECT_CHUNK_CELL_UNREADABLE";
    case S148_OWNER_SCAN_GUOBJECT_CHUNK_POINTER_INVALID: return "GUOBJECT_CHUNK_POINTER_INVALID";
    case S148_OWNER_SCAN_GUOBJECT_ITEM_CELL_UNREADABLE: return "GUOBJECT_ITEM_CELL_UNREADABLE";
    case S148_OWNER_SCAN_GUOBJECT_SAVED_STATE_INVALID: return "GUOBJECT_SAVED_STATE_INVALID";
    case S148_OWNER_SCAN_GUOBJECT_OBJECTS_POINTER_CHANGED: return "GUOBJECT_OBJECTS_POINTER_CHANGED";
    case S148_OWNER_SCAN_GUOBJECT_MAX_CHANGED: return "GUOBJECT_MAX_CHANGED";
    case S148_OWNER_SCAN_GUOBJECT_NUM_CHANGED: return "GUOBJECT_NUM_CHANGED";
    case S148_OWNER_SCAN_GUOBJECT_CHUNK_CHANGED: return "GUOBJECT_CHUNK_CHANGED";
    case S148_OWNER_SCAN_GUOBJECT_ITEM_CHANGED: return "GUOBJECT_ITEM_CHANGED";
    case S148_OWNER_SCAN_CENSUS_ALLOCATION_FAILED: return "CENSUS_ALLOCATION_FAILED";
    case S148_OWNER_SCAN_OBJECT_POINTER_INVALID: return "OBJECT_POINTER_INVALID";
    case S148_OWNER_SCAN_OBJECT_CLASS_INVALID: return "OBJECT_CLASS_INVALID";
    case S148_OWNER_SCAN_GAME_INSTANCE_CHAIN_MALFORMED: return "GAME_INSTANCE_CHAIN_MALFORMED";
    case S148_OWNER_SCAN_GAME_INSTANCE_CDO_UNKNOWN: return "GAME_INSTANCE_CDO_UNKNOWN";
    case S148_OWNER_SCAN_GAME_INSTANCE_CENSUS_CAPACITY: return "GAME_INSTANCE_CENSUS_CAPACITY";
    case S148_OWNER_SCAN_DUPLICATE_GAME_INSTANCE: return "DUPLICATE_GAME_INSTANCE";
    case S148_OWNER_SCAN_LOCAL_PLAYER_CONTROLLER_CELL_UNREADABLE: return "LOCAL_PLAYER_CONTROLLER_CELL_UNREADABLE";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_TARGET_NULL: return "LOCAL_PLAYERS_TARGET_NULL";
    case S148_OWNER_SCAN_GAME_INSTANCE_NOT_LIVE: return "GAME_INSTANCE_NOT_LIVE";
    case S148_OWNER_SCAN_GAME_INSTANCE_CLASS_INVALID: return "GAME_INSTANCE_CLASS_INVALID";
    case S148_OWNER_SCAN_GAME_INSTANCE_CHAIN_NO_MATCH: return "GAME_INSTANCE_CHAIN_NO_MATCH";
    case S148_OWNER_SCAN_GAME_INSTANCE_IS_CDO: return "GAME_INSTANCE_IS_CDO";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_SCHEMA_INVALID: return "LOCAL_PLAYERS_SCHEMA_INVALID";
    case S148_OWNER_SCAN_SCHEMA_CLASS_INVALID: return "SCHEMA_CLASS_INVALID";
    case S148_OWNER_SCAN_SCHEMA_LOOKUP_NO_MATCH: return "SCHEMA_LOOKUP_NO_MATCH";
    case S148_OWNER_SCAN_SCHEMA_LOOKUP_MALFORMED: return "SCHEMA_LOOKUP_MALFORMED";
    case S148_OWNER_SCAN_SCHEMA_PROPERTY_POINTER_INVALID: return "SCHEMA_PROPERTY_POINTER_INVALID";
    case S148_OWNER_SCAN_SCHEMA_CONVENIENCE_OFFSET_INVALID: return "SCHEMA_CONVENIENCE_OFFSET_INVALID";
    case S148_OWNER_SCAN_SCHEMA_OFFSET_MISMATCH: return "SCHEMA_OFFSET_MISMATCH";
    case S148_OWNER_SCAN_SCHEMA_REQUIRED_OFFSET_MISMATCH: return "SCHEMA_REQUIRED_OFFSET_MISMATCH";
    case S148_OWNER_SCAN_SCHEMA_OUTER_ELEMENT_SIZE_INVALID: return "SCHEMA_OUTER_ELEMENT_SIZE_INVALID";
    case S148_OWNER_SCAN_SCHEMA_OUTER_ARRAY_DIM_INVALID: return "SCHEMA_OUTER_ARRAY_DIM_INVALID";
    case S148_OWNER_SCAN_SCHEMA_OUTER_TYPE_INVALID: return "SCHEMA_OUTER_TYPE_INVALID";
    case S148_OWNER_SCAN_SCHEMA_OUTER_OWNER_INVALID: return "SCHEMA_OUTER_OWNER_INVALID";
    case S148_OWNER_SCAN_SCHEMA_INNER_POINTER_INVALID: return "SCHEMA_INNER_POINTER_INVALID";
    case S148_OWNER_SCAN_SCHEMA_INNER_ELEMENT_SIZE_INVALID: return "SCHEMA_INNER_ELEMENT_SIZE_INVALID";
    case S148_OWNER_SCAN_SCHEMA_INNER_ARRAY_DIM_INVALID: return "SCHEMA_INNER_ARRAY_DIM_INVALID";
    case S148_OWNER_SCAN_SCHEMA_INNER_TYPE_INVALID: return "SCHEMA_INNER_TYPE_INVALID";
    case S148_OWNER_SCAN_SCHEMA_INNER_CLASS_INVALID: return "SCHEMA_INNER_CLASS_INVALID";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_NUM_NEGATIVE: return "LOCAL_PLAYERS_NUM_NEGATIVE";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_NUM_OVER_CAP: return "LOCAL_PLAYERS_NUM_OVER_CAP";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_MAX_BELOW_NUM: return "LOCAL_PLAYERS_MAX_BELOW_NUM";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_MAX_OVER_CAP: return "LOCAL_PLAYERS_MAX_OVER_CAP";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_EMPTY_DATA_INVALID: return "LOCAL_PLAYERS_EMPTY_DATA_INVALID";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_DATA_POINTER_INVALID: return "LOCAL_PLAYERS_DATA_POINTER_INVALID";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_DATA_UNREADABLE: return "LOCAL_PLAYERS_DATA_UNREADABLE";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_MEMBER_CELL_UNREADABLE: return "LOCAL_PLAYERS_MEMBER_CELL_UNREADABLE";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_MEMBER_NOT_LIVE: return "LOCAL_PLAYERS_MEMBER_NOT_LIVE";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_MEMBER_CLASS_INVALID: return "LOCAL_PLAYERS_MEMBER_CLASS_INVALID";
    case S148_OWNER_SCAN_LOCAL_PLAYER_CHAIN_NO_MATCH: return "LOCAL_PLAYER_CHAIN_NO_MATCH";
    case S148_OWNER_SCAN_LOCAL_PLAYER_CHAIN_MALFORMED: return "LOCAL_PLAYER_CHAIN_MALFORMED";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_MEMBER_DUPLICATE: return "LOCAL_PLAYERS_MEMBER_DUPLICATE";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_SNAPSHOT_GI_INVALID: return "LOCAL_PLAYERS_SNAPSHOT_GI_INVALID";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_SNAPSHOT_OFFSET_INVALID: return "LOCAL_PLAYERS_SNAPSHOT_OFFSET_INVALID";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_SNAPSHOT_HEADER_UNREADABLE: return "LOCAL_PLAYERS_SNAPSHOT_HEADER_UNREADABLE";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_SNAPSHOT_DATA_CHANGED: return "LOCAL_PLAYERS_SNAPSHOT_DATA_CHANGED";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_SNAPSHOT_NUM_CHANGED: return "LOCAL_PLAYERS_SNAPSHOT_NUM_CHANGED";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_SNAPSHOT_MAX_CHANGED: return "LOCAL_PLAYERS_SNAPSHOT_MAX_CHANGED";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_SNAPSHOT_MEMBER_CELL_UNREADABLE: return "LOCAL_PLAYERS_SNAPSHOT_MEMBER_CELL_UNREADABLE";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_SNAPSHOT_MEMBER_CHANGED: return "LOCAL_PLAYERS_SNAPSHOT_MEMBER_CHANGED";
    case S148_OWNER_SCAN_CONTROLLER_TARGET_NULL: return "CONTROLLER_TARGET_NULL";
    case S148_OWNER_SCAN_CONTROLLER_LOCAL_PLAYER_NOT_LIVE: return "CONTROLLER_LOCAL_PLAYER_NOT_LIVE";
    case S148_OWNER_SCAN_CONTROLLER_NOT_LIVE: return "CONTROLLER_NOT_LIVE";
    case S148_OWNER_SCAN_CONTROLLER_GAME_INSTANCE_NOT_LIVE: return "CONTROLLER_GAME_INSTANCE_NOT_LIVE";
    case S148_OWNER_SCAN_CONTROLLER_LOCAL_PLAYER_CLASS_INVALID: return "CONTROLLER_LOCAL_PLAYER_CLASS_INVALID";
    case S148_OWNER_SCAN_CONTROLLER_CLASS_INVALID: return "CONTROLLER_CLASS_INVALID";
    case S148_OWNER_SCAN_CONTROLLER_LOCAL_PLAYER_CHAIN_NO_MATCH: return "CONTROLLER_LOCAL_PLAYER_CHAIN_NO_MATCH";
    case S148_OWNER_SCAN_CONTROLLER_LOCAL_PLAYER_CHAIN_MALFORMED: return "CONTROLLER_LOCAL_PLAYER_CHAIN_MALFORMED";
    case S148_OWNER_SCAN_CONTROLLER_CHAIN_NO_MATCH: return "CONTROLLER_CHAIN_NO_MATCH";
    case S148_OWNER_SCAN_CONTROLLER_CHAIN_MALFORMED: return "CONTROLLER_CHAIN_MALFORMED";
    case S148_OWNER_SCAN_LOCAL_PLAYER_CONTROLLER_MISMATCH: return "LOCAL_PLAYER_CONTROLLER_MISMATCH";
    case S148_OWNER_SCAN_CONTROLLER_PLAYER_CELL_UNREADABLE: return "CONTROLLER_PLAYER_CELL_UNREADABLE";
    case S148_OWNER_SCAN_CONTROLLER_PLAYER_MISMATCH: return "CONTROLLER_PLAYER_MISMATCH";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_MEMBERSHIP_ZERO: return "LOCAL_PLAYERS_MEMBERSHIP_ZERO";
    case S148_OWNER_SCAN_LOCAL_PLAYERS_MEMBERSHIP_MULTIPLE: return "LOCAL_PLAYERS_MEMBERSHIP_MULTIPLE";
    case S148_OWNER_SCAN_CENSUS_GAME_INSTANCE_CLASS_CHANGED: return "CENSUS_GAME_INSTANCE_CLASS_CHANGED";
    case S148_OWNER_SCAN_CENSUS_OFFSET_CHANGED: return "CENSUS_OFFSET_CHANGED";
    case S148_OWNER_SCAN_CENSUS_DATA_CHANGED: return "CENSUS_DATA_CHANGED";
    case S148_OWNER_SCAN_CENSUS_NUM_CHANGED: return "CENSUS_NUM_CHANGED";
    case S148_OWNER_SCAN_CENSUS_MAX_CHANGED: return "CENSUS_MAX_CHANGED";
    case S148_OWNER_SCAN_CENSUS_MEMBER_CHANGED: return "CENSUS_MEMBER_CHANGED";
    case S148_OWNER_SCAN_CANDIDATE_COUNT_ZERO: return "CANDIDATE_COUNT_ZERO";
    case S148_OWNER_SCAN_CANDIDATE_COUNT_MULTIPLE: return "CANDIDATE_COUNT_MULTIPLE";
    case S148_OWNER_SCAN_UNCLASSIFIED_FAILURE: return "UNCLASSIFIED_FAILURE";
    default: return "UNKNOWN";
    }
}

enum S148PreflightIssue : uint32_t {
    S148_ISSUE_NONE = 0,
    S148_ISSUE_ASC_INVALID = 1u << 0,
    S148_ISSUE_SPAWNED_HEADER_INVALID = 1u << 1,
    S148_ISSUE_HEALTH_COUNT = 1u << 2,
    S148_ISSUE_CANDIDATE_INVALID = 1u << 3,
    S148_ISSUE_HEALTH_NOT_WRITABLE = 1u << 4,
    S148_ISSUE_HEALTH_CLASS = 1u << 5,
    S148_ISSUE_SHARED_CDO = 1u << 6,
    S148_ISSUE_HEALTH_NONFINITE = 1u << 7,
    S148_ISSUE_MAX_HEALTH_INVALID = 1u << 8,
    S148_ISSUE_MAX_HEALTH_BELOW_SEED = 1u << 9,
    S148_ISSUE_HEALTH_OUT_OF_RANGE = 1u << 10,
    S148_ISSUE_OWNER_SCAN_INCOMPLETE = 1u << 11,
    S148_ISSUE_GAME_INSTANCE_MEMBERSHIP = 1u << 12,
    S148_ISSUE_WORLD_IDENTITY = 1u << 13,
    S148_ISSUE_PROPERTY_PROVENANCE = 1u << 14,
    S148_ISSUE_SET_REGISTRATION = 1u << 15,
    S148_ISSUE_ASC_OWNERSHIP = 1u << 16,
    S148_ISSUE_AVATAR_BINDING = 1u << 17,
    S148_ISSUE_SPAWNED_MEMBER_TYPE = 1u << 18,
    S148_ISSUE_ATTRIBUTE_LAYOUT = 1u << 19,
    S148_ISSUE_CENSUS_CLOSURE = 1u << 20,
    S148_ISSUE_STRUCT_PAYLOAD = 1u << 21,
};

struct S148HealthFacts {
    uint8_t ownerScanComplete;
    uint8_t gameInstanceMembershipValid;
    uint8_t worldIdentityValid;
    uint8_t reflectedProvenanceValid;
    uint8_t registrationScanComplete;
    uint8_t registrationOwnerValid;
    uint8_t registrationCount;
    uint8_t ascValid;
    uint8_t ascInstanceOwned;
    uint8_t avatarBindingValid;
    uint8_t spawnedHeaderValid;
    uint8_t spawnedMemberTypesValid;
    uint8_t attributeLayoutValid;
    uint8_t censusClosureValid;
    uint8_t structPayloadValid;
    uint8_t healthCandidateCount;
    uint8_t candidateReadable;
    uint8_t candidateWritable;
    uint8_t candidateClassExact;
    uint8_t candidateIsCdo;
    uint8_t candidateHasCdoOuter;
    uint8_t maxHealthPresent;
    uint8_t maxHealthReadable;
    uint32_t originalBaseBits;
    uint32_t originalCurrentBits;
    uint32_t maxBaseBits;
    uint32_t maxCurrentBits;
};

static inline bool S148FiniteFloatBits(uint32_t bits) {
    return (bits & 0x7F800000u) != 0x7F800000u;
}

// IEEE-754 positive finite floats preserve numeric ordering in their unsigned bit pattern.
static inline bool S148PositiveAtLeastSeed(uint32_t bits) {
    return S148FiniteFloatBits(bits) && (bits & 0x80000000u) == 0 &&
           bits >= S148_HEALTH_SEED_BITS;
}

static inline bool S148NonNegativeAtMost(uint32_t bits, uint32_t maxBits) {
    return S148FiniteFloatBits(bits) && S148FiniteFloatBits(maxBits) &&
           (bits & 0x80000000u) == 0 && (maxBits & 0x80000000u) == 0 &&
           bits <= maxBits;
}

static inline uint32_t S148PreflightIssues(const S148HealthFacts& facts) {
    uint32_t issues = S148_ISSUE_NONE;
    if (!facts.ownerScanComplete) issues |= S148_ISSUE_OWNER_SCAN_INCOMPLETE;
    if (!facts.gameInstanceMembershipValid) issues |= S148_ISSUE_GAME_INSTANCE_MEMBERSHIP;
    if (!facts.worldIdentityValid) issues |= S148_ISSUE_WORLD_IDENTITY;
    if (!facts.reflectedProvenanceValid) issues |= S148_ISSUE_PROPERTY_PROVENANCE;
    if (!facts.registrationScanComplete || !facts.registrationOwnerValid ||
        facts.registrationCount != 1)
        issues |= S148_ISSUE_SET_REGISTRATION;
    if (!facts.ascValid) issues |= S148_ISSUE_ASC_INVALID;
    if (!facts.ascInstanceOwned) issues |= S148_ISSUE_ASC_OWNERSHIP;
    if (!facts.avatarBindingValid) issues |= S148_ISSUE_AVATAR_BINDING;
    if (!facts.spawnedHeaderValid) issues |= S148_ISSUE_SPAWNED_HEADER_INVALID;
    if (!facts.spawnedMemberTypesValid) issues |= S148_ISSUE_SPAWNED_MEMBER_TYPE;
    if (!facts.attributeLayoutValid) issues |= S148_ISSUE_ATTRIBUTE_LAYOUT;
    if (!facts.censusClosureValid) issues |= S148_ISSUE_CENSUS_CLOSURE;
    if (!facts.structPayloadValid) issues |= S148_ISSUE_STRUCT_PAYLOAD;
    if (facts.healthCandidateCount != 1) issues |= S148_ISSUE_HEALTH_COUNT;
    if (!facts.candidateReadable) issues |= S148_ISSUE_CANDIDATE_INVALID;
    if (!facts.candidateWritable) issues |= S148_ISSUE_HEALTH_NOT_WRITABLE;
    if (!facts.candidateClassExact) issues |= S148_ISSUE_HEALTH_CLASS;
    if (facts.candidateIsCdo || facts.candidateHasCdoOuter) issues |= S148_ISSUE_SHARED_CDO;
    if (!S148FiniteFloatBits(facts.originalBaseBits) ||
        !S148FiniteFloatBits(facts.originalCurrentBits))
        issues |= S148_ISSUE_HEALTH_NONFINITE;
    bool maxValid = facts.maxHealthPresent && facts.maxHealthReadable &&
                    S148FiniteFloatBits(facts.maxBaseBits) &&
                    S148FiniteFloatBits(facts.maxCurrentBits);
    if (!maxValid) issues |= S148_ISSUE_MAX_HEALTH_INVALID;
    if (maxValid && (!S148PositiveAtLeastSeed(facts.maxBaseBits) ||
                     !S148PositiveAtLeastSeed(facts.maxCurrentBits)))
        issues |= S148_ISSUE_MAX_HEALTH_BELOW_SEED;
    if (maxValid && S148FiniteFloatBits(facts.originalBaseBits) &&
        S148FiniteFloatBits(facts.originalCurrentBits) &&
        (!S148NonNegativeAtMost(facts.originalBaseBits, facts.maxBaseBits) ||
         !S148NonNegativeAtMost(facts.originalCurrentBits, facts.maxCurrentBits)))
        issues |= S148_ISSUE_HEALTH_OUT_OF_RANGE;
    return issues;
}

static inline bool S148SeedExact(uint32_t baseBits, uint32_t currentBits) {
    return baseBits == S148_HEALTH_SEED_BITS && currentBits == S148_HEALTH_SEED_BITS;
}

static inline bool S148ImmediateReceipt(bool functionResolved, bool callFaulted,
                                        bool identityMatches, uint32_t currentBits) {
    return functionResolved && !callFaulted && identityMatches &&
           currentBits == S148_HEALTH_EXPECTED_BITS;
}

static inline bool S148LaterReceipt(bool immediateReceipt, bool identityMatches,
                                    uint32_t currentBits) {
    return immediateReceipt && identityMatches && currentBits == S148_HEALTH_EXPECTED_BITS;
}

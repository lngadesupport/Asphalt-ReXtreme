#include "RexIntegrationShim.h"

#include <stdio.h>

extern int RexShim_GaiaIsReady(void);
extern int RexShim_GaiaIsNetworkRequired(void);
extern int RexShim_GlobalSyncCommit(uint32_t reason, uint32_t* operation_id);
extern uint32_t RexShim_GlobalSyncPendingCount(void);

static int failures = 0;

#define CHECK(expr) do { \
    if (!(expr)) { \
        printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #expr); \
        failures += 1; \
    } \
} while (0)

static int write_u32_le(FILE* file, uint32_t value) {
    unsigned char bytes[4];

    bytes[0] = (unsigned char)(value & 0xFFu);
    bytes[1] = (unsigned char)((value >> 8) & 0xFFu);
    bytes[2] = (unsigned char)((value >> 16) & 0xFFu);
    bytes[3] = (unsigned char)((value >> 24) & 0xFFu);

    return fwrite(bytes, 1u, sizeof(bytes), file) == sizeof(bytes);
}

static int write_content_fixture(const char* path) {
    static const unsigned char magic[8] = {
        'R', 'E', 'X', 'C', 'T', 'V', '2', 0
    };
    FILE* file = 0;
    int ok = 1;

    if (fopen_s(&file, path, "wb") != 0 || file == 0) {
        return 0;
    }

    ok = ok && fwrite(magic, 1u, sizeof(magic), file) == sizeof(magic);
    ok = ok && write_u32_le(file, 2u);
    ok = ok && write_u32_le(file, 2u);

    ok = ok && write_u32_le(file, 501u);
    ok = ok && write_u32_le(file, 1u);
    ok = ok && write_u32_le(file, 1u);
    ok = ok && write_u32_le(file, 9501u);
    ok = ok && write_u32_le(file, 4u);

    ok = ok && write_u32_le(file, 502u);
    ok = ok && write_u32_le(file, 0u);
    ok = ok && write_u32_le(file, 0u);
    ok = ok && write_u32_le(file, 0u);
    ok = ok && write_u32_le(file, 0u);

    ok = ok && write_u32_le(file, 1u);
    ok = ok && write_u32_le(file, 9501u);
    ok = ok && write_u32_le(file, 7u);

    ok = ok && write_u32_le(file, 0u);

    if (fclose(file) != 0) {
        ok = 0;
    }

    return ok;
}

static void cleanup_state_files(const char* path) {
    char tmp_path[160];
    char bak_path[160];

    sprintf_s(tmp_path, sizeof(tmp_path), "%s.tmp", path);
    sprintf_s(bak_path, sizeof(bak_path), "%s.bak", path);

    remove(path);
    remove(tmp_path);
    remove(bak_path);
}

static void test_shim_rejects_missing_core_and_can_retry(void) {
    CHECK(RexShim_GetAbiVersion() == REX_SHIM_ABI_VERSION);
    CHECK(
        RexShim_Start(
            "MissingRexCore.dll",
            "MissingContent.dat",
            "MissingState.dat"
        ) == 0
    );
    CHECK(RexShim_IsStarted() == 0);
}

static void test_shim_transports_garage_events_and_snapshots(void) {
    const char* content_path = "RexShimContentTest.dat";
    const char* state_path = "RexShimStateTest.dat";
    RexGarageSnapshotV1 snapshot = {0};
    int action_result = -1;

    remove(content_path);
    cleanup_state_files(state_path);

    CHECK(write_content_fixture(content_path) == 1);

    CHECK(
        RexShim_Start(
            "RexCore.dll",
            content_path,
            state_path
        ) == 1
    );
    CHECK(RexShim_IsStarted() == 1);

    {
        uint32_t operation_id = 0u;
        CHECK(RexShim_GaiaIsReady() == 1);
        CHECK(RexShim_GaiaIsNetworkRequired() == 0);
        CHECK(RexShim_GlobalSyncPendingCount() == 0u);
        CHECK(
            RexShim_GlobalSyncCommit(
                REX_GLOBAL_SYNC_REASON_PROFILE_BOOTSTRAP,
                &operation_id
            ) == REX_GLOBAL_SYNC_OK
        );
        CHECK(operation_id == 1u);
        CHECK(RexShim_GlobalSyncPendingCount() == 0u);
    }

    CHECK(RexShim_GarageEnter(501u) == 1);
    CHECK(RexShim_CopyGarageSnapshot(&snapshot) == 1);
    CHECK(snapshot.abi_version == REX_BOUNDARY_ABI_VERSION);
    CHECK(snapshot.selected_vehicle_id == 501u);
    CHECK(snapshot.blueprint_balance == 7u);
    CHECK(snapshot.blueprint_cost == 4u);
    CHECK(snapshot.owned == 0);
    CHECK(snapshot.montar_enabled == 1);

    CHECK(RexShim_GarageSelectionChanged(502u) == 1);
    CHECK(RexShim_CopyGarageSnapshot(&snapshot) == 1);
    CHECK(snapshot.selected_vehicle_id == 502u);
    CHECK(snapshot.unlocked == 0);
    CHECK(snapshot.montar_enabled == 0);

    CHECK(RexShim_GarageSelectionChanged(501u) == 1);
    CHECK(RexShim_GarageMontarPressed() == 0);
    CHECK(RexShim_GetLastActionResult(&action_result) == 1);
    CHECK(action_result == 0);

    CHECK(RexShim_CopyGarageSnapshot(&snapshot) == 1);
    CHECK(snapshot.selected_vehicle_id == 501u);
    CHECK(snapshot.owned == 1);
    CHECK(snapshot.montar_enabled == 0);
    CHECK(snapshot.blueprint_balance == 3u);

    remove(content_path);
    cleanup_state_files(state_path);
}

int main(void) {
    test_shim_rejects_missing_core_and_can_retry();
    test_shim_transports_garage_events_and_snapshots();

    if (failures != 0) {
        printf("%d shim test assertion(s) failed.\n", failures);
        return 1;
    }

    printf("ReX integration shim tests passed.\n");
    return 0;
}

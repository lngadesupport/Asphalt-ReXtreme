#include "RexGaia.h"
#include "RexGlobalSync.h"
#include "RexState.h"

#include <stdio.h>
#include <string.h>

static int failures = 0;

#define CHECK(expr) do { \
    if (!(expr)) { \
        printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #expr); \
        failures += 1; \
    } \
} while (0)

static void cleanup_state_files(const char* path) {
    char tmp[512];
    char bak[512];

    remove(path);
    if (sprintf_s(tmp, sizeof(tmp), "%s.tmp", path) >= 0) {
        remove(tmp);
    }
    if (sprintf_s(bak, sizeof(bak), "%s.bak", path) >= 0) {
        remove(bak);
    }
}

static void test_gaia_creates_local_session_without_network(void) {
    RexGaia gaia = {0};
    RexGaiaSession session = {0};

    CHECK(RexGaia_Init(&gaia, "campaign-local") == 1);
    CHECK(RexGaia_IsReady(&gaia) == 1);
    CHECK(RexGaia_IsNetworkRequired(&gaia) == 0);

    CHECK(RexGaia_GetSession(&gaia, &session) == 1);
    CHECK(strcmp(session.provider, "rex-local") == 0);
    CHECK(strcmp(session.profile_id, "campaign-local") == 0);
    CHECK(session.authenticated == 1);
    CHECK(session.offline == 1);
}

static void test_gaia_rejects_empty_profile_id(void) {
    RexGaia gaia = {0};

    CHECK(RexGaia_Init(&gaia, "") == 0);
    CHECK(RexGaia_IsReady(&gaia) == 0);
}

typedef struct SyncObserver {
    int calls;
    RexGlobalSyncResult last_result;
    uint64_t last_revision;
    uint32_t last_operation_id;
} SyncObserver;

static void on_sync_complete(
    void* context,
    uint32_t operation_id,
    RexGlobalSyncResult result,
    uint64_t revision
) {
    SyncObserver* observer = (SyncObserver*)context;
    observer->calls += 1;
    observer->last_operation_id = operation_id;
    observer->last_result = result;
    observer->last_revision = revision;
}

static void test_globalsync_commits_local_state_and_completes_once(void) {
    const char* path = "RexGlobalSyncTest.dat";
    RexState state;
    RexState reloaded;
    RexGlobalSync sync = {0};
    SyncObserver observer = {0};
    uint32_t operation_id = 0u;

    cleanup_state_files(path);
    RexState_Init(&state);

    CHECK(
        RexGlobalSync_Init(
            &sync,
            &state,
            path,
            on_sync_complete,
            &observer
        ) == 1
    );

    CHECK(RexGlobalSync_IsNetworkRequired(&sync) == 0);
    CHECK(RexGlobalSync_GetPendingCount(&sync) == 0u);

    CHECK(
        RexGlobalSync_Commit(
            &sync,
            REX_GLOBAL_SYNC_REASON_PROFILE_BOOTSTRAP,
            &operation_id
        ) == REX_GLOBAL_SYNC_OK
    );

    CHECK(operation_id == 1u);
    CHECK(observer.calls == 1);
    CHECK(observer.last_operation_id == 1u);
    CHECK(observer.last_result == REX_GLOBAL_SYNC_OK);
    CHECK(observer.last_revision == 1u);
    CHECK(state.revision == 1u);
    CHECK(RexGlobalSync_GetPendingCount(&sync) == 0u);

    RexState_Init(&reloaded);
    CHECK(RexState_Load(&reloaded, path) == 1);
    CHECK(reloaded.revision == 1u);

    cleanup_state_files(path);
}

static void test_globalsync_failure_does_not_advance_revision(void) {
    RexState state;
    RexGlobalSync sync = {0};
    SyncObserver observer = {0};
    uint32_t operation_id = 0u;

    RexState_Init(&state);

    CHECK(
        RexGlobalSync_Init(
            &sync,
            &state,
            "",
            on_sync_complete,
            &observer
        ) == 0
    );
    CHECK(state.revision == 0u);
    CHECK(observer.calls == 0);
    CHECK(operation_id == 0u);
}

int main(void) {
    test_gaia_creates_local_session_without_network();
    test_gaia_rejects_empty_profile_id();
    test_globalsync_commits_local_state_and_completes_once();
    test_globalsync_failure_does_not_advance_revision();

    if (failures != 0) {
        printf("%d backend service assertion(s) failed.\n", failures);
        return 1;
    }

    printf("ReX Gaia/GlobalSync tests passed.\n");
    return 0;
}

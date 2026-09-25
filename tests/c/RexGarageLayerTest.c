#include "RexCampaign.h"
#include "RexContent.h"
#include "RexState.h"
#include "RexGaragePresenter.h"
#include "RexGarageViewModel.h"
#include "RexTutorialController.h"
#include "RexPresentationAdapterV2.h"
#include "RexRuntime.h"
#include "RexHost.h"
#include "RexBoundaryV1.h"

#include <stdio.h>

extern int RexHost_GaiaIsReady(void);
extern int RexHost_GaiaIsNetworkRequired(void);
extern uint32_t RexHost_GlobalSyncPendingCount(void);
extern int RexHost_GlobalSyncCommit(uint32_t reason, uint32_t* operation_id);

static int failures = 0;

#define CHECK(expr) do { \
    if (!(expr)) { \
        printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #expr); \
        failures += 1; \
    } \
} while (0)

static RexGarageViewModel build_vm(RexGarageViewModelInput input) {
    RexGarageViewModel vm = {0};
    RexGarageViewModel_Build(&input, &vm);
    return vm;
}

static void test_ready_vehicle_enables_build(void) {
    RexGarageViewModelInput input = {0};
    RexGarageViewModel vm;

    input.selected_vehicle_id = 42;
    input.unlocked = 1;
    input.has_recipe = 1;
    input.blueprint_balance = 12;
    input.blueprint_cost = 10;

    vm = build_vm(input);

    CHECK(vm.selected_vehicle_id == 42);
    CHECK(vm.build_enabled == 1);
    CHECK(vm.build_status == REX_GARAGE_BUILD_READY);
}

static void test_owned_vehicle_disables_build(void) {
    RexGarageViewModelInput input = {0};
    RexGarageViewModel vm;

    input.selected_vehicle_id = 42;
    input.owned = 1;
    input.unlocked = 1;
    input.has_recipe = 1;
    input.blueprint_balance = 50;
    input.blueprint_cost = 10;

    vm = build_vm(input);

    CHECK(vm.build_enabled == 0);
    CHECK(vm.build_status == REX_GARAGE_BUILD_OWNED);
}

static void test_no_selection_is_not_buildable(void) {
    RexGarageViewModelInput input = {0};
    RexGarageViewModel vm = build_vm(input);

    CHECK(vm.build_enabled == 0);
    CHECK(vm.build_status == REX_GARAGE_BUILD_NO_SELECTION);
}

static void test_locked_vehicle_is_not_buildable(void) {
    RexGarageViewModelInput input = {0};
    RexGarageViewModel vm;

    input.selected_vehicle_id = 55;
    input.unlocked = 0;
    input.has_recipe = 1;
    input.blueprint_balance = 99;
    input.blueprint_cost = 5;

    vm = build_vm(input);

    CHECK(vm.build_enabled == 0);
    CHECK(vm.build_status == REX_GARAGE_BUILD_LOCKED);
}

static void test_vehicle_without_recipe_is_unavailable(void) {
    RexGarageViewModelInput input = {0};
    RexGarageViewModel vm;

    input.selected_vehicle_id = 56;
    input.unlocked = 1;
    input.has_recipe = 0;
    input.blueprint_balance = 99;

    vm = build_vm(input);

    CHECK(vm.build_enabled == 0);
    CHECK(vm.build_status == REX_GARAGE_BUILD_UNAVAILABLE);
}

static void test_insufficient_blueprints_disables_build(void) {
    RexGarageViewModelInput input = {0};
    RexGarageViewModel vm;

    input.selected_vehicle_id = 77;
    input.unlocked = 1;
    input.has_recipe = 1;
    input.blueprint_balance = 4;
    input.blueprint_cost = 5;

    vm = build_vm(input);

    CHECK(vm.build_enabled == 0);
    CHECK(vm.build_status == REX_GARAGE_BUILD_NEEDS_BLUEPRINTS);
}

static void test_tutorial_waits_until_build_is_available(void) {
    RexTutorialController tutorial = {0};

    RexTutorialController_Init(&tutorial, 0);
    RexTutorialController_OnGarageEntered(&tutorial, 0);

    CHECK(RexTutorialController_GetState(&tutorial) == REX_TUTORIAL_IDLE);
    CHECK(RexTutorialController_ShouldFocusBuild(&tutorial) == 0);

    RexTutorialController_OnBuildPressed(&tutorial);
    CHECK(RexTutorialController_GetState(&tutorial) == REX_TUTORIAL_IDLE);
}

static void test_tutorial_advances_only_after_successful_build(void) {
    RexTutorialController tutorial = {0};

    RexTutorialController_Init(&tutorial, 0);
    CHECK(RexTutorialController_GetState(&tutorial) == REX_TUTORIAL_IDLE);

    RexTutorialController_OnGarageEntered(&tutorial, 1);
    CHECK(RexTutorialController_ShouldFocusBuild(&tutorial) == 1);

    RexTutorialController_OnBuildPressed(&tutorial);
    CHECK(RexTutorialController_GetState(&tutorial) == REX_TUTORIAL_WAIT_BUILD_RESULT);

    RexTutorialController_OnBuildResult(&tutorial, 0);
    CHECK(RexTutorialController_GetState(&tutorial) == REX_TUTORIAL_FOCUS_BUILD);

    RexTutorialController_OnBuildPressed(&tutorial);
    RexTutorialController_OnBuildResult(&tutorial, 1);

    CHECK(RexTutorialController_IsComplete(&tutorial) == 1);
    CHECK(RexTutorialController_ShouldFocusBuild(&tutorial) == 0);
}

static void test_completed_tutorial_stays_complete(void) {
    RexTutorialController tutorial = {0};

    RexTutorialController_Init(&tutorial, 1);
    RexTutorialController_OnGarageEntered(&tutorial, 1);
    RexTutorialController_OnBuildPressed(&tutorial);
    RexTutorialController_OnBuildResult(&tutorial, 0);

    CHECK(RexTutorialController_IsComplete(&tutorial) == 1);
}

typedef struct FakeCampaign {
    RexGarageViewModelInput vehicle;
    int read_success;
    int read_calls;
    int acquire_calls;
    int tutorial_complete_calls;
    int tutorial_complete;
    RexCampaignActionResult acquire_result;
} FakeCampaign;

static int fake_read_vehicle(
    void* context,
    uint32_t vehicle_id,
    RexGarageViewModelInput* output
) {
    FakeCampaign* fake = (FakeCampaign*)context;
    fake->read_calls += 1;

    if (!fake->read_success) {
        return 0;
    }

    *output = fake->vehicle;
    output->selected_vehicle_id = vehicle_id;
    return 1;
}

static RexCampaignActionResult fake_acquire_vehicle(
    void* context,
    uint32_t vehicle_id
) {
    FakeCampaign* fake = (FakeCampaign*)context;
    fake->acquire_calls += 1;

    if (fake->acquire_result == REX_CAMPAIGN_ACTION_OK &&
        fake->vehicle.selected_vehicle_id == vehicle_id) {
        fake->vehicle.owned = 1;
    }

    return fake->acquire_result;
}

static int fake_complete_garage_tutorial(void* context) {
    FakeCampaign* fake = (FakeCampaign*)context;
    fake->tutorial_complete_calls += 1;
    fake->tutorial_complete = 1;
    return 1;
}

static RexCampaignGarageApi fake_api(FakeCampaign* fake) {
    RexCampaignGarageApi api = {0};
    api.context = fake;
    api.read_vehicle = fake_read_vehicle;
    api.acquire_vehicle = fake_acquire_vehicle;
    api.complete_garage_tutorial = fake_complete_garage_tutorial;
    return api;
}

static FakeCampaign ready_fake(uint32_t vehicle_id) {
    FakeCampaign fake = {0};
    fake.vehicle.selected_vehicle_id = vehicle_id;
    fake.vehicle.unlocked = 1;
    fake.vehicle.has_recipe = 1;
    fake.vehicle.blueprint_balance = 12;
    fake.vehicle.blueprint_cost = 10;
    fake.read_success = 1;
    fake.acquire_result = REX_CAMPAIGN_ACTION_OK;
    return fake;
}

static void test_presenter_enter_builds_view_model_and_tutorial(void) {
    FakeCampaign fake = ready_fake(42);
    RexGaragePresenter presenter = {0};
    const RexGarageViewModel* vm;

    RexGaragePresenter_Init(&presenter, fake_api(&fake), 0);
    CHECK(RexGaragePresenter_OnEnter(&presenter, 42) == 1);

    vm = RexGaragePresenter_GetViewModel(&presenter);
    CHECK(vm->selected_vehicle_id == 42);
    CHECK(vm->build_enabled == 1);
    CHECK(RexGaragePresenter_ShouldFocusBuild(&presenter) == 1);
}

static void test_presenter_car_selection_rebuilds_view_model(void) {
    FakeCampaign fake = ready_fake(42);
    RexGaragePresenter presenter = {0};
    const RexGarageViewModel* vm;

    RexGaragePresenter_Init(&presenter, fake_api(&fake), 0);
    CHECK(RexGaragePresenter_OnEnter(&presenter, 42) == 1);

    fake.vehicle.unlocked = 0;
    CHECK(RexGaragePresenter_OnCarSelected(&presenter, 77) == 1);

    vm = RexGaragePresenter_GetViewModel(&presenter);
    CHECK(vm->selected_vehicle_id == 77);
    CHECK(vm->build_enabled == 0);
    CHECK(vm->build_status == REX_GARAGE_BUILD_LOCKED);
}

static void test_presenter_successful_build_refreshes_owned_state(void) {
    FakeCampaign fake = ready_fake(42);
    RexGaragePresenter presenter = {0};
    RexGaragePresenterResult result;
    const RexGarageViewModel* vm;

    RexGaragePresenter_Init(&presenter, fake_api(&fake), 0);
    CHECK(RexGaragePresenter_OnEnter(&presenter, 42) == 1);

    result = RexGaragePresenter_OnMontarPressed(&presenter);
    vm = RexGaragePresenter_GetViewModel(&presenter);

    CHECK(result == REX_GARAGE_PRESENTER_OK);
    CHECK(fake.acquire_calls == 1);
    CHECK(vm->owned == 1);
    CHECK(vm->build_enabled == 0);
    CHECK(vm->build_status == REX_GARAGE_BUILD_OWNED);
    CHECK(RexGaragePresenter_IsTutorialComplete(&presenter) == 1);
    CHECK(fake.tutorial_complete_calls == 1);
    CHECK(fake.tutorial_complete == 1);
}

static void test_presenter_rejects_disabled_build_without_campaign_call(void) {
    FakeCampaign fake = ready_fake(42);
    RexGaragePresenter presenter = {0};

    fake.vehicle.owned = 1;

    RexGaragePresenter_Init(&presenter, fake_api(&fake), 0);
    CHECK(RexGaragePresenter_OnEnter(&presenter, 42) == 1);

    CHECK(
        RexGaragePresenter_OnMontarPressed(&presenter) ==
        REX_GARAGE_PRESENTER_NOT_BUILDABLE
    );
    CHECK(fake.acquire_calls == 0);
}

static void test_presenter_failed_campaign_action_returns_tutorial_to_focus(void) {
    FakeCampaign fake = ready_fake(42);
    RexGaragePresenter presenter = {0};

    fake.acquire_result = REX_CAMPAIGN_ACTION_REJECTED;

    RexGaragePresenter_Init(&presenter, fake_api(&fake), 0);
    CHECK(RexGaragePresenter_OnEnter(&presenter, 42) == 1);

    CHECK(
        RexGaragePresenter_OnMontarPressed(&presenter) ==
        REX_GARAGE_PRESENTER_CAMPAIGN_FAILED
    );
    CHECK(fake.acquire_calls == 1);
    CHECK(RexGaragePresenter_ShouldFocusBuild(&presenter) == 1);
    CHECK(RexGaragePresenter_GetViewModel(&presenter)->build_enabled == 1);
}

static void test_presenter_reports_read_failure(void) {
    FakeCampaign fake = ready_fake(42);
    RexGaragePresenter presenter = {0};

    fake.read_success = 0;

    RexGaragePresenter_Init(&presenter, fake_api(&fake), 0);
    CHECK(RexGaragePresenter_OnEnter(&presenter, 42) == 0);
    CHECK(fake.read_calls == 1);
}


static void cleanup_state_files(const char* path) {
    char tmp_path[128];
    char bak_path[128];

    sprintf_s(tmp_path, sizeof(tmp_path), "%s.tmp", path);
    sprintf_s(bak_path, sizeof(bak_path), "%s.bak", path);

    remove(path);
    remove(tmp_path);
    remove(bak_path);
}

static void test_content_lookup_is_new_local_catalog(void) {
    const RexContentVehicle vehicles[] = {
        {101u, 1, 1, 9001u, 3u},
        {202u, 0, 0, 0u, 0u}
    };
    RexContent content = {0};
    const RexContentVehicle* found;

    RexContent_Init(&content, vehicles, 2u);

    found = RexContent_FindVehicle(&content, 101u);
    CHECK(found != 0);
    CHECK(found->blueprint_id == 9001u);
    CHECK(found->blueprint_cost == 3u);
    CHECK(RexContent_FindVehicle(&content, 999u) == 0);
}

static void test_state_owns_inventory_and_round_trip_persistence(void) {
    const char* path = "RexCampaignStateTest.dat";
    RexState state;
    RexState loaded;

    cleanup_state_files(path);
    RexState_Init(&state);

    CHECK(RexState_AddOwned(&state, 101u) == 1);
    CHECK(RexState_SetBlueprintBalance(&state, 9001u, 7u) == 1);
    CHECK(RexState_SpendBlueprints(&state, 9001u, 2u) == 1);
    RexState_SetGarageTutorialComplete(&state, 1);
    state.revision = 9u;

    CHECK(RexState_Save(&state, path) == 1);

    RexState_Init(&loaded);
    CHECK(RexState_Load(&loaded, path) == 1);
    CHECK(loaded.version == REX_STATE_VERSION);
    CHECK(loaded.revision == 9u);
    CHECK(RexState_IsOwned(&loaded, 101u) == 1);
    CHECK(RexState_GetBlueprintBalance(&loaded, 9001u) == 5u);
    CHECK(loaded.garage_tutorial_complete == 1);

    cleanup_state_files(path);
}

static void test_campaign_transaction_spends_blueprints_and_persists(void) {
    const char* path = "RexCampaignAcquireTest.dat";
    const RexContentVehicle vehicles[] = {
        {101u, 1, 1, 9001u, 3u}
    };
    RexContent content = {0};
    RexState state;
    RexState loaded;
    RexCampaign campaign = {0};
    RexGlobalSync global_sync = {0};
    RexGarageViewModelInput input = {0};

    cleanup_state_files(path);
    RexContent_Init(&content, vehicles, 1u);
    RexState_Init(&state);
    CHECK(RexState_SetBlueprintBalance(&state, 9001u, 5u) == 1);
    CHECK(RexGlobalSync_Init(&global_sync, &state, path, 0, 0) == 1);
    CHECK(RexCampaign_Init(&campaign, &content, &state, &global_sync) == 1);

    CHECK(RexCampaign_ReadVehicle(&campaign, 101u, &input) == 1);
    CHECK(input.owned == 0);
    CHECK(input.unlocked == 1);
    CHECK(input.has_recipe == 1);
    CHECK(input.blueprint_balance == 5u);
    CHECK(input.blueprint_cost == 3u);

    CHECK(RexCampaign_AcquireVehicle(&campaign, 101u) == REX_CAMPAIGN_ACTION_OK);
    CHECK(RexState_IsOwned(&state, 101u) == 1);
    CHECK(RexState_GetBlueprintBalance(&state, 9001u) == 2u);
    CHECK(state.revision == 1u);

    RexState_Init(&loaded);
    CHECK(RexState_Load(&loaded, path) == 1);
    CHECK(RexState_IsOwned(&loaded, 101u) == 1);
    CHECK(RexState_GetBlueprintBalance(&loaded, 9001u) == 2u);
    CHECK(loaded.revision == 1u);

    cleanup_state_files(path);
}

static void test_campaign_rejects_invalid_transaction_without_mutation(void) {
    const char* path = "RexCampaignRejectTest.dat";
    const RexContentVehicle vehicles[] = {
        {101u, 1, 1, 9001u, 3u}
    };
    RexContent content = {0};
    RexState state;
    RexCampaign campaign = {0};
    RexGlobalSync global_sync = {0};

    cleanup_state_files(path);
    RexContent_Init(&content, vehicles, 1u);
    RexState_Init(&state);
    CHECK(RexState_SetBlueprintBalance(&state, 9001u, 2u) == 1);
    CHECK(RexGlobalSync_Init(&global_sync, &state, path, 0, 0) == 1);
    CHECK(RexCampaign_Init(&campaign, &content, &state, &global_sync) == 1);

    CHECK(
        RexCampaign_AcquireVehicle(&campaign, 101u) ==
        REX_CAMPAIGN_ACTION_REJECTED
    );
    CHECK(RexState_IsOwned(&state, 101u) == 0);
    CHECK(RexState_GetBlueprintBalance(&state, 9001u) == 2u);
    CHECK(state.revision == 0u);

    cleanup_state_files(path);
}

static void test_real_campaign_api_drives_presenter_without_legacy_runtime(void) {
    const char* path = "RexCampaignPresenterTest.dat";
    const RexContentVehicle vehicles[] = {
        {303u, 1, 1, 9303u, 4u}
    };
    RexContent content = {0};
    RexState state;
    RexCampaign campaign = {0};
    RexGlobalSync global_sync = {0};
    RexGaragePresenter presenter = {0};

    cleanup_state_files(path);
    RexContent_Init(&content, vehicles, 1u);
    RexState_Init(&state);
    CHECK(RexState_SetBlueprintBalance(&state, 9303u, 6u) == 1);
    CHECK(RexGlobalSync_Init(&global_sync, &state, path, 0, 0) == 1);
    CHECK(RexCampaign_Init(&campaign, &content, &state, &global_sync) == 1);

    RexGaragePresenter_Init(
        &presenter,
        RexCampaign_MakeGarageApi(&campaign),
        RexCampaign_IsGarageTutorialComplete(&campaign)
    );

    CHECK(RexGaragePresenter_OnEnter(&presenter, 303u) == 1);
    CHECK(RexGaragePresenter_GetViewModel(&presenter)->build_enabled == 1);
    CHECK(RexGaragePresenter_OnMontarPressed(&presenter) == REX_GARAGE_PRESENTER_OK);
    CHECK(RexGaragePresenter_GetViewModel(&presenter)->owned == 1);
    CHECK(RexState_GetBlueprintBalance(&state, 9303u) == 2u);

    cleanup_state_files(path);
}



static void test_state_load_falls_back_to_backup_after_current_corruption(void) {
    const char* path = "RexCampaignBackupTest.dat";
    RexState state;
    RexState loaded;
    FILE* corrupt = 0;

    cleanup_state_files(path);
    RexState_Init(&state);
    state.revision = 1u;
    CHECK(RexState_SetBlueprintBalance(&state, 7001u, 11u) == 1);
    CHECK(RexState_Save(&state, path) == 1);

    state.revision = 2u;
    CHECK(RexState_SetBlueprintBalance(&state, 7001u, 22u) == 1);
    CHECK(RexState_Save(&state, path) == 1);

    CHECK(fopen_s(&corrupt, path, "wb") == 0);
    CHECK(corrupt != 0);
    if (corrupt != 0) {
        CHECK(fwrite("bad", 1u, 3u, corrupt) == 3u);
        CHECK(fclose(corrupt) == 0);
    }

    RexState_Init(&loaded);
    CHECK(RexState_Load(&loaded, path) == 1);
    CHECK(loaded.revision == 1u);
    CHECK(RexState_GetBlueprintBalance(&loaded, 7001u) == 11u);

    cleanup_state_files(path);
}

static void test_real_campaign_presenter_persists_tutorial_completion(void) {
    const char* path = "RexCampaignTutorialTest.dat";
    const RexContentVehicle vehicles[] = {
        {404u, 1, 1, 9404u, 2u}
    };
    RexContent content = {0};
    RexState state;
    RexState loaded;
    RexCampaign campaign = {0};
    RexGlobalSync global_sync = {0};
    RexGaragePresenter presenter = {0};

    cleanup_state_files(path);
    RexContent_Init(&content, vehicles, 1u);
    RexState_Init(&state);
    CHECK(RexState_SetBlueprintBalance(&state, 9404u, 3u) == 1);
    CHECK(RexGlobalSync_Init(&global_sync, &state, path, 0, 0) == 1);
    CHECK(RexCampaign_Init(&campaign, &content, &state, &global_sync) == 1);

    RexGaragePresenter_Init(
        &presenter,
        RexCampaign_MakeGarageApi(&campaign),
        RexCampaign_IsGarageTutorialComplete(&campaign)
    );

    CHECK(RexGaragePresenter_OnEnter(&presenter, 404u) == 1);
    CHECK(RexGaragePresenter_OnMontarPressed(&presenter) == REX_GARAGE_PRESENTER_OK);
    CHECK(RexCampaign_IsGarageTutorialComplete(&campaign) == 1);

    RexState_Init(&loaded);
    CHECK(RexState_Load(&loaded, path) == 1);
    CHECK(loaded.garage_tutorial_complete == 1);

    cleanup_state_files(path);
}



static int write_u32_le(FILE* file, uint32_t value) {
    unsigned char data[4];

    data[0] = (unsigned char)(value & 0xFFu);
    data[1] = (unsigned char)((value >> 8) & 0xFFu);
    data[2] = (unsigned char)((value >> 16) & 0xFFu);
    data[3] = (unsigned char)((value >> 24) & 0xFFu);

    return fwrite(data, 1u, sizeof(data), file) == sizeof(data);
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
    ok = ok && write_u32_le(file, REX_CONTENT_VERSION);
    ok = ok && write_u32_le(file, 2u);

    ok = ok && write_u32_le(file, 501u);
    ok = ok && write_u32_le(file, 1u);
    ok = ok && write_u32_le(file, 1u);
    ok = ok && write_u32_le(file, 9501u);
    ok = ok && write_u32_le(file, 7u);

    ok = ok && write_u32_le(file, 502u);
    ok = ok && write_u32_le(file, 0u);
    ok = ok && write_u32_le(file, 0u);
    ok = ok && write_u32_le(file, 0u);
    ok = ok && write_u32_le(file, 0u);

    ok = ok && write_u32_le(file, 1u);
    ok = ok && write_u32_le(file, 9501u);
    ok = ok && write_u32_le(file, 10u);

    ok = ok && write_u32_le(file, 1u);
    ok = ok && write_u32_le(file, 502u);

    if (fclose(file) != 0) {
        ok = 0;
    }

    return ok;
}

static void test_content_v2_binary_file_loads_local_catalog(void) {
    const char* path = "CampaignContentV2Test.dat";
    RexContent content = {0};
    const RexContentVehicle* first;
    const RexContentVehicle* second;

    remove(path);
    CHECK(write_content_fixture(path) == 1);
    CHECK(RexContent_Load(&content, path) == 1);
    CHECK(content.vehicle_count == 2u);

    first = RexContent_FindVehicle(&content, 501u);
    second = RexContent_FindVehicle(&content, 502u);

    CHECK(first != 0);
    CHECK(first->unlocked_by_default == 1);
    CHECK(first->has_recipe == 1);
    CHECK(first->blueprint_id == 9501u);
    CHECK(first->blueprint_cost == 7u);

    CHECK(second != 0);
    CHECK(second->unlocked_by_default == 0);
    CHECK(second->has_recipe == 0);

    CHECK(content.initial_balance_count == 1u);
    CHECK(content.initial_balances[0].blueprint_id == 9501u);
    CHECK(content.initial_balances[0].amount == 10u);
    CHECK(content.starter_owned_count == 1u);
    CHECK(content.starter_owned_vehicles[0] == 502u);

    remove(path);
}

static void test_content_v2_rejects_invalid_file(void) {
    const char* path = "CampaignContentV2Invalid.dat";
    FILE* file = 0;
    RexContent content = {0};

    remove(path);
    CHECK(fopen_s(&file, path, "wb") == 0);
    CHECK(file != 0);
    if (file != 0) {
        CHECK(fwrite("bad", 1u, 3u, file) == 3u);
        CHECK(fclose(file) == 0);
    }

    CHECK(RexContent_Load(&content, path) == 0);
    remove(path);
}



typedef struct FakePresentation {
    uint32_t selected_vehicle_id;
    int present_calls;
    int action_calls;
    int focus_build;
    RexGarageViewModel last_view_model;
    RexGaragePresenterResult last_action_result;
} FakePresentation;

static uint32_t fake_presentation_read_selected_vehicle_id(
    void* context
) {
    FakePresentation* presentation = (FakePresentation*)context;
    return presentation->selected_vehicle_id;
}

static void fake_presentation_present_garage(
    void* context,
    const RexGarageViewModel* view_model,
    int focus_build
) {
    FakePresentation* presentation = (FakePresentation*)context;
    presentation->present_calls += 1;
    presentation->last_view_model = *view_model;
    presentation->focus_build = focus_build;
}

static void fake_presentation_present_action_result(
    void* context,
    RexGaragePresenterResult result
) {
    FakePresentation* presentation = (FakePresentation*)context;
    presentation->action_calls += 1;
    presentation->last_action_result = result;
}

static RexPresentationGaragePort fake_presentation_port(
    FakePresentation* presentation
) {
    RexPresentationGaragePort port = {0};

    port.context = presentation;
    port.read_selected_vehicle_id =
        fake_presentation_read_selected_vehicle_id;
    port.present_garage =
        fake_presentation_present_garage;
    port.present_action_result =
        fake_presentation_present_action_result;

    return port;
}

static void test_presentation_adapter_enters_and_presents_view_model(void) {
    FakeCampaign fake = ready_fake(601u);
    FakePresentation presentation = {0};
    RexGaragePresenter presenter = {0};
    RexPresentationAdapterV2 adapter = {0};

    presentation.selected_vehicle_id = 601u;

    RexGaragePresenter_Init(
        &presenter,
        fake_api(&fake),
        0
    );

    CHECK(
        RexPresentationAdapterV2_Init(
            &adapter,
            &presenter,
            fake_presentation_port(&presentation)
        ) == 1
    );

    CHECK(RexPresentationAdapterV2_OnEnter(&adapter) == 1);
    CHECK(presentation.present_calls == 1);
    CHECK(presentation.last_view_model.selected_vehicle_id == 601u);
    CHECK(presentation.last_view_model.build_enabled == 1);
    CHECK(presentation.focus_build == 1);
}

static void test_presentation_adapter_selection_change_rebuilds_state(void) {
    FakeCampaign fake = ready_fake(601u);
    FakePresentation presentation = {0};
    RexGaragePresenter presenter = {0};
    RexPresentationAdapterV2 adapter = {0};

    presentation.selected_vehicle_id = 601u;

    RexGaragePresenter_Init(
        &presenter,
        fake_api(&fake),
        0
    );
    CHECK(
        RexPresentationAdapterV2_Init(
            &adapter,
            &presenter,
            fake_presentation_port(&presentation)
        ) == 1
    );
    CHECK(RexPresentationAdapterV2_OnEnter(&adapter) == 1);

    fake.vehicle.unlocked = 0;
    presentation.selected_vehicle_id = 602u;

    CHECK(
        RexPresentationAdapterV2_OnSelectionChanged(&adapter) == 1
    );
    CHECK(presentation.present_calls == 2);
    CHECK(presentation.last_view_model.selected_vehicle_id == 602u);
    CHECK(presentation.last_view_model.build_enabled == 0);
    CHECK(
        presentation.last_view_model.build_status ==
        REX_GARAGE_BUILD_LOCKED
    );
}

static void test_presentation_adapter_routes_montar_and_renders_result(void) {
    FakeCampaign fake = ready_fake(603u);
    FakePresentation presentation = {0};
    RexGaragePresenter presenter = {0};
    RexPresentationAdapterV2 adapter = {0};
    RexGaragePresenterResult result;

    presentation.selected_vehicle_id = 603u;

    RexGaragePresenter_Init(
        &presenter,
        fake_api(&fake),
        0
    );
    CHECK(
        RexPresentationAdapterV2_Init(
            &adapter,
            &presenter,
            fake_presentation_port(&presentation)
        ) == 1
    );
    CHECK(RexPresentationAdapterV2_OnEnter(&adapter) == 1);

    result = RexPresentationAdapterV2_OnMontarPressed(&adapter);

    CHECK(result == REX_GARAGE_PRESENTER_OK);
    CHECK(fake.acquire_calls == 1);
    CHECK(presentation.action_calls == 1);
    CHECK(presentation.last_action_result == REX_GARAGE_PRESENTER_OK);
    CHECK(presentation.present_calls == 2);
    CHECK(presentation.last_view_model.owned == 1);
    CHECK(presentation.last_view_model.build_enabled == 0);
    CHECK(presentation.focus_build == 0);
}

static void test_presentation_adapter_requires_only_presentation_contract(void) {
    FakeCampaign fake = ready_fake(604u);
    FakePresentation presentation = {0};
    RexGaragePresenter presenter = {0};
    RexPresentationAdapterV2 adapter = {0};
    RexPresentationGaragePort port;

    RexGaragePresenter_Init(
        &presenter,
        fake_api(&fake),
        0
    );

    port = fake_presentation_port(&presentation);
    port.present_garage = 0;

    CHECK(
        RexPresentationAdapterV2_Init(
            &adapter,
            &presenter,
            port
        ) == 0
    );
}



static void test_runtime_bootstrap_composes_new_campaign_stack(void) {
    const char* content_path = "RexRuntimeContentTest.dat";
    const char* state_path = "RexRuntimeStateTest.dat";
    RexState seed;
    RexRuntime runtime = {0};
    FakePresentation presentation = {0};
    RexState reloaded;

    remove(content_path);
    cleanup_state_files(state_path);

    CHECK(write_content_fixture(content_path) == 1);

    RexState_Init(&seed);
    CHECK(
        RexState_SetBlueprintBalance(
            &seed,
            9501u,
            9u
        ) == 1
    );
    CHECK(RexState_Save(&seed, state_path) == 1);

    presentation.selected_vehicle_id = 501u;

    CHECK(
        RexRuntime_Init(
            &runtime,
            content_path,
            state_path,
            fake_presentation_port(&presentation)
        ) == 1
    );
    CHECK(runtime.initialized == 1);
    CHECK(RexGaia_IsReady(&runtime.gaia) == 1);
    CHECK(RexGaia_IsNetworkRequired(&runtime.gaia) == 0);
    CHECK(runtime.platform_services.initialized == 1);
    {
        RexPlatformCapabilities caps = {0};
        CHECK(
            RexPlatformServices_GetCapabilities(
                &runtime.platform_services,
                &caps
            ) == 1
        );
        CHECK(caps.profile_ready == 1);
        CHECK(caps.cloud_sync_enabled == 0);
        CHECK(caps.network_required == 0);
        CHECK(caps.login_authenticated == 1);
        CHECK(caps.license_active == 1);
        CHECK(caps.iap_enabled == 0);
        CHECK(caps.ads_enabled == 0);
        CHECK(caps.social_enabled == 0);
        CHECK(caps.matchmaking_enabled == 0);
        CHECK(caps.online_events_enabled == 0);
        CHECK(caps.update_required == 0);
    }
    CHECK(RexGlobalSync_IsNetworkRequired(&runtime.global_sync) == 0);
    CHECK(runtime.global_sync.state == &runtime.state);
    CHECK(runtime.global_sync.next_operation_id == 1u);

    CHECK(RexRuntime_OnGarageEnter(&runtime) == 1);
    CHECK(presentation.present_calls == 1);
    CHECK(presentation.last_view_model.selected_vehicle_id == 501u);
    CHECK(presentation.last_view_model.build_enabled == 1);

    CHECK(
        RexRuntime_OnGarageMontarPressed(&runtime) ==
        REX_GARAGE_PRESENTER_OK
    );
    CHECK(presentation.last_view_model.owned == 1);
    CHECK(runtime.state.revision == 1u);
    CHECK(runtime.global_sync.next_operation_id == 2u);
    CHECK(RexGlobalSync_GetPendingCount(&runtime.global_sync) == 0u);

    RexState_Init(&reloaded);
    CHECK(RexState_Load(&reloaded, state_path) == 1);
    CHECK(RexState_IsOwned(&reloaded, 501u) == 1);
    CHECK(
        RexState_GetBlueprintBalance(
            &reloaded,
            9501u
        ) == 2u
    );

    remove(content_path);
    cleanup_state_files(state_path);
}

static void test_runtime_first_launch_creates_new_state_file(void) {
    const char* content_path = "RexRuntimeFirstContent.dat";
    const char* state_path = "RexRuntimeFirstState.dat";
    RexRuntime runtime = {0};
    FakePresentation presentation = {0};
    RexState loaded;

    remove(content_path);
    cleanup_state_files(state_path);

    CHECK(write_content_fixture(content_path) == 1);
    presentation.selected_vehicle_id = 501u;

    CHECK(
        RexRuntime_Init(
            &runtime,
            content_path,
            state_path,
            fake_presentation_port(&presentation)
        ) == 1
    );
    CHECK(runtime.state.version == REX_STATE_VERSION);
    CHECK(runtime.state.revision == 0u);
    CHECK(
        RexState_GetBlueprintBalance(
            &runtime.state,
            9501u
        ) == 10u
    );
    CHECK(RexState_IsOwned(&runtime.state, 502u) == 1);

    RexState_Init(&loaded);
    CHECK(RexState_Load(&loaded, state_path) == 1);
    CHECK(loaded.version == REX_STATE_VERSION);
    CHECK(loaded.revision == 0u);
    CHECK(
        RexState_GetBlueprintBalance(
            &loaded,
            9501u
        ) == 10u
    );
    CHECK(RexState_IsOwned(&loaded, 502u) == 1);

    remove(content_path);
    cleanup_state_files(state_path);
}

static void test_runtime_rejects_invalid_content_without_starting(void) {
    const char* content_path = "RexRuntimeInvalidContent.dat";
    const char* state_path = "RexRuntimeInvalidState.dat";
    RexRuntime runtime = {0};
    FakePresentation presentation = {0};
    FILE* file = 0;

    remove(content_path);
    cleanup_state_files(state_path);

    CHECK(fopen_s(&file, content_path, "wb") == 0);
    CHECK(file != 0);
    if (file != 0) {
        CHECK(fwrite("bad", 1u, 3u, file) == 3u);
        CHECK(fclose(file) == 0);
    }

    CHECK(
        RexRuntime_Init(
            &runtime,
            content_path,
            state_path,
            fake_presentation_port(&presentation)
        ) == 0
    );
    CHECK(runtime.initialized == 0);

    remove(content_path);
    cleanup_state_files(state_path);
}




typedef struct FakeBoundaryPresentation {
    uint32_t selected_vehicle_id;
    RexGarageSnapshotV1 last_snapshot;
    int snapshot_calls;
    int action_calls;
    int last_action_result;
} FakeBoundaryPresentation;

static uint32_t fake_boundary_read_selected(void* context) {
    FakeBoundaryPresentation* fake = (FakeBoundaryPresentation*)context;
    return fake->selected_vehicle_id;
}

static void fake_boundary_present_snapshot(
    void* context,
    const RexGarageSnapshotV1* snapshot
) {
    FakeBoundaryPresentation* fake = (FakeBoundaryPresentation*)context;
    fake->last_snapshot = *snapshot;
    fake->snapshot_calls += 1;
}

static void fake_boundary_present_action(
    void* context,
    int result
) {
    FakeBoundaryPresentation* fake = (FakeBoundaryPresentation*)context;
    fake->last_action_result = result;
    fake->action_calls += 1;
}

static RexGamePresentationPortV1 fake_boundary_port(
    FakeBoundaryPresentation* fake
) {
    RexGamePresentationPortV1 port = {0};
    port.abi_version = REX_BOUNDARY_ABI_VERSION;
    port.struct_size = (uint32_t)sizeof(port);
    port.context = fake;
    port.read_selected_vehicle_id = fake_boundary_read_selected;
    port.present_garage_snapshot = fake_boundary_present_snapshot;
    port.present_action_result = fake_boundary_present_action;
    return port;
}

static void test_boundary_v1_reports_stable_abi_version(void) {
    CHECK(RexHost_GetBoundaryAbiVersion() == REX_BOUNDARY_ABI_VERSION);
}

static void test_boundary_v1_rejects_wrong_abi_without_starting(void) {
    FakeBoundaryPresentation presentation = {0};
    RexGamePresentationPortV1 port = fake_boundary_port(&presentation);

    port.abi_version = REX_BOUNDARY_ABI_VERSION + 1u;

    CHECK(
        RexHost_StartV1(
            "does-not-matter.dat",
            "does-not-matter-state.dat",
            &port
        ) == 0
    );
    CHECK(RexHost_IsStarted() == 0);
}

static void test_host_exports_drive_new_runtime_end_to_end(void) {
    const char* content_path = "RexHostContentTest.dat";
    const char* state_path = "RexHostStateTest.dat";
    FakeBoundaryPresentation presentation = {0};
    RexGamePresentationPortV1 port;
    RexState loaded;

    remove(content_path);
    cleanup_state_files(state_path);

    CHECK(write_content_fixture(content_path) == 1);

    presentation.selected_vehicle_id = 501u;
    port = fake_boundary_port(&presentation);

    CHECK(RexHost_IsStarted() == 0);
    CHECK(
        RexHost_StartV1(
            content_path,
            state_path,
            &port
        ) == 1
    );
    CHECK(RexHost_IsStarted() == 1);

    {
        uint32_t operation_id = 0u;
        CHECK(RexHost_GaiaIsReady() == 1);
        CHECK(RexHost_GaiaIsNetworkRequired() == 0);
        CHECK(RexHost_GlobalSyncPendingCount() == 0u);
        CHECK(
            RexHost_GlobalSyncCommit(
                REX_GLOBAL_SYNC_REASON_PROFILE_BOOTSTRAP,
                &operation_id
            ) == REX_GLOBAL_SYNC_OK
        );
        CHECK(operation_id == 1u);
        CHECK(RexHost_GlobalSyncPendingCount() == 0u);
    }

    CHECK(RexHost_GarageEnter() == 1);
    CHECK(presentation.snapshot_calls == 1);
    CHECK(presentation.last_snapshot.selected_vehicle_id == 501u);
    CHECK(presentation.last_snapshot.montar_enabled == 1);

    CHECK(
        RexHost_GarageMontarPressed() ==
        REX_GARAGE_PRESENTER_OK
    );
    CHECK(presentation.action_calls == 1);
    CHECK(presentation.last_action_result == REX_GARAGE_PRESENTER_OK);
    CHECK(presentation.last_snapshot.owned == 1);
    CHECK(presentation.last_snapshot.montar_enabled == 0);

    RexState_Init(&loaded);
    CHECK(RexState_Load(&loaded, state_path) == 1);
    CHECK(RexState_IsOwned(&loaded, 501u) == 1);
    CHECK(
        RexState_GetBlueprintBalance(
            &loaded,
            9501u
        ) == 3u
    );

    remove(content_path);
    cleanup_state_files(state_path);
}


int main(void) {
    test_ready_vehicle_enables_build();
    test_owned_vehicle_disables_build();
    test_no_selection_is_not_buildable();
    test_locked_vehicle_is_not_buildable();
    test_vehicle_without_recipe_is_unavailable();
    test_insufficient_blueprints_disables_build();
    test_tutorial_waits_until_build_is_available();
    test_tutorial_advances_only_after_successful_build();
    test_completed_tutorial_stays_complete();
    test_presenter_enter_builds_view_model_and_tutorial();
    test_presenter_car_selection_rebuilds_view_model();
    test_presenter_successful_build_refreshes_owned_state();
    test_presenter_rejects_disabled_build_without_campaign_call();
    test_presenter_failed_campaign_action_returns_tutorial_to_focus();
    test_presenter_reports_read_failure();
    test_content_lookup_is_new_local_catalog();
    test_state_owns_inventory_and_round_trip_persistence();
    test_campaign_transaction_spends_blueprints_and_persists();
    test_campaign_rejects_invalid_transaction_without_mutation();
    test_real_campaign_api_drives_presenter_without_legacy_runtime();
    test_state_load_falls_back_to_backup_after_current_corruption();
    test_real_campaign_presenter_persists_tutorial_completion();
    test_content_v2_binary_file_loads_local_catalog();
    test_content_v2_rejects_invalid_file();
    test_presentation_adapter_enters_and_presents_view_model();
    test_presentation_adapter_selection_change_rebuilds_state();
    test_presentation_adapter_routes_montar_and_renders_result();
    test_presentation_adapter_requires_only_presentation_contract();
    test_runtime_bootstrap_composes_new_campaign_stack();
    test_runtime_first_launch_creates_new_state_file();
    test_runtime_rejects_invalid_content_without_starting();
    test_boundary_v1_reports_stable_abi_version();
    test_boundary_v1_rejects_wrong_abi_without_starting();
    test_host_exports_drive_new_runtime_end_to_end();

    if (failures != 0) {
        printf("%d test assertion(s) failed.\n", failures);
        return 1;
    }

    printf("Rex garage layer tests passed.\n");
    return 0;
}

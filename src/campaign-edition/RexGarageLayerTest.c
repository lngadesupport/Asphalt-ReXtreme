#include "RexCampaign.h"
#include "RexContent.h"
#include "RexState.h"
#include "RexGaragePresenter.h"
#include "RexGarageViewModel.h"
#include "RexTutorialController.h"

#include <stdio.h>

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

static RexCampaignGarageApi fake_api(FakeCampaign* fake) {
    RexCampaignGarageApi api;
    api.context = fake;
    api.read_vehicle = fake_read_vehicle;
    api.acquire_vehicle = fake_acquire_vehicle;
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
    RexGarageViewModelInput input = {0};

    cleanup_state_files(path);
    RexContent_Init(&content, vehicles, 1u);
    RexState_Init(&state);
    CHECK(RexState_SetBlueprintBalance(&state, 9001u, 5u) == 1);
    CHECK(RexCampaign_Init(&campaign, &content, &state, path) == 1);

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

    cleanup_state_files(path);
    RexContent_Init(&content, vehicles, 1u);
    RexState_Init(&state);
    CHECK(RexState_SetBlueprintBalance(&state, 9001u, 2u) == 1);
    CHECK(RexCampaign_Init(&campaign, &content, &state, path) == 1);

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
    RexGaragePresenter presenter = {0};

    cleanup_state_files(path);
    RexContent_Init(&content, vehicles, 1u);
    RexState_Init(&state);
    CHECK(RexState_SetBlueprintBalance(&state, 9303u, 6u) == 1);
    CHECK(RexCampaign_Init(&campaign, &content, &state, path) == 1);

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

    if (failures != 0) {
        printf("%d test assertion(s) failed.\n", failures);
        return 1;
    }

    printf("Rex garage layer tests passed.\n");
    return 0;
}

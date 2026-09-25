#include "RexGarageViewModel.h"
#include "RexTutorialController.h"

#include <stdio.h>

static int failures = 0;

#define CHECK(expr) do {     if (!(expr)) {         printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #expr);         failures += 1;     } } while (0)

static void test_ready_vehicle_enables_build(void) {
    RexGarageViewModelInput input = {0};
    RexGarageViewModel vm = {0};

    input.selected_vehicle_id = 42;
    input.unlocked = 1;
    input.has_recipe = 1;
    input.blueprint_balance = 12;
    input.blueprint_cost = 10;

    RexGarageViewModel_Build(&input, &vm);

    CHECK(vm.selected_vehicle_id == 42);
    CHECK(vm.build_enabled == 1);
    CHECK(vm.build_status == REX_GARAGE_BUILD_READY);
}

static void test_owned_vehicle_disables_build(void) {
    RexGarageViewModelInput input = {0};
    RexGarageViewModel vm = {0};

    input.selected_vehicle_id = 42;
    input.owned = 1;
    input.unlocked = 1;
    input.has_recipe = 1;
    input.blueprint_balance = 50;
    input.blueprint_cost = 10;

    RexGarageViewModel_Build(&input, &vm);

    CHECK(vm.build_enabled == 0);
    CHECK(vm.build_status == REX_GARAGE_BUILD_OWNED);
}

static void test_insufficient_blueprints_disables_build(void) {
    RexGarageViewModelInput input = {0};
    RexGarageViewModel vm = {0};

    input.selected_vehicle_id = 77;
    input.unlocked = 1;
    input.has_recipe = 1;
    input.blueprint_balance = 4;
    input.blueprint_cost = 5;

    RexGarageViewModel_Build(&input, &vm);

    CHECK(vm.build_enabled == 0);
    CHECK(vm.build_status == REX_GARAGE_BUILD_NEEDS_BLUEPRINTS);
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

int main(void) {
    test_ready_vehicle_enables_build();
    test_owned_vehicle_disables_build();
    test_insufficient_blueprints_disables_build();
    test_tutorial_advances_only_after_successful_build();
    test_completed_tutorial_stays_complete();

    if (failures != 0) {
        printf("%d test assertion(s) failed.\n", failures);
        return 1;
    }

    printf("Rex garage layer tests passed.\n");
    return 0;
}

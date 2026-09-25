#include "RexTutorialController.h"

void RexTutorialController_Init(
    RexTutorialController* controller,
    int already_completed
) {
    controller->state = already_completed
        ? REX_TUTORIAL_COMPLETE
        : REX_TUTORIAL_IDLE;
}

void RexTutorialController_OnGarageEntered(
    RexTutorialController* controller,
    int build_available
) {
    if (controller->state == REX_TUTORIAL_COMPLETE) {
        return;
    }

    if (controller->state == REX_TUTORIAL_IDLE && build_available) {
        controller->state = REX_TUTORIAL_FOCUS_BUILD;
    }
}

void RexTutorialController_OnBuildPressed(
    RexTutorialController* controller
) {
    if (controller->state == REX_TUTORIAL_FOCUS_BUILD) {
        controller->state = REX_TUTORIAL_WAIT_BUILD_RESULT;
    }
}

void RexTutorialController_OnBuildResult(
    RexTutorialController* controller,
    int success
) {
    if (controller->state != REX_TUTORIAL_WAIT_BUILD_RESULT) {
        return;
    }

    controller->state = success
        ? REX_TUTORIAL_COMPLETE
        : REX_TUTORIAL_FOCUS_BUILD;
}

RexTutorialState RexTutorialController_GetState(
    const RexTutorialController* controller
) {
    return controller->state;
}

int RexTutorialController_ShouldFocusBuild(
    const RexTutorialController* controller
) {
    return controller->state == REX_TUTORIAL_FOCUS_BUILD;
}

int RexTutorialController_IsComplete(
    const RexTutorialController* controller
) {
    return controller->state == REX_TUTORIAL_COMPLETE;
}

#pragma once

#ifdef __cplusplus
extern "C" {
#endif

typedef enum RexTutorialState {
    REX_TUTORIAL_IDLE = 0,
    REX_TUTORIAL_FOCUS_BUILD = 1,
    REX_TUTORIAL_WAIT_BUILD_RESULT = 2,
    REX_TUTORIAL_COMPLETE = 3
} RexTutorialState;

typedef struct RexTutorialController {
    RexTutorialState state;
} RexTutorialController;

void RexTutorialController_Init(
    RexTutorialController* controller,
    int already_completed
);

void RexTutorialController_OnGarageEntered(
    RexTutorialController* controller,
    int build_available
);

void RexTutorialController_OnBuildPressed(
    RexTutorialController* controller
);

void RexTutorialController_OnBuildResult(
    RexTutorialController* controller,
    int success
);

RexTutorialState RexTutorialController_GetState(
    const RexTutorialController* controller
);

int RexTutorialController_ShouldFocusBuild(
    const RexTutorialController* controller
);

int RexTutorialController_IsComplete(
    const RexTutorialController* controller
);

#ifdef __cplusplus
}
#endif

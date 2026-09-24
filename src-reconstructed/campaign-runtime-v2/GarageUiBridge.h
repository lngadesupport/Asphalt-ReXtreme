#pragma once
#include "CampaignRuntimeV2.h"

namespace rextreme::campaign2 {

// UI bridge contract.
//
// The original garage is treated strictly as a renderer/input surface.
// No original CraftCar request, request state, backend callback, observer,
// inventory writer, ownership writer, event synchronizer or persistence path
// is authoritative after this bridge is enabled.
//
// Binary integration must provide only:
//   1. selected car_id from the garage selection,
//   2. recipe lookup from Campaign Edition data,
//   3. a visual refresh notification after a local transaction.
//
// Ownership/economy decisions always come from GarageController.
struct GarageUiBridge {
    virtual ~GarageUiBridge() = default;
    virtual CarId SelectedCarId(void* gs_garage) = 0;
    virtual bool RecipeFor(CarId car_id, CraftRecipe& out) = 0;
    virtual void Refresh(void* gs_garage) = 0;
    virtual void ShowInsufficientBlueprints(void* gs_garage) = 0;
};

class GarageActionRouter final {
public:
    GarageActionRouter(GarageController& controller, GarageUiBridge& ui)
        : controller_(controller), ui_(ui) {}

    CraftResult OnBuildPressed(void* gs_garage) {
        const CarId car = ui_.SelectedCarId(gs_garage);
        CraftRecipe recipe{};
        if (car == 0 || !ui_.RecipeFor(car, recipe)) {
            return {false, car, 0, 0, controller_.Snapshot().revision, "recipe_not_found"};
        }

        const CraftResult result = controller_.Craft(recipe);
        if (result.success) {
            ui_.Refresh(gs_garage);
        } else if (result.message == "insufficient_blueprints") {
            ui_.ShowInsufficientBlueprints(gs_garage);
        }
        return result;
    }

private:
    GarageController& controller_;
    GarageUiBridge& ui_;
};

} // namespace rextreme::campaign2

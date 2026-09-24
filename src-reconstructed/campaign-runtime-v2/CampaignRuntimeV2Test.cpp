#include "CampaignRuntimeV2.h"
#include <cassert>
#include <filesystem>

using namespace rextreme::campaign2;

int main() {
    const auto path = std::filesystem::temp_directory_path() / L"rextreme_campaign_v2_test.ini";
    std::filesystem::remove(path);

    State s{};
    s.blueprints[77] = 10;
    Persistence p(path.wstring());
    GarageController g(s, p);

    CraftRecipe r{42, 77, 4};
    assert(g.CanCraft(r));

    const auto result = g.Craft(r);
    assert(result.success);
    assert(g.IsOwned(42));
    assert(g.BlueprintBalance(77) == 6);

    State reload{};
    Persistence p2(path.wstring());
    assert(p2.Load(reload));
    assert(reload.owned_cars.count(42) == 1);
    assert(reload.blueprints[77] == 6);

    std::filesystem::remove(path);
    return 0;
}

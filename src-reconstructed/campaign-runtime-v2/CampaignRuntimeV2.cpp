#include "CampaignRuntimeV2.h"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <sstream>

namespace rextreme::campaign2 {

namespace {
constexpr const char* kMagic = "REXTREME_CAMPAIGN_V2";

bool ParseInt(const std::string& s, std::int32_t& out) {
    try {
        size_t used = 0;
        long long v = std::stoll(s, &used, 10);
        if (used != s.size()) return false;
        if (v < INT32_MIN || v > INT32_MAX) return false;
        out = static_cast<std::int32_t>(v);
        return true;
    } catch (...) {
        return false;
    }
}
}

Persistence::Persistence(std::wstring path) : path_(std::move(path)) {}

bool Persistence::Load(State& out) const {
    std::ifstream f(std::filesystem::path(path_), std::ios::binary);
    if (!f) return false;

    std::string line;
    if (!std::getline(f, line) || line != kMagic) return false;

    State temp{};
    while (std::getline(f, line)) {
        if (line.rfind("version=", 0) == 0) {
            temp.version = static_cast<std::uint32_t>(std::stoul(line.substr(8)));
        } else if (line.rfind("revision=", 0) == 0) {
            temp.revision = std::stoull(line.substr(9));
        } else if (line.rfind("owned=", 0) == 0) {
            std::int32_t id = 0;
            if (ParseInt(line.substr(6), id) && id != 0) temp.owned_cars.insert(id);
        } else if (line.rfind("bp=", 0) == 0) {
            const auto payload = line.substr(3);
            const auto sep = payload.find(':');
            if (sep == std::string::npos) continue;
            std::int32_t id = 0, amount = 0;
            if (ParseInt(payload.substr(0, sep), id) &&
                ParseInt(payload.substr(sep + 1), amount) &&
                id != 0 && amount >= 0) {
                temp.blueprints[id] = amount;
            }
        }
    }

    out = std::move(temp);
    return true;
}

bool Persistence::Save(const State& state) const {
    const std::filesystem::path target(path_);
    std::error_code ec;
    std::filesystem::create_directories(target.parent_path(), ec);

    const auto tmp = target.wstring() + L".tmp";
    {
        std::ofstream f(std::filesystem::path(tmp), std::ios::binary | std::ios::trunc);
        if (!f) return false;
        f << kMagic << "\n";
        f << "version=" << state.version << "\n";
        f << "revision=" << state.revision << "\n";

        std::vector<CarId> cars(state.owned_cars.begin(), state.owned_cars.end());
        std::sort(cars.begin(), cars.end());
        for (CarId id : cars) f << "owned=" << id << "\n";

        std::vector<std::pair<BlueprintId,std::int32_t>> bp(state.blueprints.begin(), state.blueprints.end());
        std::sort(bp.begin(), bp.end(), [](const auto& a, const auto& b){ return a.first < b.first; });
        for (const auto& [id, amount] : bp) f << "bp=" << id << ":" << amount << "\n";
    }

    std::filesystem::rename(std::filesystem::path(tmp), target, ec);
    if (!ec) return true;

    std::filesystem::remove(target, ec);
    ec.clear();
    std::filesystem::rename(std::filesystem::path(tmp), target, ec);
    return !ec;
}

bool Profile::IsOwned(CarId car) const {
    return car != 0 && state_.owned_cars.find(car) != state_.owned_cars.end();
}

bool Profile::AddOwned(CarId car) {
    if (car == 0) return false;
    return state_.owned_cars.insert(car).second;
}

std::int32_t Inventory::Balance(BlueprintId id) const {
    const auto it = state_.blueprints.find(id);
    return it == state_.blueprints.end() ? 0 : it->second;
}

bool Inventory::CanSpend(BlueprintId id, std::int32_t amount) const {
    return id != 0 && amount >= 0 && Balance(id) >= amount;
}

bool Inventory::Spend(BlueprintId id, std::int32_t amount) {
    if (!CanSpend(id, amount)) return false;
    state_.blueprints[id] -= amount;
    return true;
}

void Inventory::Grant(BlueprintId id, std::int32_t amount) {
    if (id == 0 || amount <= 0) return;
    state_.blueprints[id] += amount;
}

void EventBus::Publish(Event e) {
    history_.push_back(e);
}

CraftService::CraftService(State& state, Persistence& persistence, EventBus& bus)
    : state_(state), persistence_(persistence), bus_(bus) {}

CraftResult CraftService::Craft(const CraftRecipe& recipe) {
    CraftResult r{};
    r.car_id = recipe.car_id;

    Profile profile(state_);
    Inventory inventory(state_);

    bus_.Publish({EventBus::Type::CraftRequested, recipe.car_id, state_.revision});

    if (recipe.car_id == 0 || recipe.blueprint_id == 0 || recipe.blueprint_cost < 0) {
        r.message = "invalid_recipe";
        bus_.Publish({EventBus::Type::CraftRejected, recipe.car_id, state_.revision});
        return r;
    }

    if (profile.IsOwned(recipe.car_id)) {
        r.success = true;
        r.revision = state_.revision;
        r.message = "already_owned";
        bus_.Publish({EventBus::Type::GarageRefreshRequested, recipe.car_id, state_.revision});
        return r;
    }

    r.blueprints_before = inventory.Balance(recipe.blueprint_id);
    if (!inventory.CanSpend(recipe.blueprint_id, recipe.blueprint_cost)) {
        r.message = "insufficient_blueprints";
        bus_.Publish({EventBus::Type::CraftRejected, recipe.car_id, state_.revision});
        return r;
    }

    State backup = state_;
    if (!inventory.Spend(recipe.blueprint_id, recipe.blueprint_cost) ||
        !profile.AddOwned(recipe.car_id)) {
        state_ = std::move(backup);
        r.message = "transaction_failed";
        bus_.Publish({EventBus::Type::CraftRejected, recipe.car_id, state_.revision});
        return r;
    }

    ++state_.revision;

    if (!persistence_.Save(state_)) {
        state_ = std::move(backup);
        r.message = "persist_failed";
        bus_.Publish({EventBus::Type::CraftRejected, recipe.car_id, state_.revision});
        return r;
    }

    r.success = true;
    r.blueprints_after = inventory.Balance(recipe.blueprint_id);
    r.revision = state_.revision;
    r.message = "crafted";

    bus_.Publish({EventBus::Type::CraftSucceeded, recipe.car_id, state_.revision});
    bus_.Publish({EventBus::Type::StateSaved, recipe.car_id, state_.revision});
    bus_.Publish({EventBus::Type::GarageRefreshRequested, recipe.car_id, state_.revision});
    return r;
}

GarageController::GarageController(State& state, Persistence& persistence)
    : state_(state),
      persistence_(persistence),
      profile_(state_),
      inventory_(state_),
      craft_(state_, persistence_, bus_) {}

bool GarageController::Load() { return persistence_.Load(state_); }
bool GarageController::Save() { return persistence_.Save(state_); }
bool GarageController::IsOwned(CarId car) const { return profile_.IsOwned(car); }
std::int32_t GarageController::BlueprintBalance(BlueprintId id) const { return inventory_.Balance(id); }

bool GarageController::CanCraft(const CraftRecipe& recipe) const {
    if (recipe.car_id == 0 || recipe.blueprint_id == 0 || recipe.blueprint_cost < 0) return false;
    if (profile_.IsOwned(recipe.car_id)) return true;
    return inventory_.CanSpend(recipe.blueprint_id, recipe.blueprint_cost);
}

CraftResult GarageController::Craft(const CraftRecipe& recipe) {
    return craft_.Craft(recipe);
}

} // namespace rextreme::campaign2

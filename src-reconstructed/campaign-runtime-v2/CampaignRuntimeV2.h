#pragma once
#include <cstdint>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace rextreme::campaign2 {

using CarId = std::int32_t;
using BlueprintId = std::int32_t;

struct CraftRecipe {
    CarId car_id = 0;
    BlueprintId blueprint_id = 0;
    std::int32_t blueprint_cost = 0;
};

struct CraftResult {
    bool success = false;
    CarId car_id = 0;
    std::int32_t blueprints_before = 0;
    std::int32_t blueprints_after = 0;
    std::uint64_t revision = 0;
    std::string message;
};

struct State {
    std::uint32_t version = 1;
    std::uint64_t revision = 0;
    std::unordered_set<CarId> owned_cars;
    std::unordered_map<BlueprintId, std::int32_t> blueprints;
};

class Persistence final {
public:
    explicit Persistence(std::wstring path);
    bool Load(State& out) const;
    bool Save(const State& state) const;
    const std::wstring& Path() const { return path_; }
private:
    std::wstring path_;
};

class Profile final {
public:
    explicit Profile(State& state) : state_(state) {}
    bool IsOwned(CarId car) const;
    bool AddOwned(CarId car);
private:
    State& state_;
};

class Inventory final {
public:
    explicit Inventory(State& state) : state_(state) {}
    std::int32_t Balance(BlueprintId id) const;
    bool CanSpend(BlueprintId id, std::int32_t amount) const;
    bool Spend(BlueprintId id, std::int32_t amount);
    void Grant(BlueprintId id, std::int32_t amount);
private:
    State& state_;
};

class EventBus final {
public:
    enum class Type : std::uint8_t {
        CraftRequested,
        CraftSucceeded,
        CraftRejected,
        StateSaved,
        GarageRefreshRequested
    };
    struct Event {
        Type type{};
        CarId car_id = 0;
        std::uint64_t revision = 0;
    };
    void Publish(Event e);
    const std::vector<Event>& History() const { return history_; }
private:
    std::vector<Event> history_;
};

class CraftService final {
public:
    CraftService(State& state, Persistence& persistence, EventBus& bus);
    CraftResult Craft(const CraftRecipe& recipe);
private:
    State& state_;
    Persistence& persistence_;
    EventBus& bus_;
};

class GarageController final {
public:
    GarageController(State& state, Persistence& persistence);

    bool Load();
    bool Save();

    bool IsOwned(CarId car) const;
    std::int32_t BlueprintBalance(BlueprintId id) const;
    bool CanCraft(const CraftRecipe& recipe) const;
    CraftResult Craft(const CraftRecipe& recipe);

    void SetSelectedCar(CarId car) { selected_car_ = car; }
    CarId SelectedCar() const { return selected_car_; }

    const State& Snapshot() const { return state_; }
    const EventBus& Events() const { return bus_; }

private:
    State& state_;
    Persistence& persistence_;
    Profile profile_;
    Inventory inventory_;
    EventBus bus_;
    CraftService craft_;
    CarId selected_car_ = 0;
};

} // namespace rextreme::campaign2

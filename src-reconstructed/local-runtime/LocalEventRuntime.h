#pragma once
#include <windows.h>
#include <cstdint>

namespace rextreme::local {

enum class EventType : std::uint32_t {
    RuntimeStarted = 1,
    CraftRequested = 2,
    CraftCommitted = 3,
    RuntimeError = 4
};

struct LocalEvent {
    EventType type = EventType::RuntimeStarted;
    std::int32_t car_id = 0;
    void* garage = nullptr;
    std::uint32_t sequence = 0;
};

struct RuntimeSnapshot {
    std::uint32_t revision = 0;
    std::uint32_t craft_count = 0;
    std::int32_t last_car_id = 0;
    bool last_car_owned = false;
    wchar_t status[256]{};
};

bool Start(HINSTANCE module);
void Stop();
bool IsCarOwned(std::int32_t car_id);
RuntimeSnapshot Snapshot();

} // namespace rextreme::local

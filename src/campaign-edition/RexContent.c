#include "RexContent.h"

void RexContent_Init(
    RexContent* content,
    const RexContentVehicle* vehicles,
    uint32_t vehicle_count
) {
    content->vehicles = vehicles;
    content->vehicle_count = vehicle_count;
}

const RexContentVehicle* RexContent_FindVehicle(
    const RexContent* content,
    uint32_t vehicle_id
) {
    uint32_t i;

    if (content == 0 || content->vehicles == 0 || vehicle_id == 0u) {
        return 0;
    }

    for (i = 0u; i < content->vehicle_count; ++i) {
        if (content->vehicles[i].vehicle_id == vehicle_id) {
            return &content->vehicles[i];
        }
    }

    return 0;
}

#include "RexContent.h"

#include <stdio.h>
#include <string.h>

static const unsigned char REX_CONTENT_MAGIC[8] = {
    'R', 'E', 'X', 'C', 'T', 'V', '2', 0
};

static int RexContent_ReadBytes(
    FILE* file,
    void* data,
    size_t size
) {
    return fread(data, 1u, size, file) == size;
}

static int RexContent_ReadU32(
    FILE* file,
    uint32_t* value
) {
    unsigned char data[4];

    if (!RexContent_ReadBytes(file, data, sizeof(data))) {
        return 0;
    }

    *value =
        ((uint32_t)data[0]) |
        ((uint32_t)data[1] << 8) |
        ((uint32_t)data[2] << 16) |
        ((uint32_t)data[3] << 24);

    return 1;
}

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

int RexContent_Load(
    RexContent* content,
    const char* path
) {
    FILE* file = 0;
    unsigned char magic[8];
    uint32_t version;
    uint32_t vehicle_count;
    uint32_t i;
    RexContent loaded;

    if (content == 0 || path == 0) {
        return 0;
    }

    if (fopen_s(&file, path, "rb") != 0 || file == 0) {
        return 0;
    }

    memset(&loaded, 0, sizeof(loaded));

    if (!RexContent_ReadBytes(file, magic, sizeof(magic)) ||
        memcmp(magic, REX_CONTENT_MAGIC, sizeof(magic)) != 0 ||
        !RexContent_ReadU32(file, &version) ||
        version != REX_CONTENT_VERSION ||
        !RexContent_ReadU32(file, &vehicle_count) ||
        vehicle_count > REX_CONTENT_MAX_VEHICLES) {
        fclose(file);
        return 0;
    }

    for (i = 0u; i < vehicle_count; ++i) {
        uint32_t unlocked;
        uint32_t has_recipe;

        if (!RexContent_ReadU32(
                file,
                &loaded.loaded_vehicles[i].vehicle_id) ||
            !RexContent_ReadU32(file, &unlocked) ||
            !RexContent_ReadU32(file, &has_recipe) ||
            !RexContent_ReadU32(
                file,
                &loaded.loaded_vehicles[i].blueprint_id) ||
            !RexContent_ReadU32(
                file,
                &loaded.loaded_vehicles[i].blueprint_cost)) {
            fclose(file);
            return 0;
        }

        loaded.loaded_vehicles[i].unlocked_by_default =
            unlocked != 0u;
        loaded.loaded_vehicles[i].has_recipe =
            has_recipe != 0u;
    }

    if (fclose(file) != 0) {
        return 0;
    }

    loaded.vehicle_count = vehicle_count;
    *content = loaded;
    content->vehicles = content->loaded_vehicles;

    return 1;
}

#include "RexState.h"

#include <stdio.h>
#include <string.h>

static const unsigned char REX_STATE_MAGIC[8] = {
    'R', 'E', 'X', 'S', 'T', 'V', '1', 0
};

static int RexState_WriteBytes(
    FILE* file,
    const void* data,
    size_t size
) {
    return fwrite(data, 1u, size, file) == size;
}

static int RexState_ReadBytes(
    FILE* file,
    void* data,
    size_t size
) {
    return fread(data, 1u, size, file) == size;
}

static int RexState_WriteU32(FILE* file, uint32_t value) {
    unsigned char data[4];

    data[0] = (unsigned char)(value & 0xFFu);
    data[1] = (unsigned char)((value >> 8) & 0xFFu);
    data[2] = (unsigned char)((value >> 16) & 0xFFu);
    data[3] = (unsigned char)((value >> 24) & 0xFFu);

    return RexState_WriteBytes(file, data, sizeof(data));
}

static int RexState_ReadU32(FILE* file, uint32_t* value) {
    unsigned char data[4];

    if (!RexState_ReadBytes(file, data, sizeof(data))) {
        return 0;
    }

    *value =
        ((uint32_t)data[0]) |
        ((uint32_t)data[1] << 8) |
        ((uint32_t)data[2] << 16) |
        ((uint32_t)data[3] << 24);

    return 1;
}

static int RexState_WriteU64(FILE* file, uint64_t value) {
    unsigned char data[8];
    unsigned int i;

    for (i = 0u; i < 8u; ++i) {
        data[i] = (unsigned char)((value >> (i * 8u)) & 0xFFu);
    }

    return RexState_WriteBytes(file, data, sizeof(data));
}

static int RexState_ReadU64(FILE* file, uint64_t* value) {
    unsigned char data[8];
    unsigned int i;
    uint64_t result = 0u;

    if (!RexState_ReadBytes(file, data, sizeof(data))) {
        return 0;
    }

    for (i = 0u; i < 8u; ++i) {
        result |= ((uint64_t)data[i]) << (i * 8u);
    }

    *value = result;
    return 1;
}

void RexState_Init(RexState* state) {
    memset(state, 0, sizeof(*state));
    state->version = REX_STATE_VERSION;
}

int RexState_IsOwned(
    const RexState* state,
    uint32_t vehicle_id
) {
    uint32_t i;

    if (state == 0 || vehicle_id == 0u) {
        return 0;
    }

    for (i = 0u; i < state->owned_count; ++i) {
        if (state->owned_vehicles[i] == vehicle_id) {
            return 1;
        }
    }

    return 0;
}

int RexState_AddOwned(
    RexState* state,
    uint32_t vehicle_id
) {
    if (state == 0 || vehicle_id == 0u) {
        return 0;
    }

    if (RexState_IsOwned(state, vehicle_id)) {
        return 1;
    }

    if (state->owned_count >= REX_STATE_MAX_OWNED_VEHICLES) {
        return 0;
    }

    state->owned_vehicles[state->owned_count] = vehicle_id;
    state->owned_count += 1u;
    return 1;
}

uint32_t RexState_GetBlueprintBalance(
    const RexState* state,
    uint32_t blueprint_id
) {
    uint32_t i;

    if (state == 0 || blueprint_id == 0u) {
        return 0u;
    }

    for (i = 0u; i < state->blueprint_count; ++i) {
        if (state->blueprints[i].blueprint_id == blueprint_id) {
            return state->blueprints[i].amount;
        }
    }

    return 0u;
}

int RexState_SetBlueprintBalance(
    RexState* state,
    uint32_t blueprint_id,
    uint32_t amount
) {
    uint32_t i;

    if (state == 0 || blueprint_id == 0u) {
        return 0;
    }

    for (i = 0u; i < state->blueprint_count; ++i) {
        if (state->blueprints[i].blueprint_id == blueprint_id) {
            state->blueprints[i].amount = amount;
            return 1;
        }
    }

    if (state->blueprint_count >= REX_STATE_MAX_BLUEPRINTS) {
        return 0;
    }

    state->blueprints[state->blueprint_count].blueprint_id = blueprint_id;
    state->blueprints[state->blueprint_count].amount = amount;
    state->blueprint_count += 1u;
    return 1;
}

int RexState_SpendBlueprints(
    RexState* state,
    uint32_t blueprint_id,
    uint32_t amount
) {
    uint32_t balance;

    if (state == 0 || blueprint_id == 0u) {
        return 0;
    }

    balance = RexState_GetBlueprintBalance(state, blueprint_id);
    if (balance < amount) {
        return 0;
    }

    return RexState_SetBlueprintBalance(
        state,
        blueprint_id,
        balance - amount
    );
}

void RexState_SetGarageTutorialComplete(
    RexState* state,
    int complete
) {
    if (state != 0) {
        state->garage_tutorial_complete = complete != 0;
    }
}

static int RexState_WriteFile(
    const RexState* state,
    const char* path
) {
    FILE* file = 0;
    uint32_t i;
    int ok = 1;

    if (fopen_s(&file, path, "wb") != 0 || file == 0) {
        return 0;
    }

    ok = ok && RexState_WriteBytes(
        file,
        REX_STATE_MAGIC,
        sizeof(REX_STATE_MAGIC)
    );
    ok = ok && RexState_WriteU32(file, REX_STATE_VERSION);
    ok = ok && RexState_WriteU64(file, state->revision);
    ok = ok && RexState_WriteU32(
        file,
        state->garage_tutorial_complete ? 1u : 0u
    );
    ok = ok && RexState_WriteU32(file, state->owned_count);
    ok = ok && RexState_WriteU32(file, state->blueprint_count);

    for (i = 0u; ok && i < state->owned_count; ++i) {
        ok = RexState_WriteU32(file, state->owned_vehicles[i]);
    }

    for (i = 0u; ok && i < state->blueprint_count; ++i) {
        ok = RexState_WriteU32(
            file,
            state->blueprints[i].blueprint_id
        );
        if (ok) {
            ok = RexState_WriteU32(
                file,
                state->blueprints[i].amount
            );
        }
    }

    if (fclose(file) != 0) {
        ok = 0;
    }

    if (!ok) {
        remove(path);
    }

    return ok;
}

int RexState_Save(
    const RexState* state,
    const char* path
) {
    char tmp_path[512];
    char bak_path[512];
    FILE* current = 0;
    int had_current = 0;

    if (state == 0 || path == 0 ||
        state->owned_count > REX_STATE_MAX_OWNED_VEHICLES ||
        state->blueprint_count > REX_STATE_MAX_BLUEPRINTS) {
        return 0;
    }

    if (sprintf_s(tmp_path, sizeof(tmp_path), "%s.tmp", path) < 0 ||
        sprintf_s(bak_path, sizeof(bak_path), "%s.bak", path) < 0) {
        return 0;
    }

    remove(tmp_path);

    if (!RexState_WriteFile(state, tmp_path)) {
        return 0;
    }

    if (fopen_s(&current, path, "rb") == 0 && current != 0) {
        had_current = 1;
        fclose(current);
    }

    if (had_current) {
        remove(bak_path);
        if (rename(path, bak_path) != 0) {
            remove(tmp_path);
            return 0;
        }
    }

    if (rename(tmp_path, path) != 0) {
        if (had_current) {
            rename(bak_path, path);
        }
        remove(tmp_path);
        return 0;
    }

    return 1;
}

static int RexState_ReadFile(
    RexState* state,
    const char* path
) {
    FILE* file = 0;
    unsigned char magic[8];
    uint32_t version;
    uint32_t tutorial;
    uint32_t owned_count;
    uint32_t blueprint_count;
    uint32_t i;
    RexState loaded;

    if (fopen_s(&file, path, "rb") != 0 || file == 0) {
        return 0;
    }

    RexState_Init(&loaded);

    if (!RexState_ReadBytes(file, magic, sizeof(magic)) ||
        memcmp(magic, REX_STATE_MAGIC, sizeof(magic)) != 0 ||
        !RexState_ReadU32(file, &version) ||
        version != REX_STATE_VERSION ||
        !RexState_ReadU64(file, &loaded.revision) ||
        !RexState_ReadU32(file, &tutorial) ||
        !RexState_ReadU32(file, &owned_count) ||
        !RexState_ReadU32(file, &blueprint_count) ||
        owned_count > REX_STATE_MAX_OWNED_VEHICLES ||
        blueprint_count > REX_STATE_MAX_BLUEPRINTS) {
        fclose(file);
        return 0;
    }

    loaded.version = version;
    loaded.garage_tutorial_complete = tutorial != 0u;
    loaded.owned_count = owned_count;
    loaded.blueprint_count = blueprint_count;

    for (i = 0u; i < owned_count; ++i) {
        if (!RexState_ReadU32(file, &loaded.owned_vehicles[i])) {
            fclose(file);
            return 0;
        }
    }

    for (i = 0u; i < blueprint_count; ++i) {
        if (!RexState_ReadU32(
                file,
                &loaded.blueprints[i].blueprint_id) ||
            !RexState_ReadU32(
                file,
                &loaded.blueprints[i].amount)) {
            fclose(file);
            return 0;
        }
    }

    if (fclose(file) != 0) {
        return 0;
    }

    *state = loaded;
    return 1;
}

int RexState_Load(
    RexState* state,
    const char* path
) {
    char bak_path[512];

    if (state == 0 || path == 0) {
        return 0;
    }

    if (RexState_ReadFile(state, path)) {
        return 1;
    }

    if (sprintf_s(bak_path, sizeof(bak_path), "%s.bak", path) < 0) {
        return 0;
    }

    return RexState_ReadFile(state, bak_path);
}

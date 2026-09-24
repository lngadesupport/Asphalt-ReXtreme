#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_PRESENTATION_SETTINGS_VERSION 1u
#define CAMPAIGN_REPLAY_FORMAT_VERSION 1u
#define CAMPAIGN_REPLAY_MARKER_MAX 4096u

/*
  Presentation settings are deliberately conservative.
  Zero means "use the original Asphalt Xtreme value/behavior".
  Renderer/camera adapters may apply an override only after the corresponding
  capability is verified for the supported original build.
*/
typedef struct CampaignPresentationSettings {
    uint32_t size;
    uint32_t version;
    uint32_t revision;
    uint32_t flags;

    int32_t fov_x100;              /* 0 = original */
    int32_t camera_distance_x1000; /* 0 = original */
    int32_t camera_height_x1000;   /* 0 = original */
    int32_t camera_smoothing_x1000;/* 0 = original */

    uint32_t checksum;
} CampaignPresentationSettings;

enum CampaignPresentationFlags {
    CAMPAIGN_PRESENTATION_REPLAY_ENABLED = 1u << 0,
    CAMPAIGN_PRESENTATION_PHOTO_ENABLED  = 1u << 1
};

typedef struct CampaignReplaySample {
    uint32_t time_ms;
    int32_t entity_id;
    float position_x;
    float position_y;
    float position_z;
    float rotation_x;
    float rotation_y;
    float rotation_z;
    float rotation_w;
    float velocity_x;
    float velocity_y;
    float velocity_z;
    uint32_t state_flags;
} CampaignReplaySample;

typedef struct CampaignReplayMarker {
    uint32_t time_ms;
    uint32_t type;
    int32_t entity_id;
    int32_t value;
} CampaignReplayMarker;

enum CampaignReplayMarkerType {
    CAMPAIGN_REPLAY_MARKER_START = 1,
    CAMPAIGN_REPLAY_MARKER_TAKEDOWN = 2,
    CAMPAIGN_REPLAY_MARKER_JUMP = 3,
    CAMPAIGN_REPLAY_MARKER_WRECK = 4,
    CAMPAIGN_REPLAY_MARKER_OVERTAKE = 5,
    CAMPAIGN_REPLAY_MARKER_FINISH = 6,
    CAMPAIGN_REPLAY_MARKER_CUSTOM = 100
};

typedef struct CampaignReplayInfo {
    uint32_t size;
    uint32_t active;
    uint32_t sample_count;
    uint32_t capacity;
    uint32_t dropped_samples;
    uint32_t marker_count;
    uint32_t dropped_markers;
    uint32_t first_time_ms;
    uint32_t last_time_ms;
} CampaignReplayInfo;

enum CampaignPhotoCameraMode {
    CAMPAIGN_PHOTO_CAMERA_ORIGINAL = 0,
    CAMPAIGN_PHOTO_CAMERA_FREE = 1,
    CAMPAIGN_PHOTO_CAMERA_ORBIT = 2
};

typedef struct CampaignPhotoState {
    uint32_t size;
    uint32_t active;
    uint32_t camera_mode;
    uint32_t hide_hud;

    int32_t target_entity_id;
    int32_t fov_x100;       /* 0 = original/current */
    int32_t distance_x1000;
    int32_t height_x1000;
    int32_t roll_x100;
} CampaignPhotoState;

enum CampaignPresentationOp {
    CAMPAIGN_PRESENTATION_OP_NONE = 0,

    CAMPAIGN_PRESENTATION_OP_LOAD_SETTINGS = 1,
    CAMPAIGN_PRESENTATION_OP_SAVE_SETTINGS = 2,
    CAMPAIGN_PRESENTATION_OP_GET_SETTINGS = 3,
    CAMPAIGN_PRESENTATION_OP_SET_SETTINGS = 4,
    CAMPAIGN_PRESENTATION_OP_RESET_SETTINGS = 5,

    CAMPAIGN_PRESENTATION_OP_REPLAY_START = 20,
    CAMPAIGN_PRESENTATION_OP_REPLAY_STOP = 21,
    CAMPAIGN_PRESENTATION_OP_REPLAY_CLEAR = 22,
    CAMPAIGN_PRESENTATION_OP_REPLAY_RECORD = 23,
    CAMPAIGN_PRESENTATION_OP_REPLAY_INFO = 24,
    CAMPAIGN_PRESENTATION_OP_REPLAY_GET_SAMPLE = 25,
    CAMPAIGN_PRESENTATION_OP_REPLAY_SAVE = 26,
    CAMPAIGN_PRESENTATION_OP_REPLAY_LOAD = 27,
    CAMPAIGN_PRESENTATION_OP_REPLAY_ADD_MARKER = 28,
    CAMPAIGN_PRESENTATION_OP_REPLAY_GET_MARKER = 29,

    CAMPAIGN_PRESENTATION_OP_PHOTO_ENTER = 40,
    CAMPAIGN_PRESENTATION_OP_PHOTO_EXIT = 41,
    CAMPAIGN_PRESENTATION_OP_PHOTO_GET = 42,
    CAMPAIGN_PRESENTATION_OP_PHOTO_SET = 43
};

typedef struct CampaignPresentationCommand {
    uint32_t size;
    uint32_t op;

    int32_t a;
    int32_t b;
    int32_t c;
    int32_t d;

    uint32_t ptr0;
    uint32_t ptr1;

    int32_t status;
    int32_t out0;
    int32_t out1;
    int32_t out2;
} CampaignPresentationCommand;

int __cdecl CampaignPresentationInvoke(CampaignPresentationCommand* command);

int __cdecl CampaignPresentationLoadSettings(void);
int __cdecl CampaignPresentationSaveSettings(void);
int __cdecl CampaignPresentationGetSettings(CampaignPresentationSettings* out);
int __cdecl CampaignPresentationSetSettings(const CampaignPresentationSettings* settings);
int __cdecl CampaignPresentationResetSettings(void);

int __cdecl CampaignReplayStart(uint32_t capacity);
int __cdecl CampaignReplayStop(void);
int __cdecl CampaignReplayClear(void);
int __cdecl CampaignReplayRecord(const CampaignReplaySample* sample);
int __cdecl CampaignReplayGetInfo(CampaignReplayInfo* out);
int __cdecl CampaignReplayGetSample(uint32_t chronological_index, CampaignReplaySample* out);
int __cdecl CampaignReplaySave(const wchar_t* path);
int __cdecl CampaignReplayLoad(const wchar_t* path);
int __cdecl CampaignReplayAddMarker(const CampaignReplayMarker* marker);
int __cdecl CampaignReplayGetMarker(uint32_t index, CampaignReplayMarker* out);

int __cdecl CampaignPhotoEnter(const CampaignPhotoState* initial);
int __cdecl CampaignPhotoExit(void);
int __cdecl CampaignPhotoGet(CampaignPhotoState* out);
int __cdecl CampaignPhotoSet(const CampaignPhotoState* state);

#ifdef __cplusplus
}
#endif

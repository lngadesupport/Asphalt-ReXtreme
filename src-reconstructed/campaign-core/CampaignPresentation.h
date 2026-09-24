#pragma once
#include <stdint.h>
#include "CampaignPresentationCatalog.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CAMPAIGN_PRESENTATION_SETTINGS_VERSION 1u
#define CAMPAIGN_REPLAY_FORMAT_VERSION 3u
#define CAMPAIGN_REPLAY_MARKER_MAX 4096u
#define CAMPAIGN_REPLAY_LIBRARY_MAX 256u
#define CAMPAIGN_REPLAY_FILENAME_MAX 260u

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

typedef struct CampaignReplayMetadata {
    uint32_t size;
    uint32_t version;
    int32_t event_id;
    int32_t track_id;
    int32_t player_car_id;
    int32_t race_mode;
    uint32_t session_id;
    uint32_t flags;
} CampaignReplayMetadata;

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

typedef struct CampaignReplayPlaybackState {
    uint32_t size;
    uint32_t loaded;
    uint32_t playing;
    uint32_t current_time_ms;
    uint32_t first_time_ms;
    uint32_t last_time_ms;
    uint32_t speed_permille; /* 1000 = 1.0x */
    uint32_t selected_marker;
} CampaignReplayPlaybackState;

typedef struct CampaignReplayLibraryEntry {
    uint32_t size;
    wchar_t filename[CAMPAIGN_REPLAY_FILENAME_MAX];
    CampaignReplayMetadata metadata;
    uint32_t sample_count;
    uint32_t marker_count;
    uint32_t first_time_ms;
    uint32_t last_time_ms;
    uint32_t duration_ms;
    uint32_t file_size_low;
    uint32_t file_size_high;
    uint32_t modified_time_low;
    uint32_t modified_time_high;
} CampaignReplayLibraryEntry;

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

    float position_x;
    float position_y;
    float position_z;
    int32_t pitch_x100;
    int32_t yaw_x100;
    int32_t roll_x100;
    int32_t move_speed_x1000;
} CampaignPhotoState;

enum CampaignPresentationOp {
    CAMPAIGN_PRESENTATION_OP_NONE = 0,

    CAMPAIGN_PRESENTATION_OP_LOAD_SETTINGS = 1,
    CAMPAIGN_PRESENTATION_OP_SAVE_SETTINGS = 2,
    CAMPAIGN_PRESENTATION_OP_GET_SETTINGS = 3,
    CAMPAIGN_PRESENTATION_OP_SET_SETTINGS = 4,
    CAMPAIGN_PRESENTATION_OP_RESET_SETTINGS = 5,

    CAMPAIGN_PRESENTATION_OP_CAPABILITY_RELOAD = 10,
    CAMPAIGN_PRESENTATION_OP_CAPABILITY_COUNT = 11,
    CAMPAIGN_PRESENTATION_OP_CAPABILITY_GET = 12,
    CAMPAIGN_PRESENTATION_OP_CAPABILITY_GET_VALUE = 13,
    CAMPAIGN_PRESENTATION_OP_CAPABILITY_SET_VALUE = 14,
    CAMPAIGN_PRESENTATION_OP_CAPABILITY_RESET_VALUE = 15,

    CAMPAIGN_PRESENTATION_OP_REPLAY_GET_AUTO_PATH = 16,
    CAMPAIGN_PRESENTATION_OP_REPLAY_SAVE_AUTO = 17,
    CAMPAIGN_PRESENTATION_OP_REPLAY_SET_METADATA = 18,
    CAMPAIGN_PRESENTATION_OP_REPLAY_GET_METADATA = 19,
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
    CAMPAIGN_PRESENTATION_OP_REPLAY_PLAY = 30,
    CAMPAIGN_PRESENTATION_OP_REPLAY_PAUSE = 31,
    CAMPAIGN_PRESENTATION_OP_REPLAY_SEEK = 32,
    CAMPAIGN_PRESENTATION_OP_REPLAY_SET_SPEED = 33,
    CAMPAIGN_PRESENTATION_OP_REPLAY_PLAYBACK_STATE = 34,
    CAMPAIGN_PRESENTATION_OP_REPLAY_SAMPLE_AT_TIME = 35,
    CAMPAIGN_PRESENTATION_OP_REPLAY_NEXT_MARKER = 36,
    CAMPAIGN_PRESENTATION_OP_REPLAY_PREVIOUS_MARKER = 37,
    CAMPAIGN_PRESENTATION_OP_REPLAY_ADVANCE = 38,
    CAMPAIGN_PRESENTATION_OP_REPLAY_STEP = 39,

    CAMPAIGN_PRESENTATION_OP_PHOTO_ENTER = 40,
    CAMPAIGN_PRESENTATION_OP_PHOTO_EXIT = 41,
    CAMPAIGN_PRESENTATION_OP_PHOTO_GET = 42,
    CAMPAIGN_PRESENTATION_OP_PHOTO_SET = 43,
    CAMPAIGN_PRESENTATION_OP_PHOTO_MOVE = 44,
    CAMPAIGN_PRESENTATION_OP_PHOTO_ROTATE = 45,
    CAMPAIGN_PRESENTATION_OP_PHOTO_SET_FOV = 46,
    CAMPAIGN_PRESENTATION_OP_PHOTO_SET_SPEED = 47,
    CAMPAIGN_PRESENTATION_OP_PHOTO_RESET_VIEW = 48,

    CAMPAIGN_PRESENTATION_OP_REPLAY_LIBRARY_REFRESH = 50,
    CAMPAIGN_PRESENTATION_OP_REPLAY_LIBRARY_COUNT = 51,
    CAMPAIGN_PRESENTATION_OP_REPLAY_LIBRARY_GET = 52,
    CAMPAIGN_PRESENTATION_OP_REPLAY_LIBRARY_LOAD = 53,
    CAMPAIGN_PRESENTATION_OP_REPLAY_LIBRARY_DELETE = 54,

    CAMPAIGN_PRESENTATION_OP_DIAGNOSTICS = 60
};

typedef struct CampaignPresentationDiagnostics {
    uint32_t size;
    uint32_t settings_revision;
    uint32_t verified_capability_count;
    uint32_t verified_binding_count;
    uint32_t replay_recording;
    uint32_t replay_sample_count;
    uint32_t replay_marker_count;
    uint32_t replay_loaded;
    uint32_t replay_playing;
    uint32_t replay_time_ms;
    uint32_t photo_active;
    uint32_t photo_camera_mode;
    uint32_t photo_binding_count;
    uint32_t photo_free_camera_ready;
    uint32_t replay_binding_count;
    uint32_t replay_recording_ready;
} CampaignPresentationDiagnostics;

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

int __cdecl CampaignReplayGetAutoPath(wchar_t* out, uint32_t capacity_chars);
int __cdecl CampaignReplaySaveAuto(void);
int __cdecl CampaignReplaySetMetadata(const CampaignReplayMetadata* metadata);
int __cdecl CampaignReplayGetMetadata(CampaignReplayMetadata* out);
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
int __cdecl CampaignReplayPlay(void);
int __cdecl CampaignReplayPause(void);
int __cdecl CampaignReplaySeek(uint32_t time_ms);
int __cdecl CampaignReplaySetSpeed(uint32_t speed_permille);
int __cdecl CampaignReplayGetPlaybackState(CampaignReplayPlaybackState* out);
int __cdecl CampaignReplayGetSampleAtTime(uint32_t time_ms, int32_t entity_id, CampaignReplaySample* out);
int __cdecl CampaignReplayNextMarker(uint32_t from_time_ms, CampaignReplayMarker* out);
int __cdecl CampaignReplayPreviousMarker(uint32_t from_time_ms, CampaignReplayMarker* out);
int __cdecl CampaignReplayAdvance(uint32_t real_delta_ms);
int __cdecl CampaignReplayStep(int32_t direction, int32_t entity_id);

int __cdecl CampaignReplayLibraryRefresh(void);
uint32_t __cdecl CampaignReplayLibraryCount(void);
int __cdecl CampaignReplayLibraryGet(uint32_t index, CampaignReplayLibraryEntry* out);
int __cdecl CampaignReplayLibraryLoad(uint32_t index);
int __cdecl CampaignReplayLibraryDelete(uint32_t index);

int __cdecl CampaignPhotoEnter(const CampaignPhotoState* initial);
int __cdecl CampaignPhotoExit(void);
int __cdecl CampaignPhotoGet(CampaignPhotoState* out);
int __cdecl CampaignPhotoSet(const CampaignPhotoState* state);
int __cdecl CampaignPhotoMove(int32_t dx_x1000, int32_t dy_x1000, int32_t dz_x1000);
int __cdecl CampaignPhotoRotate(int32_t pitch_delta_x100, int32_t yaw_delta_x100, int32_t roll_delta_x100);
int __cdecl CampaignPhotoSetFov(int32_t fov_x100);
int __cdecl CampaignPhotoSetMoveSpeed(int32_t speed_x1000);
int __cdecl CampaignPhotoResetView(void);
int __cdecl CampaignPresentationGetDiagnostics(CampaignPresentationDiagnostics* out);

#ifdef __cplusplus
}
#endif

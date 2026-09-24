.386
.model flat

EXTERN _CampaignCraftInvoke:PROC
EXTERN _CampaignIsOwned:PROC
EXTERN _CampaignExecuteCommand:PROC
EXTERN _CampaignApplyUpgradeBatch:PROC
EXTERN _CampaignApplyLegacyUpgradeSelection:PROC
EXTERN _CampaignPurchaseLegacyStore:PROC
EXTERN _CampaignBeginCareerFromPreRequest:PROC
EXTERN _CampaignFinishCareerFromPostRequest:PROC
EXTERN _CampaignBeginRaceFromGui:PROC
EXTERN _CampaignFinishRaceFromGui:PROC
EXTERN _CampaignBeginRaceAdapter:PROC
EXTERN _CampaignUiSubmit:PROC
EXTERN _CampaignOnlineResolve:PROC
EXTERN _CampaignEventPoll:PROC
EXTERN _CampaignFrontendSubmit:PROC
EXTERN _CampaignFrontendBoot:PROC
EXTERN _CampaignFrontendLobbyReady:PROC
EXTERN _CampaignFrontendGarageBuild:PROC
EXTERN _CampaignFrontendIsOwned:PROC

CAMPAIGN_CRAFT_MAGIC   EQU 0C0DEC0DEh
CAMPAIGN_OWNED_MAGIC   EQU 0C0DE0A11h
CAMPAIGN_COMMAND_MAGIC     EQU 0C0DECA11h
CAMPAIGN_RACE_BEGIN_MAGIC  EQU 0C0DEB001h
CAMPAIGN_RACE_FINISH_MAGIC EQU 0C0DEF001h
CAMPAIGN_CAREER_BEGIN_MAGIC EQU 0C0DEB072h
CAMPAIGN_UPGRADE_BATCH_MAGIC EQU 0C0DE4401h
CAMPAIGN_UPGRADE_LEGACY_MAGIC EQU 0C0DE4402h
CAMPAIGN_STORE_LEGACY_MAGIC EQU 0C0DE5501h
CAMPAIGN_UI_MAGIC           EQU 0C0DE7701h
CAMPAIGN_POLICY_MAGIC       EQU 0C0DE7702h
CAMPAIGN_EVENT_POLL_MAGIC   EQU 0C0DE7703h
CAMPAIGN_FRONTEND_MAGIC     EQU 0C0DE7704h
CAMPAIGN_FRONTEND_BOOT_MAGIC  EQU 0C0DE7710h
CAMPAIGN_FRONTEND_LOBBY_MAGIC EQU 0C0DE7711h
CAMPAIGN_FRONTEND_OWNERSHIP_MAGIC EQU 0C0DE7712h
CAMPAIGN_FRONTEND_GARAGE_BUILD_MAGIC EQU 0C0DE7713h

.code

noop_ret PROC
    ret
noop_ret ENDP

noop_ret4 PROC
    ret 4
noop_ret4 ENDP

ret_false PROC
    xor eax, eax
    ret
ret_false ENDP

ret_null PROC
    xor eax, eax
    ret
ret_null ENDP

; Existing imported IGP call used only as a stable no-startup command gateway.
;
; selector is the original single stack argument.
; ECX is repurposed by our patched call sites:
;   CRAFT   -> GS_Garage*
;   OWNED   -> car_id
;   COMMAND -> CampaignCommand*
;   UPGRADE BATCH -> CampaignUpgradeBatchArgs*
;   RACE BEGIN/FINISH -> GameModeGUIBase*
campaign_gateway PROC
    mov eax, DWORD PTR [esp+4]

    cmp eax, CAMPAIGN_CRAFT_MAGIC
    je campaign_craft

    cmp eax, CAMPAIGN_OWNED_MAGIC
    je campaign_owned

    cmp eax, CAMPAIGN_COMMAND_MAGIC
    je campaign_command

    cmp eax, CAMPAIGN_RACE_BEGIN_MAGIC
    je campaign_race_begin

    cmp eax, CAMPAIGN_RACE_FINISH_MAGIC
    je campaign_race_finish

    cmp eax, CAMPAIGN_CAREER_BEGIN_MAGIC
    je campaign_career_begin

    cmp eax, CAMPAIGN_UPGRADE_BATCH_MAGIC
    je campaign_upgrade_batch

    cmp eax, CAMPAIGN_UPGRADE_LEGACY_MAGIC
    je campaign_upgrade_legacy

    cmp eax, CAMPAIGN_STORE_LEGACY_MAGIC
    je campaign_store_legacy

    cmp eax, CAMPAIGN_UI_MAGIC
    je campaign_ui

    cmp eax, CAMPAIGN_POLICY_MAGIC
    je campaign_policy

    cmp eax, CAMPAIGN_EVENT_POLL_MAGIC
    je campaign_event_poll

    cmp eax, CAMPAIGN_FRONTEND_MAGIC
    je campaign_frontend

    cmp eax, CAMPAIGN_FRONTEND_BOOT_MAGIC
    je campaign_frontend_boot

    cmp eax, CAMPAIGN_FRONTEND_LOBBY_MAGIC
    je campaign_frontend_lobby

    cmp eax, CAMPAIGN_FRONTEND_OWNERSHIP_MAGIC
    je campaign_frontend_ownership

    cmp eax, CAMPAIGN_FRONTEND_GARAGE_BUILD_MAGIC
    je campaign_frontend_garage_build

    xor eax, eax
    ret 4

campaign_craft:
    push ecx
    call _CampaignCraftInvoke
    add esp, 4
    ret 4

campaign_owned:
    push ecx
    call _CampaignIsOwned
    add esp, 4
    ret 4

campaign_command:
    push ecx
    call _CampaignExecuteCommand
    add esp, 4
    ret 4

campaign_race_begin:
    push ecx
    call _CampaignBeginRaceFromGui
    add esp, 4
    ret 4

campaign_race_finish:
    push ecx
    call _CampaignFinishRaceFromGui
    add esp, 4
    ret 4

campaign_career_begin:
    push ecx
    call _CampaignBeginRaceAdapter
    add esp, 4
    ret 4

campaign_upgrade_batch:
    push ecx
    call _CampaignApplyUpgradeBatch
    add esp, 4
    ret 4

campaign_upgrade_legacy:
    push ecx
    call _CampaignApplyLegacyUpgradeSelection
    add esp, 4
    ret 4

campaign_store_legacy:
    push ecx
    call _CampaignPurchaseLegacyStore
    add esp, 4
    ret 4

campaign_ui:
    push ecx
    call _CampaignUiSubmit
    add esp, 4
    ret 4

campaign_policy:
    push ecx
    call _CampaignOnlineResolve
    add esp, 4
    ret 4

campaign_event_poll:
    push ecx
    call _CampaignEventPoll
    add esp, 4
    ret 4

campaign_frontend:
    push ecx
    call _CampaignFrontendSubmit
    add esp, 4
    ret 4

campaign_frontend_boot:
    call _CampaignFrontendBoot
    ret 4

campaign_frontend_lobby:
    call _CampaignFrontendLobbyReady
    ret 4

campaign_frontend_ownership:
    ; Explicit Campaign car-ownership query.
    ; ECX carries car_id. No generic STL/container hook participates.
    push ecx
    call _CampaignFrontendIsOwned
    add esp, 4
    ret 4

campaign_frontend_garage_build:
    push ecx
    call _CampaignFrontendGarageBuild
    add esp, 4
    ret 4
campaign_gateway ENDP

PUBLIC _CampaignInvokeGarageUi
_CampaignInvokeGarageUi PROC
    mov ecx, DWORD PTR [esp+4]
    test ecx, ecx
    jz ui_done

    mov eax, DWORD PTR [ecx]
    test eax, eax
    jz ui_done

    ; UI-only adapter.  Original garage business logic is not used.
    call DWORD PTR [eax]
ui_done:
    ret
_CampaignInvokeGarageUi ENDP

END

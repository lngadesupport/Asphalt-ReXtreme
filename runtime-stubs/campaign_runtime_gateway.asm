.386
.model flat

EXTERN _CampaignFrontendDispatch:PROC
EXTERN _CampaignFrontendRead:PROC
EXTERN _CampaignFrontendBoot:PROC
EXTERN _CampaignFrontendEnterLobby:PROC
EXTERN _CampaignFrontendBuildSelected:PROC
EXTERN _CampaignFrontendSelectCar:PROC

CAMPAIGN_RT_DISPATCH_MAGIC EQU 0C0DE9001h
CAMPAIGN_RT_READ_MAGIC EQU 0C0DE9002h
CAMPAIGN_RT_BUILD_SELECTED_MAGIC EQU 0C0DE9003h
CAMPAIGN_RT_SELECT_CAR_MAGIC EQU 0C0DE9004h
CAMPAIGN_RT_BOOT_MAGIC EQU 0C0DE9005h
CAMPAIGN_RT_LOBBY_MAGIC EQU 0C0DE9006h

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

campaign_runtime_gateway PROC
    mov eax, DWORD PTR [esp+4]

    cmp eax, CAMPAIGN_RT_DISPATCH_MAGIC
    je rt_dispatch

    cmp eax, CAMPAIGN_RT_READ_MAGIC
    je rt_read

    cmp eax, CAMPAIGN_RT_BUILD_SELECTED_MAGIC
    je rt_build_selected

    cmp eax, CAMPAIGN_RT_SELECT_CAR_MAGIC
    je rt_select_car

    cmp eax, CAMPAIGN_RT_BOOT_MAGIC
    je rt_boot

    cmp eax, CAMPAIGN_RT_LOBBY_MAGIC
    je rt_lobby

    xor eax, eax
    ret 4

rt_dispatch:
    push ecx
    call _CampaignFrontendDispatch
    add esp, 4
    ret 4

rt_read:
    push ecx
    call _CampaignFrontendRead
    add esp, 4
    ret 4

rt_build_selected:
    call _CampaignFrontendBuildSelected
    ret 4

rt_select_car:
    push ecx
    call _CampaignFrontendSelectCar
    add esp, 4
    ret 4

rt_boot:
    call _CampaignFrontendBoot
    ret 4

rt_lobby:
    call _CampaignFrontendEnterLobby
    ret 4

campaign_runtime_gateway ENDP

END

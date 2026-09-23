.386
.model flat

EXTERN _CampaignCraftInvoke:PROC
EXTERN _CampaignIsOwned:PROC
EXTERN _CampaignExecuteCommand:PROC
EXTERN _CampaignBeginRaceFromGui:PROC
EXTERN _CampaignFinishRaceFromGui:PROC
EXTERN _CampaignBeginRaceAdapter:PROC

CAMPAIGN_CRAFT_MAGIC   EQU 0C0DEC0DEh
CAMPAIGN_OWNED_MAGIC   EQU 0C0DE0A11h
CAMPAIGN_COMMAND_MAGIC     EQU 0C0DECA11h
CAMPAIGN_RACE_BEGIN_MAGIC  EQU 0C0DEB001h
CAMPAIGN_RACE_FINISH_MAGIC EQU 0C0DEF001h
CAMPAIGN_CAREER_BEGIN_MAGIC EQU 0C0DEB072h

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

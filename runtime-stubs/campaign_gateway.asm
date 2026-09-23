.386
.model flat

EXTERN _CampaignCraftInvoke:PROC
EXTERN _CampaignIsOwned:PROC
EXTERN _CampaignExecuteCommand:PROC

CAMPAIGN_CRAFT_MAGIC   EQU 0C0DEC0DEh
CAMPAIGN_OWNED_MAGIC   EQU 0C0DE0A11h
CAMPAIGN_COMMAND_MAGIC EQU 0C0DECA11h

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
campaign_gateway PROC
    mov eax, DWORD PTR [esp+4]

    cmp eax, CAMPAIGN_CRAFT_MAGIC
    je campaign_craft

    cmp eax, CAMPAIGN_OWNED_MAGIC
    je campaign_owned

    cmp eax, CAMPAIGN_COMMAND_MAGIC
    je campaign_command

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

.386
.model flat

EXTERN _RexCampaignBoot:PROC
EXTERN _RexCampaignEnterHome:PROC
EXTERN _RexCampaignSelectCar:PROC
EXTERN _RexCampaignBuildCar:PROC
EXTERN _RexCampaignDispatch:PROC
EXTERN _RexCampaignReadView:PROC

REX_SEL_BOOT        EQU 0DEC0A001h
REX_SEL_HOME        EQU 0DEC0A002h
REX_SEL_BUILD       EQU 0DEC0A003h
REX_SEL_SELECT_CAR  EQU 0DEC0A004h
REX_SEL_DISPATCH    EQU 0DEC0A005h
REX_SEL_READ_VIEW   EQU 0DEC0A006h

.code

rex_noop PROC
    ret
rex_noop ENDP

rex_noop4 PROC
    ret 4
rex_noop4 ENDP

rex_false PROC
    xor eax,eax
    ret
rex_false ENDP

rex_null PROC
    xor eax,eax
    ret
rex_null ENDP

rex_gateway PROC
    mov eax,DWORD PTR [esp+4]

    cmp eax,REX_SEL_BOOT
    je do_boot
    cmp eax,REX_SEL_HOME
    je do_home
    cmp eax,REX_SEL_BUILD
    je do_build
    cmp eax,REX_SEL_SELECT_CAR
    je do_select
    cmp eax,REX_SEL_DISPATCH
    je do_dispatch
    cmp eax,REX_SEL_READ_VIEW
    je do_read

    xor eax,eax
    ret 4

do_boot:
    call _RexCampaignBoot
    ret 4

do_home:
    call _RexCampaignEnterHome
    ret 4

do_build:
    call _RexCampaignBuildCar
    ret 4

do_select:
    push ecx
    call _RexCampaignSelectCar
    add esp,4
    ret 4

do_dispatch:
    push ecx
    call _RexCampaignDispatch
    add esp,4
    ret 4

do_read:
    push ecx
    call _RexCampaignReadView
    add esp,4
    ret 4

rex_gateway ENDP

END

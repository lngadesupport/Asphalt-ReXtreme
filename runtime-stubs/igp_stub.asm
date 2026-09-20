.386
.model flat
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

END

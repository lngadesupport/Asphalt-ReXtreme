__declspec(naked) void noop_ret(void) { __asm ret }
__declspec(naked) void noop_ret4(void) { __asm ret 4 }
__declspec(naked) void ret_false(void) { __asm xor eax, eax __asm ret }
__declspec(naked) void ret_null(void) { __asm xor eax, eax __asm ret }

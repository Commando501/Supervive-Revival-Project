  0x55CD510  4885d2                 test rdx, rdx
  0x55CD513  0f847a020000           je 0x7ff6b45cd793
  0x55CD519  48895c2410             mov qword ptr [rsp + 0x10], rbx
  0x55CD51E  48897c2418             mov qword ptr [rsp + 0x18], rdi
  0x55CD523  4c89742420             mov qword ptr [rsp + 0x20], r14
  0x55CD528  55                     push rbp
  0x55CD529  488d6c24a0             lea rbp, [rsp - 0x60]
  0x55CD52E  4881ec60010000         sub rsp, 0x160
  0x55CD535  8b420c                 mov eax, dword ptr [rdx + 0xc]
  0x55CD538  498bd8                 mov rbx, r8
  0x55CD53B  c1e81e                 shr eax, 0x1e
  0x55CD53E  488bfa                 mov rdi, rdx
  0x55CD541  f6d0                   not al
  0x55CD543  4c8bf1                 mov r14, rcx
  0x55CD546  a801                   test al, 1
  0x55CD548  0f842d020000           je 0x7ff6b45cd77b
  0x55CD54E  e84df50000             call 0x7ff6b45dcaa0
  0x55CD553  84c0                   test al, al
  0x55CD555  0f8520020000           jne 0x7ff6b45cd77b
  0x55CD55B  498b86c0000000         mov rax, qword ptr [r14 + 0xc0]
  0x55CD562  4885c0                 test rax, rax
  0x55CD565  7508                   jne 0x7ff6b45cd56f
  0x55CD567  498bce                 mov rcx, r14
  0x55CD56A  e8d126fefd             call 0x7ff6b25afc40
  0x55CD56F  488bc8                 mov rcx, rax
  0x55CD572  e8d9159bfb             call 0x7ff6aff7eb50
  0x55CD577  4885c0                 test rax, rax
  0x55CD57A  0f8432020000           je 0x7ff6b45cd7b2
  0x55CD580  488bc8                 mov rcx, rax
  0x55CD583  e848a8ffff             call 0x7ff6b45c7dd0
  0x55CD588  84c0                   test al, al
  0x55CD58A  0f8422020000           je 0x7ff6b45cd7b2
  0x55CD590  f20f104310             movsd xmm0, qword ptr [rbx + 0x10]
  0x55CD595  488bcf                 mov rcx, rdi
  0x55CD598  f20f580528ff5403       addsd xmm0, qword ptr [rip + 0x354ff28]
  0x55CD5A0  f20f104b10             movsd xmm1, qword ptr [rbx + 0x10]
  0x55CD5A5  4889b42470010000       mov qword ptr [rsp + 0x170], rsi
  0x55CD5AD  0f29b42450010000       movaps xmmword ptr [rsp + 0x150], xmm6
  0x55CD5B5  0f1033                 movups xmm6, xmmword ptr [rbx]
  0x55CD5B8  f20f1145d8             movsd qword ptr [rbp - 0x28], xmm0
  0x55CD5BD  0f117520               movups xmmword ptr [rbp + 0x20], xmm6
  0x55CD5C1  f20f114d30             movsd qword ptr [rbp + 0x30], xmm1
  0x55CD5C6  e8050b0f00             call 0x7ff6b46be0d0
  0x55CD5CB  488bf0                 mov rsi, rax
  0x55CD5CE  4885c0                 test rax, rax
  0x55CD5D1  0f84bd010000           je 0x7ff6b45cd794
  0x55CD5D7  488bc8                 mov rcx, rax
  0x55CD5DA  e8e1b7f2ff             call 0x7ff6b44f8dc0
  0x55CD5DF  84c0                   test al, al
  0x55CD5E1  0f84ad010000           je 0x7ff6b45cd794
  0x55CD5E7  488b8eb0010000         mov rcx, qword ptr [rsi + 0x1b0]
  0x55CD5EE  4885c9                 test rcx, rcx
  0x55CD5F1  0f848d000000           je 0x7ff6b45cd684
  0x55CD5F7  0f108100020000         movups xmm0, xmmword ptr [rcx + 0x200]
  0x55CD5FE  0f108910020000         movups xmm1, xmmword ptr [rcx + 0x210]
  0x55CD605  4881c1e8010000         add rcx, 0x1e8
  0x55CD60C  0f294590               movaps xmmword ptr [rbp - 0x70], xmm0
  0x55CD610  0f294da0               movaps xmmword ptr [rbp - 0x60], xmm1
  0x55CD614  e887c8aefc             call 0x7ff6b10b9ea0
  0x55CD619  0f284d90               movaps xmm1, xmmword ptr [rbp - 0x70]
  0x55CD61D  488bd8                 mov rbx, rax
  0x55CD620  0f104010               movups xmm0, xmmword ptr [rax + 0x10]
  0x55CD624  660fc245a004           cmpneqpd xmm0, xmmword ptr [rbp - 0x60]
  0x55CD62A  660f50d0               movmskpd edx, xmm0
  0x55CD62E  0f28c1                 movaps xmm0, xmm1
  0x55CD631  660fc20004             cmpneqpd xmm0, xmmword ptr [rax]
  0x55CD636  660f50c8               movmskpd ecx, xmm0
  0x55CD63A  c1e202                 shl edx, 2
  0x55CD63D  0bd1                   or edx, ecx
  0x55CD63F  7429                   je 0x7ff6b45cd66a
  0x55CD641  0f1108                 movups xmmword ptr [rax], xmm1
  0x55CD644  488d5538               lea rdx, [rbp + 0x38]
  0x55CD648  0f2845a0               movaps xmm0, xmmword ptr [rbp - 0x60]
  0x55CD64C  488d4d90               lea rcx, [rbp - 0x70]
  0x55CD650  0f114010               movups xmmword ptr [rax + 0x10], xmm0
  0x55CD654  e8677aadfb             call 0x7ff6b00a50c0
  0x55CD659  0f1000                 movups xmm0, xmmword ptr [rax]
  0x55CD65C  0f114320               movups xmmword ptr [rbx + 0x20], xmm0
  0x55CD660  f20f104810             movsd xmm1, qword ptr [rax + 0x10]
  0x55CD665  f20f114b30             movsd qword ptr [rbx + 0x30], xmm1
  0x55CD66A  0f104320               movups xmm0, xmmword ptr [rbx + 0x20]
  0x55CD66E  488d442470             lea rax, [rsp + 0x70]
  0x55CD673  f20f104b30             movsd xmm1, qword ptr [rbx + 0x30]
  0x55CD678  0f11442470             movups xmmword ptr [rsp + 0x70], xmm0
  0x55CD67D  f20f114d80             movsd qword ptr [rbp - 0x80], xmm1
  0x55CD682  eb1c                   jmp 0x7ff6b45cd6a0
  0x55CD684  0f10052db13f04         movups xmm0, xmmword ptr [rip + 0x43fb12d]
  0x55CD68B  488d45b0               lea rax, [rbp - 0x50]
  0x55CD68F  0f1145b0               movups xmmword ptr [rbp - 0x50], xmm0
  0x55CD693  f20f10052db13f04       movsd xmm0, qword ptr [rip + 0x43fb12d]
  0x55CD69B  f20f1145c0             movsd qword ptr [rbp - 0x40], xmm0
  0x55CD6A0  0f1000                 movups xmm0, xmmword ptr [rax]
  0x55CD6A3  4c8d45e0               lea r8, [rbp - 0x20]
  0x55CD6A7  c644246000             mov byte ptr [rsp + 0x60], 0
  0x55CD6AC  f20f104810             movsd xmm1, qword ptr [rax + 0x10]
  0x55CD6B1  488d5500               lea rdx, [rbp]
  0x55CD6B5  c644245801             mov byte ptr [rsp + 0x58], 1
  0x55CD6BA  33c0                   xor eax, eax
  0x55CD6BC  4889442450             mov qword ptr [rsp + 0x50], rax
  0x55CD6C1  0f57db                 xorps xmm3, xmm3
  0x55CD6C4  4889442448             mov qword ptr [rsp + 0x48], rax
  0x55CD6C9  488bce                 mov rcx, rsi
  0x55CD6CC  88442440               mov byte ptr [rsp + 0x40], al
  0x55CD6D0  88442438               mov byte ptr [rsp + 0x38], al
  0x55CD6D4  0f2945e0               movaps xmmword ptr [rbp - 0x20], xmm0
  0x55CD6D8  f20f1045d8             movsd xmm0, qword ptr [rbp - 0x28]
  0x55CD6DD  88442430               mov byte ptr [rsp + 0x30], al
  0x55CD6E1  f20f114510             movsd qword ptr [rbp + 0x10], xmm0
  0x55CD6E6  f30f1005f2390d02       movss xmm0, dword ptr [rip + 0x20d39f2]
  0x55CD6EE  f30f11442428           movss dword ptr [rsp + 0x28], xmm0
  0x55CD6F4  f30f115c2420           movss dword ptr [rsp + 0x20], xmm3
  0x55CD6FA  f20f114df0             movsd qword ptr [rbp - 0x10], xmm1
  0x55CD6FF  0f297500               movaps xmmword ptr [rbp], xmm6
  0x55CD703  e8e8a90900             call 0x7ff6b46680f0
  0x55CD708  b201                   mov dl, 1
  0x55CD70A  488bce                 mov rcx, rsi
  0x55CD70D  e83ecedcfd             call 0x7ff6b239a550
  0x55CD712  488d5520               lea rdx, [rbp + 0x20]
  0x55CD716  488bce                 mov rcx, rsi
  0x55CD719  e80244ffff             call 0x7ff6b45c1b20
  0x55CD71E  33d2                   xor edx, edx
  0x55CD720  488bce                 mov rcx, rsi
  0x55CD723  e828cedcfd             call 0x7ff6b239a550
  0x55CD728  488bce                 mov rcx, rsi
  0x55CD72B  e810c620fe             call 0x7ff6b27d9d40
  0x55CD730  f30f1186101c0000       movss dword ptr [rsi + 0x1c10], xmm0
  0x55CD738  49639e38010000         movsxd rbx, dword ptr [r14 + 0x138]
  0x55CD73F  8d4301                 lea eax, [rbx + 1]
  0x55CD742  41898638010000         mov dword ptr [r14 + 0x138], eax
  0x55CD749  413b863c010000         cmp eax, dword ptr [r14 + 0x13c]
  0x55CD750  760e                   jbe 0x7ff6b45cd760
  0x55CD752  8bd3                   mov edx, ebx
  0x55CD754  498d8e30010000         lea rcx, [r14 + 0x130]
  0x55CD75B  e870b19cfb             call 0x7ff6aff988d0
  0x55CD760  498b8630010000         mov rax, qword ptr [r14 + 0x130]
  0x55CD767  48893cd8               mov qword ptr [rax + rbx*8], rdi
  0x55CD76B  488bb42470010000       mov rsi, qword ptr [rsp + 0x170]
  0x55CD773  0f28b42450010000       movaps xmm6, xmmword ptr [rsp + 0x150]
  0x55CD77B  4c8d9c2460010000       lea r11, [rsp + 0x160]
  0x55CD783  498b5b18               mov rbx, qword ptr [r11 + 0x18]
  0x55CD787  498b7b20               mov rdi, qword ptr [r11 + 0x20]
  0x55CD78B  4d8b7328               mov r14, qword ptr [r11 + 0x28]
  0x55CD78F  498be3                 mov rsp, r11
  0x55CD792  5d                     pop rbp
  0x55CD793  c3                     ret 
  0x55CD794  803d2593a60402         cmp byte ptr [rip + 0x4a69325], 2
  0x55CD79B  72ce                   jb 0x7ff6b45cd76b
  0x55CD79D  488d154cf85403         lea rdx, [rip + 0x354f84c]
  0x55CD7A4  488d0d1593a604         lea rcx, [rip + 0x4a69315]
  0x55CD7AB  e8a0dea9fb             call 0x7ff6b006b650
  0x55CD7B0  ebb9                   jmp 0x7ff6b45cd76b
  0x55CD7B2  803dc786a60402         cmp byte ptr [rip + 0x4a686c7], 2
  0x55CD7B9  7213                   jb 0x7ff6b45cd7ce
  0x55CD7BB  488d1546f75403         lea rdx, [rip + 0x354f746]
  0x55CD7C2  488d0db786a604         lea rcx, [rip + 0x4a686b7]
  0x55CD7C9  e882dea9fb             call 0x7ff6b006b650
  0x55CD7CE  488d155bf75403         lea rdx, [rip + 0x354f75b]
  0x55CD7D5  488d4c2470             lea rcx, [rsp + 0x70]
  0x55CD7DA  e841f19dfb             call 0x7ff6affac920
  0x55CD7DF  488d4c2470             lea rcx, [rsp + 0x70]
  0x55CD7E4  e837149bfb             call 0x7ff6aff7ec20
  0x55CD7E9  488b4c2470             mov rcx, qword ptr [rsp + 0x70]
  0x55CD7EE  4885c9                 test rcx, rcx
  0x55CD7F1  7488                   je 0x7ff6b45cd77b
  0x55CD7F3  e818bba2fb             call 0x7ff6afff9310
  0x55CD7F8  eb81                   jmp 0x7ff6b45cd77b

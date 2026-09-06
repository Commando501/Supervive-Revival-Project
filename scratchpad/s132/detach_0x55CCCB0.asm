  0x55CCCB0  4885d2                 test rdx, rdx
  0x55CCCB3  0f84ae010000           je 0x7ff6b45cce67
  0x55CCCB9  4889542410             mov qword ptr [rsp + 0x10], rdx
  0x55CCCBE  55                     push rbp
  0x55CCCBF  4157                   push r15
  0x55CCCC1  4883ec68               sub rsp, 0x68
  0x55CCCC5  8b420c                 mov eax, dword ptr [rdx + 0xc]
  0x55CCCC8  4d8bf8                 mov r15, r8
  0x55CCCCB  c1e81e                 shr eax, 0x1e
  0x55CCCCE  488be9                 mov rbp, rcx
  0x55CCCD1  f6d0                   not al
  0x55CCCD3  a801                   test al, 1
  0x55CCCD5  0f8485010000           je 0x7ff6b45cce60
  0x55CCCDB  4889742460             mov qword ptr [rsp + 0x60], rsi
  0x55CCCE0  4d85c0                 test r8, r8
  0x55CCCE3  7507                   jne 0x7ff6b45cccec
  0x55CCCE5  4c8bb9b8000000         mov r15, qword ptr [rcx + 0xb8]
  0x55CCCEC  488b8930010000         mov rcx, qword ptr [rcx + 0x130]
  0x55CCCF3  48638538010000         movsxd rax, dword ptr [rbp + 0x138]
  0x55CCCFA  488d14c1               lea rdx, [rcx + rax*8]
  0x55CCCFE  483bca                 cmp rcx, rdx
  0x55CCD01  0f8454010000           je 0x7ff6b45cce5b
  0x55CCD07  48899c2480000000       mov qword ptr [rsp + 0x80], rbx
  0x55CCD0F  488b9c2488000000       mov rbx, qword ptr [rsp + 0x88]
  0x55CCD17  483919                 cmp qword ptr [rcx], rbx
  0x55CCD1A  740e                   je 0x7ff6b45ccd2a
  0x55CCD1C  4883c108               add rcx, 8
  0x55CCD20  483bca                 cmp rcx, rdx
  0x55CCD23  75f2                   jne 0x7ff6b45ccd17
  0x55CCD25  e929010000             jmp 0x7ff6b45cce53
  0x55CCD2A  488bcb                 mov rcx, rbx
  0x55CCD2D  48897c2458             mov qword ptr [rsp + 0x58], rdi
  0x55CCD32  e899130f00             call 0x7ff6b46be0d0
  0x55CCD37  488bf8                 mov rdi, rax
  0x55CCD3A  4885c0                 test rax, rax
  0x55CCD3D  0f84e0000000           je 0x7ff6b45cce23
  0x55CCD43  488bc8                 mov rcx, rax
  0x55CCD46  e875c0f2ff             call 0x7ff6b44f8dc0
  0x55CCD4B  84c0                   test al, al
  0x55CCD4D  0f84d0000000           je 0x7ff6b45cce23
  0x55CCD53  488bcf                 mov rcx, rdi
  0x55CCD56  4c89742450             mov qword ptr [rsp + 0x50], r14
  0x55CCD5B  e8c01e9bfb             call 0x7ff6aff7ec20
  0x55CCD60  41b801000000           mov r8d, 1
  0x55CCD66  488d1583e85403         lea rdx, [rip + 0x354e883]
  0x55CCD6D  488d8c2498000000       lea rcx, [rsp + 0x98]
  0x55CCD75  e856c0b6fb             call 0x7ff6b0138dd0
  0x55CCD7A  488d8ff0010000         lea rcx, [rdi + 0x1f0]
  0x55CCD81  488d942498000000       lea rdx, [rsp + 0x98]
  0x55CCD89  e8822bb3fb             call 0x7ff6b00ff910
  0x55CCD8E  b201                   mov dl, 1
  0x55CCD90  488bcf                 mov rcx, rdi
  0x55CCD93  e8b8d7dcfd             call 0x7ff6b239a550
  0x55CCD98  33d2                   xor edx, edx
  0x55CCD9A  488bcf                 mov rcx, rdi
  0x55CCD9D  e89ec2fcff             call 0x7ff6b4599040
  0x55CCDA2  488bcf                 mov rcx, rdi
  0x55CCDA5  e88697fbff             call 0x7ff6b4586530
  0x55CCDAA  488bcf                 mov rcx, rdi
  0x55CCDAD  e82efbfdff             call 0x7ff6b45ac8e0
  0x55CCDB2  4c8bf0                 mov r14, rax
  0x55CCDB5  4885c0                 test rax, rax
  0x55CCDB8  741a                   je 0x7ff6b45ccdd4
  0x55CCDBA  4c8b00                 mov r8, qword ptr [rax]
  0x55CCDBD  b201                   mov dl, 1
  0x55CCDBF  488bc8                 mov rcx, rax
  0x55CCDC2  41ff90e0030000         call qword ptr [r8 + 0x3e0]
  0x55CCDC9  41c786a00100000000803f mov dword ptr [r14 + 0x1a0], 0x3f800000
  0x55CCDD4  4d8bcf                 mov r9, r15
  0x55CCDD7  488d542430             lea rdx, [rsp + 0x30]
  0x55CCDDC  4c8bc7                 mov r8, rdi
  0x55CCDDF  488bcd                 mov rcx, rbp
  0x55CCDE2  e809bc0000             call 0x7ff6b45d89f0
  0x55CCDE7  4533c9                 xor r9d, r9d
  0x55CCDEA  c644242000             mov byte ptr [rsp + 0x20], 0
  0x55CCDEF  4533c0                 xor r8d, r8d
  0x55CCDF2  488d542430             lea rdx, [rsp + 0x30]
  0x55CCDF7  488bcf                 mov rcx, rdi
  0x55CCDFA  e8a1d9dcfd             call 0x7ff6b239a7a0
  0x55CCDFF  488bd3                 mov rdx, rbx
  0x55CCE02  488bcd                 mov rcx, rbp
  0x55CCE05  e8b669e8ff             call 0x7ff6b44537c0
  0x55CCE0A  488bcb                 mov rcx, rbx
  0x55CCE0D  e86ea0ffff             call 0x7ff6b45c6e80
  0x55CCE12  4c8b742450             mov r14, qword ptr [rsp + 0x50]
  0x55CCE17  4885c0                 test rax, rax
  0x55CCE1A  7407                   je 0x7ff6b45cce23
  0x55CCE1C  c680d000000001         mov byte ptr [rax + 0xd0], 1
  0x55CCE23  488d942488000000       lea rdx, [rsp + 0x88]
  0x55CCE2B  488d8d30010000         lea rcx, [rbp + 0x130]
  0x55CCE32  e8296ac2fb             call 0x7ff6b01f3860
  0x55CCE37  488b8c2488000000       mov rcx, qword ptr [rsp + 0x88]
  0x55CCE3F  488b7c2458             mov rdi, qword ptr [rsp + 0x58]
  0x55CCE44  4885c9                 test rcx, rcx
  0x55CCE47  740a                   je 0x7ff6b45cce53
  0x55CCE49  4533c0                 xor r8d, r8d
  0x55CCE4C  b203                   mov dl, 3
  0x55CCE4E  e8cd1d9bfb             call 0x7ff6aff7ec20
  0x55CCE53  488b9c2480000000       mov rbx, qword ptr [rsp + 0x80]
  0x55CCE5B  488b742460             mov rsi, qword ptr [rsp + 0x60]

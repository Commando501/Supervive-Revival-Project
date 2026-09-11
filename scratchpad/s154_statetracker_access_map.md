# S154 state-tracker offset access map (offline, merged14)

Enumeration of readers/writers for the 8 state-tracker offsets discovered
in the S153 WALL P auto-fire hunt (docs/wall-p-autofire-mechanism-s153.md).

## `[reg + 0xC0D]` -- 6 unique accesses

### fn 0x5515C55..0x5515D6D (0x118 B)

  - `0x5515D48` **WRITE** (1B): `mov byte ptr [rsi + 0xc0d], al`

### fn 0x5679D50..0x5679DC5 (0x75 B)

  - `0x5679D62` **CMP** (1B): `cmp byte ptr [rcx + 0xc0d], 0`

### fn 0x5679DF7..0x5679E60 (0x69 B)

  - `0x5679E21` **CMP** (1B): `cmp byte ptr [rcx + 0xc0d], 0`

### fn 0x5679E80..0x5679EF8 (0x78 B)

  - `0x5679E92` **CMP** (1B): `cmp byte ptr [rcx + 0xc0d], 0`

### fn 0x5679F2C..0x5679F98 (0x6c B)

  - `0x5679F59` **CMP** (1B): `cmp byte ptr [rcx + 0xc0d], 0`

### fn NO_PDATA

  - `0x5525360` **WRITE** (1B): `mov byte ptr [rsi + 0xc0d], 0`

## `[reg + 0xBFC]` -- 15 unique accesses

### fn 0x1265DF0..0x127BAB0 (0x15cc0 B)

  - `0x126C8CC` **WRITE** (4B): `mov dword ptr [rsp + 0xbfc], eax`
  - `0x126C8E3` **READ** (4B): `mov edx, dword ptr [rsp + 0xbfc]`

### fn 0x127BAB0..0x128E530 (0x12a80 B)

  - `0x1284463` **WRITE** (4B): `mov dword ptr [rsp + 0xbfc], eax`
  - `0x128447A` **READ** (4B): `mov edx, dword ptr [rsp + 0xbfc]`

### fn 0x2616680..0x261DA12 (0x7392 B)

  - `0x261941A` **WRITE** (4B): `mov dword ptr [rbp + 0xbfc], 0x79e8ff00`

### fn 0x2DA8BDA..0x2DA8DAE (0x1d4 B)

  - `0x2DA8D56` **CMP** (4B): `cmp eax, dword ptr [rbp + 0xbfc]`

### fn 0x31A0010..0x31A02DA (0x2ca B)

  - `0x31A026A` **WRITE** (4B): `mov dword ptr [rdi + 0xbfc], 0x3f800000`

### fn 0x3EEB790..0x3EEB7AC (0x1c B)

  - `0x3EEB798` **TEST** (1B): `test byte ptr [rcx + 0xbfc], 1`

### fn 0x4AF2200..0x4AF3B0A (0x190a B)

  - `0x4AF2D90` **WRITE** (4B): `mov dword ptr [rdi + 0xbfc], 0x80`

### fn 0x56777B0..0x5677EE2 (0x732 B)

  - `0x5677BEA` **WRITE** (1B): `mov byte ptr [rdi + 0xbfc], cl`

### fn 0x5679D50..0x5679DC5 (0x75 B)

  - `0x5679D56` **CMP** (1B): `cmp byte ptr [rcx + 0xbfc], 0`
  - `0x5679D74` **WRITE** (1B): `mov byte ptr [rcx + 0xbfc], 0`

### fn 0x5679E80..0x5679EF8 (0x78 B)

  - `0x5679EA0` **WRITE** (1B): `mov byte ptr [rcx + 0xbfc], 0`
  - `0x5679EEB` **WRITE** (1B): `mov byte ptr [rcx + 0xbfc], 1`

### fn NO_PDATA

  - `0x32BAE00` **WRITE** (4B): `or dword ptr [rcx + 0xbfc], 1`

## `[reg + 0xBEC]` -- 19 unique accesses

### fn 0x1265DF0..0x127BAB0 (0x15cc0 B)

  - `0x126C655` **WRITE** (4B): `mov dword ptr [rsp + 0xbec], 0x20`
  - `0x126C774` **READ** (4B): `mov eax, dword ptr [rsp + 0xbec]`

### fn 0x127BAB0..0x128E530 (0x12a80 B)

  - `0x12841EC` **WRITE** (4B): `mov dword ptr [rsp + 0xbec], 2`
  - `0x128430B` **READ** (4B): `mov eax, dword ptr [rsp + 0xbec]`

### fn 0x215F460..0x215FB66 (0x706 B)

  - `0x215F5EA` **READ** (4B): `ucomiss xmm0, dword ptr [rax + 0xbec]`

### fn 0x2531650..0x2535328 (0x3cd8 B)

  - `0x2531B21` **READ** (4B): `mov eax, dword ptr [rbp + 0xbec]`

### fn 0x2616680..0x261DA12 (0x7392 B)

  - `0x26193EE` **WRITE** (4B): `mov dword ptr [rbp + 0xbec], eax`

### fn 0x26A54E8..0x26A6392 (0xeaa B)

  - `0x26A56BD` **WRITE** (4B): `mov dword ptr [rcx + 0xbec], 0x3f800000`

### fn 0x273934B..0x2739692 (0x347 B)

  - `0x2739358` **READ** (4B): `adc dword ptr [rsi + 0xbec], eax`

### fn 0x276E0C1..0x276F52B (0x146a B)

  - `0x276EFC2` **READ** (1B): `adc byte ptr [rcx + 0xbec], bl`

### fn 0x28D3BD6..0x28D4205 (0x62f B)

  - `0x28D3CD8` **READ** (4B): `ucomiss xmm0, dword ptr [rax + 0xbec]`

### fn 0x31A0010..0x31A02DA (0x2ca B)

  - `0x31A024B` **WRITE** (4B): `mov dword ptr [rdi + 0xbec], 0x3f800000`

### fn 0x3ED66C0..0x3ED7099 (0x9d9 B)

  - `0x3ED6DC5` **READ** (4B): `adc dword ptr [rsi + 0xbec], ecx`

### fn 0x56777B0..0x5677EE2 (0x732 B)

  - `0x5677A32` **WRITE** (1B): `mov byte ptr [rdi + 0xbec], cl`

### fn 0x5679DF7..0x5679E60 (0x69 B)

  - `0x5679E1A` **WRITE** (1B): `mov byte ptr [rcx + 0xbec], 1`
  - `0x5679E53` **WRITE** (1B): `mov byte ptr [rbx + 0xbec], 0`

### fn 0x5679F2C..0x5679F98 (0x6c B)

  - `0x5679F52` **WRITE** (1B): `mov byte ptr [rcx + 0xbec], 1`
  - `0x5679F8B` **WRITE** (1B): `mov byte ptr [rbx + 0xbec], 0`

### fn 0x567EB90..0x567F0FA (0x56a B)

  - `0x567EE11` **READ** (1B): `movzx ecx, byte ptr [rbx + 0xbec]`

## `[reg + 0xBF4]` -- 23 unique accesses

### fn 0x1265DF0..0x127BAB0 (0x15cc0 B)

  - `0x126C814` **WRITE** (4B): `mov dword ptr [rsp + 0xbf4], eax`
  - `0x126C82F` **READ** (4B): `movsxd eax, dword ptr [rsp + 0xbf4]`

### fn 0x127BAB0..0x128E530 (0x12a80 B)

  - `0x12843AB` **WRITE** (4B): `mov dword ptr [rsp + 0xbf4], eax`
  - `0x12843C6` **READ** (4B): `movsxd eax, dword ptr [rsp + 0xbf4]`

### fn 0x1D8A620..0x1D8A6F9 (0xd9 B)

  - `0x1D8A6C5` **CMP** (4B): `cmp eax, dword ptr [rbx + 0xbf4]`

### fn 0x1D94500..0x1D94B2C (0x62c B)

  - `0x1D945E3` **READ** (4B): `mov eax, dword ptr [rsi + 0xbf4]`

### fn 0x21A289B..0x21A2A31 (0x196 B)

  - `0x21A291F` **CMP** (4B): `cmp eax, dword ptr [rbp + 0xbf4]`

### fn 0x2616680..0x261DA12 (0x7392 B)

  - `0x2619406` **WRITE** (4B): `mov dword ptr [rbp + 0xbf4], 0x10001`

### fn 0x2710CB5..0x2711274 (0x5bf B)

  - `0x2710D16` **READ** (1B): `adc byte ptr [rax + 0xbf4], al`

### fn 0x273934B..0x2739692 (0x347 B)

  - `0x2739370` **WRITE** (4B): `mov dword ptr [rsi + 0xbf4], 0x3f800000`

### fn 0x273D0A1..0x273D22B (0x18a B)

  - `0x273D0F5` **READ** (1B): `adc byte ptr [rax + 0xbf4], al`

### fn 0x274896C..0x27494E5 (0xb79 B)

  - `0x2748C6A` **READ** (1B): `adc byte ptr [rcx + 0xbf4], al`

### fn 0x274AD90..0x274AE86 (0xf6 B)

  - `0x274AE13` **READ** (4B): `mov ecx, dword ptr [rax + 0xbf4]`

### fn 0x276E0C1..0x276F52B (0x146a B)

  - `0x276EF64` **READ** (1B): `adc byte ptr [rcx + 0xbf4], al`

### fn 0x279E177..0x279E1D8 (0x61 B)

  - `0x279E18C` **CMP** (4B): `cmp eax, dword ptr [rdi + 0xbf4]`

### fn 0x27B77ED..0x27B782C (0x3f B)

  - `0x27B77FD` **CMP** (4B): `cmp eax, dword ptr [rsi + 0xbf4]`

### fn 0x30E0C90..0x30E0D7C (0xec B)

  - `0x30E0CF9` **READ** (4B): `mov eax, dword ptr [rdi + 0xbf4]`

### fn 0x31A0010..0x31A02DA (0x2ca B)

  - `0x31A0260` **WRITE** (4B): `mov dword ptr [rdi + 0xbf4], 0x43ac8000`

### fn 0x56777B0..0x5677EE2 (0x732 B)

  - `0x5677BDE` **WRITE** (1B): `mov byte ptr [rdi + 0xbf4], cl`

### fn 0x5679D50..0x5679DC5 (0x75 B)

  - `0x5679D7B` **WRITE** (1B): `mov byte ptr [rcx + 0xbf4], 0`
  - `0x5679DB8` **WRITE** (1B): `mov byte ptr [rcx + 0xbf4], 1`

### fn 0x5679E80..0x5679EF8 (0x78 B)

  - `0x5679E86` **CMP** (1B): `cmp byte ptr [rcx + 0xbf4], 0`
  - `0x5679EA7` **WRITE** (1B): `mov byte ptr [rcx + 0xbf4], 0`

## `[reg + 0xC0C]` -- 35 unique accesses

### fn 0x111ED9A..0x111EEDB (0x141 B)

  - `0x111EE0E` **READ** (4B): `mov eax, dword ptr [rcx + 0xc0c]`

### fn 0x1121770..0x11217F6 (0x86 B)

  - `0x1121776` **CMP** (4B): `cmp dword ptr [rcx + 0xc0c], 0`

### fn 0x11299D4..0x1129A21 (0x4d B)

  - `0x11299EA` **CMP** (4B): `cmp dword ptr [rsi + 0xc0c], esi`

### fn 0x112A500..0x112A5B7 (0xb7 B)

  - `0x112A52F` **READ** (4B): `mov eax, dword ptr [rcx + 0xc0c]`
  - `0x112A58D` **WRITE** (4B): `mov dword ptr [rdi + 0xc0c], edx`

### fn 0x112A930..0x112A9A9 (0x79 B)

  - `0x112A97F` **CMP** (4B): `cmp ebx, dword ptr [rdi + 0xc0c]`
  - `0x112A993` **WRITE** (4B): `mov dword ptr [rdi + 0xc0c], ebx`

### fn 0x1265DF0..0x127BAB0 (0x15cc0 B)

  - `0x126CAB6` **WRITE** (4B): `mov dword ptr [rsp + 0xc0c], eax`
  - `0x126CAD1` **READ** (4B): `movsxd eax, dword ptr [rsp + 0xc0c]`

### fn 0x127BAB0..0x128E530 (0x12a80 B)

  - `0x128464D` **WRITE** (4B): `mov dword ptr [rsp + 0xc0c], eax`
  - `0x1284668` **READ** (4B): `movsxd eax, dword ptr [rsp + 0xc0c]`

### fn 0x1EB37B0..0x1EB38DE (0x12e B)

  - `0x1EB37E3` **WRITE** (4B): `mov dword ptr [rcx + 0xc0c], 0x180`
  - `0x1EB37F2` **READ** (4B): `mov eax, dword ptr [rcx + 0xc0c]`
  - `0x1EB3852` **WRITE** (4B): `mov dword ptr [rbx + 0xc0c], eax`

### fn 0x219FBA0..0x219FC2D (0x8d B)

  - `0x219FC1D` **CMP** (4B): `cmp eax, dword ptr [rcx + 0xc0c]`

### fn 0x21CFA10..0x21CFA3D (0x2d B)

  - `0x21CFA31` **READ** (4B): `mov eax, dword ptr [rdx + 0xc0c]`

### fn 0x21CFA55..0x21CFA9E (0x49 B)

  - `0x21CFA7D` **WRITE** (4B): `mov dword ptr [rdx + 0xc0c], ecx`

### fn 0x310C910..0x310C98C (0x7c B)

  - `0x310C940` **READ** (1B): `adc byte ptr [rcx + 0xc0c], al`
  - `0x310C94A` **READ** (1B): `adc byte ptr [rcx + 0xc0c], al`

### fn 0x31A0010..0x31A02DA (0x2ca B)

  - `0x31A0289` **WRITE** (4B): `mov dword ptr [rdi + 0xc0c], 0x3f800000`

### fn 0x3827AE1..0x3827CD9 (0x1f8 B)

  - `0x3827C73` **CMP** (4B): `cmp eax, dword ptr [rdi + 0xc0c]`

### fn 0x3847840..0x38478A1 (0x61 B)

  - `0x3847885` **READ** (4B): `movsxd eax, dword ptr [rdi + 0xc0c]`

### fn 0x3871286..0x3871764 (0x4de B)

  - `0x3871707` **CMP** (4B): `cmp eax, dword ptr [rdi + 0xc0c]`

### fn 0x5679DD0..0x5679DF7 (0x27 B)

  - `0x5679DD6` **CMP** (1B): `cmp byte ptr [rcx + 0xc0c], 0`

### fn 0x5679DF7..0x5679E60 (0x69 B)

  - `0x5679E28` **WRITE** (1B): `mov byte ptr [rcx + 0xc0c], 0`

### fn 0x5679F2C..0x5679F98 (0x6c B)

  - `0x5679F60` **WRITE** (1B): `mov byte ptr [rcx + 0xc0c], 0`

### fn 0x5679F98..0x5679FAD (0x15 B)

  - `0x5679FA0` **WRITE** (1B): `mov byte ptr [rcx + 0xc0c], 1`

### fn NO_PDATA

  - `0x21CFF9E` **CMP** (4B): `cmp edx, dword ptr [rcx + 0xc0c]`
  - `0x21CFFA6` **WRITE** (4B): `mov dword ptr [rcx + 0xc0c], edx`
  - `0x30B9170` **READ** (4B): `mov eax, dword ptr [rcx + 0xc0c]`
  - `0x30F143F` **READ** (16B): `addps xmm0, xmmword ptr [rcx + 0xc0c]`
  - `0x30F1449` **READ** (1B): `adc byte ptr [rcx + 0xc0c], al`
  - `0x30F15C2` **READ** (1B): `adc byte ptr [rcx + 0xc0c], al`
  - `0x30F4022` **READ** (4B): `adc dword ptr [rcx + 0xc0c], ecx`
  - `0x312A8E5` **READ** (4B): `mov eax, dword ptr [rcx + 0xc0c]`

## `[reg + 0xC04]` -- 17 unique accesses

### fn 0x115E04D..0x115E15D (0x110 B)

  - `0x115E121` **READ** (4B): `lea eax, [rdi + 0xc04]`

### fn 0x1265DF0..0x127BAB0 (0x15cc0 B)

  - `0x126C8F7` **WRITE** (4B): `mov dword ptr [rsp + 0xc04], 0x20`
  - `0x126CA16` **READ** (4B): `mov eax, dword ptr [rsp + 0xc04]`

### fn 0x127BAB0..0x128E530 (0x12a80 B)

  - `0x128448E` **WRITE** (4B): `mov dword ptr [rsp + 0xc04], 2`
  - `0x12845AD` **READ** (4B): `mov eax, dword ptr [rsp + 0xc04]`

### fn 0x21A2720..0x21A2879 (0x159 B)

  - `0x21A2804` **READ** (4B): `mov eax, dword ptr [rbp + 0xc04]`

### fn 0x31A0010..0x31A02DA (0x2ca B)

  - `0x31A027F` **WRITE** (4B): `mov dword ptr [rdi + 0xc04], 0x43340000`

### fn 0x3B0FFA0..0x3B10188 (0x1e8 B)

  - `0x3B0FFE4` **CMP** (4B): `cmp edx, dword ptr [rax + 0xc04]`

### fn 0x4AF2200..0x4AF3B0A (0x190a B)

  - `0x4AF2DA5` **WRITE** (4B): `mov dword ptr [rdi + 0xc04], esi`

### fn 0x56777B0..0x5677EE2 (0x732 B)

  - `0x5677BF6` **WRITE** (1B): `mov byte ptr [rdi + 0xc04], cl`

### fn 0x5679DF7..0x5679E60 (0x69 B)

  - `0x5679E2F` **WRITE** (1B): `mov byte ptr [rcx + 0xc04], 0`

### fn 0x5679E60..0x5679E75 (0x15 B)

  - `0x5679E68` **WRITE** (1B): `mov byte ptr [rcx + 0xc04], 1`

### fn 0x5679F00..0x5679F2C (0x2c B)

  - `0x5679F06` **CMP** (1B): `cmp byte ptr [rcx + 0xc04], 0`

### fn 0x5679F2C..0x5679F98 (0x6c B)

  - `0x5679F67` **WRITE** (1B): `mov byte ptr [rcx + 0xc04], 0`

### fn 0x6C4E580..0x6C4E8D4 (0x354 B)

  - `0x6C4E7F4` **READ** (4B): `lea edi, [rsi + 0xc04]`

### fn 0x6C4EA20..0x6C4EC56 (0x236 B)

  - `0x6C4EA75` **READ** (4B): `lea ebx, [rsi + 0xc04]`

### fn 0x6C4EC60..0x6C4EFED (0x38d B)

  - `0x6C4ED3F` **READ** (4B): `lea edx, [rsi + 0xc04]`

## `[reg + 0xBF8]` -- 139 unique accesses

### fn 0x1265DF0..0x127BAB0 (0x15cc0 B)

  - `0x126C7A6` **WRITE** (4B): `mov dword ptr [rsp + 0xbf8], 0x20`
  - `0x126C8C5` **READ** (4B): `mov eax, dword ptr [rsp + 0xbf8]`

### fn 0x127BAB0..0x128E530 (0x12a80 B)

  - `0x128433D` **WRITE** (4B): `mov dword ptr [rsp + 0xbf8], 2`
  - `0x128445C` **READ** (4B): `mov eax, dword ptr [rsp + 0xbf8]`

### fn 0x128E530..0x1298456 (0x9f26 B)

  - `0x128F57A` **WRITE** (4B): `mov dword ptr [rsp + 0xbf8], eax`
  - `0x128F589` **READ** (4B): `mov ecx, dword ptr [rsp + 0xbf8]`

### fn 0x13969A0..0x13B9981 (0x22fe1 B)

  - `0x1399E7B` **WRITE** (4B): `mov dword ptr [rsp + 0xbf8], eax`
  - `0x1399EA9` **READ** (4B): `mov ecx, dword ptr [rsp + 0xbf8]`

### fn 0x1434AA0..0x143B7F6 (0x6d56 B)

  - `0x1439DDF` **WRITE** (1B): `mov byte ptr [rbp + 0xbf8], 1`
  - `0x1439DED` **READ** (4B): `mov eax, dword ptr [rbp + 0xbf8]`

### fn 0x148CAFA..0x14976A3 (0xaba9 B)

  - `0x14912AC` **READ** (4B): `lea ecx, [rbp + 0xbf8]`

### fn 0x14B05A0..0x14B1B6F (0x15cf B)

  - `0x14B16A8` **READ** (4B): `lea ecx, [rbp + 0xbf8]`

### fn 0x14CAD61..0x14D85FB (0xd89a B)

  - `0x14CC06F` **READ** (4B): `lea ecx, [rbp + 0xbf8]`

### fn 0x1BB8907..0x1BB89CE (0xc7 B)

  - `0x1BB8924` **READ** (1B): `adc byte ptr [rax + rdx*8 + 0xbf8], dl`

### fn 0x1FCB370..0x1FCB3AB (0x3b B)

  - `0x1FCB390` **READ** (4B): `mov ebx, dword ptr [rsp + 0xbf8]`

### fn 0x2100F80..0x2101349 (0x3c9 B)

  - `0x21012F2` **WRITE** (4B): `mov dword ptr [rbx + 0xbf8], edi`

### fn 0x2101D50..0x210223B (0x4eb B)

  - `0x2101DD1` **READ** (4B): `mov ecx, dword ptr [rbx + 0xbf8]`

### fn 0x21A2720..0x21A2879 (0x159 B)

  - `0x21A2812` **READ** (4B): `lea ecx, [rbp + 0xbf8]`
  - `0x21A2835` **READ** (4B): `mov eax, dword ptr [rbp + 0xbf8]`
  - `0x21A2864` **READ** (4B): `lea ecx, [rbp + 0xbf8]`

### fn 0x21A289B..0x21A2A31 (0x196 B)

  - `0x21A28C7` **READ** (4B): `mov eax, dword ptr [rbp + 0xbf8]`

### fn 0x236A690..0x236AF08 (0x878 B)

  - `0x236AC39` **WRITE** (4B): `mov dword ptr [rbx + 0xbf8], edi`

### fn 0x236AF10..0x236B6C7 (0x7b7 B)

  - `0x236B4B1` **WRITE** (4B): `mov dword ptr [rdi + 0xbf8], esi`

### fn 0x236CED0..0x236DC38 (0xd68 B)

  - `0x236D448` **WRITE** (4B): `mov dword ptr [rbx + 0xbf8], esp`

### fn 0x23DB685..0x23DB7BB (0x136 B)

  - `0x23DB686` **WRITE** (4B): `mov dword ptr [rsp + 0xbf8], edi`

### fn 0x23DDD31..0x23DEAED (0xdbc B)

  - `0x23DEAC5` **READ** (4B): `mov edi, dword ptr [rsp + 0xbf8]`

### fn 0x2616680..0x261DA12 (0x7392 B)

  - `0x2619411` **WRITE** (4B): `mov dword ptr [rbp + 0xbf8], 0xc7660101`

### fn 0x274896C..0x27494E5 (0xb79 B)

  - `0x2748CA7` **READ** (4B): `mov eax, dword ptr [rcx + 0xbf8]`

### fn 0x2795F30..0x27963D6 (0x4a6 B)

  - `0x2796200` **WRITE** (4B): `mov dword ptr [rcx + 0xbf8], ebp`

### fn 0x2797605..0x2797B16 (0x511 B)

  - `0x2797819` **READ** (4B): `mov ebx, dword ptr [rdi + 0xbf8]`

### fn 0x27A7FD3..0x27A80F8 (0x125 B)

  - `0x27A8037` **READ** (4B): `lea ecx, [rsi + 0xbf8]`

### fn 0x27B7F10..0x27B819E (0x28e B)

  - `0x27B803F` **READ** (4B): `lea ecx, [rbx + 0xbf8]`
  - `0x27B808E` **READ** (4B): `lea ecx, [rbx + 0xbf8]`

### fn 0x27DBC30..0x27DC661 (0xa31 B)

  - `0x27DC525` **READ** (4B): `lea ecx, [rdi + 0xbf8]`

### fn 0x2BC1C60..0x2BC20B6 (0x456 B)

  - `0x2BC1CE4` **WRITE** (1B): `mov byte ptr [rcx + 0xbf8], ch`

### fn 0x2C533FE..0x2C54BBF (0x17c1 B)

  - `0x2C54732` **READ** (1B): `adc byte ptr [rbp + 0xbf8], cl`

### fn 0x2D9B730..0x2D9BE0F (0x6df B)

  - `0x2D9BCB7` **WRITE** (4B): `mov dword ptr [rdi + 0xbf8], esi`

### fn 0x2DA8BDA..0x2DA8DAE (0x1d4 B)

  - `0x2DA8D46` **READ** (4B): `movsxd esi, dword ptr [rbp + 0xbf8]`
  - `0x2DA8D50` **WRITE** (4B): `mov dword ptr [rbp + 0xbf8], eax`

### fn 0x2DA8DE0..0x2DA90F7 (0x317 B)

  - `0x2DA8E43` **READ** (4B): `mov esi, dword ptr [rdi + 0xbf8]`

### fn 0x30C3D70..0x30C4004 (0x294 B)

  - `0x30C3E2F` **READ** (4B): `lea edi, [rbp + 0xbf8]`

### fn 0x30D1C60..0x30D1E71 (0x211 B)

  - `0x30D1DB8` **WRITE** (4B): `mov dword ptr [rdi + 0xbf8], esi`

### fn 0x30DDB20..0x30DDB85 (0x65 B)

  - `0x30DDB36` **READ** (4B): `mov ebx, dword ptr [rcx + 0xbf8]`

### fn 0x3107666..0x3107730 (0xca B)

  - `0x3107712` **READ** (4B): `lea ecx, [rsi + 0xbf8]`

### fn 0x31112D0..0x311135E (0x8e B)

  - `0x31112DB` **READ** (4B): `mov ecx, dword ptr [rcx + 0xbf8]`

### fn 0x31287D0..0x31288A6 (0xd6 B)

  - `0x3128848` **READ** (4B): `mov ebx, dword ptr [rsi + 0xbf8]`

### fn 0x312B360..0x312B3A1 (0x41 B)

  - `0x312B37F` **READ** (4B): `mov ecx, dword ptr [rcx + 0xbf8]`

### fn 0x3319F40..0x331D823 (0x38e3 B)

  - `0x331BE60` **WRITE** (1B): `mov byte ptr [rbp + 0xbf8], 3`
  - `0x331BE69` **READ** (1B): `adc byte ptr [rbp + 0xbf8], cl`

### fn 0x3596C00..0x3596FF1 (0x3f1 B)

  - `0x3596EBD` **WRITE** (4B): `mov dword ptr [rdi + 0xbf8], esi`

### fn 0x35B4E50..0x35B5F6B (0x111b B)

  - `0x35B5A32` **READ** (4B): `mov ecx, dword ptr [rdi + 0xbf8]`

### fn 0x35BDDD0..0x35BDE1A (0x4a B)

  - `0x35BDDF2` **READ** (1B): `adc byte ptr [rdi + 0xbf8], al`
  - `0x35BDDFE` **WRITE** (4B): `mov dword ptr [rdi + 0xbf8], ecx`

### fn 0x3665760..0x3665EB8 (0x758 B)

  - `0x3665904` **WRITE** (4B): `mov dword ptr [rdi + 0xbf8], esi`

### fn 0x36A6370..0x36A63EF (0x7f B)

  - `0x36A638A` **READ** (4B): `mov edi, dword ptr [rax + 0xbf8]`

### fn 0x3823020..0x3823215 (0x1f5 B)

  - `0x3823170` **WRITE** (1B): `mov byte ptr [rbx + 0xbf8], 0`

### fn 0x3827AE1..0x3827CD9 (0x1f8 B)

  - `0x3827B82` **CMP** (1B): `cmp byte ptr [rdi + 0xbf8], 0`
  - `0x3827C5D` **READ** (4B): `adc dword ptr [rdi + 0xbf8], eax`

### fn 0x3827E81..0x3828261 (0x3e0 B)

  - `0x38280AF` **CMP** (1B): `cmp byte ptr [rdi + 0xbf8], 0`
  - `0x38281A1` **READ** (4B): `adc dword ptr [rdi + 0xbf8], ecx`

### fn 0x3829140..0x3829549 (0x409 B)

  - `0x38293E1` **WRITE** (1B): `mov byte ptr [rsi + 0xbf8], 0`

### fn 0x382EAA0..0x382EADF (0x3f B)

  - `0x382EABE` **CMP** (1B): `cmp byte ptr [rcx + 0xbf8], 0`

### fn 0x382EADF..0x382EC95 (0x1b6 B)

  - `0x382EB27` **CMP** (1B): `cmp byte ptr [rcx + 0xbf8], 0`
  - `0x382EB88` **CMP** (1B): `cmp byte ptr [rcx + 0xbf8], 0`

### fn 0x382F367..0x382F3C6 (0x5f B)

  - `0x382F39A` **WRITE** (1B): `mov byte ptr [rsi + 0xbf8], 0`

### fn 0x3871286..0x3871764 (0x4de B)

  - `0x387161F` **CMP** (1B): `cmp byte ptr [rdi + 0xbf8], 0`
  - `0x38716F1` **READ** (4B): `adc dword ptr [rdi + 0xbf8], ecx`

### fn 0x3886845..0x38868BE (0x79 B)

  - `0x388687D` **READ** (8B): `call qword ptr [rax + 0xbf8]`

### fn 0x389B483..0x389B4C8 (0x45 B)

  - `0x389B4AB` **READ** (8B): `call qword ptr [rax + 0xbf8]`

### fn 0x389B500..0x389B643 (0x143 B)

  - `0x389B61C` **READ** (8B): `call qword ptr [rax + 0xbf8]`

### fn 0x38A32D2..0x38A339E (0xcc B)

  - `0x38A32FA` **READ** (8B): `call qword ptr [rax + 0xbf8]`

### fn 0x392F460..0x3938E81 (0x9a21 B)

  - `0x3931ECD` **WRITE** (1B): `mov byte ptr [rbp + 0xbf8], 2`
  - `0x3931ED6` **READ** (1B): `adc byte ptr [rbp + 0xbf8], al`

### fn 0x3C516B0..0x3C55480 (0x3dd0 B)

  - `0x3C535D0` **WRITE** (1B): `mov byte ptr [rbp + 0xbf8], 3`
  - `0x3C535D9` **READ** (1B): `adc byte ptr [rbp + 0xbf8], cl`

### fn 0x3C60130..0x3C601BB (0x8b B)

  - `0x3C601A5` **READ** (8B): `call qword ptr [rax + 0xbf8]`

### fn 0x3D7BFA0..0x3D7F278 (0x32d8 B)

  - `0x3D7E8E5` **READ** (4B): `lea ecx, [rsp + 0xbf8]`
  - `0x3D7E8F2` **READ** (4B): `lea edx, [rsp + 0xbf8]`
  - `0x3D7E904` **READ** (4B): `lea ecx, [rsp + 0xbf8]`

### fn 0x42112B0..0x4218A64 (0x77b4 B)

  - `0x4215055` **READ** (4B): `mov ecx, dword ptr [rbp + 0xbf8]`

### fn 0x472B320..0x4731D04 (0x69e4 B)

  - `0x472B545` **WRITE** (4B): `mov dword ptr [rbp + 0xbf8], esi`
  - `0x472B553` **READ** (4B): `lea eax, [rbp + 0xbf8]`

### fn 0x4832F40..0x4835D3A (0x2dfa B)

  - `0x48341CA` **WRITE** (4B): `mov dword ptr [rbp + 0xbf8], esi`

### fn 0x483CF90..0x48411F3 (0x4263 B)

  - `0x4840536` **WRITE** (1B): `mov byte ptr [rbp + 0xbf8], dh`

### fn 0x48418A0..0x4845727 (0x3e87 B)

  - `0x48449DD` **WRITE** (4B): `mov dword ptr [rbp + 0xbf8], eax`

### fn 0x4845730..0x484A195 (0x4a65 B)

  - `0x4849AC5` **READ** (4B): `lea edx, [rbp + 0xbf8]`
  - `0x4849B2A` **WRITE** (4B): `mov dword ptr [rbp + 0xbf8], esi`

### fn 0x484F3B0..0x4853D4B (0x499b B)

  - `0x4853836` **READ** (4B): `lea edx, [rbp + 0xbf8]`
  - `0x485388D` **WRITE** (4B): `mov dword ptr [rbp + 0xbf8], esi`

### fn 0x48570B0..0x485D8A3 (0x67f3 B)

  - `0x485849C` **WRITE** (1B): `mov byte ptr [rbp + 0xbf8], dh`

### fn 0x485D8B0..0x48628CF (0x501f B)

  - `0x4861DA7` **WRITE** (4B): `mov dword ptr [rbp + 0xbf8], esi`

### fn 0x4864170..0x48668CD (0x275d B)

  - `0x48664AB` **WRITE** (4B): `mov dword ptr [rbp + 0xbf8], 0`

### fn 0x4869050..0x486B618 (0x25c8 B)

  - `0x486B439` **WRITE** (4B): `mov dword ptr [rbp + 0xbf8], eax`

### fn 0x486B620..0x486DA25 (0x2405 B)

  - `0x486D762` **WRITE** (4B): `mov dword ptr [rbp + 0xbf8], ebp`

### fn 0x4943840..0x4943C8E (0x44e B)

  - `0x49438F4` **READ** (4B): `lea ecx, [rbx + 0xbf8]`
  - `0x4943911` **READ** (4B): `mov ecx, dword ptr [rbx + 0xbf8]`

### fn 0x49544FE..0x4954AFD (0x5ff B)

  - `0x49549FB` **WRITE** (4B): `mov dword ptr [rbx + 0xbf8], ebp`

### fn 0x4955680..0x4956363 (0xce3 B)

  - `0x4955DB4` **READ** (4B): `lea ebp, [rdi + 0xbf8]`

### fn 0x4AC2650..0x4AC3102 (0xab2 B)

  - `0x4AC3033` **WRITE** (4B): `mov dword ptr [rdi + 0xbf8], ebp`

### fn 0x4AF2200..0x4AF3B0A (0x190a B)

  - `0x4AF2D8A` **WRITE** (4B): `mov dword ptr [rdi + 0xbf8], esi`

### fn 0x4C13DB0..0x4C14044 (0x294 B)

  - `0x4C13E6F` **READ** (4B): `lea edi, [rbp + 0xbf8]`

### fn 0x4C14C10..0x4C15343 (0x733 B)

  - `0x4C150A9` **READ** (4B): `lea eax, [rsi + 0xbf8]`

### fn 0x52C6110..0x52CA059 (0x3f49 B)

  - `0x52C7CC5` **WRITE** (1B): `mov byte ptr [rbp + 0xbf8], 3`
  - `0x52C7CDA` **READ** (1B): `adc byte ptr [rbp + 0xbf8], cl`

### fn 0x52F4A80..0x52F5153 (0x6d3 B)

  - `0x52F4E3D` **READ** (4B): `mov ecx, dword ptr [rdi + 0xbf8]`

### fn 0x559E180..0x559EF51 (0xdd1 B)

  - `0x559E58B` **WRITE** (4B): `mov dword ptr [rsi + 0xbf8], ebp`

### fn 0x564EADF..0x564EDD2 (0x2f3 B)

  - `0x564EB10` **READ** (4B): `lea edi, [rbp + 0xbf8]`

### fn 0x5672C1B..0x5672E32 (0x217 B)

  - `0x5672C43` **READ** (4B): `lea esi, [rbp + 0xbf8]`

### fn 0x56777B0..0x5677EE2 (0x732 B)

  - `0x5677BE4` **WRITE** (4B): `mov dword ptr [rdi + 0xbf8], ecx`

### fn 0x5679D50..0x5679DC5 (0x75 B)

  - `0x5679D6B` **READ** (1B): `adc byte ptr [rcx + 0xbf8], al`

### fn 0x5679E80..0x5679EF8 (0x78 B)

  - `0x5679EE5` **READ** (4B): `adc dword ptr [rcx + 0xbf8], ecx`

### fn 0x567B720..0x567B94F (0x22f B)

  - `0x567B88D` **READ** (4B): `lea ecx, [rsi + 0xbf8]`

### fn 0x567D880..0x567D963 (0xe3 B)

  - `0x567D8FF` **READ** (4B): `lea ecx, [rbx + 0xbf8]`

### fn 0x567D970..0x567DA1B (0xab B)

  - `0x567D9E5` **READ** (4B): `lea ecx, [rax + 0xbf8]`

### fn 0x568DE60..0x568E170 (0x310 B)

  - `0x568DF44` **READ** (4B): `lea esi, [rbp + 0xbf8]`

### fn 0x56BD71E..0x56BDE9F (0x781 B)

  - `0x56BD9E7` **READ** (8B): `call qword ptr [rax + 0xbf8]`

### fn 0x5919C40..0x591D61F (0x39df B)

  - `0x5919E40` **READ** (4B): `lea eax, [rsp + rax + 0xbf8]`

### fn 0x5BCAEA0..0x5BCB03B (0x19b B)

  - `0x5BCAFC9` **WRITE** (4B): `mov dword ptr [rbx + 0xbf8], eax`

### fn 0x63F53F0..0x63F5681 (0x291 B)

  - `0x63F549D` **WRITE** (4B): `mov dword ptr [rdi + 0xbf8], esi`

### fn 0x63F5690..0x63F59A7 (0x317 B)

  - `0x63F574E` **WRITE** (4B): `mov dword ptr [rdi + 0xbf8], esi`

### fn 0x63F59B0..0x63F5D6D (0x3bd B)

  - `0x63F5A6B` **WRITE** (4B): `mov dword ptr [rdi + 0xbf8], esi`

### fn 0x63F6840..0x63F6A7A (0x23a B)

  - `0x63F6A4E` **READ** (4B): `mov ecx, dword ptr [rbx + 0xbf8]`

### fn 0x642E16C..0x642E58E (0x422 B)

  - `0x642E4CC` **READ** (4B): `mov ecx, dword ptr [rsi + 0xbf8]`

### fn 0x6448F72..0x6448FB2 (0x40 B)

  - `0x6448F73` **READ** (4B): `mov ecx, dword ptr [rsp + 0xbf8]`

### fn 0x6FAF419..0x6FAF576 (0x15d B)

  - `0x6FAF45D` **WRITE** (4B): `mov dword ptr [rdi + rbp*8 + 0xbf8], eax`
  - `0x6FAF505` **READ** (4B): `mov eax, dword ptr [rdi + rbp*8 + 0xbf8]`
  - `0x6FAF50D` **READ** (4B): `sub eax, dword ptr [rdi + rbx*8 + 0xbf8]`

### fn 0xF626D0..0xF64060 (0x1990 B)

  - `0xF639BA` **WRITE** (4B): `mov dword ptr [rbp + 0xbf8], eax`

### fn NO_PDATA

  - `0xF82370` **WRITE** (4B): `mov dword ptr [rcx + 0xbf8], eax`
  - `0x1EED3B9` **WRITE** (4B): `mov dword ptr [rcx + 0xbf8], eax`
  - `0x274A003` **READ** (1B): `adc byte ptr [rax + 0xbf8], cl`
  - `0x30DD5C1` **READ** (4B): `mov eax, dword ptr [rcx + 0xbf8]`
  - `0x30F4B51` **READ** (4B): `mov ecx, dword ptr [rcx + 0xbf8]`
  - `0x3127F68` **READ** (4B): `mov eax, dword ptr [rcx + 0xbf8]`
  - `0x38A838D` **READ** (4B): `mov eax, dword ptr [rax + 0xbf8]`
  - `0x3C094F6` **READ** (4B): `adc dword ptr [rax + 0xbf8], edx`
  - `0x553D126` **WRITE** (4B): `mov dword ptr [rbp + 0xbf8], ebp`
  - `0x553D1D5` **READ** (4B): `mov ecx, dword ptr [rbp + 0xbf8]`
  - `0x63DC3E5` **READ** (4B): `lea ecx, [rbp + 0xbf8]`

## `[reg + 0xBF0]` -- 181 unique accesses

### fn 0x1265DF0..0x127BAB0 (0x15cc0 B)

  - `0x126C77B` **WRITE** (4B): `mov dword ptr [rsp + 0xbf0], eax`
  - `0x126C792` **READ** (4B): `mov edx, dword ptr [rsp + 0xbf0]`

### fn 0x127BAB0..0x128E530 (0x12a80 B)

  - `0x1284312` **WRITE** (4B): `mov dword ptr [rsp + 0xbf0], eax`
  - `0x1284329` **READ** (4B): `mov edx, dword ptr [rsp + 0xbf0]`

### fn 0x128E530..0x1298456 (0x9f26 B)

  - `0x128F54E` **WRITE** (4B): `mov dword ptr [rsp + 0xbf0], eax`
  - `0x128F55D` **READ** (4B): `mov ecx, dword ptr [rsp + 0xbf0]`

### fn 0x13969A0..0x13B9981 (0x22fe1 B)

  - `0x1399E6D` **WRITE** (4B): `mov dword ptr [rsp + 0xbf0], eax`
  - `0x1399E74` **READ** (4B): `mov eax, dword ptr [rsp + 0xbf0]`

### fn 0x1434AA0..0x143B7F6 (0x6d56 B)

  - `0x1439DB7` **WRITE** (1B): `mov byte ptr [rbp + 0xbf0], 1`
  - `0x1439DC5` **READ** (4B): `mov eax, dword ptr [rbp + 0xbf0]`

### fn 0x148CAFA..0x14976A3 (0xaba9 B)

  - `0x14911E1` **READ** (4B): `lea ecx, [rbp + 0xbf0]`

### fn 0x14CAD61..0x14D85FB (0xd89a B)

  - `0x14CC03F` **READ** (4B): `lea ecx, [rbp + 0xbf0]`

### fn 0x16E8650..0x16EAE04 (0x27b4 B)

  - `0x16EAC27` **CMP** (4B): `cmp dword ptr [rbp + 0xbf0], 0`
  - `0x16EAC61` **WRITE** (4B): `mov dword ptr [rbp + 0xbf0], esi`

### fn 0x1BB8907..0x1BB89CE (0xc7 B)

  - `0x1BB8916` **READ** (1B): `adc byte ptr [rax + rdx*8 + 0xbf0], ah`

### fn 0x1D87000..0x1D87927 (0x927 B)

  - `0x1D874DD` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], edi`

### fn 0x1D8A620..0x1D8A6F9 (0xd9 B)

  - `0x1D8A6B6` **READ** (4B): `movsxd edi, dword ptr [rbx + 0xbf0]`
  - `0x1D8A6BF` **WRITE** (4B): `mov dword ptr [rbx + 0xbf0], eax`

### fn 0x1D94500..0x1D94B2C (0x62c B)

  - `0x1D94554` **READ** (4B): `movsxd eax, dword ptr [rsi + 0xbf0]`
  - `0x1D945EB` **WRITE** (4B): `mov dword ptr [rsi + 0xbf0], ecx`

### fn 0x1F94DC0..0x1F98D0D (0x3f4d B)

  - `0x1F984DF` **READ** (4B): `lea ecx, [rbp + 0xbf0]`
  - `0x1F9850A` **READ** (4B): `lea ecx, [rbp + 0xbf0]`

### fn 0x1FBCEC0..0x1FBD0EE (0x22e B)

  - `0x1FBCFC3` **READ** (4B): `lea ecx, [rdi + 0xbf0]`

### fn 0x2100F80..0x2101349 (0x3c9 B)

  - `0x21012EB` **WRITE** (4B): `mov dword ptr [rbx + 0xbf0], edi`

### fn 0x2101D50..0x210223B (0x4eb B)

  - `0x2101DE3` **READ** (4B): `mov ecx, dword ptr [rbx + 0xbf0]`

### fn 0x211CDAA..0x211EF31 (0x2187 B)

  - `0x211D148` **READ** (4B): `lea ecx, [rbp + 0xbf0]`
  - `0x211D176` **READ** (8B): `movq qword ptr [rbp + 0xbf0], mm0`

### fn 0x216C315..0x216C755 (0x440 B)

  - `0x216C585` **WRITE** (4B): `sub dword ptr [rbp + 0xbf0], eax`

### fn 0x21A289B..0x21A2A31 (0x196 B)

  - `0x21A2905` **READ** (4B): `movsxd edi, dword ptr [rbp + 0xbf0]`
  - `0x21A2919` **WRITE** (4B): `mov dword ptr [rbp + 0xbf0], eax`
  - `0x21A29C5` **READ** (4B): `mov eax, dword ptr [rbp + 0xbf0]`

### fn 0x21E2710..0x21E27B6 (0xa6 B)

  - `0x21E27AA` **READ** (4B): `lea eax, [rip + 0xbf0]`

### fn 0x2331BCA..0x2331E87 (0x2bd B)

  - `0x2331CDB` **READ** (4B): `mov eax, dword ptr [rsp + rcx*8 + 0xbf0]`

### fn 0x23436FC..0x2347115 (0x3a19 B)

  - `0x2343F61` **READ** (4B): `mov ecx, dword ptr [rbp + 0xbf0]`
  - `0x23442DD` **READ** (4B): `mov eax, dword ptr [rbp + 0xbf0]`
  - `0x2345339` **READ** (4B): `mov eax, dword ptr [rbp + 0xbf0]`
  - `0x23463D2` **READ** (4B): `mov eax, dword ptr [rbp + 0xbf0]`
  - `0x23467B2` **READ** (4B): `mov eax, dword ptr [rbp + 0xbf0]`
  - `0x2346C0E` **READ** (4B): `mov eax, dword ptr [rbp + 0xbf0]`
  - `0x2346EA1` **READ** (4B): `mov eax, dword ptr [rbp + 0xbf0]`

### fn 0x23486E7..0x2348926 (0x23f B)

  - `0x2348786` **READ** (4B): `mov ecx, dword ptr [rbp + 0xbf0]`

### fn 0x236A690..0x236AF08 (0x878 B)

  - `0x236AC32` **WRITE** (4B): `mov dword ptr [rbx + 0xbf0], edi`

### fn 0x236AF10..0x236B6C7 (0x7b7 B)

  - `0x236B4AA` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], esi`

### fn 0x236CED0..0x236DC38 (0xd68 B)

  - `0x236D483` **READ** (4B): `mov ecx, dword ptr [rbx + 0xbf0]`
  - `0x236D4AB` **WRITE** (4B): `mov dword ptr [rbx + 0xbf0], esp`

### fn 0x23D9992..0x23DA6B4 (0xd22 B)

  - `0x23DA4CC` **READ** (4B): `mov ecx, dword ptr [rsi + rcx*8 + 0xbf0]`

### fn 0x258ACB3..0x258C1A0 (0x14ed B)

  - `0x258BD6E` **WRITE** (4B): `mov dword ptr [rbp + 0xbf0], eax`

### fn 0x2699E30..0x269A9F7 (0xbc7 B)

  - `0x269A2B4` **WRITE** (1B): `sub byte ptr [rbx + 0xbf0], al`
  - `0x269A2BB` **WRITE** (4B): `sub dword ptr [rdi + 0xbf0], eax`

### fn 0x269AA00..0x269B6C3 (0xcc3 B)

  - `0x269AEE5` **WRITE** (1B): `sub byte ptr [rdi + 0xbf0], al`
  - `0x269AEEC` **WRITE** (4B): `sub dword ptr [rbx + 0xbf0], eax`

### fn 0x26A54E8..0x26A6392 (0xeaa B)

  - `0x26A56D2` **WRITE** (4B): `mov dword ptr [rcx + 0xbf0], 0x3f800000`

### fn 0x273934B..0x2739692 (0x347 B)

  - `0x2739366` **WRITE** (4B): `mov dword ptr [rsi + 0xbf0], edi`

### fn 0x276E0C1..0x276F52B (0x146a B)

  - `0x276EF25` **READ** (1B): `adc byte ptr [rdi + 0xbf0], al`
  - `0x276EFBA` **READ** (1B): `adc byte ptr [rcx + 0xbf0], dl`

### fn 0x2795F30..0x27963D6 (0x4a6 B)

  - `0x27961F9` **WRITE** (4B): `mov dword ptr [rcx + 0xbf0], ebp`

### fn 0x279E177..0x279E1D8 (0x61 B)

  - `0x279E17D` **READ** (4B): `movsxd ebx, dword ptr [rdi + 0xbf0]`
  - `0x279E186` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], eax`

### fn 0x27A0748..0x27A0E79 (0x731 B)

  - `0x27A0878` **CMP** (4B): `cmp dword ptr [rdi + 0xbf0], 0`

### fn 0x27A2180..0x27A254A (0x3ca B)

  - `0x27A21D8` **CMP** (4B): `cmp dword ptr [rbx + 0xbf0], 0`

### fn 0x27A34E0..0x27A363E (0x15e B)

  - `0x27A35E7` **READ** (4B): `mov eax, dword ptr [rbx + 0xbf0]`

### fn 0x27A363E..0x27A393D (0x2ff B)

  - `0x27A38B0` **CMP** (4B): `cmp dword ptr [rbx + 0xbf0], 0`

### fn 0x27B19BD..0x27B296F (0xfb2 B)

  - `0x27B27CA` **CMP** (4B): `cmp dword ptr [rbp + 0xbf0], 0`

### fn 0x27B5EE4..0x27B6704 (0x820 B)

  - `0x27B604D` **CMP** (4B): `cmp dword ptr [rsi + 0xbf0], 0`
  - `0x27B6185` **CMP** (4B): `cmp dword ptr [rsi + 0xbf0], 0`
  - `0x27B64CE` **CMP** (4B): `cmp dword ptr [rsi + 0xbf0], 0`
  - `0x27B65F9` **CMP** (4B): `cmp dword ptr [rax + 0xbf0], 0`

### fn 0x27B77ED..0x27B782C (0x3f B)

  - `0x27B77EE` **READ** (4B): `movsxd ebx, dword ptr [rsi + 0xbf0]`
  - `0x27B77F7` **WRITE** (4B): `mov dword ptr [rsi + 0xbf0], eax`

### fn 0x27B7F10..0x27B819E (0x28e B)

  - `0x27B7F40` **CMP** (4B): `cmp dword ptr [rcx + 0xbf0], 0`

### fn 0x285DC8D..0x285F4F7 (0x186a B)

  - `0x285E8FD` **READ** (4B): `lea ecx, [rbp + 0xbf0]`

### fn 0x2BC1C60..0x2BC20B6 (0x456 B)

  - `0x2BC1CD6` **READ** (4B): `adc dword ptr [rcx + 0xbf0], eax`
  - `0x2BC1CEC` **READ** (1B): `adc byte ptr [rcx + 0xbf0], cl`

### fn 0x2C533FE..0x2C54BBF (0x17c1 B)

  - `0x2C54722` **READ** (1B): `adc byte ptr [rbp + 0xbf0], al`

### fn 0x2D9B730..0x2D9BE0F (0x6df B)

  - `0x2D9BCB0` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], esi`

### fn 0x2D9C870..0x2D9CB2E (0x2be B)

  - `0x2D9C8DC` **READ** (4B): `mov ecx, dword ptr [rbx + 0xbf0]`

### fn 0x2DA8BDA..0x2DA8DAE (0x1d4 B)

  - `0x2DA8D62` **READ** (4B): `lea ecx, [rbp + 0xbf0]`
  - `0x2DA8D6E` **READ** (4B): `mov eax, dword ptr [rbp + 0xbf0]`

### fn 0x2F5C66D..0x2F5C6E9 (0x7c B)

  - `0x2F5C699` **WRITE** (1B): `mov byte ptr [rax + 0xbf0], 0`

### fn 0x2F79CD8..0x2F79D93 (0xbb B)

  - `0x2F79D40` **CMP** (1B): `cmp byte ptr [rbx + 0xbf0], 0`

### fn 0x30D1C60..0x30D1E71 (0x211 B)

  - `0x30D1DB1` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], esi`

### fn 0x30E0C90..0x30E0D7C (0xec B)

  - `0x30E0CAA` **READ** (4B): `movsxd esi, dword ptr [rcx + 0xbf0]`
  - `0x30E0D00` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], esi`

### fn 0x30EA3D0..0x30EA3EA (0x1a B)

  - `0x30EA3E4` **READ** (4B): `movsxd eax, dword ptr [rcx + 0xbf0]`

### fn 0x30EFFF0..0x30F0007 (0x17 B)

  - `0x30EFFF8` **CMP** (4B): `cmp edx, dword ptr [rcx + 0xbf0]`

### fn 0x30F50B0..0x30F5132 (0x82 B)

  - `0x30F50CA` **CMP** (4B): `cmp edx, dword ptr [rcx + 0xbf0]`

### fn 0x30F7440..0x30F746B (0x2b B)

  - `0x30F7451` **READ** (4B): `mov eax, dword ptr [rcx + 0xbf0]`

### fn 0x30F746B..0x30F7652 (0x1e7 B)

  - `0x30F74C2` **READ** (4B): `movsxd ebp, dword ptr [rdi + 0xbf0]`
  - `0x30F758F` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], ebp`

### fn 0x3108FC2..0x3108FF2 (0x30 B)

  - `0x3108FE4` **READ** (4B): `movsxd edi, dword ptr [rsi + 0xbf0]`

### fn 0x3108FF2..0x31090E6 (0xf4 B)

  - `0x31090DB` **WRITE** (4B): `mov dword ptr [rsi + 0xbf0], ebp`

### fn 0x310A0C0..0x310A0D8 (0x18 B)

  - `0x310A0D0` **CMP** (4B): `cmp edx, dword ptr [rcx + 0xbf0]`

### fn 0x3110F60..0x311100E (0xae B)

  - `0x3110F80` **CMP** (4B): `cmp edx, dword ptr [rcx + 0xbf0]`

### fn 0x3129C20..0x3129CF9 (0xd9 B)

  - `0x3129C99` **READ** (4B): `movsxd ecx, dword ptr [rsi + 0xbf0]`

### fn 0x3129D90..0x3129E4B (0xbb B)

  - `0x3129E0A` **CMP** (4B): `cmp eax, dword ptr [rbp + 0xbf0]`

### fn 0x312B770..0x312B84A (0xda B)

  - `0x312B7E9` **CMP** (4B): `cmp eax, dword ptr [rsi + 0xbf0]`

### fn 0x312C530..0x312C60F (0xdf B)

  - `0x312C5A0` **CMP** (4B): `cmp eax, dword ptr [rsi + 0xbf0]`

### fn 0x31A0010..0x31A02DA (0x2ca B)

  - `0x31A0255` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], 7`

### fn 0x3319F40..0x331D823 (0x38e3 B)

  - `0x331BE02` **WRITE** (1B): `mov byte ptr [rbp + 0xbf0], al`

### fn 0x3405D10..0x3405D34 (0x24 B)

  - `0x3405D2E` **WRITE** (4B): `mov dword ptr [rbp + 0xbf0], eax`

### fn 0x3405EAE..0x3405FA0 (0xf2 B)

  - `0x3405F88` **READ** (4B): `mov ecx, dword ptr [rbp + 0xbf0]`

### fn 0x3596C00..0x3596FF1 (0x3f1 B)

  - `0x3596EB6` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], esi`

### fn 0x3597940..0x3597B75 (0x235 B)

  - `0x35979DB` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], 0`

### fn 0x3665760..0x3665EB8 (0x758 B)

  - `0x36658FD` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], esi`

### fn 0x369248C..0x3692580 (0xf4 B)

  - `0x36924B3` **READ** (4B): `lea ebp, [rbx + 0xbf0]`

### fn 0x36AE950..0x36AEA64 (0x114 B)

  - `0x36AEA51` **READ** (8B): `call qword ptr [rax + 0xbf0]`

### fn 0x36D7F54..0x36D9CBB (0x1d67 B)

  - `0x36D9536` **WRITE** (4B): `sub dword ptr [rbp + 0xbf0], ebx`

### fn 0x3823020..0x3823215 (0x1f5 B)

  - `0x382316A` **WRITE** (4B): `mov dword ptr [rbx + 0xbf0], edi`

### fn 0x3827AE1..0x3827CD9 (0x1f8 B)

  - `0x3827C1F` **READ** (16B): `maxps xmm1, xmmword ptr [rdi + 0xbf0]`
  - `0x3827C30` **READ** (4B): `adc dword ptr [rdi + 0xbf0], ecx`

### fn 0x3827E81..0x3828261 (0x3e0 B)

  - `0x382815C` **READ** (16B): `maxps xmm1, xmmword ptr [rdi + 0xbf0]`
  - `0x3828178` **READ** (4B): `adc dword ptr [rdi + 0xbf0], ecx`

### fn 0x3829140..0x3829549 (0x409 B)

  - `0x38293D4` **READ** (4B): `adc dword ptr [rsi + 0xbf0], eax`
  - `0x38293EA` **READ** (1B): `adc byte ptr [rsi + 0xbf0], cl`

### fn 0x382EADF..0x382EC95 (0x1b6 B)

  - `0x382EB60` **READ** (1B): `adc byte ptr [rcx + 0xbf0], dh`

### fn 0x382F367..0x382F3C6 (0x5f B)

  - `0x382F38D` **READ** (4B): `adc dword ptr [rsi + 0xbf0], eax`
  - `0x382F3A3` **READ** (1B): `adc byte ptr [rsi + 0xbf0], cl`

### fn 0x3871286..0x3871764 (0x4de B)

  - `0x38716B8` **READ** (16B): `maxps xmm1, xmmword ptr [rdi + 0xbf0]`
  - `0x38716C9` **READ** (4B): `adc dword ptr [rdi + 0xbf0], ecx`

### fn 0x387D8E9..0x387DA51 (0x168 B)

  - `0x387D9C6` **READ** (8B): `call qword ptr [rax + 0xbf0]`

### fn 0x389CE80..0x389D264 (0x3e4 B)

  - `0x389CF5A` **READ** (8B): `call qword ptr [rax + 0xbf0]`

### fn 0x392F460..0x3938E81 (0x9a21 B)

  - `0x3931E32` **WRITE** (1B): `mov byte ptr [rbp + 0xbf0], al`

### fn 0x3C516B0..0x3C55480 (0x3dd0 B)

  - `0x3C53572` **WRITE** (1B): `mov byte ptr [rbp + 0xbf0], al`

### fn 0x3C65860..0x3C65920 (0xc0 B)

  - `0x3C658FB` **READ** (8B): `call qword ptr [rax + 0xbf0]`

### fn 0x4724410..0x4725D09 (0x18f9 B)

  - `0x472498D` **WRITE** (4B): `sub dword ptr [rbp + 0xbf0], eax`
  - `0x47249A4` **READ** (4B): `lea eax, [rbp + 0xbf0]`

### fn 0x472B320..0x4731D04 (0x69e4 B)

  - `0x472B4C1` **WRITE** (4B): `mov dword ptr [rbp + 0xbf0], eax`

### fn 0x4832F40..0x4835D3A (0x2dfa B)

  - `0x48341DF` **WRITE** (1B): `mov byte ptr [rbp + 0xbf0], dh`

### fn 0x483CF90..0x48411F3 (0x4263 B)

  - `0x484052F` **WRITE** (4B): `mov dword ptr [rbp + 0xbf0], esi`

### fn 0x48418A0..0x4845727 (0x3e87 B)

  - `0x4844A0A` **WRITE** (1B): `mov byte ptr [rbp + 0xbf0], dh`

### fn 0x4845730..0x484A195 (0x4a65 B)

  - `0x4849B23` **WRITE** (4B): `mov dword ptr [rbp + 0xbf0], edi`

### fn 0x484F3B0..0x4853D4B (0x499b B)

  - `0x4853886` **WRITE** (4B): `mov dword ptr [rbp + 0xbf0], edi`

### fn 0x48570B0..0x485D8A3 (0x67f3 B)

  - `0x4858495` **WRITE** (4B): `mov dword ptr [rbp + 0xbf0], esi`

### fn 0x485D8B0..0x48628CF (0x501f B)

  - `0x4861D18` **WRITE** (4B): `mov dword ptr [rbp + 0xbf0], esi`
  - `0x4861D2F` **READ** (4B): `lea edx, [rbp + 0xbf0]`
  - `0x4861E62` **READ** (4B): `mov ecx, dword ptr [rbp + 0xbf0]`

### fn 0x4864170..0x48668CD (0x275d B)

  - `0x48664A4` **WRITE** (4B): `mov dword ptr [rbp + 0xbf0], edi`

### fn 0x4869050..0x486B618 (0x25c8 B)

  - `0x486B46A` **WRITE** (1B): `mov byte ptr [rbp + 0xbf0], ah`

### fn 0x486B620..0x486DA25 (0x2405 B)

  - `0x486D75B` **WRITE** (4B): `mov dword ptr [rbp + 0xbf0], ebp`

### fn 0x4887C50..0x4889683 (0x1a33 B)

  - `0x48880ED` **WRITE** (4B): `sub dword ptr [rbp + 0xbf0], eax`

### fn 0x4916340..0x49181AE (0x1e6e B)

  - `0x49170C9` **WRITE** (4B): `mov dword ptr [rbp + 0xbf0], esp`

### fn 0x4943840..0x4943C8E (0x44e B)

  - `0x4943921` **WRITE** (4B): `mov dword ptr [rbx + 0xbf0], esi`

### fn 0x49544FE..0x4954AFD (0x5ff B)

  - `0x49549F4` **WRITE** (4B): `mov dword ptr [rbx + 0xbf0], ebp`

### fn 0x4AC2650..0x4AC3102 (0xab2 B)

  - `0x4AC302D` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], ebp`

### fn 0x4AF2200..0x4AF3B0A (0x190a B)

  - `0x4AF2D83` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], esi`

### fn 0x52C6110..0x52CA059 (0x3f49 B)

  - `0x52C7C58` **WRITE** (1B): `mov byte ptr [rbp + 0xbf0], al`

### fn 0x53595C0..0x5359866 (0x2a6 B)

  - `0x53596D4` **READ** (4B): `mov ecx, dword ptr [rbx + 0xbf0]`

### fn 0x53C7EA0..0x53C80EE (0x24e B)

  - `0x53C7F06` **READ** (4B): `lea ecx, [rdi + 0xbf0]`

### fn 0x559E180..0x559EF51 (0xdd1 B)

  - `0x559E584` **WRITE** (4B): `mov dword ptr [rsi + 0xbf0], ebp`

### fn 0x56777B0..0x5677EE2 (0x732 B)

  - `0x5677BD8` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], ecx`

### fn 0x5679D50..0x5679DC5 (0x75 B)

  - `0x5679DB2` **READ** (4B): `adc dword ptr [rcx + 0xbf0], ecx`

### fn 0x5679E80..0x5679EF8 (0x78 B)

  - `0x5679EB0` **READ** (1B): `adc byte ptr [rcx + 0xbf0], cl`

### fn 0x58C7240..0x58C7590 (0x350 B)

  - `0x58C7455` **READ** (4B): `lea ecx, [rdi + 0xbf0]`

### fn 0x58CA614..0x58CB0D5 (0xac1 B)

  - `0x58CAF9A` **CMP** (4B): `cmp dword ptr [rbp + 0xbf0], 0`

### fn 0x58CCAB5..0x58CCB2B (0x76 B)

  - `0x58CCAC1` **READ** (4B): `lea edi, [rcx + 0xbf0]`

### fn 0x58F1350..0x58F142B (0xdb B)

  - `0x58F136E` **READ** (4B): `movsxd ebx, dword ptr [rdi + 0xbf0]`

### fn 0x58F1430..0x58F14DF (0xaf B)

  - `0x58F1459` **READ** (4B): `mov edx, dword ptr [rbx + 0xbf0]`

### fn 0x5BCAEA0..0x5BCB03B (0x19b B)

  - `0x5BCAFC2` **WRITE** (4B): `mov dword ptr [rbx + 0xbf0], eax`

### fn 0x5C08B40..0x5C08C0B (0xcb B)

  - `0x5C08B69` **READ** (4B): `lea eax, [rcx + 0xbf0]`

### fn 0x5C0E890..0x5C0EA49 (0x1b9 B)

  - `0x5C0EA26` **READ** (4B): `lea ecx, [rbp + 0xbf0]`

### fn 0x63F53F0..0x63F5681 (0x291 B)

  - `0x63F5496` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], esi`

### fn 0x63F5690..0x63F59A7 (0x317 B)

  - `0x63F5747` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], esi`

### fn 0x63F59B0..0x63F5D6D (0x3bd B)

  - `0x63F5A64` **WRITE** (4B): `mov dword ptr [rdi + 0xbf0], esi`

### fn 0x6F057F0..0x6F0582A (0x3a B)

  - `0x6F0581A` **READ** (4B): `lea ecx, [rip + 0xbf0]`

### fn 0x6F85B1F..0x6F86D00 (0x11e1 B)

  - `0x6F865C9` **READ** (4B): `mov edx, dword ptr [rbx + 0xbf0]`
  - `0x6F866BE` **READ** (4B): `mov edx, dword ptr [rbx + 0xbf0]`

### fn 0x6FAEBE0..0x6FAECE2 (0x102 B)

  - `0x6FAEC2A` **WRITE** (4B): `mov dword ptr [rbx + 0xbf0], edi`
  - `0x6FAEC7E` **WRITE** (4B): `mov dword ptr [rbx + 0xbf0], eax`

### fn 0x6FAF0F0..0x6FAF1A5 (0xb5 B)

  - `0x6FAF140` **WRITE** (4B): `mov dword ptr [rbx + 0xbf0], eax`

### fn 0xF626D0..0xF64060 (0x1990 B)

  - `0xF639AC` **WRITE** (4B): `mov dword ptr [rbp + 0xbf0], eax`

### fn NO_PDATA

  - `0x1EED3B2` **WRITE** (4B): `mov dword ptr [rcx + 0xbf0], eax`
  - `0x30EFEC8` **READ** (4B): `movsxd ecx, dword ptr [rcx + 0xbf0]`
  - `0x30F05A0` **READ** (4B): `mov eax, dword ptr [rcx + 0xbf0]`
  - `0x312A135` **READ** (4B): `mov eax, dword ptr [rcx + 0xbf0]`
  - `0x366773B` **READ** (8B): `jmp qword ptr [rax + 0xbf0]`
  - `0x36A1951` **READ** (1B): `adc byte ptr [rcx + 0xbf0], al`
  - `0x36A197B` **READ** (4B): `adc dword ptr [rcx + 0xbf0], esp`
  - `0x388629A` **WRITE** (4B): `sub dword ptr [rbp + 0xbf0], esp`
  - `0x553D11B` **WRITE** (4B): `mov dword ptr [rbp + 0xbf0], 0`
  - `0x7326008` **READ** (16B): `andnps xmm1, xmmword ptr [rdx + 0xbf0]`
  - `0x732601A` **READ** (4B): `adc dword ptr [rdx + 0xbf0], eax`

## Functions accessing multiple state-tracker offsets

  - fn `0x1265DF0..0x127BAB0` (0x15cc0 B) touches 7 offsets: 0xBEC, 0xBF0, 0xBF4, 0xBF8, 0xBFC, 0xC04, 0xC0C
  - fn `0x127BAB0..0x128E530` (0x12a80 B) touches 7 offsets: 0xBEC, 0xBF0, 0xBF4, 0xBF8, 0xBFC, 0xC04, 0xC0C
  - fn `0x31A0010..0x31A02DA` (0x2ca B) touches 6 offsets: 0xBEC, 0xBF0, 0xBF4, 0xBFC, 0xC04, 0xC0C
  - fn `0x56777B0..0x5677EE2` (0x732 B) touches 6 offsets: 0xBEC, 0xBF0, 0xBF4, 0xBF8, 0xBFC, 0xC04
  - fn `0x5679D50..0x5679DC5` (0x75 B) touches 5 offsets: 0xBF0, 0xBF4, 0xBF8, 0xBFC, 0xC0D
  - fn `0x5679E80..0x5679EF8` (0x78 B) touches 5 offsets: 0xBF0, 0xBF4, 0xBF8, 0xBFC, 0xC0D
  - fn `0x2616680..0x261DA12` (0x7392 B) touches 4 offsets: 0xBEC, 0xBF4, 0xBF8, 0xBFC
  - fn `0x4AF2200..0x4AF3B0A` (0x190a B) touches 4 offsets: 0xBF0, 0xBF8, 0xBFC, 0xC04
  - fn `0x5679DF7..0x5679E60` (0x69 B) touches 4 offsets: 0xBEC, 0xC04, 0xC0C, 0xC0D
  - fn `0x5679F2C..0x5679F98` (0x6c B) touches 4 offsets: 0xBEC, 0xC04, 0xC0C, 0xC0D
  - fn `0x21A289B..0x21A2A31` (0x196 B) touches 3 offsets: 0xBF0, 0xBF4, 0xBF8
  - fn `0x273934B..0x2739692` (0x347 B) touches 3 offsets: 0xBEC, 0xBF0, 0xBF4
  - fn `0x276E0C1..0x276F52B` (0x146a B) touches 3 offsets: 0xBEC, 0xBF0, 0xBF4
  - fn `0x2DA8BDA..0x2DA8DAE` (0x1d4 B) touches 3 offsets: 0xBF0, 0xBF8, 0xBFC
  - fn `0x3827AE1..0x3827CD9` (0x1f8 B) touches 3 offsets: 0xBF0, 0xBF8, 0xC0C
  - fn `0x3871286..0x3871764` (0x4de B) touches 3 offsets: 0xBF0, 0xBF8, 0xC0C
  - fn `0xF626D0..0xF64060` (0x1990 B) touches 2 offsets: 0xBF0, 0xBF8
  - fn `0x128E530..0x1298456` (0x9f26 B) touches 2 offsets: 0xBF0, 0xBF8
  - fn `0x13969A0..0x13B9981` (0x22fe1 B) touches 2 offsets: 0xBF0, 0xBF8
  - fn `0x1434AA0..0x143B7F6` (0x6d56 B) touches 2 offsets: 0xBF0, 0xBF8
  - fn `0x148CAFA..0x14976A3` (0xaba9 B) touches 2 offsets: 0xBF0, 0xBF8
  - fn `0x14CAD61..0x14D85FB` (0xd89a B) touches 2 offsets: 0xBF0, 0xBF8
  - fn `0x1BB8907..0x1BB89CE` (0xc7 B) touches 2 offsets: 0xBF0, 0xBF8
  - fn `0x1D8A620..0x1D8A6F9` (0xd9 B) touches 2 offsets: 0xBF0, 0xBF4
  - fn `0x1D94500..0x1D94B2C` (0x62c B) touches 2 offsets: 0xBF0, 0xBF4
  - fn `0x2100F80..0x2101349` (0x3c9 B) touches 2 offsets: 0xBF0, 0xBF8
  - fn `0x2101D50..0x210223B` (0x4eb B) touches 2 offsets: 0xBF0, 0xBF8
  - fn `0x21A2720..0x21A2879` (0x159 B) touches 2 offsets: 0xBF8, 0xC04
  - fn `0x236A690..0x236AF08` (0x878 B) touches 2 offsets: 0xBF0, 0xBF8
  - fn `0x236AF10..0x236B6C7` (0x7b7 B) touches 2 offsets: 0xBF0, 0xBF8


**Summary:** enumerated across 435 accesses; 205 distinct functions touch these offsets; 72 touch multiple.

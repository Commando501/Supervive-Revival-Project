# LANE 5 — the crashpad minidump corpus, mined

All results OFFLINE, read-only, zero launches, zero injections. Tools in `scratchpad/s133/tools/`.

| file | what it holds |
|---|---|
| `md_sweep.tsv` | one row per distinct crashpad report (124), 48 columns — the base table everything else reads |
| `SUMMARY-NUMBERS.txt` | every headline count re-derived from the TSV |
| `q1_killregion.txt` | Q1 kill-region census + ntdll positive control |
| `q1b_dualmap.txt` | the two hidden `runtime.dll` mappings, region-for-region |
| `q1c_hidden_images.txt` | census of every MEM_IMAGE allocation absent from the ModuleList |
| `q1d_shadow_exe.txt` | the hidden second mapping of the game exe |
| `q2_bootsessions.txt` | Q2 — 3 boot sessions, 6 independent controls, kill-address constancy |
| `q3_faultcensus.txt` | Q3 — full fault census at FILE and REPORT units, DEATH/untagged pairing measured |
| `q4_textpagemap.txt` | the `.text` demand-decryption bitmap from MemoryInfoList |
| `text_pages_crashonly.txt` | 41 `.text` pages decrypted in a crash but all-zero in `merged6` (29 RVA runs) |
| `q5_killstack.txt`, `q5b_killthread.txt` | the crashing stack — the kill is a fresh thread |
| `q6_protector_threads.txt` | register census (n=108) + raw stack hits |
| `q7_validated_returns.txt`, `runtime_dll_live_callsites.txt` | 84 validated live protector call-site RVAs |
| `q8_regs_and_ranking.txt` | register identities; reports ranked by novel `.text` pages |
| `q9_constant_hunt.txt`, `q9b_537ac9e1_sites.txt` | `0x537AC9E1` located: 27 sites, all `packer1` |
| `q10_syscall_decode.txt`, `q10b_syscall_decode.txt` | the syscall-number obfuscation formula |
| `q11_80f7f0.txt` | FK-10's kill primitive fully decoded |
| `q12_syscall_table.txt`, `runtime_syscall_sites.tsv` | the protector's 17-cell syscall table, 4/4 controls at zero |
| `q13_ssn_solve.txt` | the offline SSN solve — REFUTED, with the reason measured |
| `q14_threads.txt` | thread names; 5 unnamed protector-dominated worker threads |
| `runtime_dll_pe.txt` | `runtime.dll` PE headers (the identification key) |

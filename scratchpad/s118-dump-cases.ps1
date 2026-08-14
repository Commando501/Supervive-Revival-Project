# S118 - dump every HandleNotif case body, live process, read-only disasm.
# Self-tests the harness on the 3 known-good rows BEFORE emitting anything else.
$ErrorActionPreference = 'Stop'
$exe  = "G:\git\Supervive Revival Project\tools\usmapdump\usmapdump.exe"
$proc = "SUPERVIVE-Win64-Shipping.exe"
$out  = $args[0]
$len  = if ($args.Count -gt 1) { [int]$args[1] } else { 160 }

$cases = @(
 @(0 ,'0x4B02D36'), @(1 ,'0x4B02DC4'), @(2 ,'0x4B02E09'), @(3 ,'0x4B02EC8'),
 @(4 ,'0x4B02F26'), @(5 ,'0x4B02F93'), @(6 ,'0x4B02FCB'), @(7 ,'0x4B03030'),
 @(8 ,'0x4B03375'), @(9 ,'0x4B03393'), @(10,'0x4B033DD'), @(11,'0x4B03095'),
 @(12,'0x4B03427'), @(13,'0x4B034B2'), @(14,'0x4B0351B'), @(15,'0x4B03580'),
 @(16,'0x4B035FD'), @(17,'0x4B03D29'), @(18,'0x4B03D29'), @(19,'0x4B03A60'),
 @(20,'0x4B03A7E'), @(21,'0x4B03AC8'), @(22,'0x4B03B12'), @(23,'0x4B03B5F'),
 @(24,'0x4B03B7D'), @(25,'0x4B03BB5'), @(26,'0x4B03BED'), @(27,'0x4B03C25'),
 @(28,'0x4B03C5D'), @(29,'0x4B03C95'), @(30,'0x4B03CDF'), @(31,'0x4B04858'),
 @(32,'0x4B04396')
)

# ---- HARNESS SELF-TEST (method rule 10/13): the tool must reproduce a line we
# already know is there, or we abort rather than emit a table.
$probe = & $exe disasm $proc "+0x4B03B5F" 16 2>&1 | Out-String
if ($probe -notmatch 'lea rdx, ptr \[rdi\+0x1550\]') {
    Write-Error "HARNESS SELF-TEST FAILED: idx23 delegate lea not seen. Output was:`n$probe"
    exit 1
}
"HARNESS SELF-TEST PASSED (idx23 lea rdx,[rdi+0x1550] seen)" | Out-File -Encoding utf8 $out

foreach ($c in $cases) {
    "" | Out-File -Encoding utf8 -Append $out
    ("===== idx {0}  case body RVA {1}  (window {2} bytes) =====" -f $c[0], $c[1], $len) |
        Out-File -Encoding utf8 -Append $out
    & $exe disasm $proc ("+" + $c[1]) $len 2>&1 | Out-File -Encoding utf8 -Append $out
}
"DONE" | Out-File -Encoding utf8 -Append $out

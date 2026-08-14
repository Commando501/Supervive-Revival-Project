# S118 - decode the runtime TMap<FString,uint8> of notif type names at .data 0x9FFE2D0
# into an enum-value -> type-name map.  Read-only RPM (peek) against the live process.
$ErrorActionPreference = 'Stop'
$exe  = "G:\git\Supervive Revival Project\tools\usmapdump\usmapdump.exe"
$proc = "SUPERVIVE-Win64-Shipping.exe"

function PeekBytes([string]$va, [int]$n) {
    $txt = & $exe peek $proc $va $n 2>&1
    $bytes = New-Object System.Collections.Generic.List[byte]
    foreach ($l in $txt) {
        if ($l -match '^\s+[0-9A-F]{6,16}\s+((?:[0-9A-F]{2} )+)') {
            foreach ($h in ($matches[1].Trim() -split ' ')) { $bytes.Add([Convert]::ToByte($h,16)) }
        }
    }
    return ,$bytes.ToArray()
}

# --- HARNESS SELF-TEST: the parser must recover a value we already know.
# 0x9FFE6F0 is an FString{Data,Num=8,Max=8} whose buffer is "dsNotif" (confirmed
# live earlier this session).  If the hex parser is broken this fails loudly
# instead of printing an empty/garbage map.
$probe = PeekBytes "+0x9FFE6F0" 16
if ($probe.Length -ne 16) { throw "SELF-TEST FAILED: parser returned $($probe.Length) bytes, expected 16" }
$pnum = [BitConverter]::ToInt32($probe, 8)
if ($pnum -ne 8) { throw "SELF-TEST FAILED: expected Num=8 at 0x9FFE6F0, got $pnum" }
$pptr = [BitConverter]::ToUInt64($probe, 0)
$pbuf = PeekBytes ("0x{0:X}" -f $pptr) 16
$pstr = [Text.Encoding]::Unicode.GetString($pbuf).TrimEnd([char]0)
if ($pstr -ne 'dsNotif') { throw "SELF-TEST FAILED: expected 'dsNotif', got '$pstr'" }
Write-Output "SELF-TEST PASSED (0x9FFE6F0 -> 'dsNotif')`n"

# TMap header: Data ptr @+0x0, Num @+0x8, Max @+0xC
$hdr  = PeekBytes "+0x9FFE2D0" 16
$data = [BitConverter]::ToUInt64($hdr,0)
$num  = [BitConverter]::ToInt32($hdr,8)
Write-Output ("TMap data=0x{0:X} Num={1}" -f $data, $num)

$STRIDE = 32   # TSetElement<TTuple<FString,uint8>> in a TSparseArray
$rows = @()
for ($i=0; $i -lt $num; $i++) {
    $ea = $data + ($i * $STRIDE)
    $e  = PeekBytes ("0x{0:X}" -f $ea) $STRIDE
    $sp = [BitConverter]::ToUInt64($e,0)
    $sn = [BitConverter]::ToInt32($e,8)
    $val = $e[16]
    if ($sn -le 0 -or $sn -gt 128 -or $sp -eq 0) { $rows += [pscustomobject]@{ Slot=$i; Enum='?'; Name="<unparsed ptr=0x$('{0:X}' -f $sp) num=$sn>" }; continue }
    $b = PeekBytes ("0x{0:X}" -f $sp) ($sn*2)
    $s = [Text.Encoding]::Unicode.GetString($b).TrimEnd([char]0)
    $rows += [pscustomobject]@{ Slot=$i; Enum=$val; JumpIdx=($val-1); Name=$s }
}
$rows | Format-Table -AutoSize | Out-String -Width 200

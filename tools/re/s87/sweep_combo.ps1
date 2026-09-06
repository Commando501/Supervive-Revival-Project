# S88 combo sweep: test (postbits,paybits) PAIRS to see if aligning the header (postbits) AND the payload
# (paybits) TOGETHER reads cleanly. Pairs are "post:pay" strings. seed=151, injectbits=11.
# Usage:  .\tools\re\s87\sweep_combo.ps1 -Pairs "5:-16","5:-8","5:8","5:16"
param([string[]]$Pairs = @("5:-16","5:-8","5:8","5:16"), [int]$Seed = 151, [int]$Poll = 175)
$repo = 'G:\git\Supervive Revival Project'
"" | Out-File C:\Temp\SweepResults.txt
foreach($p in $Pairs){
  $parts = $p.Split(':'); $post=[int]$parts[0]; $pay=[int]$parts[1]
  & "$repo\tools\re\s87\sweep_seed.ps1" -Seed $Seed -PostBits $post -PayBits $pay -PayAt 25 -InjectBits 11 -PollSeconds $Poll *> "C:\Temp\combo_${post}_${pay}.console.log"
}
"=== COMBO SWEEP DONE ($($Pairs -join ' ')) ===" | Tee-Object -FilePath C:\Temp\SweepResults.txt -Append

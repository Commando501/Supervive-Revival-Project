# S88 multi-value POST-STABLE inject sweep. Runs a full DS cycle for each -postbits value in $PostList
# (fixed injectbits=11, seed=151) and accumulates clean summaries in C:\Temp\SweepResults.txt.
# Usage (elevated, Steam up):  .\tools\re\s87\sweep_post.ps1 -PostList 8,1,16,32
param([int[]]$PostList = @(8,1,16,32), [int]$Seed = 151, [int]$Poll = 190)
$repo = 'G:\git\Supervive Revival Project'
"" | Out-File C:\Temp\SweepResults.txt
foreach($m in $PostList){
  & "$repo\tools\re\s87\sweep_seed.ps1" -Seed $Seed -PostBits $m -InjectBits 11 -PollSeconds $Poll *> "C:\Temp\post_$m.console.log"
}
"=== POST SWEEP DONE ($($PostList -join ',')) ===" | Tee-Object -FilePath C:\Temp\SweepResults.txt -Append

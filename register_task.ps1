# Registers a Windows Scheduled Task that runs the daily brief every weekday morning.
# Run ONCE from this folder (change the time if you like):
#     powershell -ExecutionPolicy Bypass -File register_task.ps1 -Time "06:45"
#
# Pick a morning time AFTER the US pre-market data is meaningful (the brief is built on
# US index futures + the prior session's gamma). Anything ~6-9 AM ET works for a draft
# you'll review before publishing. -StartWhenAvailable catches up if the PC was off.

param([string]$Time = "06:45")

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat  = Join-Path $here "run_brief.bat"
if (-not (Test-Path $bat)) { Write-Error "run_brief.bat not found next to this script"; exit 1 }

$action   = New-ScheduledTaskAction -Execute $bat
$trigger  = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName "DailyBrief" -Action $action -Trigger $trigger -Settings $settings `
  -Description "Daily market brief -> Substack draft" -Force | Out-Null

Write-Output "Registered task 'DailyBrief' for weekdays at $Time."
Write-Output "Test it now:   Start-ScheduledTask -TaskName DailyBrief"
Write-Output "Check the log: out\run.log   (and your Substack drafts)"
Write-Output "Remove it:     Unregister-ScheduledTask -TaskName DailyBrief -Confirm:`$false"

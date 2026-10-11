# DharmaFlow AI — Register Daily Windows Scheduled Task
# Run as Administrator or normal user (for current user task)

param (
    [string]$TaskName = "DharmaFlowAI_DailyAutomation",
    [string]$DailyTime = "06:30AM"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$pythonExe = (Get-Command python).Source

if (-not $pythonExe) {
    Write-Error "Python executable not found in PATH."
    exit 1
}

$action = New-ScheduledTaskAction -Execute $pythonExe -Argument "-m app run-daily" -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $DailyTime
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

try {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "DharmaFlow AI daily video automation pipeline" -Force
    Write-Host "Successfully registered scheduled task '$TaskName' to run daily at $DailyTime." -ForegroundColor Green
    Write-Host "Working Directory: $projectRoot"
} catch {
    Write-Error "Failed to register scheduled task: $_"
}

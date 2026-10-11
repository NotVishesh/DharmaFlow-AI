# DharmaFlow AI — Unregister Daily Windows Scheduled Task

param (
    [string]$TaskName = "DharmaFlowAI_DailyAutomation"
)

try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
    Write-Host "Successfully unregistered scheduled task '$TaskName'." -ForegroundColor Green
} catch {
    Write-Warning "Scheduled task '$TaskName' does not exist or could not be removed: $_"
}

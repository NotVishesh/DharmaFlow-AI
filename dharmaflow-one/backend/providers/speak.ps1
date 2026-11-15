param([string]$TextPath, [string]$OutputPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $speaker.SetOutputToWaveFile($OutputPath)
    $speaker.Speak([System.IO.File]::ReadAllText($TextPath))
} finally {
    $speaker.Dispose()
}

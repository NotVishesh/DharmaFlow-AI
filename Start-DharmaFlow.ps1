# Windows 10/11 setup and launcher; all paths are relative to this script.
[CmdletBinding()]
param([switch]$SkipModels, [switch]$NoLaunch, [switch]$SkipSystemInstall)
$ErrorActionPreference = 'Stop'
$projectDir = Join-Path $PSScriptRoot 'dharmaflow-one'
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User') + ';' + $env:Path
}
function Run-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed (exit $LASTEXITCODE). Fix the error and rerun this command." }
}
function Ensure-Tool([string]$Command, [string]$Package) {
    if (Get-Command $Command -ErrorAction SilentlyContinue) { return }
    if ($SkipSystemInstall) { throw "Missing $Command. Install $Package first." }
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) { throw 'Install Microsoft App Installer (winget), then rerun.' }
    Run-Checked 'winget.exe' @('install','--id',$Package,'--exact','--source','winget','--accept-package-agreements','--accept-source-agreements','--disable-interactivity')
    Refresh-Path
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) { throw "$Command was installed. Open a new terminal and rerun." }
}
Refresh-Path
Ensure-Tool 'git.exe' 'Git.Git'
Ensure-Tool 'node.exe' 'OpenJS.NodeJS.LTS'
Ensure-Tool 'ffmpeg.exe' 'Gyan.FFmpeg'
Ensure-Tool 'ollama.exe' 'Ollama.Ollama'
$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $py)) {
    $python312 = $null
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        $candidate = & py.exe -3.12 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0) { $python312 = $candidate }
    }
    if (-not $python312 -and (Get-Command python.exe -ErrorAction SilentlyContinue)) {
        $candidate = & python.exe -c 'import sys; print(sys.executable if sys.version_info[:2] == (3,12) else "")'
        if ($LASTEXITCODE -eq 0 -and $candidate) { $python312 = $candidate }
    }
    if (-not $python312) {
        if ($SkipSystemInstall) { throw 'Python 3.12 is required.' }
        Run-Checked 'winget.exe' @('install','--id','Python.Python.3.12','--exact','--source','winget','--accept-package-agreements','--accept-source-agreements','--disable-interactivity')
        Refresh-Path
        $python312 = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
        if (-not (Test-Path -LiteralPath $python312)) { throw 'Python installed. Open a new terminal and rerun.' }
    }
    Run-Checked $python312 @('-m','venv',(Join-Path $PSScriptRoot '.venv'))
}
Push-Location -LiteralPath $projectDir
try {
    $requirements = @('backend/requirements.txt','backend/requirements-video.txt','backend/requirements-lipsync.txt','backend/requirements-desktop.txt','backend/requirements-windows.lock')
    $fingerprint = ($requirements | ForEach-Object { (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash }) -join ''
    $marker = Join-Path $PSScriptRoot '.venv\dharmaflow-dependencies.txt'
    if (-not (Test-Path -LiteralPath $marker) -or (Get-Content -Raw -LiteralPath $marker).Trim() -ne $fingerprint) {
        Run-Checked $py @('-m','pip','install','--upgrade','pip')
        Run-Checked $py @('-m','pip','install','torch==2.5.1','torchvision==0.20.1','torchaudio==2.5.1','--index-url','https://download.pytorch.org/whl/cu121')
        Run-Checked $py @('-m','pip','install','-c','backend/requirements-windows.lock','-r','backend/requirements.txt','-r','backend/requirements-video.txt','-r','backend/requirements-lipsync.txt','-r','backend/requirements-desktop.txt')
        Run-Checked $py @('-m','pip','check')
        Set-Content -LiteralPath $marker -Value $fingerprint
    }
    if (-not (Test-Path -LiteralPath 'backend/.env')) { Copy-Item -LiteralPath 'backend/.env.example' -Destination 'backend/.env' }
    $npmMarker = 'node_modules/.dharmaflow-lock'
    $npmHash = (Get-FileHash package-lock.json -Algorithm SHA256).Hash
    if (-not (Test-Path $npmMarker) -or (Get-Content -Raw $npmMarker).Trim() -ne $npmHash) {
        Run-Checked 'npm.cmd' @('ci')
        Set-Content $npmMarker $npmHash
    }
    $ollamaReady = $false
    try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3; $ollamaReady = $true } catch {}
    if (-not $ollamaReady) {
        Start-Process -FilePath (Get-Command ollama.exe).Source -ArgumentList 'serve' -WindowStyle Hidden
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2; $ollamaReady = $true; break } catch { Start-Sleep -Seconds 1 }
        }
        if (-not $ollamaReady) { throw 'Ollama did not start on port 11434.' }
    }
    if (-not $SkipModels) { Run-Checked $py @('-m','backend.scripts.bootstrap_models') }
    Run-Checked $py @('-m','backend.scripts.check_install')
    Run-Checked 'npm.cmd' @('run','build')
    if (-not $NoLaunch) { Run-Checked 'npm.cmd' @('start') }
} finally { Pop-Location }

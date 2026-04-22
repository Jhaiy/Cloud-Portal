Write-Host "Checking for Playit.gg client..." -ForegroundColor Cyan

$playit_check = Get-Command playit -ErrorAction SilentlyContinue

if ($playit_check) {
    Write-Host "Playit.gg client is installed. Running..." -ForegroundColor Green
} else {
  Write-Host "Playit.gg client not found. Installing..." -ForegroundColor Yellow
  winget install DevelopedMethods.playit --accept-source-agreements --accept-package-agreements --silent
}
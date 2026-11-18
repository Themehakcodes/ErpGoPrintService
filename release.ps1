<#
.SYNOPSIS
    1-Click Release Script for KCSM Print Service.
.DESCRIPTION
    1. Validates semantic version (X.Y.Z)
    2. Runs unit tests (aborts on failure)
    3. Updates core/version.py
    4. Commits, creates annotated git tag vX.Y.Z, and pushes main + tag to GitHub
    5. GitHub Actions automatically builds the Windows .exe + Setup Wizard and publishes the Release!
.EXAMPLE
    .\release.ps1 -Version 1.2.0 -Notes "Added Printed By column and busy progress bar"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Version,

    [Parameter(Mandatory = $false)]
    [string]$Notes = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1. Validate semantic version format (e.g. 1.2.0)
$CleanVersion = $Version.Trim().TrimStart("v", "V")
if ($CleanVersion -notmatch '^\d+\.\d+\.\d+$') {
    Write-Error "Invalid version '$Version'. Use semantic format X.Y.Z (e.g. 1.1.0 or 1.2.0)."
    exit 1
}
$Tag = "v$CleanVersion"

# 2. Verify git repository & remote
if (-not (Test-Path ".git")) {
    Write-Error "Git is not initialized yet. Run initial git init / remote add first (see README)."
    exit 1
}

# Check tag does not already exist
$existingTag = git tag -l $Tag
if ($existingTag) {
    Write-Error "Tag $Tag already exists! Pick a newer version number."
    exit 1
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Releasing KCSM Print Service $Tag" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 3. Update core/version.py
$versionFile = Join-Path $PSScriptRoot "core\version.py"
$content = Get-Content $versionFile -Raw
$updated = $content -replace 'APP_VERSION\s*=\s*"[^"]+"', "APP_VERSION = `"$CleanVersion`""
Set-Content -Path $versionFile -Value $updated -Encoding utf8 -NoNewline
Write-Host "[1/4] Updated core/version.py -> APP_VERSION = $CleanVersion" -ForegroundColor Green

# 4. Run unit tests before tagging
Write-Host "[2/4] Running unit tests..." -ForegroundColor Yellow
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) {
    Write-Error "Unit tests failed! Release aborted."
    exit 1
}
Write-Host "[2/4] All unit tests passed!" -ForegroundColor Green

# 5. Commit & Tag
Write-Host "[3/4] Committing and tagging $Tag..." -ForegroundColor Yellow
git add -A
$commitMsg = if ($Notes) { "chore(release): $Tag - $Notes" } else { "chore(release): $Tag" }
git commit -m $commitMsg
if ($LASTEXITCODE -ne 0) {
    Write-Host "No file changes to commit; tagging current HEAD..." -ForegroundColor DarkYellow
}
$tagMsg = if ($Notes) { "Release $Tag`n`n$Notes" } else { "Release $Tag" }
git tag -a $Tag -m $tagMsg

# 6. Push branch & tag to trigger GitHub Actions Release workflow
$branch = (git rev-parse --abbrev-ref HEAD).Trim()
Write-Host "[4/4] Pushing $branch and tag $Tag to origin..." -ForegroundColor Yellow
git push origin $branch
if ($LASTEXITCODE -ne 0) { exit 1 }
git push origin $Tag
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "  RELEASE $Tag PUSHED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "  GitHub Actions is now building KCSM_PrintService_Setup.exe" -ForegroundColor Green
Write-Host "  Track progress: https://github.com/Themehakcodes/ErpGoPrintService/actions" -ForegroundColor Cyan
Write-Host "  Release page:   https://github.com/Themehakcodes/ErpGoPrintService/releases/tag/$Tag" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Green

$ErrorActionPreference = "Stop"

$SkillName = "ark-mobile-adb"
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($env:ARK_SKILLS_DIR) {
    $TargetRoot = $env:ARK_SKILLS_DIR
} else {
    $TargetRoot = Join-Path $HOME ".arkagent\skills"
}

$Target = Join-Path $TargetRoot $SkillName
New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null

if (Test-Path $Target) {
    Remove-Item -Recurse -Force $Target
}

Copy-Item -Recurse -Force $Source $Target

Write-Host "Installed $SkillName to $Target"
Write-Host "Test:"
Write-Host "  python `"$Target\scripts\ark_mobile_adb.py`" doctor"

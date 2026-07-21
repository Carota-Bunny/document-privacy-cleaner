# Copyright (C) 2026 Carota-Bunny
# SPDX-License-Identifier: AGPL-3.0-only

param(
    [switch]$UseCurrentPython,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$Utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8
$OutputEncoding = $Utf8
$env:PYTHONUTF8 = "1"

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step 失败，退出码：$LASTEXITCODE"
    }
}

if ($UseCurrentPython) {
    $Python = (Get-Command python -ErrorAction Stop).Source
} else {
    $Venv = Join-Path $PSScriptRoot ".venv-build"
    $Python = Join-Path $Venv "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $Python)) {
        python -m venv $Venv
        Assert-LastExitCode "创建构建虚拟环境"
    }
    & $Python -m pip install --upgrade pip
    Assert-LastExitCode "升级 pip"
    & $Python -m pip install -r requirements-build.txt
    Assert-LastExitCode "安装构建依赖"
}

& $Python tools\generate_icon.py
Assert-LastExitCode "生成图标"
if (-not $SkipTests) {
    & $Python -m unittest discover -s tests -v
    Assert-LastExitCode "运行自动化测试"
}
& $Python -m PyInstaller --noconfirm --clean document_privacy_cleaner.spec
Assert-LastExitCode "构建 EXE"

$Exe = Join-Path $PSScriptRoot "dist\文档隐私清理器.exe"
if (-not (Test-Path -LiteralPath $Exe)) {
    throw "构建结束但未找到 EXE：$Exe"
}

$ExpectedVersion = (& $Python -c "from metacleaner import __version__; print(__version__)" | Select-Object -Last 1).Trim()
Assert-LastExitCode "读取源码版本"
$VersionInfo = (Get-Item -LiteralPath $Exe).VersionInfo
if ($VersionInfo.FileVersion -ne $ExpectedVersion -or $VersionInfo.ProductVersion -ne $ExpectedVersion) {
    throw "EXE 版本不匹配：预期 $ExpectedVersion，FileVersion=$($VersionInfo.FileVersion)，ProductVersion=$($VersionInfo.ProductVersion)"
}

function Invoke-ExeSmokeTest([string]$Argument, [string]$Name) {
    $Process = Start-Process -FilePath $Exe -ArgumentList $Argument -WindowStyle Hidden -PassThru
    try {
        Wait-Process -Id $Process.Id -Timeout 60 -ErrorAction Stop
    } catch {
        if (-not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force
        }
        throw "$Name 超时或启动失败"
    }
    $Process.Refresh()
    if ($Process.ExitCode -ne 0) {
        throw "$Name 失败，退出码：$($Process.ExitCode)"
    }
}

Invoke-ExeSmokeTest "--engine-smoke-test" "成品引擎自检"
$PreviousQpaPlatform = $env:QT_QPA_PLATFORM
try {
    $env:QT_QPA_PLATFORM = "offscreen"
    Invoke-ExeSmokeTest "--smoke-test" "成品 GUI 自检"
} finally {
    $env:QT_QPA_PLATFORM = $PreviousQpaPlatform
}

Write-Host "构建完成：$Exe"

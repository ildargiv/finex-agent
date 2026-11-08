# Установка агента «FinEx» (ликвидация фондов FinEx) на Windows (без WSL).
#   powershell -ExecutionPolicy Bypass -File install.ps1 hermes   # Hermes для Windows: %LOCALAPPDATA%\hermes, профиль finex
#   powershell -ExecutionPolicy Bypass -File install.ps1 claude
#   powershell -ExecutionPolicy Bypass -File install.ps1 codex
#   powershell -ExecutionPolicy Bypass -File install.ps1 openclaw
param([ValidateSet("hermes", "claude", "codex", "openclaw")][string]$Target = "hermes")
$ErrorActionPreference = "Stop"
$Src = Join-Path $PSScriptRoot "skills\finance\finex-liquidation"

function Copy-Skill($Dest) {
    New-Item -ItemType Directory -Force (Split-Path $Dest) | Out-Null
    if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
    Copy-Item -Recurse $Src $Dest
    Write-Host "Навык -> $Dest"
}

switch ($Target) {
    "hermes" {
        $hh = if ($env:HERMES_HOME) { $env:HERMES_HOME } else { Join-Path $env:LOCALAPPDATA "hermes" }
        $profile = Join-Path $hh "profiles\finex"
        if (-not (Test-Path $profile)) {
            if (Get-Command hermes -ErrorAction SilentlyContinue) {
                Write-Host "Создаю профиль Hermes 'finex' (копия текущих ключей/модели)..."
                hermes profile create finex --clone
            }
        }
        if (Test-Path $profile) {
            Copy-Item (Join-Path $PSScriptRoot "SOUL.md") (Join-Path $profile "SOUL.md") -Force
            Copy-Skill (Join-Path $profile "skills\finance\finex-liquidation")
            Write-Host "Профиль Hermes 'finex': $profile. Запуск: finex chat (или hermes -p finex chat)"
        } else {
            Copy-Skill (Join-Path $hh "skills\finance\finex-liquidation")
            Write-Host "Профиль 'finex' не создан — навык установлен в основной профиль: $hh"
        }
    }
    "claude" {
        Copy-Skill (Join-Path $HOME ".claude\skills\finex-liquidation")
        $agents = Join-Path $HOME ".claude\agents"
        New-Item -ItemType Directory -Force $agents | Out-Null
        Copy-Item (Join-Path $PSScriptRoot "agents\claude-code\finex.md") $agents -Force
        Write-Host "Субагент -> $agents\finex.md. Перезапустите Claude Code."
    }
    "codex" {
        Copy-Skill (Join-Path $HOME ".codex\skills\finex-liquidation")
        Write-Host "Перезапустите сессию Codex."
    }
    "openclaw" {
        Copy-Skill (Join-Path $HOME ".openclaw\skills\finex-liquidation")
        Write-Host "Перезапустите OpenClaw. Характер агента: добавьте SOUL.md из этой папки в SOUL.md вашего workspace."
    }
}
$desk = if ($env:FINEX_DESK) { $env:FINEX_DESK } else { Join-Path $HOME "finex-desk" }
New-Item -ItemType Directory -Force $desk | Out-Null
Write-Host "Хранилище (портфель и документы, только локально): $desk"
$py = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } elseif (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { $null }
if ($py) {
    try { & $py -m pip install --user --quiet pypdf } catch { Write-Host "Для чтения PDF: $py -m pip install pypdf" }
    try { & $py (Join-Path $Src "scripts\wiki.py") init | Out-Null; Write-Host "База знаний Obsidian готова: откройте $desk в Obsidian" } catch { Write-Host "База знаний: python wiki.py init" }
}
else { Write-Host "Python не найден: установите Python 3.9+ и pypdf" }

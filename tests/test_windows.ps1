# ============================================================
# CCS Cashflow Assistant - Test de Validación Windows
# ============================================================
# Ejecutar con: powershell -ExecutionPolicy Bypass -File tests/test_windows.ps1
# ============================================================

$ErrorActionPreference = "Stop"
$script:passed = 0
$script:failed = 0
$script:errors = @()

function Test-Check {
    param([string]$Name, [scriptblock]$Test)
    try {
        $result = & $Test
        if ($result) {
            Write-Host "  [PASS] $Name" -ForegroundColor Green
            $script:passed++
        } else {
            Write-Host "  [FAIL] $Name" -ForegroundColor Red
            $script:failed++
            $script:errors += $Name
        }
    } catch {
        Write-Host "  [ERROR] $Name : $_" -ForegroundColor Red
        $script:failed++
        $script:errors += "$Name (Exception: $_)"
    }
}

$ROOT = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path "$ROOT/pinokio.js")) {
    $ROOT = Split-Path -Parent $PSScriptRoot
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " CCS Cashflow Assistant - Validacion Windows" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# 1. ESTRUCTURA DE ARCHIVOS
# ============================================================
Write-Host "[1/7] Estructura de archivos" -ForegroundColor Yellow

Test-Check "pinokio.js existe" { Test-Path "$ROOT/pinokio.js" }
Test-Check "install.json existe" { Test-Path "$ROOT/install.json" }
Test-Check "start.json existe" { Test-Path "$ROOT/start.json" }
Test-Check "stop.json existe" { Test-Path "$ROOT/stop.json" }
Test-Check "reset.json existe" { Test-Path "$ROOT/reset.json" }
Test-Check "icon.png existe" { Test-Path "$ROOT/icon.png" }
Test-Check "server/app.py existe" { Test-Path "$ROOT/server/app.py" }
Test-Check "app/index.html existe" { Test-Path "$ROOT/app/index.html" }
Test-Check "requirements.txt existe" { Test-Path "$ROOT/requirements.txt" }
Test-Check "defaults/agents.json existe" { Test-Path "$ROOT/defaults/agents.json" }
Test-Check "defaults/prompts/ existe" { Test-Path "$ROOT/defaults/prompts" }
Test-Check "app/lib/purify.min.js existe" { Test-Path "$ROOT/app/lib/purify.min.js" }

# ============================================================
# 2. JSON VALIDOS
# ============================================================
Write-Host ""
Write-Host "[2/7] Validacion JSON" -ForegroundColor Yellow

$jsonFiles = @("install.json", "start.json", "stop.json", "reset.json", "defaults/agents.json")
foreach ($f in $jsonFiles) {
    Test-Check "$f es JSON valido" {
        $content = Get-Content "$ROOT/$f" -Raw -Encoding UTF8
        try { $null = $content | ConvertFrom-Json; $true } catch { $false }
    }
}

# ============================================================
# 3. CROSS-PLATFORM EN INSTALL.JSON
# ============================================================
Write-Host ""
Write-Host "[3/7] Cross-platform install.json" -ForegroundColor Yellow

$installContent = Get-Content "$ROOT/install.json" -Raw -Encoding UTF8

Test-Check "install.json tiene condicion win32" {
    $installContent -match "win32"
}
Test-Check "install.json tiene OllamaSetup.exe para Windows" {
    $installContent -match "OllamaSetup.exe"
}
Test-Check "install.json usa venv param para pip install" {
    $installContent -match '"venv"\s*:\s*"venv"'
}
Test-Check "install.json no tiene background: true" {
    -not ($installContent -match '"background"')
}
Test-Check "install.json muestra progreso visual (step numbers)" {
    $installContent -match "border-radius" -and $installContent -match "background"
}

# ============================================================
# 4. CROSS-PLATFORM EN START.JSON
# ============================================================
Write-Host ""
Write-Host "[4/7] Cross-platform start.json" -ForegroundColor Yellow

$startContent = Get-Content "$ROOT/start.json" -Raw -Encoding UTF8

Test-Check "start.json tiene daemon: true" {
    $startContent -match '"daemon"\s*:\s*true'
}
Test-Check "start.json tiene condicion win32" {
    $startContent -match "win32"
}
Test-Check "start.json usa 'start /B ollama serve' para Windows" {
    $startContent -match "start /B ollama serve"
}
Test-Check "start.json usa venv para servidor" {
    $startContent -match '"venv"\s*:\s*"venv"'
}
Test-Check "start.json tiene PYTHONIOENCODING" {
    $startContent -match "PYTHONIOENCODING"
}
Test-Check "start.json muestra mensajes de estado" {
    $startContent -match "Verificando motor de IA" -and $startContent -match "Aplicaci"
}
Test-Check "start.json abre browser al final" {
    $startContent -match "browser.open"
}

# ============================================================
# 5. CROSS-PLATFORM EN STOP.JSON
# ============================================================
Write-Host ""
Write-Host "[5/7] Cross-platform stop.json" -ForegroundColor Yellow

$stopContent = Get-Content "$ROOT/stop.json" -Raw -Encoding UTF8

Test-Check "stop.json tiene condicion win32" {
    $stopContent -match "win32"
}
Test-Check "stop.json usa pkill para unix" {
    $stopContent -match "pkill"
}
Test-Check "stop.json usa wmic para Windows" {
    $stopContent -match "wmic"
}
Test-Check "stop.json muestra mensaje de detencion" {
    $stopContent -match "Deteniendo" -or $stopContent -match "detenida"
}

# ============================================================
# 6. FRONTEND UX
# ============================================================
Write-Host ""
Write-Host "[6/7] Frontend UX" -ForegroundColor Yellow

$htmlContent = Get-Content "$ROOT/app/index.html" -Raw -Encoding UTF8

Test-Check "Frontend tiene readiness-banner" {
    $htmlContent -match "readiness-banner"
}
Test-Check "Frontend tiene globalLoadingOverlay" {
    $htmlContent -match "globalLoadingOverlay"
}
Test-Check "Frontend tiene funcion showGlobalLoading" {
    $htmlContent -match "function showGlobalLoading"
}
Test-Check "Frontend tiene funcion hideGlobalLoading" {
    $htmlContent -match "function hideGlobalLoading"
}
Test-Check "Frontend tiene funcion checkReadiness" {
    $htmlContent -match "function checkReadiness"
}
Test-Check "Frontend tiene funcion safeDisplayValue" {
    $htmlContent -match "function safeDisplayValue"
}
Test-Check "Frontend tiene funcion loadModelPerformance" {
    $htmlContent -match "function loadModelPerformance"
}
Test-Check "Frontend tiene modelPerfContainer" {
    $htmlContent -match "modelPerfContainer"
}
Test-Check "Frontend desactiva botones durante generacion" {
    $htmlContent -match "\.disabled\s*=\s*true"
}
Test-Check "Frontend desactiva input durante chat" {
    $htmlContent -match "input\.disabled\s*=\s*true"
}
Test-Check "Frontend tiene mensajes amigables de carga" {
    $htmlContent -match "analizando" -or $htmlContent -match "Generando"
}
Test-Check "Frontend usa DOMPurify" {
    $htmlContent -match "purify\.min\.js"
}
Test-Check "Frontend usa escapeHtml" {
    ($htmlContent | Select-String -Pattern "escapeHtml\(" -AllMatches).Matches.Count -ge 10
}
Test-Check "Frontend no usa eval()" {
    -not ($htmlContent -match "(?<!font-display.*)\beval\(")
}
Test-Check "Frontend tiene polling de readiness con setInterval" {
    $htmlContent -match "setInterval" -and $htmlContent -match "checkReadiness"
}

# ============================================================
# 7. SEGURIDAD
# ============================================================
Write-Host ""
Write-Host "[7/7] Seguridad" -ForegroundColor Yellow

$serverContent = Get-Content "$ROOT/server/app.py" -Raw -Encoding UTF8

Test-Check "Backend no tiene CORS wildcard" {
    -not ($serverContent -match 'allow_origins=\["\*"\]')
}
Test-Check "Backend tiene rate limiting" {
    $serverContent -match "_check_rate_limit"
}
Test-Check "Backend tiene _sanitize_id" {
    $serverContent -match "_sanitize_id"
}
Test-Check "Backend tiene _sanitize_filename" {
    $serverContent -match "_sanitize_filename"
}
Test-Check "Backend tiene MAX_MESSAGE_LENGTH" {
    $serverContent -match "MAX_MESSAGE_LENGTH"
}
Test-Check "Backend tiene ensure_ascii=False" {
    $serverContent -match "ensure_ascii=False"
}
Test-Check "Backend tiene endpoint /api/readiness" {
    $serverContent -match "/api/readiness"
}
Test-Check "Backend tiene endpoint /api/hardware/performance" {
    $serverContent -match "/api/hardware/performance"
}
Test-Check "Backend tiene endpoint /api/ollama/status" {
    $serverContent -match "/api/ollama/status"
}

# ============================================================
# RESUMEN
# ============================================================
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " RESUMEN" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Pasados: $($script:passed)" -ForegroundColor Green
Write-Host "  Fallidos: $($script:failed)" -ForegroundColor $(if ($script:failed -gt 0) { "Red" } else { "Green" })

if ($script:errors.Count -gt 0) {
    Write-Host ""
    Write-Host "  Errores:" -ForegroundColor Red
    foreach ($err in $script:errors) {
        Write-Host "    - $err" -ForegroundColor Red
    }
}

Write-Host ""
if ($script:failed -eq 0) {
    Write-Host "  TODOS LOS TESTS PASARON" -ForegroundColor Green
    exit 0
} else {
    Write-Host "  HAY TESTS FALLIDOS" -ForegroundColor Red
    exit 1
}

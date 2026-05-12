#!/bin/bash
# ============================================================
# CCS Cashflow Assistant - Test de Validación macOS/Linux
# ============================================================
# Ejecutar con: bash tests/test_mac.sh
# ============================================================

set -e

PASSED=0
FAILED=0
ERRORS=()

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

check() {
    local name="$1"
    local result="$2"
    if [ "$result" = "true" ]; then
        echo -e "  ${GREEN}[PASS]${NC} $name"
        PASSED=$((PASSED + 1))
    else
        echo -e "  ${RED}[FAIL]${NC} $name"
        FAILED=$((FAILED + 1))
        ERRORS+=("$name")
    fi
}

# Determinar ROOT
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

if [ ! -f "$ROOT/pinokio.js" ]; then
    echo "Error: No se encontró pinokio.js en $ROOT"
    exit 1
fi

echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN} CCS Cashflow Assistant - Validación macOS/Linux${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

# ============================================================
# 1. ESTRUCTURA DE ARCHIVOS
# ============================================================
echo -e "${YELLOW}[1/7] Estructura de archivos${NC}"

check "pinokio.js existe" "$([ -f "$ROOT/pinokio.js" ] && echo true || echo false)"
check "install.json existe" "$([ -f "$ROOT/install.json" ] && echo true || echo false)"
check "start.json existe" "$([ -f "$ROOT/start.json" ] && echo true || echo false)"
check "stop.json existe" "$([ -f "$ROOT/stop.json" ] && echo true || echo false)"
check "reset.json existe" "$([ -f "$ROOT/reset.json" ] && echo true || echo false)"
check "icon.png existe" "$([ -f "$ROOT/icon.png" ] && echo true || echo false)"
check "server/app.py existe" "$([ -f "$ROOT/server/app.py" ] && echo true || echo false)"
check "app/index.html existe" "$([ -f "$ROOT/app/index.html" ] && echo true || echo false)"
check "requirements.txt existe" "$([ -f "$ROOT/requirements.txt" ] && echo true || echo false)"
check "defaults/agents.json existe" "$([ -f "$ROOT/defaults/agents.json" ] && echo true || echo false)"
check "defaults/prompts/ existe" "$([ -d "$ROOT/defaults/prompts" ] && echo true || echo false)"
check "app/lib/purify.min.js existe" "$([ -f "$ROOT/app/lib/purify.min.js" ] && echo true || echo false)"

# ============================================================
# 2. JSON VÁLIDOS
# ============================================================
echo ""
echo -e "${YELLOW}[2/7] Validación JSON${NC}"

for f in install.json start.json stop.json reset.json defaults/agents.json; do
    if python3 -c "import json; json.loads(open('$ROOT/$f', encoding='utf-8').read())" 2>/dev/null; then
        check "$f es JSON válido" "true"
    else
        check "$f es JSON válido" "false"
    fi
done

# ============================================================
# 3. CROSS-PLATFORM EN INSTALL.JSON
# ============================================================
echo ""
echo -e "${YELLOW}[3/7] Cross-platform install.json${NC}"

INSTALL=$(cat "$ROOT/install.json")

check "install.json tiene condición win32" "$(echo "$INSTALL" | grep -q 'win32' && echo true || echo false)"
check "install.json tiene OllamaSetup.exe para Windows" "$(echo "$INSTALL" | grep -q 'OllamaSetup.exe' && echo true || echo false)"
check "install.json usa venv param para pip install" "$(echo "$INSTALL" | grep -q '"venv"' && echo true || echo false)"
check "install.json no tiene background: true" "$(echo "$INSTALL" | grep -qv '"background"' && echo true || echo false)"
check "install.json muestra progreso visual" "$(echo "$INSTALL" | grep -q 'border-radius' && echo true || echo false)"
check "install.json no crea venv manualmente" "$(echo "$INSTALL" | grep -v '"venv"' | grep -qv 'python -m venv' && echo true || echo false)"

# ============================================================
# 4. CROSS-PLATFORM EN START.JSON
# ============================================================
echo ""
echo -e "${YELLOW}[4/7] Cross-platform start.json${NC}"

START=$(cat "$ROOT/start.json")

check "start.json tiene daemon: true" "$(echo "$START" | grep -q '"daemon".*true' && echo true || echo false)"
check "start.json tiene condición win32" "$(echo "$START" | grep -q 'win32' && echo true || echo false)"
check "start.json usa 'start /B ollama serve' para Windows" "$(echo "$START" | grep -q 'start /B ollama serve' && echo true || echo false)"
check "start.json usa venv para servidor" "$(echo "$START" | grep -q '"venv"' && echo true || echo false)"
check "start.json tiene PYTHONIOENCODING" "$(echo "$START" | grep -q 'PYTHONIOENCODING' && echo true || echo false)"
check "start.json muestra mensajes de estado" "$(echo "$START" | grep -q 'Verificando motor de IA' && echo true || echo false)"
check "start.json abre browser al final" "$(echo "$START" | grep -q 'browser.open' && echo true || echo false)"
check "start.json no usa powershell para Ollama" "$(echo "$START" | grep -v 'powershell' | grep -q 'ollama' && echo true || echo false)"
check "start.json captura URL con regex" "$(echo "$START" | grep -q 'event.*http' && echo true || echo false)"

# ============================================================
# 5. CROSS-PLATFORM EN STOP.JSON
# ============================================================
echo ""
echo -e "${YELLOW}[5/7] Cross-platform stop.json${NC}"

STOP=$(cat "$ROOT/stop.json")

check "stop.json tiene condición win32" "$(echo "$STOP" | grep -q 'win32' && echo true || echo false)"
check "stop.json usa pkill para unix" "$(echo "$STOP" | grep -q 'pkill' && echo true || echo false)"
check "stop.json usa wmic para Windows" "$(echo "$STOP" | grep -q 'wmic' && echo true || echo false)"
check "stop.json muestra mensaje de detención" "$(echo "$STOP" | grep -q 'Deteniendo\|detenida' && echo true || echo false)"

# ============================================================
# 6. FRONTEND UX
# ============================================================
echo ""
echo -e "${YELLOW}[6/7] Frontend UX${NC}"

HTML=$(cat "$ROOT/app/index.html")

check "Frontend tiene readiness-banner" "$(echo "$HTML" | grep -q 'readiness-banner' && echo true || echo false)"
check "Frontend tiene globalLoadingOverlay" "$(echo "$HTML" | grep -q 'globalLoadingOverlay' && echo true || echo false)"
check "Frontend tiene función showGlobalLoading" "$(echo "$HTML" | grep -q 'function showGlobalLoading' && echo true || echo false)"
check "Frontend tiene función hideGlobalLoading" "$(echo "$HTML" | grep -q 'function hideGlobalLoading' && echo true || echo false)"
check "Frontend tiene función checkReadiness" "$(echo "$HTML" | grep -q 'function checkReadiness' && echo true || echo false)"
check "Frontend tiene función safeDisplayValue" "$(echo "$HTML" | grep -q 'function safeDisplayValue' && echo true || echo false)"
check "Frontend tiene función loadModelPerformance" "$(echo "$HTML" | grep -q 'function loadModelPerformance' && echo true || echo false)"
check "Frontend tiene modelPerfContainer" "$(echo "$HTML" | grep -q 'modelPerfContainer' && echo true || echo false)"
check "Frontend desactiva botones durante generación" "$(echo "$HTML" | grep -q '\.disabled = true' && echo true || echo false)"
check "Frontend desactiva input durante chat" "$(echo "$HTML" | grep -q 'input.disabled = true' && echo true || echo false)"
check "Frontend tiene mensajes amigables de carga" "$(echo "$HTML" | grep -q 'analizando\|Generando' && echo true || echo false)"
check "Frontend usa DOMPurify" "$(echo "$HTML" | grep -q 'purify.min.js' && echo true || echo false)"
check "Frontend usa escapeHtml (10+ veces)" "$([ $(echo "$HTML" | grep -o 'escapeHtml(' | wc -l) -ge 10 ] && echo true || echo false)"
check "Frontend no usa eval()" "$(echo "$HTML" | grep -v 'font-display' | grep -qv 'eval(' && echo true || echo false)"
check "Frontend tiene polling con setInterval" "$(echo "$HTML" | grep -q 'setInterval' && echo true || echo false)"

# ============================================================
# 7. SEGURIDAD
# ============================================================
echo ""
echo -e "${YELLOW}[7/7] Seguridad${NC}"

SERVER=$(cat "$ROOT/server/app.py")

check "Backend no tiene CORS wildcard" "$(echo "$SERVER" | grep -qv 'allow_origins=\[\"\\*\"\]' && echo true || echo false)"
check "Backend tiene rate limiting" "$(echo "$SERVER" | grep -q '_check_rate_limit' && echo true || echo false)"
check "Backend tiene _sanitize_id" "$(echo "$SERVER" | grep -q '_sanitize_id' && echo true || echo false)"
check "Backend tiene _sanitize_filename" "$(echo "$SERVER" | grep -q '_sanitize_filename' && echo true || echo false)"
check "Backend tiene MAX_MESSAGE_LENGTH" "$(echo "$SERVER" | grep -q 'MAX_MESSAGE_LENGTH' && echo true || echo false)"
check "Backend tiene ensure_ascii=False" "$(echo "$SERVER" | grep -q 'ensure_ascii=False' && echo true || echo false)"
check "Backend tiene endpoint /api/readiness" "$(echo "$SERVER" | grep -q '/api/readiness' && echo true || echo false)"
check "Backend tiene endpoint /api/hardware/performance" "$(echo "$SERVER" | grep -q '/api/hardware/performance' && echo true || echo false)"
check "Backend tiene endpoint /api/ollama/status" "$(echo "$SERVER" | grep -q '/api/ollama/status' && echo true || echo false)"
check "Backend imprime 127.0.0.1 (no 0.0.0.0)" "$(echo "$SERVER" | grep -q 'print(f\"http://127.0.0.1' && echo true || echo false)"

# ============================================================
# RESUMEN
# ============================================================
echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN} RESUMEN${NC}"
echo -e "${CYAN}============================================================${NC}"
echo -e "  ${GREEN}Pasados: $PASSED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "  ${RED}Fallidos: $FAILED${NC}"
    echo ""
    echo -e "  ${RED}Errores:${NC}"
    for err in "${ERRORS[@]}"; do
        echo -e "    ${RED}- $err${NC}"
    done
else
    echo -e "  ${GREEN}Fallidos: 0${NC}"
fi

echo ""
if [ $FAILED -eq 0 ]; then
    echo -e "  ${GREEN}TODOS LOS TESTS PASARON${NC}"
    exit 0
else
    echo -e "  ${RED}HAY TESTS FALLIDOS${NC}"
    exit 1
fi

#!/usr/bin/env python3
"""
verify_deps.py — Verifica que todas las dependencias criticas
esten instaladas en el entorno virtual antes de iniciar el servidor.

Retorna exit code 0 si todo esta OK, 1 si faltan dependencias.
Imprime mensajes claros para que Pinokio los muestre al usuario.
"""
import sys
import importlib
import subprocess

# Modulos criticos que el servidor necesita para arrancar
CRITICAL_MODULES = [
    ("requests", "requests"),
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("pydantic", "pydantic"),
    ("aiofiles", "aiofiles"),
    ("openpyxl", "openpyxl"),
    ("httpx", "httpx"),
    ("multipart", "python-multipart"),
]

def check_and_fix():
    missing = []
    for module_name, pip_name in CRITICAL_MODULES:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append((module_name, pip_name))

    if not missing:
        print("DEPS_VERIFY_OK")
        return True

    # Intentar instalar los modulos faltantes
    print(f"AVISO: Faltan {len(missing)} dependencias. Instalando automaticamente...")
    for module_name, pip_name in missing:
        print(f"  Instalando {pip_name}...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pip_name, "--quiet"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError:
            print(f"  ERROR: No se pudo instalar {pip_name}")

    # Verificar de nuevo
    still_missing = []
    for module_name, pip_name in missing:
        try:
            importlib.import_module(module_name)
        except ImportError:
            still_missing.append(module_name)

    if still_missing:
        print(f"ERROR CRITICO: No se pudieron instalar: {', '.join(still_missing)}")
        print("Ejecuta el diagnostico: scripts/diagnose.ps1 (Windows) o scripts/diagnose.sh (Mac/Linux)")
        return False

    print("DEPS_VERIFY_OK (reparadas)")
    return True


if __name__ == "__main__":
    ok = check_and_fix()
    sys.exit(0 if ok else 1)

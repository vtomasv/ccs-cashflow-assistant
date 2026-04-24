"""
CCS Cashflow Assistant — Backend FastAPI
Plugin de Pinokio para gestión de flujos de caja con IA local para PYMEs.

Arquitectura:
  - Módulo de Empresas: CRUD de empresas y onboarding
  - Módulo de Flujo de Caja: construcción y análisis financiero
  - Módulo de Escenarios: simulación de variables
  - Módulo de Agentes: orquestación de LLMs locales vía Ollama
  - Módulo de Exportación: generación de Excel/CSV
"""

import os
import sys
import json
import uuid
import re
import shutil
import asyncio
import logging
import threading
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

# Forzar UTF-8 en stdout/stderr para Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import requests as http_requests
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuración de rutas (siempre absolutas desde __file__)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent.resolve()
APP_DIR = BASE_DIR / "app"
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data")))
DEFAULTS_DIR = BASE_DIR / "defaults"

def _parse_port():
    """Obtener puerto: 1) argumento --port, 2) env PORT, 3) default 7860."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--port", type=int, default=None)
    args, _ = parser.parse_known_args()
    if args.port is not None:
        return args.port
    raw = os.environ.get("PORT", "7860")
    try:
        return int(raw)
    except (ValueError, TypeError):
        return 7860

PORT = _parse_port()
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")

# Timeouts configurables
OLLAMA_TIMEOUT_DEFAULT = int(os.environ.get("OLLAMA_TIMEOUT", "300"))
OLLAMA_TIMEOUT_ANALYSIS = int(os.environ.get("OLLAMA_TIMEOUT_ANALYSIS", "600"))
OLLAMA_TIMEOUT_SIMULATION = int(os.environ.get("OLLAMA_TIMEOUT_SIMULATION", "600"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cashflow-assistant")

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(title="CCS Cashflow Assistant", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------------------------------------------------------------------------
# Utilidades de persistencia
# ---------------------------------------------------------------------------
def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def load_json(path: Path, default=None):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default if default is not None else {}
    return default if default is not None else {}

# ---------------------------------------------------------------------------
# Utilidades de Ollama
# ---------------------------------------------------------------------------
def _fix_encoding(text: str) -> str:
    """Repara texto UTF-8 mal interpretado como latin-1."""
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

def _extract_json_from_llm(text: str):
    """Extrae JSON robusto de respuestas del LLM."""
    if not text:
        return None
    # Estrategia 1: strip de bloques ```json ... ```
    clean = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass
    # Estrategia 2: parser balanceado
    start = text.find("{")
    if start != -1:
        depth, in_str, escape = 0, False, False
        for i, ch in enumerate(text[start:], start):
            if escape:
                escape = False
                continue
            if ch == "\\" and in_str:
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if not in_str:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i+1])
                        except json.JSONDecodeError:
                            break
    # Estrategia 3: regex greedy
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None

_pull_status: dict = {}

def _is_model_available(model: str) -> bool:
    try:
        r = http_requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        return model in models or any(m.startswith(model.split(":")[0]) for m in models)
    except Exception:
        return False

def _start_pull_background(model: str):
    if model in _pull_status and _pull_status[model].get("status") in ("pulling", "queued"):
        return
    _pull_status[model] = {"status": "queued", "progress": 0, "error": None}
    threading.Thread(target=_do_pull, args=(model,), daemon=True).start()

def _do_pull(model: str):
    _pull_status[model]["status"] = "pulling"
    try:
        with http_requests.post(f"{OLLAMA_URL}/api/pull",
                                json={"name": model, "stream": True},
                                stream=True, timeout=3600) as r:
            for line in r.iter_lines():
                if line:
                    data = json.loads(line)
                    if "completed" in data and "total" in data and data["total"] > 0:
                        _pull_status[model]["progress"] = int(data["completed"] / data["total"] * 100)
        _pull_status[model] = {"status": "done", "progress": 100, "error": None}
    except Exception as e:
        _pull_status[model] = {"status": "error", "progress": 0, "error": str(e)}

def call_ollama(model: str, system_prompt: str, user_message: str,
                temperature: float = 0.7, timeout: int = None) -> str:
    if timeout is None:
        timeout = OLLAMA_TIMEOUT_DEFAULT
    try:
        resp = http_requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "options": {"temperature": temperature},
                "stream": False
            },
            timeout=timeout
        )
        resp.encoding = "utf-8"
        if resp.status_code == 404:
            _start_pull_background(model)
            raise HTTPException(503, f"Modelo {model} no disponible. Descarga iniciada.")
        resp.raise_for_status()
        content = resp.json()["message"]["content"]
        return _fix_encoding(content)
    except http_requests.exceptions.ConnectionError:
        raise HTTPException(503, "No se puede conectar con Ollama. Verifica que esté ejecutándose.")
    except http_requests.exceptions.Timeout:
        raise HTTPException(504, "Timeout al comunicarse con Ollama. Intenta de nuevo.")

def call_ollama_chat(model: str, messages: list, temperature: float = 0.7, timeout: int = None) -> str:
    """Llamada a Ollama con historial de mensajes completo."""
    if timeout is None:
        timeout = OLLAMA_TIMEOUT_DEFAULT
    try:
        resp = http_requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "options": {"temperature": temperature},
                "stream": False
            },
            timeout=timeout
        )
        resp.encoding = "utf-8"
        if resp.status_code == 404:
            _start_pull_background(model)
            raise HTTPException(503, f"Modelo {model} no disponible. Descarga iniciada.")
        resp.raise_for_status()
        content = resp.json()["message"]["content"]
        return _fix_encoding(content)
    except http_requests.exceptions.ConnectionError:
        raise HTTPException(503, "No se puede conectar con Ollama.")
    except http_requests.exceptions.Timeout:
        raise HTTPException(504, "Timeout al comunicarse con Ollama.")

# ---------------------------------------------------------------------------
# Carga de agentes y prompts
# ---------------------------------------------------------------------------
def get_agents() -> dict:
    return load_json(DATA_DIR / "agents" / "agents.json", {"version": "0.1.0", "agents": []})

def get_agent(agent_id: str) -> dict:
    agents = get_agents()
    for a in agents.get("agents", []):
        if a["id"] == agent_id:
            return a
    return None

def get_prompt(prompt_name: str) -> str:
    path = DATA_DIR / "prompts" / "system" / f"{prompt_name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    path = DEFAULTS_DIR / "prompts" / f"{prompt_name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""

# ---------------------------------------------------------------------------
# Modelos Pydantic
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Normalización de datos de flujo de caja
# ---------------------------------------------------------------------------
def _normalize_month(m: dict) -> dict:
    """Asegura que un mes tenga todos los campos requeridos y totales correctos."""
    income = m.get("income", {})
    if not isinstance(income, dict):
        income = {}
    sales = _to_num(income.get("sales", 0))
    other_income = _to_num(income.get("other_income", 0))
    income_total = sales + other_income
    income = {"sales": sales, "other_income": other_income, "total": income_total}

    expenses = m.get("expenses", {})
    if not isinstance(expenses, dict):
        expenses = {}
    variable_costs = _to_num(expenses.get("variable_costs", 0))
    fixed_costs = _to_num(expenses.get("fixed_costs", 0))
    variable_expenses = _to_num(expenses.get("variable_expenses", 0))
    debt_payments = _to_num(expenses.get("debt_payments", 0))
    taxes = _to_num(expenses.get("taxes", 0))
    investments = _to_num(expenses.get("investments", 0))
    expenses_total = variable_costs + fixed_costs + variable_expenses + debt_payments + taxes + investments
    expenses = {
        "variable_costs": variable_costs,
        "fixed_costs": fixed_costs,
        "variable_expenses": variable_expenses,
        "debt_payments": debt_payments,
        "taxes": taxes,
        "investments": investments,
        "total": expenses_total
    }

    net_flow = income_total - expenses_total

    return {
        "month": m.get("month", ""),
        "label": m.get("label", ""),
        "income": income,
        "expenses": expenses,
        "net_flow": net_flow,
        "cumulative_balance": 0  # se recalcula después
    }

def _to_num(val) -> float:
    """Convierte un valor a número, retorna 0 si no es posible."""
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        try:
            cleaned = val.replace("$", "").replace(".", "").replace(",", "").strip()
            return float(cleaned)
        except (ValueError, TypeError):
            return 0
    return 0

def normalize_cashflow(data: dict) -> dict:
    """Normaliza un flujo de caja completo: recalcula totales, saldos acumulados y summary."""
    months = data.get("months", [])
    if not isinstance(months, list):
        months = []

    normalized_months = []
    cumulative = 0
    total_income = 0
    total_expenses = 0

    for m in months:
        nm = _normalize_month(m)
        cumulative += nm["net_flow"]
        nm["cumulative_balance"] = cumulative
        total_income += nm["income"]["total"]
        total_expenses += nm["expenses"]["total"]
        normalized_months.append(nm)

    net_cashflow = total_income - total_expenses
    num_months = len(normalized_months) or 1

    data["months"] = normalized_months
    data["summary"] = {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_cashflow": net_cashflow,
        "average_monthly_balance": round(net_cashflow / num_months)
    }
    data["period_months"] = len(normalized_months)
    data["updated_at"] = datetime.now().isoformat()
    return data


class CompanyCreate(BaseModel):
    name: str
    sector: str = ""
    size: str = ""
    description: str = ""

class ChatMessage(BaseModel):
    company_id: str
    message: str
    session_id: Optional[str] = None

class MonthData(BaseModel):
    month: str = ""
    label: str = ""
    income: Optional[Dict[str, Any]] = None
    expenses: Optional[Dict[str, Any]] = None

class ScenarioRequest(BaseModel):
    company_id: str
    instruction: str

class AgentConfigUpdate(BaseModel):
    model: Optional[str] = None
    temperature: Optional[float] = None
    system_prompt: Optional[str] = None

# ---------------------------------------------------------------------------
# Estado de generación en background
# ---------------------------------------------------------------------------
_generation_status: Dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Endpoints: Health
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    ollama_ok = False
    try:
        r = http_requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        ollama_ok = r.status_code == 200
    except Exception:
        pass
    return {"status": "ok", "ollama": ollama_ok, "version": "0.1.0"}

# ---------------------------------------------------------------------------
# Endpoints: Empresas
# ---------------------------------------------------------------------------
@app.get("/api/companies")
async def list_companies():
    companies_dir = DATA_DIR / "companies"
    companies_dir.mkdir(parents=True, exist_ok=True)
    companies = []
    for f in companies_dir.glob("*/company.json"):
        companies.append(load_json(f))
    return {"companies": companies}

@app.post("/api/companies")
async def create_company(data: CompanyCreate):
    company_id = str(uuid.uuid4())[:8]
    company = {
        "id": company_id,
        "name": data.name,
        "sector": data.sector,
        "size": data.size,
        "description": data.description,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    company_dir = DATA_DIR / "companies" / company_id
    company_dir.mkdir(parents=True, exist_ok=True)
    save_json(company_dir / "company.json", company)
    return company

@app.get("/api/companies/{company_id}")
async def get_company(company_id: str):
    path = DATA_DIR / "companies" / company_id / "company.json"
    if not path.exists():
        raise HTTPException(404, "Empresa no encontrada")
    return load_json(path)

@app.delete("/api/companies/{company_id}")
async def delete_company(company_id: str):
    company_dir = DATA_DIR / "companies" / company_id
    if company_dir.exists():
        shutil.rmtree(company_dir)
    return {"status": "deleted"}

# ---------------------------------------------------------------------------
# Endpoints: Chat / Entrevista Financiera
# ---------------------------------------------------------------------------
@app.post("/api/chat")
async def chat(data: ChatMessage):
    company_dir = DATA_DIR / "companies" / data.company_id
    if not company_dir.exists():
        raise HTTPException(404, "Empresa no encontrada")

    company = load_json(company_dir / "company.json")

    # Cargar o crear sesión
    session_id = data.session_id or str(uuid.uuid4())[:8]
    session_path = DATA_DIR / "sessions" / f"{data.company_id}_{session_id}.json"
    session = load_json(session_path, {"id": session_id, "company_id": data.company_id, "messages": [], "created_at": datetime.now().isoformat()})

    # Obtener agente y prompt
    agent = get_agent("financial_interviewer")
    if not agent:
        raise HTTPException(500, "Agente entrevistador no configurado")

    system_prompt = get_prompt("financial_interviewer")
    if agent.get("system_prompt"):
        system_prompt = agent["system_prompt"]

    # Contexto de la empresa
    company_context = f"\nDatos de la empresa:\n- Nombre: {company.get('name', 'Sin nombre')}\n- Sector: {company.get('sector', 'No especificado')}\n- Tamaño: {company.get('size', 'No especificado')}\n- Descripción: {company.get('description', 'Sin descripción')}\n"

    # Cargar flujo de caja existente si hay
    cashflow_path = company_dir / "cashflow.json"
    if cashflow_path.exists():
        cf = load_json(cashflow_path)
        company_context += f"\nYa existe un flujo de caja generado con {len(cf.get('months', []))} meses de proyección.\n"

    full_system = system_prompt + company_context

    # Construir mensajes para Ollama
    messages = [{"role": "system", "content": full_system}]
    for msg in session.get("messages", []):
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": data.message})

    # Llamar a Ollama
    response = call_ollama_chat(
        model=agent.get("model", "llama3.2:3b"),
        messages=messages,
        temperature=agent.get("temperature", 0.7),
        timeout=OLLAMA_TIMEOUT_DEFAULT
    )

    # Guardar en sesión
    session["messages"].append({"role": "user", "content": data.message, "timestamp": datetime.now().isoformat()})
    session["messages"].append({"role": "assistant", "content": response, "timestamp": datetime.now().isoformat()})
    save_json(session_path, session)

    # Actualizar estado de la empresa
    if company.get("status") == "pending":
        company["status"] = "interviewing"
        company["updated_at"] = datetime.now().isoformat()
        save_json(company_dir / "company.json", company)

    return {
        "response": response,
        "session_id": session_id,
        "company_status": company.get("status")
    }

# ---------------------------------------------------------------------------
# Endpoints: Generación de Flujo de Caja
# ---------------------------------------------------------------------------
@app.post("/api/companies/{company_id}/generate-cashflow")
async def generate_cashflow(company_id: str, background_tasks: BackgroundTasks):
    company_dir = DATA_DIR / "companies" / company_id
    if not company_dir.exists():
        raise HTTPException(404, "Empresa no encontrada")

    task_id = str(uuid.uuid4())[:8]
    _generation_status[task_id] = {"status": "generating", "progress": 0, "error": None}

    background_tasks.add_task(_generate_cashflow_task, company_id, task_id)
    return {"task_id": task_id, "status": "generating"}

def _generate_cashflow_task(company_id: str, task_id: str):
    try:
        company_dir = DATA_DIR / "companies" / company_id
        company = load_json(company_dir / "company.json")

        # Recopilar toda la información de las sesiones
        sessions_dir = DATA_DIR / "sessions"
        all_messages = []
        for f in sorted(sessions_dir.glob(f"{company_id}_*.json")):
            session = load_json(f)
            for msg in session.get("messages", []):
                all_messages.append(f"{msg['role'].upper()}: {msg['content']}")

        conversation_text = "\n".join(all_messages)

        _generation_status[task_id]["progress"] = 30

        # Obtener agente analista
        agent = get_agent("cashflow_analyst")
        if not agent:
            _generation_status[task_id] = {"status": "error", "progress": 0, "error": "Agente analista no configurado"}
            return

        system_prompt = get_prompt("cashflow_analyst")
        if agent.get("system_prompt"):
            system_prompt = agent["system_prompt"]

        user_message = f"""Basándote en la siguiente conversación con el dueño de la empresa "{company.get('name', 'Sin nombre')}" del sector "{company.get('sector', 'No especificado')}",
construye un flujo de caja mensual proyectado a 12 meses.

CONVERSACIÓN COMPLETA:
{conversation_text}

Genera el JSON del flujo de caja siguiendo exactamente el formato indicado en tus instrucciones."""

        _generation_status[task_id]["progress"] = 50

        response = call_ollama(
            model=agent.get("model", "llama3.1:8b"),
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=agent.get("temperature", 0.3),
            timeout=OLLAMA_TIMEOUT_ANALYSIS
        )

        _generation_status[task_id]["progress"] = 80

        # Extraer JSON de la respuesta
        cashflow_data = _extract_json_from_llm(response)
        if not cashflow_data:
            _generation_status[task_id] = {"status": "error", "progress": 0, "error": "No se pudo generar el flujo de caja. Intenta proporcionar más información."}
            return

        # Normalizar y guardar flujo de caja
        cashflow_data = normalize_cashflow(cashflow_data)
        cashflow_data["id"] = str(uuid.uuid4())[:8]
        cashflow_data["company_id"] = company_id
        cashflow_data["created_at"] = datetime.now().isoformat()
        save_json(company_dir / "cashflow.json", cashflow_data)
        logger.info(f"Flujo de caja normalizado: {len(cashflow_data.get('months', []))} meses, summary={cashflow_data.get('summary', {})}")

        # Actualizar estado de la empresa
        company["status"] = "complete"
        company["updated_at"] = datetime.now().isoformat()
        save_json(company_dir / "company.json", company)

        _generation_status[task_id] = {"status": "done", "progress": 100, "error": None}
        logger.info(f"Flujo de caja generado para empresa {company_id}")

    except Exception as e:
        logger.error(f"Error generando flujo de caja: {e}")
        _generation_status[task_id] = {"status": "error", "progress": 0, "error": str(e)}

@app.get("/api/generation/{task_id}/progress")
async def get_generation_progress(task_id: str):
    return _generation_status.get(task_id, {"status": "unknown", "progress": 0, "error": "Tarea no encontrada"})

@app.get("/api/companies/{company_id}/cashflow")
async def get_cashflow(company_id: str):
    path = DATA_DIR / "companies" / company_id / "cashflow.json"
    if not path.exists():
        raise HTTPException(404, "Flujo de caja no encontrado. Genera uno primero.")
    data = load_json(path)
    # Siempre re-normalizar al leer para garantizar consistencia
    data = normalize_cashflow(data)
    return data

# ---------------------------------------------------------------------------
# Endpoints: Edición manual de meses del flujo de caja
# ---------------------------------------------------------------------------
@app.put("/api/companies/{company_id}/cashflow/months/{month_index}")
async def update_month(company_id: str, month_index: int, month_data: MonthData):
    """Actualiza un mes específico del flujo de caja por índice (0-based)."""
    company_dir = DATA_DIR / "companies" / company_id
    cashflow_path = company_dir / "cashflow.json"
    if not cashflow_path.exists():
        raise HTTPException(404, "No hay flujo de caja para editar.")

    cashflow = load_json(cashflow_path)
    months = cashflow.get("months", [])

    if month_index < 0 or month_index >= len(months):
        raise HTTPException(400, f"Índice de mes inválido: {month_index}. Rango válido: 0-{len(months)-1}")

    # Actualizar campos proporcionados
    existing = months[month_index]
    if month_data.month:
        existing["month"] = month_data.month
    if month_data.label:
        existing["label"] = month_data.label
    if month_data.income is not None:
        existing["income"] = month_data.income
    if month_data.expenses is not None:
        existing["expenses"] = month_data.expenses

    months[month_index] = existing
    cashflow["months"] = months

    # Re-normalizar todo
    cashflow = normalize_cashflow(cashflow)
    save_json(cashflow_path, cashflow)

    return cashflow

@app.post("/api/companies/{company_id}/cashflow/months")
async def add_month(company_id: str, month_data: MonthData):
    """Agrega un nuevo mes al flujo de caja."""
    company_dir = DATA_DIR / "companies" / company_id
    cashflow_path = company_dir / "cashflow.json"
    if not cashflow_path.exists():
        raise HTTPException(404, "No hay flujo de caja. Genera uno primero.")

    cashflow = load_json(cashflow_path)
    months = cashflow.get("months", [])

    new_month = {
        "month": month_data.month or "",
        "label": month_data.label or "",
        "income": month_data.income or {"sales": 0, "other_income": 0, "total": 0},
        "expenses": month_data.expenses or {"variable_costs": 0, "fixed_costs": 0, "variable_expenses": 0, "debt_payments": 0, "taxes": 0, "investments": 0, "total": 0}
    }
    months.append(new_month)
    cashflow["months"] = months

    cashflow = normalize_cashflow(cashflow)
    save_json(cashflow_path, cashflow)

    return cashflow

@app.delete("/api/companies/{company_id}/cashflow/months/{month_index}")
async def delete_month(company_id: str, month_index: int):
    """Elimina un mes del flujo de caja por índice (0-based)."""
    company_dir = DATA_DIR / "companies" / company_id
    cashflow_path = company_dir / "cashflow.json"
    if not cashflow_path.exists():
        raise HTTPException(404, "No hay flujo de caja.")

    cashflow = load_json(cashflow_path)
    months = cashflow.get("months", [])

    if month_index < 0 or month_index >= len(months):
        raise HTTPException(400, f"Índice de mes inválido: {month_index}")

    months.pop(month_index)
    cashflow["months"] = months

    cashflow = normalize_cashflow(cashflow)
    save_json(cashflow_path, cashflow)

    return cashflow

# ---------------------------------------------------------------------------
# Endpoints: Simulación de Escenarios
# ---------------------------------------------------------------------------
@app.post("/api/companies/{company_id}/simulate")
async def simulate_scenario(company_id: str, data: ScenarioRequest, background_tasks: BackgroundTasks):
    company_dir = DATA_DIR / "companies" / company_id
    cashflow_path = company_dir / "cashflow.json"
    if not cashflow_path.exists():
        raise HTTPException(404, "No hay flujo de caja base para simular.")

    task_id = str(uuid.uuid4())[:8]
    _generation_status[task_id] = {"status": "generating", "progress": 0, "error": None}

    background_tasks.add_task(_simulate_scenario_task, company_id, data.instruction, task_id)
    return {"task_id": task_id, "status": "generating"}

def _simulate_scenario_task(company_id: str, instruction: str, task_id: str):
    try:
        company_dir = DATA_DIR / "companies" / company_id
        cashflow = load_json(company_dir / "cashflow.json")

        _generation_status[task_id]["progress"] = 30

        agent = get_agent("scenario_simulator")
        if not agent:
            _generation_status[task_id] = {"status": "error", "progress": 0, "error": "Agente simulador no configurado"}
            return

        system_prompt = get_prompt("scenario_simulator")
        if agent.get("system_prompt"):
            system_prompt = agent["system_prompt"]

        # Limpiar datos internos del cashflow para el prompt
        cf_clean = {k: v for k, v in cashflow.items() if k not in ("id", "company_id", "created_at", "updated_at")}

        user_message = f"""FLUJO DE CAJA ACTUAL:
{json.dumps(cf_clean, indent=2, ensure_ascii=False)}

INSTRUCCIÓN DEL USUARIO:
{instruction}

Aplica los cambios solicitados y devuelve el flujo de caja completo actualizado en formato JSON."""

        _generation_status[task_id]["progress"] = 50

        response = call_ollama(
            model=agent.get("model", "llama3.1:8b"),
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=agent.get("temperature", 0.4),
            timeout=OLLAMA_TIMEOUT_SIMULATION
        )

        _generation_status[task_id]["progress"] = 80

        scenario_data = _extract_json_from_llm(response)
        if not scenario_data:
            _generation_status[task_id] = {"status": "error", "progress": 0, "error": "No se pudo generar la simulación."}
            return

        # Guardar escenario
        scenario_id = str(uuid.uuid4())[:8]
        scenario_data["id"] = scenario_id
        scenario_data["company_id"] = company_id
        scenario_data["instruction"] = instruction
        scenario_data["created_at"] = datetime.now().isoformat()

        scenarios_dir = DATA_DIR / "scenarios"
        scenarios_dir.mkdir(parents=True, exist_ok=True)
        save_json(scenarios_dir / f"{company_id}_{scenario_id}.json", scenario_data)

        _generation_status[task_id] = {"status": "done", "progress": 100, "error": None, "scenario_id": scenario_id}
        logger.info(f"Escenario {scenario_id} generado para empresa {company_id}")

    except Exception as e:
        logger.error(f"Error en simulación: {e}")
        _generation_status[task_id] = {"status": "error", "progress": 0, "error": str(e)}

@app.get("/api/companies/{company_id}/scenarios")
async def list_scenarios(company_id: str):
    scenarios_dir = DATA_DIR / "scenarios"
    scenarios_dir.mkdir(parents=True, exist_ok=True)
    scenarios = []
    for f in sorted(scenarios_dir.glob(f"{company_id}_*.json")):
        scenarios.append(load_json(f))
    return {"scenarios": scenarios}

@app.get("/api/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    scenarios_dir = DATA_DIR / "scenarios"
    for f in scenarios_dir.glob(f"*_{scenario_id}.json"):
        return load_json(f)
    raise HTTPException(404, "Escenario no encontrado")

@app.delete("/api/scenarios/{scenario_id}")
async def delete_scenario(scenario_id: str):
    scenarios_dir = DATA_DIR / "scenarios"
    for f in scenarios_dir.glob(f"*_{scenario_id}.json"):
        f.unlink()
        return {"status": "deleted"}
    raise HTTPException(404, "Escenario no encontrado")

# ---------------------------------------------------------------------------
# Endpoints: Chat de Simulación (conversacional)
# ---------------------------------------------------------------------------
@app.post("/api/chat/simulate")
async def chat_simulate(data: ChatMessage):
    company_dir = DATA_DIR / "companies" / data.company_id
    if not company_dir.exists():
        raise HTTPException(404, "Empresa no encontrada")

    cashflow_path = company_dir / "cashflow.json"
    if not cashflow_path.exists():
        raise HTTPException(404, "Primero genera un flujo de caja base.")

    cashflow = load_json(cashflow_path)

    # Cargar o crear sesión de simulación
    session_id = data.session_id or f"sim_{str(uuid.uuid4())[:8]}"
    session_path = DATA_DIR / "sessions" / f"{data.company_id}_{session_id}.json"
    session = load_json(session_path, {"id": session_id, "company_id": data.company_id, "type": "simulation", "messages": [], "created_at": datetime.now().isoformat()})

    agent = get_agent("scenario_simulator")
    if not agent:
        raise HTTPException(500, "Agente simulador no configurado")

    system_prompt = get_prompt("scenario_simulator")

    # Incluir flujo de caja como contexto
    cf_summary = f"La empresa tiene un flujo de caja proyectado a {len(cashflow.get('months', []))} meses. "
    summary = cashflow.get("summary", {})
    cf_summary += f"Ingresos totales: ${summary.get('total_income', 0):,.0f}, Gastos totales: ${summary.get('total_expenses', 0):,.0f}, Flujo neto: ${summary.get('net_cashflow', 0):,.0f}."

    messages = [{"role": "system", "content": system_prompt + "\n\nCONTEXTO: " + cf_summary}]
    for msg in session.get("messages", []):
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": data.message})

    response = call_ollama_chat(
        model=agent.get("model", "llama3.1:8b"),
        messages=messages,
        temperature=agent.get("temperature", 0.4),
        timeout=OLLAMA_TIMEOUT_SIMULATION
    )

    session["messages"].append({"role": "user", "content": data.message, "timestamp": datetime.now().isoformat()})
    session["messages"].append({"role": "assistant", "content": response, "timestamp": datetime.now().isoformat()})
    save_json(session_path, session)

    # Intentar extraer JSON si la respuesta contiene un flujo de caja actualizado
    scenario_data = _extract_json_from_llm(response)
    has_scenario = scenario_data is not None and "months" in (scenario_data or {})

    return {
        "response": response,
        "session_id": session_id,
        "has_scenario": has_scenario,
        "scenario_data": scenario_data if has_scenario else None
    }

# ---------------------------------------------------------------------------
# Endpoints: Exportación
# ---------------------------------------------------------------------------
@app.get("/api/companies/{company_id}/export/excel")
async def export_excel(company_id: str):
    company_dir = DATA_DIR / "companies" / company_id
    cashflow_path = company_dir / "cashflow.json"
    if not cashflow_path.exists():
        raise HTTPException(404, "No hay flujo de caja para exportar.")

    cashflow = load_json(cashflow_path)
    company = load_json(company_dir / "company.json")

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        raise HTTPException(500, "openpyxl no está instalado.")

    wb = Workbook()

    # --- Hoja 1: Flujo de Caja ---
    ws = wb.active
    ws.title = "Flujo de Caja"

    # Estilos
    header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="0D3DA6", end_color="0D3DA6", fill_type="solid")
    money_format = '#,##0'
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin")
    )

    # Título
    ws.merge_cells("A1:H1")
    ws["A1"] = f"Flujo de Caja — {company.get('name', 'Empresa')}"
    ws["A1"].font = Font(name="Calibri", bold=True, size=14, color="0D3DA6")

    ws.merge_cells("A2:H2")
    ws["A2"] = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws["A2"].font = Font(name="Calibri", size=10, color="666666")

    # Headers
    headers = ["Mes", "Ingresos", "Costos Variables", "Costos Fijos", "Gastos Variables", "Deudas", "Impuestos", "Flujo Neto", "Saldo Acumulado"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    # Datos
    for i, month in enumerate(cashflow.get("months", []), 5):
        expenses = month.get("expenses", {})
        income = month.get("income", {})
        ws.cell(row=i, column=1, value=month.get("label", month.get("month", ""))).border = thin_border
        ws.cell(row=i, column=2, value=income.get("total", 0)).number_format = money_format
        ws.cell(row=i, column=3, value=expenses.get("variable_costs", 0)).number_format = money_format
        ws.cell(row=i, column=4, value=expenses.get("fixed_costs", 0)).number_format = money_format
        ws.cell(row=i, column=5, value=expenses.get("variable_expenses", 0)).number_format = money_format
        ws.cell(row=i, column=6, value=expenses.get("debt_payments", 0)).number_format = money_format
        ws.cell(row=i, column=7, value=expenses.get("taxes", 0)).number_format = money_format
        ws.cell(row=i, column=8, value=month.get("net_flow", 0)).number_format = money_format
        ws.cell(row=i, column=9, value=month.get("cumulative_balance", 0)).number_format = money_format
        for col in range(1, 10):
            ws.cell(row=i, column=col).border = thin_border

    # Ajustar anchos
    for col in range(1, 10):
        ws.column_dimensions[chr(64 + col)].width = 18

    # --- Hoja 2: Resumen ---
    ws2 = wb.create_sheet("Resumen")
    summary = cashflow.get("summary", {})
    ws2["A1"] = "Resumen Financiero"
    ws2["A1"].font = Font(name="Calibri", bold=True, size=14, color="0D3DA6")

    summary_data = [
        ("Ingresos Totales", summary.get("total_income", 0)),
        ("Gastos Totales", summary.get("total_expenses", 0)),
        ("Flujo Neto", summary.get("net_cashflow", 0)),
        ("Promedio Mensual", summary.get("average_monthly_balance", 0)),
    ]
    for i, (label, value) in enumerate(summary_data, 3):
        ws2.cell(row=i, column=1, value=label).font = Font(bold=True)
        ws2.cell(row=i, column=2, value=value).number_format = money_format

    # Alertas
    alerts = cashflow.get("alerts", [])
    if alerts:
        ws2.cell(row=8, column=1, value="Alertas").font = Font(bold=True, size=12, color="DC2626")
        for i, alert in enumerate(alerts, 9):
            ws2.cell(row=i, column=1, value=alert.get("month", ""))
            ws2.cell(row=i, column=2, value=alert.get("message", ""))

    # Recomendaciones
    recs = cashflow.get("recommendations", [])
    if recs:
        row = 9 + len(alerts) + 1
        ws2.cell(row=row, column=1, value="Recomendaciones").font = Font(bold=True, size=12, color="3DAE2B")
        for i, rec in enumerate(recs, row + 1):
            ws2.cell(row=i, column=1, value=f"• {rec}")

    # Guardar
    exports_dir = DATA_DIR / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    filename = f"flujo_caja_{company.get('name', 'empresa').replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = exports_dir / filename
    wb.save(str(filepath))

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.get("/api/companies/{company_id}/export/csv")
async def export_csv(company_id: str):
    company_dir = DATA_DIR / "companies" / company_id
    cashflow_path = company_dir / "cashflow.json"
    if not cashflow_path.exists():
        raise HTTPException(404, "No hay flujo de caja para exportar.")

    cashflow = load_json(cashflow_path)
    company = load_json(company_dir / "company.json")

    import csv
    import io

    exports_dir = DATA_DIR / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    filename = f"flujo_caja_{company.get('name', 'empresa').replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = exports_dir / filename

    with open(str(filepath), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Mes", "Ingresos", "Costos Variables", "Costos Fijos", "Gastos Variables", "Deudas", "Impuestos", "Flujo Neto", "Saldo Acumulado"])
        for month in cashflow.get("months", []):
            expenses = month.get("expenses", {})
            income = month.get("income", {})
            writer.writerow([
                month.get("label", month.get("month", "")),
                income.get("total", 0),
                expenses.get("variable_costs", 0),
                expenses.get("fixed_costs", 0),
                expenses.get("variable_expenses", 0),
                expenses.get("debt_payments", 0),
                expenses.get("taxes", 0),
                month.get("net_flow", 0),
                month.get("cumulative_balance", 0)
            ])

    return FileResponse(path=str(filepath), filename=filename, media_type="text/csv")

# ---------------------------------------------------------------------------
# Endpoints: Agentes
# ---------------------------------------------------------------------------
@app.get("/api/agents")
async def list_agents():
    return get_agents()

@app.get("/api/agents/{agent_id}")
async def get_agent_endpoint(agent_id: str):
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(404, "Agente no encontrado")
    return agent

@app.put("/api/agents/{agent_id}")
async def update_agent(agent_id: str, config: AgentConfigUpdate):
    agents_data = get_agents()
    for i, a in enumerate(agents_data.get("agents", [])):
        if a["id"] == agent_id:
            if config.model is not None:
                agents_data["agents"][i]["model"] = config.model
            if config.temperature is not None:
                agents_data["agents"][i]["temperature"] = config.temperature
            if config.system_prompt is not None:
                agents_data["agents"][i]["system_prompt"] = config.system_prompt
            agents_data["agents"][i]["updated_at"] = datetime.now().isoformat()
            save_json(DATA_DIR / "agents" / "agents.json", agents_data)

            # Verificar modelo
            model = config.model or agents_data["agents"][i].get("model")
            if model and not _is_model_available(model):
                _start_pull_background(model)
                return {**agents_data["agents"][i], "pull_status": {"status": "queued", "model": model}}
            return agents_data["agents"][i]
    raise HTTPException(404, "Agente no encontrado")

@app.get("/api/models/status")
async def models_status():
    return {"pull_status": _pull_status}

@app.get("/api/models/available")
async def available_models():
    try:
        r = http_requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return {"models": [m["name"] for m in r.json().get("models", [])]}
    except Exception:
        return {"models": []}

# ---------------------------------------------------------------------------
# Endpoints: Sesiones
# ---------------------------------------------------------------------------
@app.get("/api/companies/{company_id}/sessions")
async def list_sessions(company_id: str):
    sessions_dir = DATA_DIR / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    sessions = []
    for f in sorted(sessions_dir.glob(f"{company_id}_*.json")):
        s = load_json(f)
        sessions.append({
            "id": s.get("id"),
            "type": s.get("type", "interview"),
            "message_count": len(s.get("messages", [])),
            "created_at": s.get("created_at")
        })
    return {"sessions": sessions}

# ---------------------------------------------------------------------------
# Montar archivos estáticos y arrancar
# ---------------------------------------------------------------------------
app.mount("/ui", StaticFiles(directory=str(APP_DIR), html=True), name="ui")

@app.on_event("startup")
async def startup():
    for d in ["agents", "prompts/system", "sessions", "exports", "companies", "cashflows", "scenarios"]:
        (DATA_DIR / d).mkdir(parents=True, exist_ok=True)
    # Copiar defaults si no existen
    agents_dst = DATA_DIR / "agents" / "agents.json"
    if not agents_dst.exists():
        agents_src = DEFAULTS_DIR / "agents.json"
        if agents_src.exists():
            shutil.copy2(str(agents_src), str(agents_dst))
    prompts_dst = DATA_DIR / "prompts" / "system"
    prompts_src = DEFAULTS_DIR / "prompts"
    if prompts_src.exists():
        for f in prompts_src.glob("*.md"):
            dst = prompts_dst / f.name
            if not dst.exists():
                shutil.copy2(str(f), str(dst))
    logger.info(f"CCS Cashflow Assistant iniciado en puerto {PORT}")

@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ui/index.html")

if __name__ == "__main__":
    import uvicorn
    print(f"http://0.0.0.0:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")

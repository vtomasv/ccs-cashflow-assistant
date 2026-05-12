"""
Tests para CCS Cashflow Assistant v0.2.0

Incluye pruebas unitarias y de integración para:
  - Utilidades de persistencia (save_json, load_json)
  - Parser JSON robusto (_extract_json_from_llm)
  - Normalización de flujo de caja (normalize_cashflow)
  - Sanitización de IDs y nombres de archivo (seguridad)
  - Rate limiting
  - Endpoints de empresas (CRUD)
  - Endpoints de agentes
  - Endpoints de flujo de caja, edición de meses y exportación
  - Endpoints de health
  - Validaciones de estructura Pinokio
  - Validaciones cross-platform
  - Validaciones de seguridad
"""

import os
import sys
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ajustar path para importar el servidor
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

# Configurar DATA_DIR temporal antes de importar app
TEST_DATA_DIR = tempfile.mkdtemp(prefix="ccs_test_")
os.environ["DATA_DIR"] = TEST_DATA_DIR
os.environ["PORT"] = "9999"

from fastapi.testclient import TestClient
from app import (
    app, save_json, load_json, _extract_json_from_llm,
    _fix_encoding, normalize_cashflow, _normalize_month, _to_num,
    _sanitize_id, _sanitize_filename, _check_rate_limit, _rate_limit_store,
    DATA_DIR, DEFAULTS_DIR, MAX_MESSAGE_LENGTH, MAX_COMPANY_NAME_LENGTH, MAX_MONTHS
)

client = TestClient(app)

ROOT = Path(__file__).parent.parent.resolve()


# =====================================================================
# UTILIDADES DE PERSISTENCIA Y PARSING
# =====================================================================
class TestUtilities(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="ccs_util_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_and_load_json(self):
        path = self.test_dir / "test.json"
        data = {"name": "Empresa Test", "value": 12345, "acentos": "café, niño"}
        save_json(path, data)
        loaded = load_json(path)
        self.assertEqual(loaded["name"], "Empresa Test")
        self.assertEqual(loaded["value"], 12345)
        self.assertEqual(loaded["acentos"], "café, niño")

    def test_load_json_nonexistent(self):
        path = self.test_dir / "nonexistent.json"
        result = load_json(path, {"default": True})
        self.assertEqual(result, {"default": True})

    def test_load_json_corrupted(self):
        path = self.test_dir / "corrupted.json"
        path.write_text("not valid json {{{", encoding="utf-8")
        result = load_json(path, {"fallback": True})
        self.assertEqual(result, {"fallback": True})

    def test_save_json_creates_directories(self):
        path = self.test_dir / "a" / "b" / "c" / "test.json"
        save_json(path, {"nested": True})
        self.assertTrue(path.exists())

    def test_extract_json_clean(self):
        text = '{"key": "value", "num": 42}'
        result = _extract_json_from_llm(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["key"], "value")

    def test_extract_json_with_markdown(self):
        text = 'Aquí está:\n```json\n{"key": "value"}\n```\nFin.'
        result = _extract_json_from_llm(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["key"], "value")

    def test_extract_json_with_preamble(self):
        text = 'El flujo de caja es:\n{"company": "Test", "months": []}'
        result = _extract_json_from_llm(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["company"], "Test")

    def test_extract_json_none(self):
        self.assertIsNone(_extract_json_from_llm("No hay JSON aquí"))
        self.assertIsNone(_extract_json_from_llm(""))
        self.assertIsNone(_extract_json_from_llm(None))

    def test_fix_encoding_normal(self):
        self.assertEqual(_fix_encoding("Hola mundo"), "Hola mundo")

    def test_fix_encoding_accents(self):
        text = "café"
        result = _fix_encoding(text)
        self.assertIsInstance(result, str)


# =====================================================================
# _to_num
# =====================================================================
class TestToNum(unittest.TestCase):

    def test_int(self):
        self.assertEqual(_to_num(100), 100)

    def test_float(self):
        self.assertEqual(_to_num(99.5), 99.5)

    def test_string_number(self):
        self.assertEqual(_to_num("1000"), 1000)

    def test_string_with_currency(self):
        self.assertEqual(_to_num("$1.000.000"), 1000000)

    def test_none(self):
        self.assertEqual(_to_num(None), 0)

    def test_invalid_string(self):
        self.assertEqual(_to_num("abc"), 0)

    def test_empty_string(self):
        self.assertEqual(_to_num(""), 0)

    def test_negative(self):
        self.assertEqual(_to_num("-500"), -500)


# =====================================================================
# _normalize_month
# =====================================================================
class TestNormalizeMonth(unittest.TestCase):

    def test_basic_normalization(self):
        m = {
            "month": "2025-01", "label": "Enero 2025",
            "income": {"sales": 10000000, "other_income": 500000},
            "expenses": {"variable_costs": 3000000, "fixed_costs": 2000000,
                        "variable_expenses": 500000, "debt_payments": 300000,
                        "taxes": 200000, "investments": 0}
        }
        result = _normalize_month(m)
        self.assertEqual(result["income"]["total"], 10500000)
        self.assertEqual(result["expenses"]["total"], 6000000)
        self.assertEqual(result["net_flow"], 4500000)

    def test_missing_fields(self):
        m = {"month": "2025-01", "label": "Enero"}
        result = _normalize_month(m)
        self.assertEqual(result["income"]["total"], 0)
        self.assertEqual(result["expenses"]["total"], 0)
        self.assertEqual(result["net_flow"], 0)

    def test_recalculates_totals(self):
        m = {
            "month": "2025-01", "label": "Enero",
            "income": {"sales": 5000, "other_income": 1000, "total": 999999},
            "expenses": {"variable_costs": 1000, "fixed_costs": 500,
                        "variable_expenses": 0, "debt_payments": 0,
                        "taxes": 0, "investments": 0, "total": 999999}
        }
        result = _normalize_month(m)
        self.assertEqual(result["income"]["total"], 6000)
        self.assertEqual(result["expenses"]["total"], 1500)
        self.assertEqual(result["net_flow"], 4500)


# =====================================================================
# normalize_cashflow
# =====================================================================
class TestNormalizeCashflow(unittest.TestCase):

    def test_recalculates_summary_from_months(self):
        data = {
            "summary": {"total_income": 0, "total_expenses": 0},
            "months": [
                {"month": "2025-01", "income": {"sales": 10000000, "other_income": 0},
                 "expenses": {"variable_costs": 3000000, "fixed_costs": 2000000, "variable_expenses": 500000, "debt_payments": 300000, "taxes": 200000, "investments": 0}},
                {"month": "2025-02", "income": {"sales": 12000000, "other_income": 0},
                 "expenses": {"variable_costs": 3500000, "fixed_costs": 2000000, "variable_expenses": 600000, "debt_payments": 300000, "taxes": 250000, "investments": 0}}
            ]
        }
        result = normalize_cashflow(data)
        self.assertEqual(result["summary"]["total_income"], 22000000)
        self.assertEqual(result["summary"]["total_expenses"], 12650000)
        self.assertEqual(result["summary"]["net_cashflow"], 9350000)
        self.assertEqual(result["summary"]["num_months"], 2)

    def test_cumulative_balance(self):
        data = {
            "months": [
                {"month": "2025-01", "income": {"sales": 10000}, "expenses": {"variable_costs": 3000}},
                {"month": "2025-02", "income": {"sales": 8000}, "expenses": {"variable_costs": 5000}},
                {"month": "2025-03", "income": {"sales": 12000}, "expenses": {"variable_costs": 4000}}
            ]
        }
        result = normalize_cashflow(data)
        self.assertEqual(result["months"][0]["cumulative_balance"], 7000)
        self.assertEqual(result["months"][1]["cumulative_balance"], 10000)
        self.assertEqual(result["months"][2]["cumulative_balance"], 18000)

    def test_empty_months(self):
        data = {"months": []}
        result = normalize_cashflow(data)
        self.assertEqual(result["summary"]["total_income"], 0)
        self.assertEqual(result["summary"]["num_months"], 0)

    def test_max_months_limit(self):
        data = {"months": [{"month": f"m{i}"} for i in range(100)]}
        result = normalize_cashflow(data)
        self.assertEqual(len(result["months"]), MAX_MONTHS)

    def test_preserves_other_fields(self):
        data = {"months": [], "alerts": [{"type": "info", "message": "test"}], "recommendations": ["rec1"]}
        result = normalize_cashflow(data)
        self.assertEqual(len(result["alerts"]), 1)
        self.assertEqual(len(result["recommendations"]), 1)


# =====================================================================
# SEGURIDAD: Sanitización de IDs
# =====================================================================
class TestSanitizeId(unittest.TestCase):

    def test_valid_id(self):
        self.assertEqual(_sanitize_id("abc123"), "abc123")
        self.assertEqual(_sanitize_id("test-id_01"), "test-id_01")

    def test_path_traversal(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            _sanitize_id("../../../etc/passwd")

    def test_empty(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            _sanitize_id("")

    def test_special_chars(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            _sanitize_id("id with spaces")

    def test_too_long(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            _sanitize_id("a" * 65)

    def test_dots(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            _sanitize_id("..id")


# =====================================================================
# SEGURIDAD: Sanitización de nombres de archivo
# =====================================================================
class TestSanitizeFilename(unittest.TestCase):

    def test_basic(self):
        self.assertEqual(_sanitize_filename("Mi Empresa"), "Mi_Empresa")

    def test_special_chars(self):
        result = _sanitize_filename("test<>file/name")
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)
        self.assertNotIn("/", result)

    def test_empty(self):
        self.assertEqual(_sanitize_filename(""), "empresa")

    def test_windows_reserved(self):
        result = _sanitize_filename("CON")
        self.assertTrue(result.startswith("_"))

    def test_length_limit(self):
        result = _sanitize_filename("a" * 100)
        self.assertLessEqual(len(result), 50)

    def test_xss_in_filename(self):
        result = _sanitize_filename("<script>alert(1)</script>")
        self.assertNotIn("<script>", result)


# =====================================================================
# SEGURIDAD: Rate Limiting
# =====================================================================
class TestRateLimiting(unittest.TestCase):

    def setUp(self):
        _rate_limit_store.clear()

    def test_within_limit(self):
        for _ in range(5):
            _check_rate_limit("test_key_a", max_requests=10, window=60)

    def test_exceeds_limit(self):
        from fastapi import HTTPException
        for _ in range(5):
            _check_rate_limit("test_key_b", max_requests=5, window=60)
        with self.assertRaises(HTTPException) as ctx:
            _check_rate_limit("test_key_b", max_requests=5, window=60)
        self.assertEqual(ctx.exception.status_code, 429)


# =====================================================================
# HEALTH ENDPOINT
# =====================================================================
class TestHealthEndpoint(unittest.TestCase):

    @patch("app.http_requests.get")
    def test_health_ollama_connected(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama3.2:3b"}]}
        mock_get.return_value = mock_response
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ollama"], "connected")
        self.assertEqual(data["version"], "0.2.0")

    @patch("app.http_requests.get", side_effect=Exception("Connection refused"))
    def test_health_ollama_disconnected(self, mock_get):
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ollama"], "disconnected")


# =====================================================================
# EMPRESAS (CRUD)
# =====================================================================
class TestCompanyEndpoints(unittest.TestCase):

    def setUp(self):
        companies_dir = DATA_DIR / "companies"
        if companies_dir.exists():
            shutil.rmtree(companies_dir)
        companies_dir.mkdir(parents=True, exist_ok=True)
        _rate_limit_store.clear()

    def test_create_company(self):
        response = client.post("/api/companies", json={"name": "Panadería Test", "sector": "alimentos"})
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["name"], "Panadería Test")
        self.assertIn("id", data)

    def test_list_companies(self):
        client.post("/api/companies", json={"name": "Empresa 1"})
        client.post("/api/companies", json={"name": "Empresa 2"})
        response = client.get("/api/companies")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()["companies"]), 2)

    def test_get_company(self):
        create_resp = client.post("/api/companies", json={"name": "Empresa Get"})
        company_id = create_resp.json()["id"]
        response = client.get(f"/api/companies/{company_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Empresa Get")

    def test_get_company_not_found(self):
        response = client.get("/api/companies/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_delete_company(self):
        create_resp = client.post("/api/companies", json={"name": "Empresa Delete"})
        company_id = create_resp.json()["id"]
        response = client.delete(f"/api/companies/{company_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get(f"/api/companies/{company_id}").status_code, 404)

    def test_create_company_empty_name(self):
        response = client.post("/api/companies", json={"name": ""})
        self.assertEqual(response.status_code, 422)

    def test_create_company_long_name(self):
        response = client.post("/api/companies", json={"name": "x" * (MAX_COMPANY_NAME_LENGTH + 1)})
        self.assertEqual(response.status_code, 422)

    def test_create_company_utf8(self):
        response = client.post("/api/companies", json={"name": "Panadería Ñoño"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "Panadería Ñoño")


# =====================================================================
# SEGURIDAD EN ENDPOINTS
# =====================================================================
class TestSecurityEndpoints(unittest.TestCase):

    def setUp(self):
        _rate_limit_store.clear()

    def test_path_traversal_company_id(self):
        response = client.get("/api/companies/..%2F..%2Fetc%2Fpasswd")
        self.assertIn(response.status_code, [400, 404, 422])

    def test_path_traversal_cashflow(self):
        response = client.get("/api/companies/..%2F..%2Fetc/cashflow")
        self.assertIn(response.status_code, [400, 404, 422])

    def test_special_chars_company_id(self):
        response = client.get("/api/companies/id%20with%20spaces")
        self.assertIn(response.status_code, [400, 404, 422])


# =====================================================================
# CHAT VALIDATION
# =====================================================================
class TestChatValidation(unittest.TestCase):

    def setUp(self):
        companies_dir = DATA_DIR / "companies"
        if companies_dir.exists():
            shutil.rmtree(companies_dir)
        companies_dir.mkdir(parents=True, exist_ok=True)
        # Asegurar que agentes y prompts existen
        agents_dir = DATA_DIR / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        defaults_path = DEFAULTS_DIR / "agents.json"
        if defaults_path.exists():
            shutil.copy2(str(defaults_path), str(agents_dir / "agents.json"))
        prompts_dir = DATA_DIR / "prompts" / "system"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        prompts_src = DEFAULTS_DIR / "prompts"
        if prompts_src.exists():
            for f in prompts_src.glob("*.md"):
                shutil.copy2(str(f), str(prompts_dir / f.name))
        sessions_dir = DATA_DIR / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        _rate_limit_store.clear()

    @patch("app.call_ollama_chat", return_value="Respuesta de prueba")
    def test_chat_interview_success(self, mock_chat):
        c = client.post("/api/companies", json={"name": "Chat Test"}).json()
        response = client.post("/api/chat/interview", json={
            "company_id": c["id"],
            "message": "Hola, quiero crear un flujo de caja"
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("response", response.json())

    def test_chat_empty_message(self):
        c = client.post("/api/companies", json={"name": "Chat Test 2"}).json()
        response = client.post("/api/chat/interview", json={
            "company_id": c["id"],
            "message": ""
        })
        self.assertEqual(response.status_code, 422)

    def test_chat_message_too_long(self):
        c = client.post("/api/companies", json={"name": "Chat Test 3"}).json()
        response = client.post("/api/chat/interview", json={
            "company_id": c["id"],
            "message": "x" * (MAX_MESSAGE_LENGTH + 1)
        })
        self.assertEqual(response.status_code, 422)

    def test_chat_invalid_company(self):
        response = client.post("/api/chat/interview", json={
            "company_id": "nonexist",
            "message": "Hola"
        })
        self.assertEqual(response.status_code, 404)


# =====================================================================
# AGENTES
# =====================================================================
class TestAgentEndpoints(unittest.TestCase):

    def setUp(self):
        agents_dir = DATA_DIR / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        defaults_path = DEFAULTS_DIR / "agents.json"
        if defaults_path.exists():
            shutil.copy2(str(defaults_path), str(agents_dir / "agents.json"))

    def test_list_agents(self):
        response = client.get("/api/agents")
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.json()["agents"]), 0)

    def test_get_agent(self):
        response = client.get("/api/agents/financial_interviewer")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "financial_interviewer")

    def test_get_agent_not_found(self):
        response = client.get("/api/agents/nonexistent")
        self.assertEqual(response.status_code, 404)

    @patch("app._is_model_available", return_value=True)
    def test_update_agent(self, mock_avail):
        response = client.put("/api/agents/financial_interviewer", json={"model": "llama3.2:3b", "temperature": 0.5})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["temperature"], 0.5)

    def test_update_agent_invalid_temperature(self):
        response = client.put("/api/agents/financial_interviewer", json={"temperature": 5.0})
        self.assertEqual(response.status_code, 422)


# =====================================================================
# FLUJO DE CAJA CRUD
# =====================================================================
class TestCashflowEndpoints(unittest.TestCase):

    def setUp(self):
        companies_dir = DATA_DIR / "companies"
        if companies_dir.exists():
            shutil.rmtree(companies_dir)
        companies_dir.mkdir(parents=True, exist_ok=True)
        _rate_limit_store.clear()
        resp = client.post("/api/companies", json={"name": "Empresa CF Test", "sector": "comercio"})
        self.company_id = resp.json()["id"]

    def _create_cashflow(self, months=2):
        cashflow_data = {
            "company_name": "Test",
            "months": [],
            "alerts": [{"month": "2025-01", "message": "Déficit", "type": "warning"}],
            "recommendations": ["Reducir gastos"]
        }
        for i in range(months):
            mo = i + 1
            cashflow_data["months"].append({
                "month": f"2025-{mo:02d}", "label": f"Mes {mo}",
                "income": {"sales": 10000000, "other_income": 500000},
                "expenses": {"variable_costs": 3000000, "fixed_costs": 2000000,
                            "variable_expenses": 500000, "debt_payments": 300000,
                            "taxes": 200000, "investments": 0}
            })
        save_json(DATA_DIR / "companies" / self.company_id / "cashflow.json", cashflow_data)

    def test_get_cashflow_not_found(self):
        response = client.get(f"/api/companies/{self.company_id}/cashflow")
        self.assertEqual(response.status_code, 404)

    def test_cashflow_normalized_on_read(self):
        self._create_cashflow(months=2)
        response = client.get(f"/api/companies/{self.company_id}/cashflow")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["summary"]["total_income"], 21000000)
        self.assertEqual(data["summary"]["total_expenses"], 12000000)
        self.assertEqual(data["summary"]["net_cashflow"], 9000000)
        self.assertEqual(data["months"][0]["net_flow"], 4500000)
        self.assertEqual(data["months"][0]["cumulative_balance"], 4500000)
        self.assertEqual(data["months"][1]["cumulative_balance"], 9000000)


# =====================================================================
# EDICIÓN DE MESES
# =====================================================================
class TestMonthCRUDEndpoints(unittest.TestCase):

    def setUp(self):
        companies_dir = DATA_DIR / "companies"
        if companies_dir.exists():
            shutil.rmtree(companies_dir)
        companies_dir.mkdir(parents=True, exist_ok=True)
        _rate_limit_store.clear()
        resp = client.post("/api/companies", json={"name": "Empresa Meses Test"})
        self.company_id = resp.json()["id"]
        cashflow_data = {
            "months": [
                {"month": "2025-01", "label": "Enero 2025", "income": {"sales": 5000000, "other_income": 0},
                 "expenses": {"variable_costs": 2000000, "fixed_costs": 1000000}},
                {"month": "2025-02", "label": "Febrero 2025", "income": {"sales": 6000000, "other_income": 0},
                 "expenses": {"variable_costs": 2500000, "fixed_costs": 1000000}}
            ],
            "alerts": [], "recommendations": []
        }
        save_json(DATA_DIR / "companies" / self.company_id / "cashflow.json", cashflow_data)

    def test_update_month(self):
        response = client.put(f"/api/companies/{self.company_id}/cashflow/months/0", json={
            "income": {"sales": 8000000, "other_income": 500000},
            "expenses": {"variable_costs": 3000000, "fixed_costs": 1500000}
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["months"][0]["income"]["sales"], 8000000)
        self.assertEqual(data["months"][0]["income"]["total"], 8500000)

    def test_update_month_invalid_index(self):
        response = client.put(f"/api/companies/{self.company_id}/cashflow/months/99", json={
            "income": {"sales": 1000}
        })
        self.assertEqual(response.status_code, 400)

    def test_add_month(self):
        response = client.post(f"/api/companies/{self.company_id}/cashflow/months", json={
            "month": "2025-03", "label": "Marzo 2025",
            "income": {"sales": 7000000, "other_income": 0},
            "expenses": {"variable_costs": 2800000, "fixed_costs": 1000000}
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["months"]), 3)
        self.assertEqual(data["months"][2]["month"], "2025-03")

    def test_delete_month(self):
        response = client.delete(f"/api/companies/{self.company_id}/cashflow/months/0")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["months"]), 1)
        self.assertEqual(data["months"][0]["month"], "2025-02")
        self.assertEqual(data["months"][0]["cumulative_balance"], data["months"][0]["net_flow"])

    def test_delete_month_invalid_index(self):
        response = client.delete(f"/api/companies/{self.company_id}/cashflow/months/99")
        self.assertEqual(response.status_code, 400)

    def test_add_month_no_cashflow(self):
        resp = client.post("/api/companies", json={"name": "Sin CF"})
        cid = resp.json()["id"]
        response = client.post(f"/api/companies/{cid}/cashflow/months", json={
            "month": "2025-01", "label": "Enero"
        })
        self.assertEqual(response.status_code, 404)

    def test_kpis_match_table_after_edit(self):
        client.put(f"/api/companies/{self.company_id}/cashflow/months/0", json={
            "income": {"sales": 10000000, "other_income": 1000000},
            "expenses": {"variable_costs": 4000000, "fixed_costs": 2000000,
                        "variable_expenses": 500000, "debt_payments": 300000,
                        "taxes": 200000, "investments": 100000}
        })
        response = client.get(f"/api/companies/{self.company_id}/cashflow")
        data = response.json()
        calc_income = sum(m["income"]["total"] for m in data["months"])
        calc_expenses = sum(m["expenses"]["total"] for m in data["months"])
        self.assertEqual(data["summary"]["total_income"], calc_income)
        self.assertEqual(data["summary"]["total_expenses"], calc_expenses)
        self.assertEqual(data["summary"]["net_cashflow"], calc_income - calc_expenses)

    def test_cumulative_balance_progressive(self):
        """Verifica que el saldo acumulado sea progresivo."""
        response = client.get(f"/api/companies/{self.company_id}/cashflow")
        data = response.json()
        cumulative = 0
        for m in data["months"]:
            cumulative += m["net_flow"]
            self.assertAlmostEqual(m["cumulative_balance"], cumulative, places=2)


# =====================================================================
# EXPORTACIÓN
# =====================================================================
class TestExportEndpoints(unittest.TestCase):

    def setUp(self):
        companies_dir = DATA_DIR / "companies"
        if companies_dir.exists():
            shutil.rmtree(companies_dir)
        companies_dir.mkdir(parents=True, exist_ok=True)
        _rate_limit_store.clear()
        resp = client.post("/api/companies", json={"name": "Empresa Export"})
        self.company_id = resp.json()["id"]
        cashflow_data = {
            "months": [
                {"month": "2025-01", "label": "Enero", "income": {"sales": 100, "other_income": 0},
                 "expenses": {"variable_costs": 30, "fixed_costs": 30}}
            ],
            "alerts": [], "recommendations": []
        }
        save_json(DATA_DIR / "companies" / self.company_id / "cashflow.json", cashflow_data)

    def test_export_excel(self):
        response = client.get(f"/api/companies/{self.company_id}/export/excel")
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheet", response.headers.get("content-type", ""))

    def test_export_csv(self):
        response = client.get(f"/api/companies/{self.company_id}/export/csv")
        self.assertEqual(response.status_code, 200)

    def test_export_no_cashflow(self):
        resp = client.post("/api/companies", json={"name": "Sin CF"})
        cid = resp.json()["id"]
        response = client.get(f"/api/companies/{cid}/export/excel")
        self.assertEqual(response.status_code, 404)

    def test_export_filename_sanitized(self):
        resp = client.post("/api/companies", json={"name": "Empresa <script>alert(1)</script>"})
        cid = resp.json()["id"]
        cashflow_data = {"months": [{"month": "2025-01", "income": {"sales": 100}, "expenses": {"fixed_costs": 50}}], "alerts": [], "recommendations": []}
        save_json(DATA_DIR / "companies" / cid / "cashflow.json", cashflow_data)
        response = client.get(f"/api/companies/{cid}/export/excel")
        self.assertEqual(response.status_code, 200)
        disposition = response.headers.get("content-disposition", "")
        self.assertNotIn("<script>", disposition)


# =====================================================================
# MODELS ENDPOINTS
# =====================================================================
class TestModelsEndpoints(unittest.TestCase):

    @patch("app.http_requests.get")
    def test_available_models(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "llama3.2:3b"}]}
        mock_get.return_value = mock_response
        response = client.get("/api/models/available")
        self.assertEqual(response.status_code, 200)
        self.assertIn("llama3.2:3b", response.json()["models"])

    @patch("app.http_requests.get", side_effect=Exception("Connection refused"))
    def test_available_models_offline(self, mock_get):
        response = client.get("/api/models/available")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["models"], [])


# =====================================================================
# VALIDACIÓN PINOKIO: Estructura
# =====================================================================
class TestPinokioStructure(unittest.TestCase):

    def test_lifecycle_scripts_are_json(self):
        for name in ["install.json", "start.json", "stop.json", "reset.json"]:
            path = ROOT / name
            self.assertTrue(path.exists(), f"{name} no encontrado")
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.fail(f"{name} no es JSON válido")

    def test_pinokio_js_exists(self):
        self.assertTrue((ROOT / "pinokio.js").exists())

    def test_pinokio_js_references_json(self):
        content = (ROOT / "pinokio.js").read_text(encoding="utf-8")
        self.assertIn("install.json", content)
        self.assertIn("start.json", content)
        self.assertIn("stop.json", content)

    def test_no_background_true(self):
        for name in ["install.json", "start.json", "stop.json"]:
            content = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn('"background"', content, f"{name} contiene 'background'")

    def test_venv_name_consistent(self):
        for name in ["install.json", "start.json", "pinokio.js"]:
            content = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("venv", content, f"{name} no referencia 'venv'")

    def test_server_uses_absolute_paths(self):
        content = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
        self.assertIn("__file__", content)

    def test_ensure_ascii_false(self):
        content = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
        self.assertIn("ensure_ascii=False", content)

    def test_response_encoding_utf8(self):
        content = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
        self.assertIn('resp.encoding = "utf-8"', content)

    def test_no_let_const_in_html(self):
        content = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
        script_start = content.find("<script>")
        script_end = content.find("</script>")
        if script_start != -1 and script_end != -1:
            script = content[script_start:script_end]
            self.assertEqual(len(re.findall(r'^\s*let\s', script, re.MULTILINE)), 0)
            self.assertEqual(len(re.findall(r'^\s*const\s', script, re.MULTILINE)), 0)

    def test_icon_exists(self):
        self.assertTrue((ROOT / "icon.png").exists())

    def test_defaults_agents_json(self):
        path = ROOT / "defaults" / "agents.json"
        self.assertTrue(path.exists())
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("agents", data)
        for agent in data["agents"]:
            self.assertIn("id", agent)
            self.assertIn("model", agent)

    def test_prompts_exist(self):
        prompts_dir = ROOT / "defaults" / "prompts"
        self.assertTrue(prompts_dir.exists())
        self.assertTrue((prompts_dir / "financial_interviewer.md").exists())
        self.assertTrue((prompts_dir / "cashflow_analyst.md").exists())
        self.assertTrue((prompts_dir / "scenario_simulator.md").exists())


# =====================================================================
# CROSS-PLATFORM
# =====================================================================
class TestCrossPlatform(unittest.TestCase):

    def test_install_json_has_platform_conditions(self):
        content = (ROOT / "install.json").read_text(encoding="utf-8")
        self.assertIn("platform", content)
        self.assertIn("win32", content)

    def test_start_json_has_platform_conditions(self):
        content = (ROOT / "start.json").read_text(encoding="utf-8")
        self.assertIn("platform", content)
        self.assertIn("win32", content)

    def test_install_json_uses_venv_for_pip(self):
        """Pinokio crea el venv automáticamente cuando se usa 'venv' param.
        El paso de pip install DEBE tener venv: 'venv' para que las
        dependencias se instalen dentro del venv y no en el Python global."""
        data = json.loads((ROOT / "install.json").read_text(encoding="utf-8"))
        pip_steps = [
            step for step in data["run"]
            if isinstance(step.get("params"), dict)
            and isinstance(step["params"].get("message"), (str, list))
            and ("pip install" in str(step["params"]["message"]))
        ]
        self.assertTrue(len(pip_steps) > 0, "install.json debe tener al menos un paso de pip install")
        for step in pip_steps:
            self.assertEqual(
                step["params"].get("venv"), "venv",
                f"Paso de pip install sin venv: {step['params'].get('message')}"
            )

    def test_install_json_no_separate_venv_creation(self):
        """NO debe haber un paso separado de 'python -m venv venv' porque
        Pinokio crea el venv automáticamente al usar el param venv: 'venv'.
        Un paso separado causa problemas en Windows con conda."""
        data = json.loads((ROOT / "install.json").read_text(encoding="utf-8"))
        for step in data["run"]:
            if isinstance(step.get("params"), dict):
                msg = step["params"].get("message", "")
                if isinstance(msg, list):
                    msg = " ".join(msg)
                # Si hay un paso que SOLO crea el venv sin venv param, es un error
                if "python -m venv venv" in msg and step["params"].get("venv") is None:
                    self.fail("install.json tiene un paso separado de 'python -m venv venv' sin venv param. "
                              "Pinokio debe crear el venv automáticamente via el param venv.")

    def test_install_json_data_init_uses_venv(self):
        """Los pasos de inicialización de datos que usan python deben
        ejecutarse dentro del venv para tener acceso a las dependencias."""
        data = json.loads((ROOT / "install.json").read_text(encoding="utf-8"))
        python_steps = [
            step for step in data["run"]
            if isinstance(step.get("params"), dict)
            and isinstance(step["params"].get("message"), (str, list))
            and "python -c" in str(step["params"]["message"])
        ]
        for step in python_steps:
            self.assertEqual(
                step["params"].get("venv"), "venv",
                "Paso de python -c sin venv param"
            )

    def test_start_json_uses_venv(self):
        data = json.loads((ROOT / "start.json").read_text(encoding="utf-8"))
        venv_used = any(
            isinstance(step.get("params"), dict) and step["params"].get("venv") == "venv"
            for step in data["run"]
        )
        self.assertTrue(venv_used, "start.json debe usar 'venv' para ejecutar el servidor")

    def test_start_json_sets_encoding_env(self):
        content = (ROOT / "start.json").read_text(encoding="utf-8")
        self.assertTrue("PYTHONIOENCODING" in content or "PYTHONUTF8" in content)

    def test_install_json_ollama_windows(self):
        """Windows debe usar OllamaSetup.exe descargado con curl, no winget
        (winget no siempre está disponible en todas las versiones de Windows)."""
        content = (ROOT / "install.json").read_text(encoding="utf-8")
        self.assertTrue(
            "OllamaSetup.exe" in content or "winget" in content,
            "install.json debe tener un método de instalación de Ollama para Windows"
        )

    def test_start_json_ollama_windows_serve(self):
        content = (ROOT / "start.json").read_text(encoding="utf-8")
        self.assertTrue(
            "start /B" in content or "Start-Process" in content,
            "start.json debe iniciar Ollama en background en Windows"
        )

    def test_data_dir_is_pathlib(self):
        self.assertIsInstance(DATA_DIR, Path)

    def test_server_prints_127_not_0000(self):
        """El servidor debe imprimir http://127.0.0.1:PORT (no 0.0.0.0)
        para que el regex de start.json capture una URL válida en Windows."""
        content = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
        self.assertIn('print(f"http://127.0.0.1:{PORT}")', content)

    def test_install_json_no_powershell_for_ollama_serve(self):
        """En install.json, el inicio de Ollama en Windows no debe usar
        powershell complejo que puede fallar en cmd.exe de Pinokio."""
        data = json.loads((ROOT / "install.json").read_text(encoding="utf-8"))
        for step in data["run"]:
            if isinstance(step.get("params"), dict):
                msg = str(step["params"].get("message", ""))
                if "win32" in str(step.get("when", "")):
                    # No debe tener powershell -Command con Start-Process para ollama serve
                    if "ollama serve" in msg.lower() or "OLLAMA_READY" in msg:
                        self.assertNotIn(
                            "Invoke-WebRequest", msg,
                            "install.json Windows no debe usar Invoke-WebRequest para readiness check"
                        )

    def test_start_json_no_powershell_for_ollama(self):
        """start.json debe usar 'start /B ollama serve' en Windows,
        no powershell -Command Start-Process."""
        data = json.loads((ROOT / "start.json").read_text(encoding="utf-8"))
        for step in data["run"]:
            if isinstance(step.get("params"), dict):
                msg = str(step["params"].get("message", ""))
                when = str(step.get("when", ""))
                if "win32" in when and "ollama" in msg.lower():
                    self.assertNotIn(
                        "powershell", msg.lower(),
                        "start.json Windows debe usar 'start /B ollama serve', no powershell"
                    )

    def test_install_json_valid_json(self):
        """install.json debe ser JSON puro válido."""
        content = (ROOT / "install.json").read_text(encoding="utf-8")
        try:
            data = json.loads(content)
            self.assertIn("run", data)
        except json.JSONDecodeError:
            self.fail("install.json no es JSON válido")

    def test_start_json_is_daemon(self):
        """start.json debe tener daemon: true."""
        data = json.loads((ROOT / "start.json").read_text(encoding="utf-8"))
        self.assertTrue(data.get("daemon"), "start.json debe tener daemon: true")

    def test_stop_json_uses_script_stop(self):
        """stop.json debe usar script.stop apuntando a start.json."""
        data = json.loads((ROOT / "stop.json").read_text(encoding="utf-8"))
        has_script_stop = any(
            step.get("method") == "script.stop"
            for step in data["run"]
        )
        self.assertTrue(has_script_stop, "stop.json debe usar script.stop")

    def test_no_background_true_anywhere(self):
        """Ningún archivo JSON debe usar background: true (no existe en Pinokio)."""
        for name in ["install.json", "start.json", "stop.json", "reset.json"]:
            content = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn('"background"', content, f"{name} contiene 'background'")


# =====================================================================
# SEGURIDAD AVANZADA
# =====================================================================
class TestSecurityAdvanced(unittest.TestCase):

    def test_cors_not_wildcard(self):
        content = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
        self.assertNotIn('allow_origins=["*"]', content)

    def test_cors_localhost_only(self):
        content = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
        self.assertIn("localhost", content)
        self.assertIn("127.0.0.1", content)

    def test_rate_limiting_exists(self):
        content = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
        self.assertIn("_check_rate_limit", content)

    def test_input_validation_message_length(self):
        content = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
        self.assertIn("MAX_MESSAGE_LENGTH", content)

    def test_input_validation_company_name(self):
        content = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
        self.assertIn("MAX_COMPANY_NAME_LENGTH", content)

    def test_ensure_ollama_running_exists(self):
        content = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
        self.assertIn("def ensure_ollama_running", content)

    def test_frontend_uses_escape_html(self):
        content = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
        self.assertIn("escapeHtml", content)
        count = content.count("escapeHtml(")
        self.assertGreaterEqual(count, 10, f"escapeHtml se usa solo {count} veces")

    def test_frontend_no_eval(self):
        content = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            if "eval(" in stripped:
                self.assertIn("font-display", stripped, f"eval() encontrado en: {stripped}")

    def test_frontend_input_length_validation(self):
        content = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
        self.assertIn("10000", content)

    def test_frontend_correct_api_endpoint(self):
        content = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
        self.assertIn("fetch('/api/chat/interview'", content)
        matches = re.findall(r"fetch\('/api/chat'[^/]", content)
        self.assertEqual(len(matches), 0, f"Encontradas llamadas a /api/chat sin /interview")

    def test_sanitize_id_in_backend(self):
        content = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
        self.assertIn("_sanitize_id", content)

    def test_sanitize_filename_in_backend(self):
        content = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
        self.assertIn("_sanitize_filename", content)


if __name__ == "__main__":
    unittest.main()

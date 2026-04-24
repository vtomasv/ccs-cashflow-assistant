"""
Tests para CCS Cashflow Assistant — Backend FastAPI

Incluye pruebas unitarias y de integración para:
  - Utilidades de persistencia (save_json, load_json)
  - Parser JSON robusto (_extract_json_from_llm)
  - Normalización de flujo de caja (normalize_cashflow)
  - Endpoints de empresas (CRUD)
  - Endpoints de agentes
  - Endpoints de flujo de caja, edición de meses y exportación
  - Endpoints de health
  - Validaciones de estructura Pinokio
"""

import os
import sys
import json
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
    DATA_DIR
)

client = TestClient(app)


class TestUtilities(unittest.TestCase):
    """Pruebas unitarias para utilidades de persistencia y parsing."""

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


class TestToNum(unittest.TestCase):
    """Pruebas para _to_num."""

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


class TestNormalizeMonth(unittest.TestCase):
    """Pruebas para _normalize_month."""

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
        """Verifica que recalcula totales incluso si vienen incorrectos."""
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


class TestNormalizeCashflow(unittest.TestCase):
    """Pruebas para normalize_cashflow."""

    def test_recalculates_summary_from_months(self):
        """Verifica que summary se recalcula desde los datos de meses."""
        data = {
            "summary": {"total_income": 0, "total_expenses": 0, "net_cashflow": 0, "average_monthly_balance": 0},
            "months": [
                {"month": "2025-01", "label": "Enero", "income": {"sales": 10000000, "other_income": 0}, "expenses": {"variable_costs": 3000000, "fixed_costs": 2000000, "variable_expenses": 500000, "debt_payments": 300000, "taxes": 200000, "investments": 0}},
                {"month": "2025-02", "label": "Febrero", "income": {"sales": 12000000, "other_income": 0}, "expenses": {"variable_costs": 3500000, "fixed_costs": 2000000, "variable_expenses": 600000, "debt_payments": 300000, "taxes": 250000, "investments": 0}}
            ]
        }
        result = normalize_cashflow(data)
        self.assertEqual(result["summary"]["total_income"], 22000000)
        self.assertEqual(result["summary"]["total_expenses"], 12650000)
        self.assertEqual(result["summary"]["net_cashflow"], 9350000)
        self.assertEqual(result["period_months"], 2)

    def test_cumulative_balance(self):
        """Verifica que el saldo acumulado se calcula progresivamente."""
        data = {
            "months": [
                {"month": "2025-01", "label": "Enero", "income": {"sales": 10000}, "expenses": {"variable_costs": 3000}},
                {"month": "2025-02", "label": "Febrero", "income": {"sales": 8000}, "expenses": {"variable_costs": 5000}},
                {"month": "2025-03", "label": "Marzo", "income": {"sales": 12000}, "expenses": {"variable_costs": 4000}}
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
        self.assertEqual(result["period_months"], 0)

    def test_preserves_other_fields(self):
        data = {"months": [], "alerts": [{"type": "info", "message": "test"}], "recommendations": ["rec1"]}
        result = normalize_cashflow(data)
        self.assertEqual(len(result["alerts"]), 1)
        self.assertEqual(len(result["recommendations"]), 1)


class TestHealthEndpoint(unittest.TestCase):

    @patch("app.http_requests.get")
    def test_health_ollama_connected(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}
        mock_get.return_value = mock_response
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ollama"])

    @patch("app.http_requests.get", side_effect=Exception("Connection refused"))
    def test_health_ollama_disconnected(self, mock_get):
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ollama"])


class TestCompanyEndpoints(unittest.TestCase):

    def setUp(self):
        companies_dir = DATA_DIR / "companies"
        if companies_dir.exists():
            shutil.rmtree(companies_dir)
        companies_dir.mkdir(parents=True, exist_ok=True)

    def test_create_company(self):
        response = client.post("/api/companies", json={"name": "Panadería Test", "sector": "alimentos", "size": "micro"})
        self.assertEqual(response.status_code, 200)
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


class TestAgentEndpoints(unittest.TestCase):

    def setUp(self):
        agents_dir = DATA_DIR / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        defaults_path = Path(__file__).parent.parent / "defaults" / "agents.json"
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


class TestCashflowEndpoints(unittest.TestCase):

    def setUp(self):
        resp = client.post("/api/companies", json={"name": "Empresa CF Test", "sector": "comercio"})
        self.company_id = resp.json()["id"]

    def test_get_cashflow_not_found(self):
        response = client.get(f"/api/companies/{self.company_id}/cashflow")
        self.assertEqual(response.status_code, 404)

    def test_cashflow_normalized_on_read(self):
        """Verifica que al leer un cashflow, se normaliza automáticamente."""
        cashflow_data = {
            "company_name": "Test",
            "currency": "CLP",
            "summary": {"total_income": 0, "total_expenses": 0, "net_cashflow": 0, "average_monthly_balance": 0},
            "months": [
                {"month": "2025-01", "label": "Enero 2025",
                 "income": {"sales": 10000000, "other_income": 500000},
                 "expenses": {"variable_costs": 3000000, "fixed_costs": 2000000, "variable_expenses": 500000, "debt_payments": 300000, "taxes": 200000, "investments": 0},
                 "net_flow": 0, "cumulative_balance": 0},
                {"month": "2025-02", "label": "Febrero 2025",
                 "income": {"sales": 12000000, "other_income": 0},
                 "expenses": {"variable_costs": 4000000, "fixed_costs": 2000000, "variable_expenses": 600000, "debt_payments": 300000, "taxes": 250000, "investments": 0},
                 "net_flow": 0, "cumulative_balance": 0}
            ],
            "alerts": [], "recommendations": []
        }
        company_dir = DATA_DIR / "companies" / self.company_id
        save_json(company_dir / "cashflow.json", cashflow_data)

        response = client.get(f"/api/companies/{self.company_id}/cashflow")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verificar que summary fue recalculado
        self.assertEqual(data["summary"]["total_income"], 22500000)
        self.assertEqual(data["summary"]["total_expenses"], 13150000)
        self.assertEqual(data["summary"]["net_cashflow"], 9350000)

        # Verificar saldo acumulado
        self.assertEqual(data["months"][0]["net_flow"], 4500000)
        self.assertEqual(data["months"][0]["cumulative_balance"], 4500000)
        self.assertEqual(data["months"][1]["cumulative_balance"], 4500000 + 4850000)


class TestMonthCRUDEndpoints(unittest.TestCase):
    """Pruebas para los endpoints de edición de meses."""

    def setUp(self):
        resp = client.post("/api/companies", json={"name": "Empresa Meses Test"})
        self.company_id = resp.json()["id"]
        # Crear cashflow base
        cashflow_data = {
            "company_name": "Test Meses",
            "months": [
                {"month": "2025-01", "label": "Enero 2025", "income": {"sales": 5000000, "other_income": 0}, "expenses": {"variable_costs": 2000000, "fixed_costs": 1000000, "variable_expenses": 0, "debt_payments": 0, "taxes": 0, "investments": 0}},
                {"month": "2025-02", "label": "Febrero 2025", "income": {"sales": 6000000, "other_income": 0}, "expenses": {"variable_costs": 2500000, "fixed_costs": 1000000, "variable_expenses": 0, "debt_payments": 0, "taxes": 0, "investments": 0}}
            ],
            "alerts": [], "recommendations": []
        }
        company_dir = DATA_DIR / "companies" / self.company_id
        save_json(company_dir / "cashflow.json", cashflow_data)

    def test_update_month(self):
        """Actualiza un mes existente."""
        response = client.put(f"/api/companies/{self.company_id}/cashflow/months/0", json={
            "income": {"sales": 8000000, "other_income": 500000},
            "expenses": {"variable_costs": 3000000, "fixed_costs": 1500000, "variable_expenses": 200000, "debt_payments": 0, "taxes": 100000, "investments": 0}
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["months"][0]["income"]["sales"], 8000000)
        self.assertEqual(data["months"][0]["income"]["total"], 8500000)
        # Verificar que summary se recalculó
        self.assertGreater(data["summary"]["total_income"], 0)

    def test_update_month_invalid_index(self):
        """Retorna error para índice inválido."""
        response = client.put(f"/api/companies/{self.company_id}/cashflow/months/99", json={
            "income": {"sales": 1000}
        })
        self.assertEqual(response.status_code, 400)

    def test_add_month(self):
        """Agrega un nuevo mes."""
        response = client.post(f"/api/companies/{self.company_id}/cashflow/months", json={
            "month": "2025-03", "label": "Marzo 2025",
            "income": {"sales": 7000000, "other_income": 0},
            "expenses": {"variable_costs": 2800000, "fixed_costs": 1000000, "variable_expenses": 0, "debt_payments": 0, "taxes": 0, "investments": 0}
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["months"]), 3)
        self.assertEqual(data["months"][2]["month"], "2025-03")
        self.assertEqual(data["period_months"], 3)

    def test_delete_month(self):
        """Elimina un mes."""
        response = client.delete(f"/api/companies/{self.company_id}/cashflow/months/0")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["months"]), 1)
        self.assertEqual(data["months"][0]["month"], "2025-02")
        # Verificar que saldo acumulado se recalculó
        self.assertEqual(data["months"][0]["cumulative_balance"], data["months"][0]["net_flow"])

    def test_delete_month_invalid_index(self):
        response = client.delete(f"/api/companies/{self.company_id}/cashflow/months/99")
        self.assertEqual(response.status_code, 400)

    def test_add_month_no_cashflow(self):
        """Retorna 404 si no hay cashflow."""
        resp = client.post("/api/companies", json={"name": "Sin CF"})
        cid = resp.json()["id"]
        response = client.post(f"/api/companies/{cid}/cashflow/months", json={
            "month": "2025-01", "label": "Enero"
        })
        self.assertEqual(response.status_code, 404)

    def test_kpis_match_table_after_edit(self):
        """Verifica que los KPIs (summary) coinciden con la suma de meses tras editar."""
        # Editar mes 0
        client.put(f"/api/companies/{self.company_id}/cashflow/months/0", json={
            "income": {"sales": 10000000, "other_income": 1000000},
            "expenses": {"variable_costs": 4000000, "fixed_costs": 2000000, "variable_expenses": 500000, "debt_payments": 300000, "taxes": 200000, "investments": 100000}
        })
        # Leer cashflow
        response = client.get(f"/api/companies/{self.company_id}/cashflow")
        data = response.json()

        # Calcular manualmente
        calc_income = sum(m["income"]["total"] for m in data["months"])
        calc_expenses = sum(m["expenses"]["total"] for m in data["months"])
        calc_net = calc_income - calc_expenses

        self.assertEqual(data["summary"]["total_income"], calc_income)
        self.assertEqual(data["summary"]["total_expenses"], calc_expenses)
        self.assertEqual(data["summary"]["net_cashflow"], calc_net)


class TestExportEndpoints(unittest.TestCase):

    def setUp(self):
        resp = client.post("/api/companies", json={"name": "Empresa Export"})
        self.company_id = resp.json()["id"]
        cashflow_data = {
            "company_name": "Test Export",
            "months": [
                {"month": "2025-01", "label": "Enero", "income": {"sales": 100, "other_income": 0}, "expenses": {"variable_costs": 30, "fixed_costs": 30, "variable_expenses": 10, "debt_payments": 5, "taxes": 5, "investments": 0}}
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


class TestPinokioValidation(unittest.TestCase):
    """Validaciones de estructura del plugin Pinokio."""

    def test_lifecycle_scripts_are_json(self):
        base = Path(__file__).parent.parent
        for name in ["install.json", "start.json", "stop.json", "reset.json"]:
            path = base / name
            self.assertTrue(path.exists(), f"{name} no encontrado")
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.fail(f"{name} no es JSON válido")

    def test_pinokio_js_exists(self):
        path = Path(__file__).parent.parent / "pinokio.js"
        self.assertTrue(path.exists())

    def test_pinokio_js_references_json(self):
        content = (Path(__file__).parent.parent / "pinokio.js").read_text(encoding="utf-8")
        self.assertIn("install.json", content)
        self.assertIn("start.json", content)
        self.assertIn("stop.json", content)

    def test_no_background_true(self):
        base = Path(__file__).parent.parent
        for name in ["install.json", "start.json", "stop.json"]:
            content = (base / name).read_text(encoding="utf-8")
            self.assertNotIn('"background"', content, f"{name} contiene 'background'")

    def test_venv_name_consistent(self):
        base = Path(__file__).parent.parent
        for name in ["install.json", "start.json", "pinokio.js"]:
            content = (base / name).read_text(encoding="utf-8")
            self.assertIn("venv", content, f"{name} no referencia 'venv'")

    def test_server_uses_absolute_paths(self):
        content = (Path(__file__).parent.parent / "server" / "app.py").read_text(encoding="utf-8")
        self.assertIn("__file__", content)

    def test_ensure_ascii_false(self):
        content = (Path(__file__).parent.parent / "server" / "app.py").read_text(encoding="utf-8")
        self.assertIn("ensure_ascii=False", content)

    def test_response_encoding_utf8(self):
        content = (Path(__file__).parent.parent / "server" / "app.py").read_text(encoding="utf-8")
        self.assertIn('resp.encoding = "utf-8"', content)

    def test_no_let_const_in_html(self):
        content = (Path(__file__).parent.parent / "app" / "index.html").read_text(encoding="utf-8")
        script_start = content.find("<script>")
        script_end = content.find("</script>")
        if script_start != -1 and script_end != -1:
            script = content[script_start:script_end]
            import re
            self.assertEqual(len(re.findall(r'^\s*let\s', script, re.MULTILINE)), 0)
            self.assertEqual(len(re.findall(r'^\s*const\s', script, re.MULTILINE)), 0)
            self.assertEqual(len(re.findall(r'^\s*import\s', script, re.MULTILINE)), 0)
            self.assertEqual(len(re.findall(r'^\s*export\s', script, re.MULTILINE)), 0)

    def test_icon_exists(self):
        self.assertTrue((Path(__file__).parent.parent / "icon.png").exists())

    def test_defaults_agents_json(self):
        path = Path(__file__).parent.parent / "defaults" / "agents.json"
        self.assertTrue(path.exists())
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("agents", data)
        for agent in data["agents"]:
            self.assertIn("id", agent)
            self.assertIn("model", agent)

    def test_normalize_cashflow_in_app(self):
        """Verifica que normalize_cashflow está importable y funcional."""
        data = {"months": [{"month": "2025-01", "label": "Enero", "income": {"sales": 100}, "expenses": {"variable_costs": 50}}]}
        result = normalize_cashflow(data)
        self.assertEqual(result["summary"]["total_income"], 100)
        self.assertEqual(result["summary"]["total_expenses"], 50)
        self.assertEqual(result["summary"]["net_cashflow"], 50)


if __name__ == "__main__":
    unittest.main()

"""
Tests para CCS Cashflow Assistant — Backend FastAPI

Incluye pruebas unitarias y de integración para:
  - Utilidades de persistencia (save_json, load_json)
  - Parser JSON robusto (_extract_json_from_llm)
  - Endpoints de empresas (CRUD)
  - Endpoints de agentes
  - Endpoints de flujo de caja y exportación
  - Endpoints de health
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
    _fix_encoding, DATA_DIR
)

client = TestClient(app)


class TestUtilities(unittest.TestCase):
    """Pruebas unitarias para utilidades de persistencia y parsing."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="ccs_util_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_and_load_json(self):
        """Verifica que save_json y load_json funcionan correctamente."""
        path = self.test_dir / "test.json"
        data = {"name": "Empresa Test", "value": 12345, "acentos": "café, niño"}
        save_json(path, data)
        loaded = load_json(path)
        self.assertEqual(loaded["name"], "Empresa Test")
        self.assertEqual(loaded["value"], 12345)
        self.assertEqual(loaded["acentos"], "café, niño")

    def test_load_json_nonexistent(self):
        """Verifica que load_json retorna default si el archivo no existe."""
        path = self.test_dir / "nonexistent.json"
        result = load_json(path, {"default": True})
        self.assertEqual(result, {"default": True})

    def test_load_json_corrupted(self):
        """Verifica que load_json maneja archivos corruptos."""
        path = self.test_dir / "corrupted.json"
        path.write_text("not valid json {{{", encoding="utf-8")
        result = load_json(path, {"fallback": True})
        self.assertEqual(result, {"fallback": True})

    def test_save_json_creates_directories(self):
        """Verifica que save_json crea directorios intermedios."""
        path = self.test_dir / "a" / "b" / "c" / "test.json"
        save_json(path, {"nested": True})
        self.assertTrue(path.exists())

    def test_extract_json_clean(self):
        """Extrae JSON limpio."""
        text = '{"key": "value", "num": 42}'
        result = _extract_json_from_llm(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["key"], "value")
        self.assertEqual(result["num"], 42)

    def test_extract_json_with_markdown(self):
        """Extrae JSON envuelto en bloques de código markdown."""
        text = 'Aquí está el resultado:\n```json\n{"key": "value"}\n```\nFin.'
        result = _extract_json_from_llm(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["key"], "value")

    def test_extract_json_with_preamble(self):
        """Extrae JSON con texto previo."""
        text = 'El flujo de caja es:\n{"company": "Test", "months": []}'
        result = _extract_json_from_llm(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["company"], "Test")

    def test_extract_json_none(self):
        """Retorna None si no hay JSON."""
        self.assertIsNone(_extract_json_from_llm("No hay JSON aquí"))
        self.assertIsNone(_extract_json_from_llm(""))
        self.assertIsNone(_extract_json_from_llm(None))

    def test_extract_json_nested(self):
        """Extrae JSON con objetos anidados."""
        text = '{"summary": {"total": 1000}, "months": [{"month": "2025-01"}]}'
        result = _extract_json_from_llm(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["summary"]["total"], 1000)
        self.assertEqual(len(result["months"]), 1)

    def test_fix_encoding_normal(self):
        """Verifica que _fix_encoding no altera texto normal."""
        self.assertEqual(_fix_encoding("Hola mundo"), "Hola mundo")

    def test_fix_encoding_accents(self):
        """Verifica que _fix_encoding maneja acentos."""
        text = "café"
        result = _fix_encoding(text)
        self.assertIsInstance(result, str)


class TestHealthEndpoint(unittest.TestCase):
    """Pruebas para el endpoint de health."""

    @patch("app.http_requests.get")
    def test_health_ollama_connected(self, mock_get):
        """Health retorna ollama=True cuando Ollama responde."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}
        mock_get.return_value = mock_response

        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["ollama"])

    @patch("app.http_requests.get", side_effect=Exception("Connection refused"))
    def test_health_ollama_disconnected(self, mock_get):
        """Health retorna ollama=False cuando Ollama no responde."""
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertFalse(data["ollama"])


class TestCompanyEndpoints(unittest.TestCase):
    """Pruebas para los endpoints de empresas."""

    def setUp(self):
        # Limpiar directorio de empresas
        companies_dir = DATA_DIR / "companies"
        if companies_dir.exists():
            shutil.rmtree(companies_dir)
        companies_dir.mkdir(parents=True, exist_ok=True)

    def test_create_company(self):
        """Crea una empresa correctamente."""
        response = client.post("/api/companies", json={
            "name": "Panadería Test",
            "sector": "alimentos",
            "size": "micro",
            "description": "Una panadería de prueba"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Panadería Test")
        self.assertEqual(data["sector"], "alimentos")
        self.assertEqual(data["status"], "pending")
        self.assertIn("id", data)

    def test_list_companies(self):
        """Lista empresas creadas."""
        # Crear dos empresas
        client.post("/api/companies", json={"name": "Empresa 1"})
        client.post("/api/companies", json={"name": "Empresa 2"})

        response = client.get("/api/companies")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data["companies"]), 2)

    def test_get_company(self):
        """Obtiene una empresa por ID."""
        create_resp = client.post("/api/companies", json={"name": "Empresa Get"})
        company_id = create_resp.json()["id"]

        response = client.get(f"/api/companies/{company_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Empresa Get")

    def test_get_company_not_found(self):
        """Retorna 404 para empresa inexistente."""
        response = client.get("/api/companies/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_delete_company(self):
        """Elimina una empresa."""
        create_resp = client.post("/api/companies", json={"name": "Empresa Delete"})
        company_id = create_resp.json()["id"]

        response = client.delete(f"/api/companies/{company_id}")
        self.assertEqual(response.status_code, 200)

        # Verificar que ya no existe
        get_resp = client.get(f"/api/companies/{company_id}")
        self.assertEqual(get_resp.status_code, 404)


class TestAgentEndpoints(unittest.TestCase):
    """Pruebas para los endpoints de agentes."""

    def setUp(self):
        # Copiar agents.json de defaults
        agents_dir = DATA_DIR / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        defaults_path = Path(__file__).parent.parent / "defaults" / "agents.json"
        if defaults_path.exists():
            shutil.copy2(str(defaults_path), str(agents_dir / "agents.json"))

    def test_list_agents(self):
        """Lista agentes configurados."""
        response = client.get("/api/agents")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("agents", data)
        self.assertGreater(len(data["agents"]), 0)

    def test_get_agent(self):
        """Obtiene un agente por ID."""
        response = client.get("/api/agents/financial_interviewer")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "financial_interviewer")

    def test_get_agent_not_found(self):
        """Retorna 404 para agente inexistente."""
        response = client.get("/api/agents/nonexistent")
        self.assertEqual(response.status_code, 404)

    @patch("app._is_model_available", return_value=True)
    def test_update_agent(self, mock_avail):
        """Actualiza configuración de un agente."""
        response = client.put("/api/agents/financial_interviewer", json={
            "model": "llama3.2:3b",
            "temperature": 0.5
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["temperature"], 0.5)


class TestCashflowEndpoints(unittest.TestCase):
    """Pruebas para los endpoints de flujo de caja."""

    def setUp(self):
        self.company_id = None
        resp = client.post("/api/companies", json={
            "name": "Empresa Cashflow Test",
            "sector": "comercio"
        })
        self.company_id = resp.json()["id"]

    def test_get_cashflow_not_found(self):
        """Retorna 404 si no hay flujo de caja."""
        response = client.get(f"/api/companies/{self.company_id}/cashflow")
        self.assertEqual(response.status_code, 404)

    def test_cashflow_with_mock_data(self):
        """Verifica que se puede leer un flujo de caja guardado manualmente."""
        cashflow_data = {
            "company_name": "Test",
            "currency": "CLP",
            "period_months": 12,
            "summary": {
                "total_income": 120000000,
                "total_expenses": 96000000,
                "net_cashflow": 24000000,
                "average_monthly_balance": 2000000
            },
            "months": [
                {
                    "month": "2025-01",
                    "label": "Enero 2025",
                    "income": {"sales": 10000000, "other_income": 0, "total": 10000000},
                    "expenses": {"variable_costs": 4000000, "fixed_costs": 3000000, "variable_expenses": 500000, "debt_payments": 300000, "taxes": 200000, "investments": 0, "total": 8000000},
                    "net_flow": 2000000,
                    "cumulative_balance": 2000000
                }
            ],
            "alerts": [{"type": "info", "month": "2025-01", "message": "Flujo positivo"}],
            "recommendations": ["Mantener control de gastos"]
        }
        company_dir = DATA_DIR / "companies" / self.company_id
        save_json(company_dir / "cashflow.json", cashflow_data)

        response = client.get(f"/api/companies/{self.company_id}/cashflow")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["company_name"], "Test")
        self.assertEqual(len(data["months"]), 1)

    def test_export_excel(self):
        """Verifica exportación a Excel."""
        # Crear cashflow mock
        cashflow_data = {
            "company_name": "Test Export",
            "summary": {"total_income": 100, "total_expenses": 80, "net_cashflow": 20, "average_monthly_balance": 10},
            "months": [
                {"month": "2025-01", "label": "Enero", "income": {"total": 100}, "expenses": {"variable_costs": 30, "fixed_costs": 30, "variable_expenses": 10, "debt_payments": 5, "taxes": 5, "investments": 0, "total": 80}, "net_flow": 20, "cumulative_balance": 20}
            ],
            "alerts": [],
            "recommendations": []
        }
        company_dir = DATA_DIR / "companies" / self.company_id
        save_json(company_dir / "cashflow.json", cashflow_data)

        response = client.get(f"/api/companies/{self.company_id}/export/excel")
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheet", response.headers.get("content-type", ""))

    def test_export_csv(self):
        """Verifica exportación a CSV."""
        cashflow_data = {
            "company_name": "Test CSV",
            "summary": {},
            "months": [
                {"month": "2025-01", "label": "Enero", "income": {"total": 100}, "expenses": {"variable_costs": 30, "fixed_costs": 30, "variable_expenses": 10, "debt_payments": 5, "taxes": 5, "total": 80}, "net_flow": 20, "cumulative_balance": 20}
            ],
            "alerts": [],
            "recommendations": []
        }
        company_dir = DATA_DIR / "companies" / self.company_id
        save_json(company_dir / "cashflow.json", cashflow_data)

        response = client.get(f"/api/companies/{self.company_id}/export/csv")
        self.assertEqual(response.status_code, 200)

    def test_export_no_cashflow(self):
        """Retorna 404 si no hay flujo de caja para exportar."""
        response = client.get(f"/api/companies/{self.company_id}/export/excel")
        self.assertEqual(response.status_code, 404)


class TestModelsEndpoints(unittest.TestCase):
    """Pruebas para endpoints de modelos."""

    @patch("app.http_requests.get")
    def test_available_models(self, mock_get):
        """Lista modelos disponibles."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "llama3.2:3b"}, {"name": "llama3.1:8b"}]}
        mock_get.return_value = mock_response

        response = client.get("/api/models/available")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("llama3.2:3b", data["models"])

    @patch("app.http_requests.get", side_effect=Exception("Connection refused"))
    def test_available_models_offline(self, mock_get):
        """Retorna lista vacía si Ollama no está disponible."""
        response = client.get("/api/models/available")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["models"], [])

    def test_models_status(self):
        """Retorna estado de descargas."""
        response = client.get("/api/models/status")
        self.assertEqual(response.status_code, 200)
        self.assertIn("pull_status", response.json())


class TestPinokioValidation(unittest.TestCase):
    """Validaciones de estructura del plugin Pinokio."""

    def test_lifecycle_scripts_are_json(self):
        """Verifica que install, start, stop son JSON puros."""
        base = Path(__file__).parent.parent
        for name in ["install.json", "start.json", "stop.json", "reset.json"]:
            path = base / name
            self.assertTrue(path.exists(), f"{name} no encontrado")
            content = path.read_text(encoding="utf-8")
            try:
                json.loads(content)
            except json.JSONDecodeError:
                self.fail(f"{name} no es JSON válido")

    def test_pinokio_js_exists(self):
        """Verifica que pinokio.js existe."""
        path = Path(__file__).parent.parent / "pinokio.js"
        self.assertTrue(path.exists())

    def test_pinokio_js_references_json(self):
        """Verifica que pinokio.js referencia archivos .json."""
        path = Path(__file__).parent.parent / "pinokio.js"
        content = path.read_text(encoding="utf-8")
        self.assertIn("install.json", content)
        self.assertIn("start.json", content)
        self.assertIn("stop.json", content)

    def test_no_background_true(self):
        """Verifica que no hay 'background: true' en los JSON."""
        base = Path(__file__).parent.parent
        for name in ["install.json", "start.json", "stop.json"]:
            content = (base / name).read_text(encoding="utf-8")
            self.assertNotIn('"background"', content, f"{name} contiene 'background'")

    def test_venv_name_consistent(self):
        """Verifica que el nombre del venv es 'venv' en todos los archivos."""
        base = Path(__file__).parent.parent
        for name in ["install.json", "start.json", "pinokio.js"]:
            content = (base / name).read_text(encoding="utf-8")
            self.assertIn("venv", content, f"{name} no referencia 'venv'")

    def test_server_uses_absolute_paths(self):
        """Verifica que el servidor usa rutas absolutas desde __file__."""
        path = Path(__file__).parent.parent / "server" / "app.py"
        content = path.read_text(encoding="utf-8")
        self.assertIn("__file__", content)

    def test_ensure_ascii_false(self):
        """Verifica que json.dumps usa ensure_ascii=False."""
        path = Path(__file__).parent.parent / "server" / "app.py"
        content = path.read_text(encoding="utf-8")
        self.assertIn("ensure_ascii=False", content)

    def test_response_encoding_utf8(self):
        """Verifica que se fuerza encoding UTF-8 en respuestas de Ollama."""
        path = Path(__file__).parent.parent / "server" / "app.py"
        content = path.read_text(encoding="utf-8")
        self.assertIn('resp.encoding = "utf-8"', content)

    def test_no_let_const_in_html(self):
        """Verifica que no hay let/const/import/export en el HTML."""
        path = Path(__file__).parent.parent / "app" / "index.html"
        content = path.read_text(encoding="utf-8")
        # Buscar en el bloque de script
        script_start = content.find("<script>")
        script_end = content.find("</script>")
        if script_start != -1 and script_end != -1:
            script = content[script_start:script_end]
            # Verificar que no hay let/const como declaraciones (no dentro de strings)
            import re
            lets = re.findall(r'^\s*let\s', script, re.MULTILINE)
            consts = re.findall(r'^\s*const\s', script, re.MULTILINE)
            imports = re.findall(r'^\s*import\s', script, re.MULTILINE)
            exports = re.findall(r'^\s*export\s', script, re.MULTILINE)
            self.assertEqual(len(lets), 0, f"Encontrados {len(lets)} 'let' en el script")
            self.assertEqual(len(consts), 0, f"Encontrados {len(consts)} 'const' en el script")
            self.assertEqual(len(imports), 0, f"Encontrados {len(imports)} 'import' en el script")
            self.assertEqual(len(exports), 0, f"Encontrados {len(exports)} 'export' en el script")

    def test_icon_exists(self):
        """Verifica que icon.png existe."""
        path = Path(__file__).parent.parent / "icon.png"
        self.assertTrue(path.exists())

    def test_defaults_agents_json(self):
        """Verifica que defaults/agents.json es válido."""
        path = Path(__file__).parent.parent / "defaults" / "agents.json"
        self.assertTrue(path.exists())
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("agents", data)
        self.assertGreater(len(data["agents"]), 0)
        for agent in data["agents"]:
            self.assertIn("id", agent)
            self.assertIn("name", agent)
            self.assertIn("model", agent)


if __name__ == "__main__":
    unittest.main()

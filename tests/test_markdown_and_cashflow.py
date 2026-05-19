"""Tests de integración para renderizado de markdown y generación de cashflow."""
import sys
import os
import json
import re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from app import normalize_cashflow, _rescue_cashflow_structure


class TestMarkdownInFrontend:
    """Verifica que el HTML tiene la función renderMarkdown correctamente implementada."""

    def setup_method(self):
        html_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'index.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            self.html = f.read()

    def test_render_markdown_function_exists(self):
        """La función renderMarkdown existe en el HTML."""
        assert 'function renderMarkdown(' in self.html

    def test_render_markdown_escapes_html_first(self):
        """renderMarkdown llama a escapeHtml primero (seguridad)."""
        # Buscar que la función usa escapeHtml
        fn_match = re.search(r'function renderMarkdown\(text\)\s*\{(.*?)\n    \}', self.html, re.DOTALL)
        assert fn_match is not None
        fn_body = fn_match.group(1)
        assert 'escapeHtml(text)' in fn_body

    def test_render_markdown_handles_bold(self):
        """renderMarkdown convierte **texto** en <strong>."""
        fn_match = re.search(r'function renderMarkdown\(text\)\s*\{(.*?)\n    \}', self.html, re.DOTALL)
        fn_body = fn_match.group(1)
        assert '<strong>' in fn_body
        assert '\\*\\*' in fn_body

    def test_render_markdown_handles_line_breaks(self):
        """renderMarkdown convierte \\n en <br>."""
        fn_match = re.search(r'function renderMarkdown\(text\)\s*\{(.*?)\n    \}', self.html, re.DOTALL)
        fn_body = fn_match.group(1)
        assert '<br>' in fn_body

    def test_chat_messages_use_render_markdown(self):
        """Los mensajes del asistente usan renderMarkdown en vez de escapeHtml."""
        # Buscar que los mensajes del asistente usan renderMarkdown
        assert "renderMarkdown(safeDisplayValue(data.response))" in self.html
        assert "renderMarkdown(data.response)" in self.html

    def test_user_messages_still_use_escape_html(self):
        """Los mensajes del usuario siguen usando escapeHtml (no markdown)."""
        assert "escapeHtml(message)" in self.html

    def test_chat_css_styles_for_markdown(self):
        """Hay estilos CSS para markdown dentro de mensajes del chat."""
        assert '.chat-message.assistant strong' in self.html
        assert '.chat-message.assistant em' in self.html
        assert '.chat-message.assistant ul' in self.html

    def test_no_lookbehind_regex(self):
        """No hay lookbehind regex que no sea compatible con navegadores antiguos."""
        # Buscar (?<= o (?<! en el script (dentro de <script>)
        script_match = re.search(r'<script>(.*?)</script>', self.html, re.DOTALL)
        if script_match:
            script = script_match.group(1)
            lookbehinds = re.findall(r'\(\?<[!=]', script)
            assert len(lookbehinds) == 0, f"Lookbehind encontrado en el script: {lookbehinds}"


class TestCashflowGenerationRobustness:
    """Tests que simulan respuestas reales del LLM para verificar la robustez."""

    def test_typical_llm_response(self):
        """Respuesta típica del LLM con formato correcto."""
        data = {
            "company_name": "Turismo Cognitivo",
            "currency": "CLP",
            "period_months": 12,
            "start_month": "2025-01",
            "months": [
                {
                    "month": "2025-01",
                    "label": "Enero 2025",
                    "income": {"sales": 13000000, "other_income": 0, "total": 13000000},
                    "expenses": {
                        "variable_costs": 6500000,
                        "fixed_costs": 1800000,
                        "variable_expenses": 0,
                        "debt_payments": 1800000,
                        "taxes": 0,
                        "investments": 0,
                        "total": 10100000
                    },
                    "net_flow": 2900000,
                    "cumulative_balance": 2900000
                }
            ] * 12,
            "alerts": [],
            "recommendations": ["Reducir costos variables"]
        }
        result = normalize_cashflow(data)
        assert len(result["months"]) == 12
        assert result["summary"]["total_income"] == 156000000
        assert result["summary"]["total_expenses"] == 121200000

    def test_llm_response_with_text_before_json(self):
        """Simula que el LLM devuelve texto antes del JSON."""
        # Esto se maneja en _extract_json_from_llm, aquí verificamos normalize
        data = {
            "months": [
                {
                    "month": "2025-01",
                    "income": {"sales": 13000000, "other_income": 0},
                    "expenses": {"variable_costs": 6500000, "fixed_costs": 1800000,
                                 "variable_expenses": 0, "debt_payments": 1800000,
                                 "taxes": 0, "investments": 0}
                }
            ]
        }
        result = normalize_cashflow(data)
        assert result["months"][0]["income"]["total"] == 13000000
        assert result["months"][0]["expenses"]["total"] == 10100000
        assert result["months"][0]["net_flow"] == 2900000

    def test_llm_response_missing_totals(self):
        """LLM no calcula totales, normalize los recalcula."""
        data = {
            "months": [
                {
                    "month": "2025-01",
                    "label": "Enero",
                    "income": {"sales": 5000000, "other_income": 1000000},
                    "expenses": {"variable_costs": 2000000, "fixed_costs": 1000000,
                                 "variable_expenses": 500000, "debt_payments": 300000,
                                 "taxes": 200000, "investments": 0}
                }
            ]
        }
        result = normalize_cashflow(data)
        assert result["months"][0]["income"]["total"] == 6000000
        assert result["months"][0]["expenses"]["total"] == 4000000
        assert result["months"][0]["net_flow"] == 2000000
        assert result["months"][0]["cumulative_balance"] == 2000000

    def test_llm_response_with_wrong_totals(self):
        """LLM calcula mal los totales, normalize los corrige."""
        data = {
            "months": [
                {
                    "month": "2025-01",
                    "income": {"sales": 10000000, "other_income": 500000, "total": 999},
                    "expenses": {"variable_costs": 5000000, "fixed_costs": 2000000,
                                 "variable_expenses": 0, "debt_payments": 0,
                                 "taxes": 0, "investments": 0, "total": 999},
                    "net_flow": 999,
                    "cumulative_balance": 999
                }
            ]
        }
        result = normalize_cashflow(data)
        # Los totales se recalculan correctamente
        assert result["months"][0]["income"]["total"] == 10500000
        assert result["months"][0]["expenses"]["total"] == 7000000
        assert result["months"][0]["net_flow"] == 3500000

    def test_real_world_scenario_from_screenshot(self):
        """Simula el escenario real de la captura de pantalla del usuario."""
        # El usuario mencionó: 13 millones de ingresos, 6.5M costos variables,
        # 1.8M gastos fijos, 1.8M deudas, 40M plataformas al año, etc.
        data = {
            "company_name": "Turismo Cognitivo con Meta Ray-Ban",
            "currency": "CLP",
            "meses": [
                {
                    "mes": "2025-01",
                    "etiqueta": "Enero 2025",
                    "ingresos": {"ventas": 13000000, "otros_ingresos": 0},
                    "gastos": {
                        "costos_variables": 6500000,
                        "costos_fijos": 1800000,
                        "gastos_variables": 0,
                        "deudas": 1800000,
                        "impuestos": 0,
                        "inversiones": 3333333
                    }
                }
            ] * 12
        }
        result = normalize_cashflow(data)
        assert len(result["months"]) == 12
        assert result["months"][0]["income"]["sales"] == 13000000
        assert result["months"][0]["expenses"]["debt_payments"] == 1800000
        assert result["months"][0]["expenses"]["investments"] == 3333333
        total_exp = 6500000 + 1800000 + 0 + 1800000 + 0 + 3333333
        assert result["months"][0]["expenses"]["total"] == total_exp
        assert result["months"][0]["net_flow"] == 13000000 - total_exp
        assert result["summary"]["num_months"] == 12

    def test_cashflow_is_reusable_across_app(self):
        """El cashflow normalizado tiene todos los campos necesarios para dashboard, simulador y exportación."""
        data = {
            "months": [
                {
                    "month": "2025-01",
                    "label": "Enero 2025",
                    "income": {"sales": 10000000, "other_income": 500000},
                    "expenses": {"variable_costs": 4000000, "fixed_costs": 2000000,
                                 "variable_expenses": 500000, "debt_payments": 300000,
                                 "taxes": 200000, "investments": 100000}
                }
            ]
        }
        result = normalize_cashflow(data)
        month = result["months"][0]

        # Campos necesarios para el dashboard
        assert "income" in month
        assert "total" in month["income"]
        assert "expenses" in month
        assert "total" in month["expenses"]
        assert "net_flow" in month
        assert "cumulative_balance" in month
        assert "month" in month
        assert "label" in month

        # Campos necesarios para el simulador
        assert "sales" in month["income"]
        assert "other_income" in month["income"]
        assert "variable_costs" in month["expenses"]
        assert "fixed_costs" in month["expenses"]
        assert "variable_expenses" in month["expenses"]
        assert "debt_payments" in month["expenses"]
        assert "taxes" in month["expenses"]
        assert "investments" in month["expenses"]

        # Summary necesario para exportación
        assert "summary" in result
        assert "total_income" in result["summary"]
        assert "total_expenses" in result["summary"]
        assert "net_cashflow" in result["summary"]
        assert "average_monthly_balance" in result["summary"]
        assert "num_months" in result["summary"]

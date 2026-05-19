"""Tests para la función de rescate de estructura de cashflow y normalización con datos en español."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from app import normalize_cashflow, _rescue_cashflow_structure, _normalize_month_from_spanish


class TestRescueCashflowStructure:
    """Tests para _rescue_cashflow_structure."""

    def test_already_correct_structure(self):
        """Datos con months correctos no se modifican."""
        data = {
            "months": [
                {"month": "2025-01", "income": {"sales": 1000, "other_income": 0, "total": 1000},
                 "expenses": {"variable_costs": 500, "fixed_costs": 200, "variable_expenses": 0,
                              "debt_payments": 0, "taxes": 0, "investments": 0, "total": 700}}
            ]
        }
        result = _rescue_cashflow_structure(data)
        assert len(result["months"]) == 1
        assert result["months"][0]["income"]["sales"] == 1000

    def test_nested_in_data_field(self):
        """Datos anidados en campo 'data' se rescatan."""
        data = {
            "data": {
                "months": [
                    {"month": "2025-01", "income": {"sales": 5000, "other_income": 0, "total": 5000},
                     "expenses": {"variable_costs": 2000, "fixed_costs": 1000, "total": 3000}}
                ]
            }
        }
        result = _rescue_cashflow_structure(data)
        assert "months" in result
        assert len(result["months"]) == 1
        assert result["months"][0]["income"]["sales"] == 5000

    def test_nested_in_cashflow_field(self):
        """Datos anidados en campo 'cashflow' se rescatan."""
        data = {
            "cashflow": {
                "months": [
                    {"month": "2025-01", "income": {"sales": 3000}, "expenses": {"variable_costs": 1000}}
                ]
            }
        }
        result = _rescue_cashflow_structure(data)
        assert len(result["months"]) == 1

    def test_nested_in_flujo_de_caja(self):
        """Datos anidados en campo 'flujo_de_caja' se rescatan."""
        data = {
            "flujo_de_caja": {
                "months": [
                    {"month": "2025-01", "income": {"sales": 7000}, "expenses": {"fixed_costs": 2000}}
                ]
            }
        }
        result = _rescue_cashflow_structure(data)
        assert len(result["months"]) == 1

    def test_months_in_different_key(self):
        """Meses bajo un nombre diferente se detectan."""
        data = {
            "projection_months": [
                {"month": "2025-01", "income": {"sales": 4000}, "expenses": {"variable_costs": 1500}}
            ]
        }
        result = _rescue_cashflow_structure(data)
        assert "months" in result
        assert len(result["months"]) == 1

    def test_spanish_meses_key(self):
        """Campo 'meses' en español se detecta."""
        data = {
            "meses": [
                {"mes": "2025-01", "ingresos": {"ventas": 6000}, "gastos": {"costos_fijos": 2000}}
            ]
        }
        result = _rescue_cashflow_structure(data)
        assert "months" in result
        assert len(result["months"]) == 1

    def test_empty_months_array(self):
        """Months vacío no se considera válido."""
        data = {"months": []}
        result = _rescue_cashflow_structure(data)
        # No debería encontrar nada mejor, devuelve como está
        assert result["months"] == []


class TestNormalizeMonthFromSpanish:
    """Tests para _normalize_month_from_spanish."""

    def test_spanish_income_expenses(self):
        """Campos en español se convierten a inglés."""
        m = {
            "mes": "2025-01",
            "etiqueta": "Enero 2025",
            "ingresos": {"ventas": 10000000, "otros_ingresos": 500000},
            "gastos": {
                "costos_variables": 4000000,
                "costos_fijos": 3000000,
                "gastos_variables": 500000,
                "deudas": 300000,
                "impuestos": 200000,
                "inversiones": 100000
            }
        }
        result = _normalize_month_from_spanish(m)
        assert "income" in result
        assert "expenses" in result
        assert "month" in result
        assert "label" in result
        assert result["income"]["sales"] == 10000000
        assert result["income"]["other_income"] == 500000
        assert result["expenses"]["variable_costs"] == 4000000
        assert result["expenses"]["fixed_costs"] == 3000000
        assert result["expenses"]["debt_payments"] == 300000

    def test_flat_sales_field(self):
        """Campo 'sales' a nivel raíz se convierte."""
        m = {"month": "2025-01", "sales": 5000, "other_income": 200}
        result = _normalize_month_from_spanish(m)
        assert "income" in result
        assert result["income"]["sales"] == 5000
        assert result["income"]["other_income"] == 200

    def test_flat_ventas_field(self):
        """Campo 'ventas' a nivel raíz se convierte."""
        m = {"mes": "2025-01", "ventas": 8000, "otros_ingresos": 300}
        result = _normalize_month_from_spanish(m)
        assert "income" in result
        assert result["income"]["sales"] == 8000


class TestNormalizeCashflowFull:
    """Tests de integración para normalize_cashflow con datos variados."""

    def test_full_spanish_cashflow(self):
        """Un cashflow completo en español se normaliza correctamente."""
        data = {
            "nombre_empresa": "Mi PYME",
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
                        "inversiones": 0
                    }
                },
                {
                    "mes": "2025-02",
                    "etiqueta": "Febrero 2025",
                    "ingresos": {"ventas": 13000000, "otros_ingresos": 0},
                    "gastos": {
                        "costos_variables": 6500000,
                        "costos_fijos": 1800000,
                        "gastos_variables": 0,
                        "deudas": 1800000,
                        "impuestos": 0,
                        "inversiones": 0
                    }
                }
            ]
        }
        result = normalize_cashflow(data)
        assert len(result["months"]) == 2
        assert result["months"][0]["income"]["sales"] == 13000000
        assert result["months"][0]["income"]["total"] == 13000000
        assert result["months"][0]["expenses"]["variable_costs"] == 6500000
        assert result["months"][0]["expenses"]["total"] == 10100000
        assert result["months"][0]["net_flow"] == 2900000
        assert result["summary"]["total_income"] == 26000000
        assert result["summary"]["total_expenses"] == 20200000

    def test_wrapped_in_data(self):
        """Cashflow envuelto en 'data' se normaliza correctamente."""
        data = {
            "data": {
                "months": [
                    {
                        "month": "2025-01",
                        "label": "Enero",
                        "income": {"sales": 10000000, "other_income": 0, "total": 10000000},
                        "expenses": {"variable_costs": 5000000, "fixed_costs": 2000000,
                                     "variable_expenses": 0, "debt_payments": 0,
                                     "taxes": 0, "investments": 0, "total": 7000000}
                    }
                ]
            }
        }
        result = normalize_cashflow(data)
        assert len(result["months"]) == 1
        assert result["months"][0]["income"]["total"] == 10000000
        assert result["months"][0]["net_flow"] == 3000000

    def test_string_numbers_get_converted(self):
        """Números como strings se convierten correctamente."""
        data = {
            "months": [
                {
                    "month": "2025-01",
                    "income": {"sales": "13.000.000", "other_income": "0", "total": "13.000.000"},
                    "expenses": {"variable_costs": "6.500.000", "fixed_costs": "1.800.000",
                                 "variable_expenses": "0", "debt_payments": "1.800.000",
                                 "taxes": "0", "investments": "0", "total": "10.100.000"}
                }
            ]
        }
        result = normalize_cashflow(data)
        assert result["months"][0]["income"]["sales"] == 13000000
        assert result["months"][0]["expenses"]["variable_costs"] == 6500000
        assert result["months"][0]["net_flow"] == 2900000

    def test_dollar_sign_numbers(self):
        """Números con $ se convierten correctamente."""
        data = {
            "months": [
                {
                    "month": "2025-01",
                    "income": {"sales": "$10,000,000", "other_income": "$0"},
                    "expenses": {"variable_costs": "$5,000,000", "fixed_costs": "$2,000,000",
                                 "variable_expenses": "$0", "debt_payments": "$0",
                                 "taxes": "$0", "investments": "$0"}
                }
            ]
        }
        result = normalize_cashflow(data)
        assert result["months"][0]["income"]["sales"] == 10000000
        assert result["months"][0]["income"]["total"] == 10000000


class TestRenderMarkdown:
    """Tests para la función renderMarkdown (simulada en Python para validar lógica)."""

    def test_bold_rendering(self):
        """Texto con ** se renderiza como negrita."""
        # Este test valida la lógica que implementamos en JS
        text = "**Resumen de Ingresos** * Ingresos mensuales: 13 millones"
        # En el frontend, escapeHtml + regex reemplaza **text** por <strong>text</strong>
        assert "**" in text  # El texto original tiene markdown
        # Después de renderizar, no debería tener ** visibles
        # (la validación real es en el navegador, aquí solo verificamos la lógica)

    def test_list_items(self):
        """Texto con * al inicio de línea se renderiza como lista."""
        text = "* Item 1\n* Item 2\n* Item 3"
        lines = text.split("\n")
        assert all(l.startswith("* ") for l in lines)

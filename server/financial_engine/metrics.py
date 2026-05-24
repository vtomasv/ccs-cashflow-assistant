"""
metrics.py — Cálculo de métricas financieras avanzadas.
Proporciona indicadores clave para la toma de decisiones de PYMEs:
- Caja mínima
- Mes de caja negativa
- Break-even operativo
- Runway
- Margen bruto
- Margen EBITDA
- Necesidad máxima de financiamiento
- Sensibilidad por variable
"""

from typing import List, Dict, Optional, Tuple
from .core import CashflowModel, MonthData, IncomeData, ExpenseData, BusinessProfile
import copy


class FinancialMetrics:
    """Calculador de métricas financieras a partir de un CashflowModel."""

    def __init__(self, model: CashflowModel):
        self.model = model
        self.months = model.months

    def calculate_all(self) -> dict:
        """Calcula todas las métricas disponibles y retorna un diccionario completo."""
        if not self.months:
            return {"error": "No hay datos de meses para calcular métricas"}

        return {
            "caja_minima": self.caja_minima(),
            "mes_caja_negativa": self.mes_caja_negativa(),
            "break_even_operativo": self.break_even_operativo(),
            "runway_meses": self.runway(),
            "margen_bruto_pct": self.margen_bruto(),
            "margen_ebitda_pct": self.margen_ebitda(),
            "necesidad_financiamiento": self.necesidad_financiamiento(),
            "sensibilidad": self.sensibilidad_por_variable(),
            "resumen_ejecutivo": self.resumen_ejecutivo(),
            "recomendaciones_financiamiento": self.recomendaciones_financiamiento(),
            "optimizacion_caja": self.optimizacion_caja(),
        }

    def caja_minima(self) -> dict:
        """
        Calcula el saldo mínimo proyectado en todo el período.
        Retorna el valor y el mes donde ocurre.
        """
        if not self.months:
            return {"valor": 0, "mes": "", "indice": 0}

        min_balance = float("inf")
        min_month = ""
        min_index = 0

        for i, m in enumerate(self.months):
            if m.cumulative_balance < min_balance:
                min_balance = m.cumulative_balance
                min_month = m.label
                min_index = i

        return {
            "valor": round(min_balance, 2),
            "mes": min_month,
            "indice": min_index,
            "es_negativa": min_balance < 0,
        }

    def mes_caja_negativa(self) -> dict:
        """
        Identifica el primer mes donde el saldo acumulado cae por debajo de cero.
        Retorna None si nunca ocurre.
        """
        for i, m in enumerate(self.months):
            if m.cumulative_balance < 0:
                return {
                    "mes": m.label,
                    "indice": i,
                    "deficit": round(abs(m.cumulative_balance), 2),
                    "existe": True,
                }
        return {"mes": None, "indice": None, "deficit": 0, "existe": False}

    def break_even_operativo(self) -> dict:
        """
        Calcula el nivel de ventas mensuales necesario para cubrir todos los costos.
        Break-even = Costos Fijos / (1 - Costos Variables / Ventas)
        """
        total_sales = sum(m.income.sales for m in self.months)
        total_variable = sum(m.expenses.variable_costs for m in self.months)
        total_fixed = sum(m.expenses.fixed_costs + m.expenses.variable_expenses +
                          m.expenses.debt_payments + m.expenses.taxes for m in self.months)

        if total_sales == 0:
            return {"ventas_mensuales_necesarias": 0, "margen_contribucion_pct": 0, "alcanzado": False}

        # Margen de contribución = (Ventas - Costos Variables) / Ventas
        margen_contribucion = (total_sales - total_variable) / total_sales if total_sales > 0 else 0

        if margen_contribucion <= 0:
            return {
                "ventas_mensuales_necesarias": float("inf"),
                "margen_contribucion_pct": round(margen_contribucion * 100, 1),
                "alcanzado": False,
                "mensaje": "El margen de contribución es negativo: cada venta genera pérdida."
            }

        # Break-even mensual promedio
        fixed_monthly_avg = total_fixed / len(self.months)
        break_even_sales = fixed_monthly_avg / margen_contribucion

        # ¿Se alcanza?
        avg_monthly_sales = total_sales / len(self.months)
        alcanzado = avg_monthly_sales >= break_even_sales

        return {
            "ventas_mensuales_necesarias": round(break_even_sales, 2),
            "ventas_mensuales_actuales": round(avg_monthly_sales, 2),
            "margen_contribucion_pct": round(margen_contribucion * 100, 1),
            "alcanzado": alcanzado,
            "holgura_pct": round((avg_monthly_sales - break_even_sales) / break_even_sales * 100, 1) if break_even_sales > 0 else 0,
        }

    def runway(self) -> dict:
        """
        Calcula cuántos meses puede sobrevivir la empresa con la caja actual
        si tiene pérdidas netas mensuales.
        Runway = Caja Inicial / |Gasto Neto Mensual Promedio| (solo si hay pérdidas)
        """
        initial_cash = self.model.initial_cash
        net_flows = [m.net_flow for m in self.months]
        avg_net_flow = sum(net_flows) / len(net_flows) if net_flows else 0

        if avg_net_flow >= 0:
            return {
                "meses": float("inf"),
                "es_rentable": True,
                "mensaje": "La empresa es rentable en promedio: no necesita runway.",
                "caja_inicial": round(initial_cash, 2),
            }

        # Runway = caja / burn rate mensual
        burn_rate = abs(avg_net_flow)
        runway_months = initial_cash / burn_rate if burn_rate > 0 else 0

        return {
            "meses": round(runway_months, 1),
            "es_rentable": False,
            "burn_rate_mensual": round(burn_rate, 2),
            "caja_inicial": round(initial_cash, 2),
            "mensaje": f"Con la caja actual, la empresa puede operar {runway_months:.1f} meses antes de quedarse sin fondos.",
        }

    def margen_bruto(self) -> dict:
        """
        Margen Bruto = (Ventas - Costos Variables) / Ventas
        Indica la eficiencia de producción/compra.
        """
        total_sales = sum(m.income.sales for m in self.months)
        total_variable = sum(m.expenses.variable_costs for m in self.months)

        if total_sales == 0:
            return {"pct": 0, "absoluto": 0, "mensaje": "Sin ventas registradas"}

        margen = (total_sales - total_variable) / total_sales
        absoluto = total_sales - total_variable

        # Margen por mes
        mensual = []
        for m in self.months:
            if m.income.sales > 0:
                mg = (m.income.sales - m.expenses.variable_costs) / m.income.sales
                mensual.append({"mes": m.label, "pct": round(mg * 100, 1)})
            else:
                mensual.append({"mes": m.label, "pct": 0})

        return {
            "pct": round(margen * 100, 1),
            "absoluto": round(absoluto, 2),
            "mensual": mensual,
        }

    def margen_ebitda(self) -> dict:
        """
        Margen EBITDA = EBITDA / Ventas
        EBITDA = Ventas - Costos Variables - Costos Fijos - Gastos Variables
        (excluye deuda, impuestos, inversiones/depreciación)
        """
        total_sales = sum(m.income.total for m in self.months)
        total_variable = sum(m.expenses.variable_costs for m in self.months)
        total_fixed = sum(m.expenses.fixed_costs for m in self.months)
        total_var_expenses = sum(m.expenses.variable_expenses for m in self.months)

        ebitda = total_sales - total_variable - total_fixed - total_var_expenses

        if total_sales == 0:
            return {"pct": 0, "absoluto": 0, "mensaje": "Sin ventas registradas"}

        margen = ebitda / total_sales

        return {
            "pct": round(margen * 100, 1),
            "absoluto": round(ebitda, 2),
            "ebitda_mensual_promedio": round(ebitda / len(self.months), 2) if self.months else 0,
        }

    def necesidad_financiamiento(self, colchon_pct: float = 20.0) -> dict:
        """
        Calcula la necesidad máxima de financiamiento:
        = |saldo negativo más profundo| + colchón de seguridad
        """
        min_balance = min(m.cumulative_balance for m in self.months) if self.months else 0

        if min_balance >= 0:
            return {
                "necesita_financiamiento": False,
                "monto": 0,
                "monto_con_colchon": 0,
                "colchon_pct": colchon_pct,
                "mensaje": "No se requiere financiamiento externo.",
            }

        deficit = abs(min_balance)
        colchon = deficit * (colchon_pct / 100)
        monto_total = deficit + colchon

        return {
            "necesita_financiamiento": True,
            "monto": round(deficit, 2),
            "monto_con_colchon": round(monto_total, 2),
            "colchon_pct": colchon_pct,
            "mensaje": f"Se necesitan ${monto_total:,.0f} de financiamiento (incluye {colchon_pct}% de colchón).",
        }

    def sensibilidad_por_variable(self, variacion_pct: float = 10.0) -> dict:
        """
        Análisis de sensibilidad: mide el impacto en la caja final
        al variar ±variacion_pct% cada variable principal.
        Retorna un ranking de variables por impacto.
        """
        if not self.months:
            return {"variables": [], "variacion_pct": variacion_pct}

        # Caja final base
        base_final = self.months[-1].cumulative_balance

        variables = [
            ("ventas", "sales"),
            ("costos_variables", "variable_costs"),
            ("costos_fijos", "fixed_costs"),
            ("gastos_variables", "variable_expenses"),
            ("deuda", "debt_payments"),
            ("impuestos", "taxes"),
        ]

        resultados = []

        for var_name, field_name in variables:
            # Simular +variacion_pct%
            impact_up = self._simulate_variable_change(field_name, variacion_pct / 100, base_final)
            # Simular -variacion_pct%
            impact_down = self._simulate_variable_change(field_name, -variacion_pct / 100, base_final)

            swing = abs(impact_up - impact_down)

            resultados.append({
                "variable": var_name,
                "impacto_positivo": round(impact_up, 2),
                "impacto_negativo": round(impact_down, 2),
                "swing_total": round(swing, 2),
                "es_ingreso": field_name == "sales",
            })

        # Ordenar por swing (mayor impacto primero)
        resultados.sort(key=lambda x: x["swing_total"], reverse=True)

        return {
            "variables": resultados,
            "variacion_pct": variacion_pct,
            "caja_final_base": round(base_final, 2),
        }

    def _simulate_variable_change(self, field_name: str, change_pct: float, base_final: float) -> float:
        """Simula un cambio porcentual en una variable y retorna el delta en caja final."""
        cumulative = self.model.initial_cash

        for m in self.months:
            income_total = m.income.total
            expenses_total = m.expenses.total

            if field_name == "sales":
                income_total = m.income.sales * (1 + change_pct) + m.income.other_income
            elif field_name in ("variable_costs", "fixed_costs", "variable_expenses", "debt_payments", "taxes"):
                original_val = getattr(m.expenses, field_name, 0)
                delta = original_val * change_pct
                expenses_total += delta

            net_flow = income_total - expenses_total
            cumulative += net_flow

        return cumulative - base_final

    def resumen_ejecutivo(self) -> dict:
        """Genera un resumen ejecutivo con semáforo de salud financiera."""
        if not self.months:
            return {"salud": "sin_datos", "score": 0, "indicadores": []}

        # Calcular score de salud (0-100)
        score = 50  # Base

        # Factor: rentabilidad
        total_net = sum(m.net_flow for m in self.months)
        if total_net > 0:
            score += 15
        elif total_net < 0:
            score -= 20

        # Factor: caja siempre positiva
        min_balance = min(m.cumulative_balance for m in self.months)
        if min_balance > 0:
            score += 20
        elif min_balance < 0:
            score -= 15

        # Factor: margen bruto saludable (>30%)
        total_sales = sum(m.income.sales for m in self.months)
        total_variable = sum(m.expenses.variable_costs for m in self.months)
        if total_sales > 0:
            margen = (total_sales - total_variable) / total_sales
            if margen > 0.4:
                score += 10
            elif margen > 0.25:
                score += 5
            elif margen < 0.15:
                score -= 10

        # Factor: tendencia de crecimiento
        if len(self.months) >= 3:
            first_quarter_avg = sum(m.income.sales for m in self.months[:3]) / 3
            last_quarter_avg = sum(m.income.sales for m in self.months[-3:]) / 3
            if last_quarter_avg > first_quarter_avg * 1.05:
                score += 5

        score = max(0, min(100, score))

        # Determinar semáforo
        if score >= 75:
            salud = "excelente"
            color = "#22c55e"
            emoji = "🟢"
        elif score >= 55:
            salud = "buena"
            color = "#4ade80"
            emoji = "🟡"
        elif score >= 35:
            salud = "riesgosa"
            color = "#f59e0b"
            emoji = "🟠"
        else:
            salud = "critica"
            color = "#dc2626"
            emoji = "🔴"

        return {
            "salud": salud,
            "score": score,
            "color": color,
            "emoji": emoji,
            "total_ingresos": round(sum(m.income.total for m in self.months), 2),
            "total_gastos": round(sum(m.expenses.total for m in self.months), 2),
            "flujo_neto_total": round(total_net, 2),
            "caja_final": round(self.months[-1].cumulative_balance, 2) if self.months else 0,
        }

    def recomendaciones_financiamiento(self) -> List[dict]:
        """Genera recomendaciones de financiamiento basadas en las métricas."""
        recomendaciones = []
        necesidad = self.necesidad_financiamiento()
        runway_data = self.runway()
        break_even = self.break_even_operativo()

        if necesidad.get("necesita_financiamiento", False):
            monto = necesidad.get("monto_con_colchon", 0)

            # Línea de crédito si el déficit es temporal
            meses_negativos = sum(1 for m in self.months if m.cumulative_balance < 0)
            if meses_negativos <= 3:
                recomendaciones.append({
                    "tipo": "linea_credito",
                    "titulo": "Línea de Crédito Revolving",
                    "monto_sugerido": round(monto, 0),
                    "razon": f"Déficit temporal ({meses_negativos} meses). Una línea de crédito permite cubrir baches sin comprometer capital.",
                    "prioridad": "alta",
                })
            else:
                recomendaciones.append({
                    "tipo": "credito_largo_plazo",
                    "titulo": "Crédito a Mediano Plazo",
                    "monto_sugerido": round(monto, 0),
                    "razon": f"Déficit prolongado ({meses_negativos} meses). Se recomienda financiamiento estructurado.",
                    "prioridad": "alta",
                })

        if not runway_data.get("es_rentable", True) and runway_data.get("meses", 999) < 6:
            burn_rate = runway_data.get("burn_rate_mensual", 0)
            runway_meses = runway_data.get("meses", 0)
            recomendaciones.append({
                "tipo": "inyeccion_capital",
                "titulo": "Inyección de Capital Urgente",
                "monto_sugerido": round(burn_rate * 6, 0),
                "razon": f"Runway de solo {runway_meses:.1f} meses. Se necesita capital para al menos 6 meses de operación.",
                "prioridad": "critica",
            })

        if not break_even.get("alcanzado", True):
            ventas_act = break_even.get('ventas_mensuales_actuales', 0)
            ventas_nec = break_even.get('ventas_mensuales_necesarias', 0)
            recomendaciones.append({
                "tipo": "optimizacion_costos",
                "titulo": "Reducción de Costos o Aumento de Precios",
                "monto_sugerido": 0,
                "razon": f"Las ventas actuales (${ventas_act:,.0f}) están por debajo del break-even (${ventas_nec:,.0f})." if ventas_act and ventas_nec else "Las ventas no alcanzan el punto de equilibrio.",
                "prioridad": "alta",
            })

        if not recomendaciones:
            recomendaciones.append({
                "tipo": "ahorro",
                "titulo": "Fondo de Reserva",
                "monto_sugerido": round(sum(m.expenses.total for m in self.months) / len(self.months) * 3, 0) if self.months else 0,
                "razon": "La empresa es saludable. Se recomienda mantener un fondo de reserva de 3 meses de gastos.",
                "prioridad": "media",
            })

        return recomendaciones

    def optimizacion_caja(self) -> List[dict]:
        """Genera sugerencias de optimización de caja basadas en el análisis."""
        sugerencias = []
        profile = self.model.profile

        # Optimización de plazos de cobro
        if profile.collection_days > 30:
            ahorro_estimado = sum(m.income.sales for m in self.months) / len(self.months) * (profile.collection_days - 30) / 30 * 0.03
            sugerencias.append({
                "area": "cobros",
                "titulo": "Reducir plazo de cobro",
                "descripcion": f"Actualmente cobra a {profile.collection_days} días. Reducir a 30 días liberaría capital de trabajo.",
                "ahorro_estimado_mensual": round(ahorro_estimado, 0),
                "impacto": "alto" if profile.collection_days > 60 else "medio",
            })

        # Optimización de inventario
        if profile.inventory_days > 45:
            sugerencias.append({
                "area": "inventario",
                "titulo": "Optimizar rotación de inventario",
                "descripcion": f"Inventario de {profile.inventory_days} días es alto. Reducir a 30 días libera caja.",
                "ahorro_estimado_mensual": 0,
                "impacto": "medio",
            })

        # Negociar plazos de pago
        if profile.payment_days < 30:
            sugerencias.append({
                "area": "pagos",
                "titulo": "Negociar plazos con proveedores",
                "descripcion": f"Actualmente paga a {profile.payment_days} días. Negociar 45-60 días mejora el flujo.",
                "ahorro_estimado_mensual": 0,
                "impacto": "medio",
            })

        # Estacionalidad: preparar reservas
        if profile.seasonality_pattern:
            sp = profile.seasonality_pattern
            if isinstance(sp, list):
                meses_bajos = [i + 1 for i, v in enumerate(sp) if v < 0.85]
            elif isinstance(sp, dict):
                meses_bajos = [k for k, v in sp.items() if v < 0.85]
            else:
                meses_bajos = []
            if meses_bajos:
                sugerencias.append({
                    "area": "estacionalidad",
                    "titulo": "Crear reserva para temporada baja",
                    "descripcion": f"Los meses {meses_bajos} tienen baja demanda. Acumular reservas en temporada alta.",
                    "ahorro_estimado_mensual": 0,
                    "impacto": "alto",
                })

        # Marketing ROI
        total_marketing = sum(m.expenses.variable_expenses for m in self.months)
        total_sales = sum(m.income.sales for m in self.months)
        if total_marketing > 0 and total_sales > 0:
            roi_marketing = total_sales / total_marketing
            if roi_marketing < 5:
                sugerencias.append({
                    "area": "marketing",
                    "titulo": "Revisar eficiencia del gasto en marketing",
                    "descripcion": f"ROI de marketing actual: {roi_marketing:.1f}x. Considerar reasignar presupuesto a canales más efectivos.",
                    "ahorro_estimado_mensual": 0,
                    "impacto": "medio",
                })

        return sugerencias

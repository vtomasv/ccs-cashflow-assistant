"""
core.py — Estructuras de datos y normalización del modelo de cashflow.
Representa el flujo de caja como un modelo orientado a objetos para facilitar
la simulación mes a mes, la aplicación de estacionalidad y fluctuaciones.
"""

import copy
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import List, Dict, Optional, Any


@dataclass
class IncomeData:
    """Ingresos de un mes."""
    sales: float = 0.0
    other_income: float = 0.0

    @property
    def total(self) -> float:
        return self.sales + self.other_income

    def to_dict(self) -> dict:
        return {"sales": round(self.sales, 2), "other_income": round(self.other_income, 2), "total": round(self.total, 2)}


@dataclass
class ExpenseData:
    """Gastos de un mes."""
    variable_costs: float = 0.0
    fixed_costs: float = 0.0
    variable_expenses: float = 0.0
    debt_payments: float = 0.0
    taxes: float = 0.0
    investments: float = 0.0

    @property
    def total(self) -> float:
        return (self.variable_costs + self.fixed_costs + self.variable_expenses +
                self.debt_payments + self.taxes + self.investments)

    def to_dict(self) -> dict:
        return {
            "variable_costs": round(self.variable_costs, 2),
            "fixed_costs": round(self.fixed_costs, 2),
            "variable_expenses": round(self.variable_expenses, 2),
            "debt_payments": round(self.debt_payments, 2),
            "taxes": round(self.taxes, 2),
            "investments": round(self.investments, 2),
            "total": round(self.total, 2),
        }


@dataclass
class MonthData:
    """Datos financieros de un mes individual."""
    month: str = ""           # "2026-06"
    label: str = ""           # "Junio 2026"
    income: IncomeData = field(default_factory=IncomeData)
    expenses: ExpenseData = field(default_factory=ExpenseData)
    net_flow: float = 0.0
    cumulative_balance: float = 0.0
    # Metadatos de simulación
    seasonality_factor: float = 1.0
    market_factor: float = 1.0
    notes: List[str] = field(default_factory=list)

    def recalculate(self):
        """Recalcula net_flow a partir de income y expenses."""
        self.net_flow = self.income.total - self.expenses.total

    def to_dict(self) -> dict:
        d = {
            "month": self.month,
            "label": self.label,
            "income": self.income.to_dict(),
            "expenses": self.expenses.to_dict(),
            "net_flow": round(self.net_flow, 2),
            "cumulative_balance": round(self.cumulative_balance, 2),
        }
        if self.notes:
            d["notes"] = self.notes
        if self.seasonality_factor != 1.0:
            d["seasonality_factor"] = round(self.seasonality_factor, 3)
        if self.market_factor != 1.0:
            d["market_factor"] = round(self.market_factor, 3)
        return d


@dataclass
class BusinessProfile:
    """Perfil del negocio extraído de la entrevista."""
    name: str = ""
    sector: str = ""
    description: str = ""
    products: List[str] = field(default_factory=list)
    customer_segments: List[str] = field(default_factory=list)
    revenue_model: str = ""
    avg_price: float = 0.0
    monthly_volume: float = 0.0
    purchase_frequency: str = ""
    expected_growth_pct: float = 0.0
    churn_rate_pct: float = 0.0
    seasonality_pattern: Dict[int, float] = field(default_factory=dict)  # mes -> factor
    variable_cost_pct: float = 0.0  # % de ventas
    fixed_costs_monthly: float = 0.0
    salaries_monthly: float = 0.0
    marketing_monthly: float = 0.0
    tax_rate_pct: float = 0.0
    collection_days: int = 0
    payment_days: int = 0
    inventory_days: int = 0
    debt_monthly_payment: float = 0.0
    capex_planned: Dict[int, float] = field(default_factory=dict)  # mes -> monto
    initial_cash: float = 0.0
    main_risks: List[str] = field(default_factory=list)
    currency: str = "CLP"
    country: str = ""
    # Datos de mercado obtenidos de internet
    market_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "sector": self.sector,
            "description": self.description,
            "products": self.products,
            "customer_segments": self.customer_segments,
            "revenue_model": self.revenue_model,
            "avg_price": self.avg_price,
            "monthly_volume": self.monthly_volume,
            "purchase_frequency": self.purchase_frequency,
            "expected_growth_pct": self.expected_growth_pct,
            "churn_rate_pct": self.churn_rate_pct,
            "seasonality_pattern": self.seasonality_pattern,
            "variable_cost_pct": self.variable_cost_pct,
            "fixed_costs_monthly": self.fixed_costs_monthly,
            "salaries_monthly": self.salaries_monthly,
            "marketing_monthly": self.marketing_monthly,
            "tax_rate_pct": self.tax_rate_pct,
            "collection_days": self.collection_days,
            "payment_days": self.payment_days,
            "inventory_days": self.inventory_days,
            "debt_monthly_payment": self.debt_monthly_payment,
            "capex_planned": self.capex_planned,
            "initial_cash": self.initial_cash,
            "main_risks": self.main_risks,
            "currency": self.currency,
            "country": self.country,
            "market_data": self.market_data,
        }


class CashflowModel:
    """
    Modelo de flujo de caja completo con capacidad de generación mes a mes,
    aplicación de estacionalidad, fluctuaciones de mercado y crecimiento.
    """

    def __init__(self, profile: BusinessProfile, initial_cash: float = 0.0):
        self.profile = profile
        self.months: List[MonthData] = []
        self.initial_cash = initial_cash or profile.initial_cash
        self.assumptions: List[str] = []
        self.market_seasonality: Dict[int, float] = {}  # Datos de internet

    def generate_month(self, month_index: int, start_date: date,
                       progress_callback=None) -> MonthData:
        """
        Genera un mes individual del flujo de caja aplicando:
        - Crecimiento esperado
        - Estacionalidad del negocio
        - Factores de mercado
        - Fluctuaciones aleatorias (si se proporcionan)
        
        Retorna el MonthData generado y opcionalmente notifica progreso.
        """
        # Calcular fecha del mes
        target_month = (start_date.month + month_index - 1) % 12 + 1
        target_year = start_date.year + (start_date.month + month_index - 1) // 12
        month_str = f"{target_year}-{target_month:02d}"

        # Nombre del mes en español
        month_names = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                       "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        label = f"{month_names[target_month - 1]} {target_year}"

        # Factor de crecimiento compuesto mensual
        monthly_growth = (1 + self.profile.expected_growth_pct / 100) ** (1 / 12)
        growth_factor = monthly_growth ** month_index

        # Factor de estacionalidad (del perfil del negocio)
        sp = self.profile.seasonality_pattern
        if isinstance(sp, list):
            seasonality_factor = sp[target_month - 1] if target_month <= len(sp) else 1.0
        elif isinstance(sp, dict):
            seasonality_factor = sp.get(target_month, 1.0)
        else:
            seasonality_factor = 1.0

        # Factor de mercado (de datos de internet)
        market_factor = self.market_seasonality.get(target_month, 1.0)

        # Calcular ingresos
        base_sales = self.profile.avg_price * self.profile.monthly_volume
        if base_sales == 0:
            # Fallback: usar datos de la entrevista si no hay precio/volumen
            base_sales = self.profile.fixed_costs_monthly * 1.5  # Supuesto: margen ~33%

        adjusted_sales = base_sales * growth_factor * seasonality_factor * market_factor

        # Churn effect (reduce volumen gradualmente si hay churn)
        if self.profile.churn_rate_pct > 0:
            monthly_churn = self.profile.churn_rate_pct / 100 / 12
            retention_factor = (1 - monthly_churn) ** month_index
            adjusted_sales *= retention_factor

        income = IncomeData(
            sales=adjusted_sales,
            other_income=0.0
        )

        # Calcular gastos
        # variable_cost_pct puede venir como fracción (0.35) o porcentaje (35)
        vcp = self.profile.variable_cost_pct
        if vcp > 1:  # Es porcentaje (ej: 35)
            variable_costs = adjusted_sales * (vcp / 100)
        elif vcp > 0:  # Es fracción (ej: 0.35)
            variable_costs = adjusted_sales * vcp
        else:
            variable_costs = adjusted_sales * 0.4  # Default 40%
        fixed_costs = self.profile.fixed_costs_monthly + self.profile.salaries_monthly

        # Inflación en costos fijos (si hay datos de mercado)
        inflation_annual = self.profile.market_data.get("inflation_annual_pct", 0)
        if inflation_annual > 0:
            monthly_inflation = (1 + inflation_annual / 100) ** (1 / 12)
            fixed_costs *= monthly_inflation ** month_index

        # Marketing
        variable_expenses = self.profile.marketing_monthly

        # Impuestos (simplificado: % sobre margen bruto)
        gross_margin = adjusted_sales - variable_costs
        taxes = max(0, gross_margin * (self.profile.tax_rate_pct / 100)) if self.profile.tax_rate_pct > 0 else 0

        # Deuda
        debt_payments = self.profile.debt_monthly_payment

        # CAPEX planificado (puede ser dict {mes: monto} o un valor fijo mensual)
        cp = self.profile.capex_planned
        if isinstance(cp, dict):
            investments = cp.get(month_index + 1, 0.0)
        else:
            investments = float(cp) if cp else 0.0

        expenses = ExpenseData(
            variable_costs=variable_costs,
            fixed_costs=fixed_costs,
            variable_expenses=variable_expenses,
            debt_payments=debt_payments,
            taxes=taxes,
            investments=investments,
        )

        # Crear el mes
        month_data = MonthData(
            month=month_str,
            label=label,
            income=income,
            expenses=expenses,
            seasonality_factor=seasonality_factor,
            market_factor=market_factor,
        )
        month_data.recalculate()

        # Calcular saldo acumulado
        if month_index == 0:
            month_data.cumulative_balance = self.initial_cash + month_data.net_flow
        else:
            prev_balance = self.months[month_index - 1].cumulative_balance if self.months else self.initial_cash
            month_data.cumulative_balance = prev_balance + month_data.net_flow

        return month_data

    def generate_all_months(self, num_months: int = 12, start_date: date = None,
                            progress_callback=None) -> List[MonthData]:
        """
        Genera todos los meses del flujo de caja uno a uno.
        El progress_callback recibe (month_index, total_months, month_data, notification_message).
        """
        if start_date is None:
            today = date.today()
            start_date = date(today.year, today.month, 1)

        self.months = []
        for i in range(num_months):
            month_data = self.generate_month(i, start_date, progress_callback)
            self.months.append(month_data)

            # Generar notificación contextual
            if progress_callback:
                notification = self._generate_notification(i, month_data)
                progress_callback(i, num_months, month_data, notification)

        return self.months

    def _generate_notification(self, month_index: int, month_data: MonthData) -> str:
        """
        Genera un mensaje de notificación contextualizado al negocio del usuario.
        Usa los productos, sector y datos del perfil para crear mensajes relevantes.
        """
        products_str = ", ".join(self.profile.products[:2]) if self.profile.products else "productos"
        sector = self.profile.sector or "tu negocio"
        name = self.profile.name or "tu empresa"

        notifications = []

        # Notificaciones basadas en estacionalidad
        if month_data.seasonality_factor > 1.1:
            notifications.append(
                f"📈 Temporada alta para {name}: simulando aumento de demanda de {products_str}"
            )
        elif month_data.seasonality_factor < 0.9:
            notifications.append(
                f"📉 Temporada baja: modelando reducción estacional en ventas de {products_str}"
            )

        # Notificaciones basadas en eventos del mes
        if month_data.expenses.investments > 0:
            notifications.append(
                f"🏗️ Inversión planificada de ${month_data.expenses.investments:,.0f} en {month_data.label}"
            )

        # Notificaciones de crecimiento
        if month_index > 0 and self.profile.expected_growth_pct > 0:
            notifications.append(
                f"🚀 Aplicando crecimiento mensual: simulando nuevos clientes para {products_str}"
            )

        # Notificaciones de riesgo
        if month_data.net_flow < 0:
            notifications.append(
                f"⚠️ Flujo negativo detectado en {month_data.label}: evaluando necesidad de financiamiento"
            )
        elif month_data.cumulative_balance < 0:
            notifications.append(
                f"🔴 Caja acumulada negativa: analizando opciones de cobertura para {name}"
            )

        # Notificaciones de mercado
        if month_data.market_factor != 1.0:
            if month_data.market_factor > 1.0:
                notifications.append(
                    f"🌐 Datos de mercado: tendencia positiva en el sector {sector} para este período"
                )
            else:
                notifications.append(
                    f"🌐 Datos de mercado: contracción esperada en el sector {sector}"
                )

        # Si no hay notificaciones específicas, generar una genérica contextual
        if not notifications:
            generic_messages = [
                f"💰 Calculando ingresos de {products_str} para {month_data.label}...",
                f"📊 Proyectando costos operativos de {name} en {month_data.label}...",
                f"🔄 Simulando ciclo de cobros y pagos de {name}...",
                f"📋 Modelando gastos fijos y variables de {sector}...",
            ]
            notifications.append(generic_messages[month_index % len(generic_messages)])

        return notifications[0] if len(notifications) == 1 else " | ".join(notifications[:2])

    def to_dict(self) -> dict:
        """Exporta el modelo completo como diccionario compatible con el formato existente."""
        months_data = [m.to_dict() for m in self.months]

        total_income = sum(m.income.total for m in self.months)
        total_expenses = sum(m.expenses.total for m in self.months)
        net_cashflow = total_income - total_expenses
        num_months = len(self.months)

        return {
            "company_name": self.profile.name,
            "currency": self.profile.currency,
            "period_months": num_months,
            "start_month": self.months[0].month if self.months else "",
            "initial_cash": self.initial_cash,
            "months": months_data,
            "summary": {
                "total_income": round(total_income, 2),
                "total_expenses": round(total_expenses, 2),
                "net_cashflow": round(net_cashflow, 2),
                "average_monthly_balance": round(net_cashflow / num_months, 2) if num_months > 0 else 0,
                "num_months": num_months,
            },
            "assumptions": self.assumptions,
            "profile": self.profile.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CashflowModel":
        """Reconstruye un CashflowModel desde un diccionario (cashflow.json guardado)."""
        profile_data = data.get("profile", {})
        profile = BusinessProfile(
            name=profile_data.get("name", data.get("company_name", "")),
            sector=profile_data.get("sector", ""),
            description=profile_data.get("description", ""),
            products=profile_data.get("products", []),
            customer_segments=profile_data.get("customer_segments", []),
            revenue_model=profile_data.get("revenue_model", ""),
            avg_price=profile_data.get("avg_price", 0),
            monthly_volume=profile_data.get("monthly_volume", 0),
            purchase_frequency=profile_data.get("purchase_frequency", ""),
            expected_growth_pct=profile_data.get("expected_growth_pct", 0),
            churn_rate_pct=profile_data.get("churn_rate_pct", 0),
            seasonality_pattern={int(k): v for k, v in profile_data.get("seasonality_pattern", {}).items()},
            variable_cost_pct=profile_data.get("variable_cost_pct", 0),
            fixed_costs_monthly=profile_data.get("fixed_costs_monthly", 0),
            salaries_monthly=profile_data.get("salaries_monthly", 0),
            marketing_monthly=profile_data.get("marketing_monthly", 0),
            tax_rate_pct=profile_data.get("tax_rate_pct", 0),
            collection_days=profile_data.get("collection_days", 0),
            payment_days=profile_data.get("payment_days", 0),
            inventory_days=profile_data.get("inventory_days", 0),
            debt_monthly_payment=profile_data.get("debt_monthly_payment", 0),
            capex_planned={int(k): v for k, v in profile_data.get("capex_planned", {}).items()},
            initial_cash=profile_data.get("initial_cash", data.get("initial_cash", 0)),
            main_risks=profile_data.get("main_risks", []),
            currency=profile_data.get("currency", data.get("currency", "CLP")),
            country=profile_data.get("country", ""),
            market_data=profile_data.get("market_data", {}),
        )

        model = cls(profile=profile, initial_cash=data.get("initial_cash", profile.initial_cash))
        model.assumptions = data.get("assumptions", [])

        # Reconstruir meses
        for m in data.get("months", []):
            income_d = m.get("income", {})
            expenses_d = m.get("expenses", {})
            month_data = MonthData(
                month=m.get("month", ""),
                label=m.get("label", ""),
                income=IncomeData(
                    sales=income_d.get("sales", 0),
                    other_income=income_d.get("other_income", 0),
                ),
                expenses=ExpenseData(
                    variable_costs=expenses_d.get("variable_costs", 0),
                    fixed_costs=expenses_d.get("fixed_costs", 0),
                    variable_expenses=expenses_d.get("variable_expenses", 0),
                    debt_payments=expenses_d.get("debt_payments", 0),
                    taxes=expenses_d.get("taxes", 0),
                    investments=expenses_d.get("investments", 0),
                ),
                net_flow=m.get("net_flow", 0),
                cumulative_balance=m.get("cumulative_balance", 0),
                seasonality_factor=m.get("seasonality_factor", 1.0),
                market_factor=m.get("market_factor", 1.0),
                notes=m.get("notes", []),
            )
            model.months.append(month_data)

        return model

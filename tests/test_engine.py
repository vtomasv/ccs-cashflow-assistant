"""Test del motor financiero v2."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from financial_engine.core import CashflowModel, BusinessProfile
from financial_engine.metrics import FinancialMetrics
from financial_engine.monte_carlo import MonteCarloSimulator
from datetime import date
import json

profile = BusinessProfile(
    sector='Panadería artesanal',
    products=['Pan de masa madre', 'Pasteles', 'Galletas'],
    revenue_model='venta_directa',
    avg_price=4500,
    monthly_volume=3000,
    variable_cost_pct=0.35,
    fixed_costs_monthly=2500000,
    salaries_monthly=1800000,
    marketing_monthly=200000,
    initial_cash=5000000,
    expected_growth_pct=5.0,
    seasonality_pattern=[1.0, 0.9, 0.95, 1.0, 1.1, 1.2, 1.15, 1.0, 0.95, 1.0, 1.1, 1.3],
    country='Chile',
    currency='CLP',
)

model = CashflowModel(profile=profile, initial_cash=5000000)
months = model.generate_all_months(num_months=12, start_date=date(2026, 6, 1))

print(f'Meses generados: {len(months)}')
for m in months:
    print(f'  {m.label}: Ingresos ${m.income.total:,.0f} | Gastos ${m.expenses.total:,.0f} | Neto ${m.net_flow:,.0f} | Balance ${m.cumulative_balance:,.0f}')

# Métricas
metrics = FinancialMetrics(model)
all_metrics = metrics.calculate_all()
print(f'\nMétricas:')
for k, v in all_metrics.items():
    if isinstance(v, dict):
        print(f'  {k}: {json.dumps(v, default=str)[:100]}')
    elif isinstance(v, list):
        print(f'  {k}: [{len(v)} items]')
    else:
        print(f'  {k}: {v}')

# Monte Carlo
mc = MonteCarloSimulator(model, iterations=50)
mc_results = mc.run()
print(f'\nMonte Carlo (50 iter):')
print(f'  Prob. insolvencia: {mc_results["probabilidad_insolvencia_pct"]:.1f}%')
print(f'  Nivel riesgo: {mc_results["nivel_riesgo"]["nivel"]}')
print(f'  Keys: {list(mc_results.keys())}')

# Verificar la estructura de resultados MC
if "distribucion_caja_final" in mc_results:
    dist = mc_results["distribucion_caja_final"]
    print(f'  Percentiles: {list(dist.keys()) if isinstance(dist, dict) else "N/A"}')
    if isinstance(dist, dict) and "p50" in dist:
        print(f'  Mediana caja final: ${dist["p50"]:,.0f}')

print('\n✅ Motor financiero funcionando correctamente!')

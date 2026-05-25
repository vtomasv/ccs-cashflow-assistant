# Skill: Extracción de Datos

## Objetivo
Extraer datos financieros estructurados de conversaciones en lenguaje natural para alimentar el motor de flujo de caja.

## Formato de Salida JSON
```json
{
  "business_type": "string",
  "products": ["string"],
  "avg_price": number,
  "monthly_volume": number,
  "revenue_model": "string",
  "fixed_costs_monthly": number,
  "salaries_monthly": number,
  "variable_cost_pct": number,
  "initial_cash": number,
  "expected_growth_pct": number,
  "seasonality_pattern": {"1": 1.0, "2": 0.8, ...},
  "churn_rate_pct": number,
  "collection_days": number,
  "payment_days": number,
  "debt_monthly_payment": number,
  "tax_rate_pct": number
}
```

## Reglas de Extracción

Los números deben extraerse sin formato (sin puntos de miles ni símbolos de moneda). Cuando el usuario da rangos como "entre 50.000 y 60.000", se usa el promedio (55.000). Los porcentajes se almacenan como decimales entre 0 y 1 (ej: 35% → 0.35). Si un dato no se menciona explícitamente, se omite del JSON (no inventar).

## Validaciones
- Precios y volúmenes deben ser positivos
- Porcentajes entre 0 y 1
- Costos fijos no pueden ser negativos
- Estacionalidad: factores entre 0.3 y 2.0

## Manejo de Ambigüedad
Si la información es ambigua, marcar el campo con un comentario de confianza baja y usar el valor más conservador.

# Skill: Análisis de Sensibilidad

## Objetivo
Identificar qué variables tienen mayor impacto en el flujo de caja para priorizar acciones de gestión.

## Metodología
Se varía cada variable independientemente en ±10%, ±20% y ±30% mientras las demás se mantienen constantes, midiendo el impacto en el saldo final acumulado.

## Variables Analizadas

Las variables principales del análisis incluyen ventas (volumen y precio), costos variables (porcentaje sobre ventas), costos fijos mensuales, salarios, crecimiento mensual, churn de clientes, y plazo de cobro.

## Formato de Salida

Para cada variable se calcula el coeficiente de sensibilidad, que indica cuánto cambia el saldo final por cada 1% de variación en la variable. Las variables se ordenan de mayor a menor impacto.

| Variable | Sensibilidad | Impacto ±10% |
|----------|-------------|--------------|
| Ventas | Alta | ±$X en caja final |
| Costos fijos | Media | ±$Y en caja final |
| Crecimiento | Media | ±$Z en caja final |

## Recomendaciones Automáticas
Basándose en el análisis de sensibilidad, el sistema genera recomendaciones priorizadas sobre dónde enfocar esfuerzos de gestión para maximizar el flujo de caja.

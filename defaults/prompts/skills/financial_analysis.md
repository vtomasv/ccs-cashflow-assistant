# Skill: Análisis Financiero

## Objetivo
Analizar los datos financieros recopilados para generar proyecciones de flujo de caja precisas y útiles para la toma de decisiones.

## Capacidades
1. **Proyección de ingresos**: Calcular ingresos mensuales considerando volumen × precio × estacionalidad × crecimiento
2. **Estructura de costos**: Separar costos fijos de variables y proyectar su evolución
3. **Capital de trabajo**: Calcular necesidades de financiamiento por desfases de cobro/pago
4. **Punto de equilibrio**: Determinar ventas mínimas para cubrir costos
5. **Análisis de sensibilidad**: Identificar variables que más impactan el flujo

## Métricas Clave
- **Caja mínima**: El punto más bajo del saldo acumulado en 12 meses
- **Runway**: Meses que puede operar sin ingresos adicionales
- **Margen bruto**: (Ingresos - Costos Variables) / Ingresos
- **Margen EBITDA**: (Ingresos - Costos Operativos) / Ingresos
- **Break-even**: Ventas mensuales necesarias para flujo neto = 0

## Formato de Salida
Generar JSON estructurado con:
- 12 meses de proyección
- Desglose de ingresos y gastos por categoría
- Saldo acumulado mes a mes
- Métricas resumen
- Supuestos utilizados

# Skill: Descubrimiento Financiero

## Objetivo
Identificar y recopilar los 22 parámetros financieros necesarios para construir un modelo de flujo de caja preciso.

## Áreas Prioritarias (ordenadas por impacto en cashflow)
1. **Ingresos**: Productos/servicios, precios, volúmenes, frecuencia de compra
2. **Costos Variables**: Porcentaje sobre ventas, materias primas, comisiones
3. **Costos Fijos**: Arriendo, servicios, seguros, suscripciones
4. **Salarios**: Nómina total mensual, cargas sociales
5. **Estacionalidad**: Meses altos/bajos, eventos que afectan ventas
6. **Crecimiento**: Tasa esperada, nuevos clientes, churn
7. **Capital de Trabajo**: Plazos de cobro, plazos de pago, inventario
8. **Deuda y CAPEX**: Pagos de deuda, inversiones planificadas
9. **Impuestos**: Tasa efectiva, periodicidad de pago
10. **Riesgos**: Principales amenazas al flujo de caja

## Técnicas de Extracción
- Si el usuario no sabe un dato exacto, proponer rangos
- Si falta información, proponer supuestos razonables marcados como [SUPUESTO]
- Priorizar datos que más afectan la proyección (ingresos > costos > timing)
- Validar coherencia entre datos (ej: si vende 100 unidades a $5.000, ingresos ≈ $500.000)

## Supuestos por Defecto
| Variable | Supuesto | Fuente |
|----------|----------|--------|
| Crecimiento | 3% mensual | Promedio PYME |
| Churn | 5% mensual | Industria general |
| Costos variables | 35% de ventas | Promedio retail |
| Impuestos | 19% (IVA) + 27% (renta) | Chile |
| Plazo cobro | 15 días | Venta directa |
| Plazo pago | 30 días | Proveedores estándar |

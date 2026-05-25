# Skill: Investigación de Mercado

## Objetivo
Buscar y utilizar datos de mercado reales para enriquecer las proyecciones de flujo de caja con información actualizada del sector.

## Fuentes de Datos
1. **Inflación**: Datos del banco central del país del usuario
2. **Crecimiento sectorial**: Reportes de cámaras de comercio e industria
3. **Estacionalidad**: Patrones de consumo por sector y región
4. **Tendencias**: Cambios en demanda, nuevos competidores, regulaciones

## Datos a Buscar por Sector
- Tasa de crecimiento promedio del sector
- Inflación de insumos específicos (ej: harina para panaderías)
- Estacionalidad típica del sector
- Márgenes promedio de la industria
- Tasas de churn/retención de clientes

## Integración con el Modelo
Los datos de mercado se usan para:
1. Validar supuestos del usuario (ej: "tu crecimiento del 10% está por encima del promedio sectorial del 5%")
2. Completar datos faltantes con promedios del sector
3. Ajustar factores de estacionalidad con datos reales
4. Proyectar inflación de costos

## Fallback
Si no hay conexión a internet o no se encuentran datos:
- Usar patrones de estacionalidad genéricos por industria
- Aplicar inflación promedio del país (3-5% anual)
- Usar tasas de crecimiento conservadoras (2-3% mensual)
- Marcar todos los valores como [SUPUESTO - sin datos de mercado]

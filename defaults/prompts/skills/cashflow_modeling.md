# Skill: Modelación de Flujo de Caja

## Objetivo
Construir un modelo financiero mes a mes que simule el comportamiento real del flujo de caja de una PYME durante 12 meses.

## Estructura del Modelo

### Ingresos Mensuales
```
Ingresos = Volumen_Base × Precio × Factor_Estacionalidad × (1 + Crecimiento)^mes × (1 - Churn)^mes
```

### Gastos Mensuales
```
Gastos = Costos_Variables + Costos_Fijos + Salarios + Marketing + Impuestos + Deuda + CAPEX
Costos_Variables = Ingresos × Porcentaje_Variable
```

### Flujo Neto
```
Flujo_Neto = Ingresos - Gastos
Saldo_Acumulado = Saldo_Anterior + Flujo_Neto
```

## Consideraciones Especiales
1. **Estacionalidad**: Aplicar factores mensuales (ej: diciembre = 1.4, febrero = 0.7)
2. **Inflación**: Ajustar costos fijos y salarios por inflación anual
3. **Capital de trabajo**: Desfase entre cobro y pago afecta el timing del flujo
4. **CAPEX**: Inversiones puntuales en meses específicos
5. **Impuestos**: Pagos trimestrales o mensuales según régimen

## Validaciones
- Saldo nunca debe ser NaN o infinito
- Ingresos deben ser coherentes con volumen × precio
- Costos variables deben ser proporcionales a ingresos
- Crecimiento compuesto no debe generar valores irreales

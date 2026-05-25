# Skill: Simulación Monte Carlo

## Objetivo
Ejecutar simulaciones probabilísticas para evaluar el riesgo financiero del negocio bajo incertidumbre.

## Metodología
La simulación Monte Carlo ejecuta N iteraciones (típicamente 500-5000) del modelo de flujo de caja, variando aleatoriamente las variables clave según distribuciones de probabilidad.

## Variables Aleatorias

| Variable | Distribución | Parámetros |
|----------|-------------|------------|
| Ventas mensuales | Normal | μ = volumen_base, σ = 20% |
| Costos variables | Normal | μ = costo_base, σ = 10% |
| Crecimiento | Normal | μ = growth_rate, σ = 2% |
| Estacionalidad | Uniforme | ±15% del factor base |
| Nuevos clientes | Poisson | λ = clientes_esperados |

## Métricas de Salida

El resultado de Monte Carlo produce las siguientes métricas de riesgo:

La **probabilidad de insolvencia** representa el porcentaje de iteraciones donde la caja llega a cero o negativo en algún mes. El **Value at Risk (VaR) al 95%** indica la pérdida máxima esperada con 95% de confianza. Las **bandas de confianza** muestran los percentiles 10, 25, 50, 75 y 90 del saldo acumulado para cada mes. El **mes de mayor riesgo** identifica el mes con mayor probabilidad de caja negativa.

## Interpretación para el Usuario
- Prob. insolvencia < 5%: Riesgo bajo, negocio estable
- Prob. insolvencia 5-20%: Riesgo moderado, considerar reservas
- Prob. insolvencia 20-50%: Riesgo alto, necesita financiamiento
- Prob. insolvencia > 50%: Riesgo crítico, reestructurar modelo

## Configuración
- Iteraciones por defecto: 1000
- Seed aleatorio: configurable para reproducibilidad
- Timeout: 30 segundos máximo
